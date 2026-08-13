# Regex + NER + 문맥 규칙 기반 개인정보 및 Secret 탐지

import ipaddress
import logging
import re

from tools.ner_detector import detect_ner_pii


logger = logging.getLogger(__name__)


# =========================================================
# 공통 함수
# =========================================================

def _add_result(
    results,
    pii_type,
    count,
    risk_level,
):
    """
    같은 개인정보 종류가 이미 존재하면
    count를 합산한다.
    """

    if count <= 0:
        return

    for item in results:
        if item["type"] == pii_type:
            item["count"] += count
            return

    results.append({
        "type": pii_type,
        "count": count,
        "risk_level": risk_level,
        "masked": True,
    })


def _mask_name(name):
    """
    이름 마스킹

    김철     -> 김*
    김현영   -> 김*영
    남궁민수 -> 남**수
    """

    if len(name) <= 1:
        return "*"

    if len(name) == 2:
        return name[0] + "*"

    return (
        name[0]
        + "*" * (len(name) - 2)
        + name[-1]
    )


def _mask_digits(value):
    """
    숫자만 *로 변경한다.
    -, 공백 등의 형식은 유지한다.
    """

    return "".join(
        "*" if char.isdigit()
        else char
        for char in value
    )


# =========================================================
# 개인정보 탐지
# =========================================================

def detect_pii(text):
    """
    개인정보 탐지

    1차:
        Regex
        -> 정형 개인정보 탐지 및 마스킹

    2차:
        NER
        -> 비정형 이름 탐지

    3차:
        Department Detector
        -> suffix + 문맥 기반 비정형 부서 탐지

    반환:
    {
        "pii_found": [...],
        "masked_text": "..."
    }
    """

    if not isinstance(
        text,
        str
    ):
        raise TypeError(
            "text는 문자열이어야 합니다."
        )

    pii_found = []
    masked_text = text

    # =====================================================
    # 1. 주민등록번호
    # HIGH
    # =====================================================

    rrn_pattern = re.compile(
        r"(?<!\d)"
        r"\d{6}"
        r"[- ]?"
        r"[1-4]\d{6}"
        r"(?!\d)"
    )

    def mask_rrn(match):
        return _mask_digits(
            match.group()
        )

    masked_text, count = rrn_pattern.subn(
        mask_rrn,
        masked_text,
    )

    _add_result(
        pii_found,
        "주민등록번호",
        count,
        "HIGH",
    )

    # =====================================================
    # 2. 여권번호
    # HIGH
    #
    # 여권 번호: M12345678
    # 여권 번호(M12345678)
    # 형태 모두 지원
    # =====================================================

    passport_pattern = re.compile(
        r"(?P<label>"
        r"여권\s*번호|"
        r"여권\s*No\.?"
        r")"
        r"(?P<separator>"
        r"\s*[:|]?\s*"
        r"\(?\s*"
        r")"
        r"(?P<value>"
        r"[A-Z]{1,2}\d{7,8}"
        r")"
        r"(?P<close>"
        r"\s*\)?"
        r")",
        re.IGNORECASE,
    )

    passport_count = 0

    def mask_passport(match):
        nonlocal passport_count

        passport_count += 1

        label = match.group(
            "label"
        )

        separator = match.group(
            "separator"
        )

        value = match.group(
            "value"
        )

        close = match.group(
            "close"
        )

        return (
            label
            + separator
            + "*" * len(value)
            + close
        )

    masked_text = passport_pattern.sub(
        mask_passport,
        masked_text,
    )

    _add_result(
        pii_found,
        "여권번호",
        passport_count,
        "HIGH",
    )

    # =====================================================
    # 3. 개인 휴대폰
    # HIGH
    # =====================================================

    mobile_pattern = re.compile(
        r"(?<!\d)"
        r"010"
        r"[-.\s]?"
        r"\d{3,4}"
        r"[-.\s]?"
        r"\d{4}"
        r"(?!\d)"
    )

    mobile_count = 0

    def mask_mobile(match):
        nonlocal mobile_count

        mobile_count += 1

        return "010-****-****"

    masked_text = mobile_pattern.sub(
        mask_mobile,
        masked_text,
    )

    _add_result(
        pii_found,
        "개인휴대폰",
        mobile_count,
        "HIGH",
    )

    # =====================================================
    # 4. 업무 이메일
    # LOW
    #
    # PDF에서 @ 또는 . 주변에 공백이 생긴 경우도 허용
    # =====================================================

    email_pattern = re.compile(
        r"\b"
        r"(?P<username>"
        r"[A-Za-z0-9._%+-]+"
        r")"
        r"\s*@\s*"
        r"(?P<domain>"
        r"[A-Za-z0-9-]+"
        r"(?:"
        r"\s*\.\s*"
        r"[A-Za-z0-9-]+"
        r")+"
        r")"
        r"\b"
    )

    email_count = 0

    def mask_email(match):
        nonlocal email_count

        email_count += 1

        username = match.group(
            "username"
        )

        domain = re.sub(
            r"\s*\.\s*",
            ".",
            match.group(
                "domain"
            )
        )

        if not username:
            masked_user = "*"

        elif len(username) <= 2:
            masked_user = (
                username[0]
                + "*"
            )

        else:
            masked_user = (
                username[:2]
                + "*" * (
                    len(username) - 2
                )
            )

        return (
            masked_user
            + "@"
            + domain
        )

    masked_text = email_pattern.sub(
        mask_email,
        masked_text,
    )

    _add_result(
        pii_found,
        "업무이메일",
        email_count,
        "LOW",
    )

    # =====================================================
    # 5. 자택 주소
    # HIGH
    #
    # 회사 주소는 탐지하지 않고
    # 자택/거주지 문맥에서만 탐지
    # =====================================================

    # -----------------------------------------------------
    # 거주지인 '주소'
    # 자택인 '주소'
    # 같은 자연어 표현
    # -----------------------------------------------------

    quoted_address_pattern = re.compile(
        r"(?P<prefix>"
        r"(?:자택|거주지)"
        r"\s*(?:인|은|는)"
        r"\s*"
        r")"
        r"(?P<quote>['\"])"
        r"(?P<value>"
        r"[^'\"]{5,120}"
        r")"
        r"(?P=quote)"
    )

    address_count = 0

    def mask_quoted_address(match):
        nonlocal address_count

        value = (
            match.group(
                "value"
            )
            .strip()
        )

        if not value:
            return match.group()

        address_count += 1

        return (
            match.group(
                "prefix"
            )
            + match.group(
                "quote"
            )
            + "*" * len(value)
            + match.group(
                "quote"
            )
        )

    masked_text = quoted_address_pattern.sub(
        mask_quoted_address,
        masked_text,
    )

    # -----------------------------------------------------
    # 자택 주소: ...
    # 거주지: ...
    # 같은 정형 표현
    # -----------------------------------------------------

    address_pattern = re.compile(
        r"(?P<label>"
        r"자택\s*주소|"
        r"집\s*주소|"
        r"거주지"
        r")"
        r"\s*[:|]\s*"
        r"(?P<value>.*?)"
        r"(?="
            r"\s*\|"
            r"|\r?\n"
            r"|\s*-\s*(?:"
                r"주민등록번호|"
                r"연락처|"
                r"전화번호|"
                r"휴대폰|"
                r"이메일|"
                r"계좌|"
                r"부서|"
                r"직급|"
                r"사번|"
                r"작성일자|"
                r"본인\s*확인"
            r")"
            r"|\s*■"
            r"|$"
        r")"
    )

    def mask_address(match):
        nonlocal address_count

        value = (
            match.group(
                "value"
            )
            .strip()
        )

        if not value:
            return match.group()

        address_count += 1

        return (
            match.group(
                "label"
            )
            + ": "
            + "*" * len(value)
        )

    masked_text = address_pattern.sub(
        mask_address,
        masked_text,
    )

    _add_result(
        pii_found,
        "자택주소",
        address_count,
        "HIGH",
    )

    # =====================================================
    # 6. 계좌번호
    # HIGH
    #
    # 계좌: 110-...
    # 계좌: 신한은행 110-...
    # 급여 계좌인 국민은행 123456-...
    # 모두 지원
    # =====================================================

    account_pattern = re.compile(
        r"(?P<label>"
        r"계좌\s*번호|"
        r"지정\s*계좌|"
        r"급여\s*계좌|"
        r"계좌"
        r")"
        r"(?P<separator>"
        r"\s*"
        r"(?:[:|]|인|은|는)?"
        r"\s*"
        r")"
        r"(?P<bank>"
        r"(?:"
            r"[가-힣A-Za-z0-9]{2,20}"
            r"(?:은행|뱅크|Bank)"
            r"\s*"
        r")?"
        r")"
        r"(?P<value>"
            r"(?:"
                r"\d{2,6}-"
            r"){1,4}"
            r"\d{2,6}"
            r"|"
            r"\d{8,20}"
        r")",
        re.IGNORECASE,
    )

    account_count = 0

    def mask_account(match):
        nonlocal account_count

        account_count += 1

        return (
            match.group(
                "label"
            )
            + match.group(
                "separator"
            )
            + match.group(
                "bank"
            )
            + _mask_digits(
                match.group(
                    "value"
                )
            )
        )

    masked_text = account_pattern.sub(
        mask_account,
        masked_text,
    )

    _add_result(
        pii_found,
        "계좌번호",
        account_count,
        "HIGH",
    )

    # =====================================================
    # 7. 회사 전화번호
    # LOW
    # =====================================================

    company_phone_pattern = re.compile(
        r"(?<!\d)"
        r"(?:"
            r"02"
            r"|"
            r"0[3-6][1-5]"
        r")"
        r"[-.\s]?"
        r"\d{3,4}"
        r"[-.\s]?"
        r"\d{4}"
        r"(?!\d)"
    )

    company_phone_count = 0

    def mask_company_phone(match):
        nonlocal company_phone_count

        company_phone_count += 1

        return _mask_digits(
            match.group()
        )

    masked_text = company_phone_pattern.sub(
        mask_company_phone,
        masked_text,
    )

    # -----------------------------------------------------
    # 내선번호
    # -----------------------------------------------------

    extension_pattern = re.compile(
        r"(?P<label>"
        r"내선\s*번호|"
        r"내선"
        r")"
        r"\s*[:|]?\s*"
        r"(?P<value>"
        r"\d{2,6}"
        r")"
    )

    extension_count = 0

    def mask_extension(match):
        nonlocal extension_count

        extension_count += 1

        value = match.group(
            "value"
        )

        return (
            match.group(
                "label"
            )
            + ": "
            + "*" * len(value)
        )

    masked_text = extension_pattern.sub(
        mask_extension,
        masked_text,
    )

    company_phone_count += (
        extension_count
    )

    _add_result(
        pii_found,
        "회사전화번호",
        company_phone_count,
        "LOW",
    )

    # =====================================================
    # 8. 이름
    # LOW
    #
    # Regex에서는 명확한 양식만 처리
    # 자연어 속 이름은 NER이 담당
    # =====================================================

    name_pattern = re.compile(
        r"(?P<label>"
        r"성명|"
        r"이름|"
        r"담당자|"
        r"작성자|"
        r"신청자|"
        r"결재자|"
        r"예금주"
        r")"
        r"\s*[:|]\s*"
        r"(?P<value>"
        r"[가-힣]{2,5}"
        r")"
    )

    name_count = 0

    def mask_name_match(match):
        nonlocal name_count

        name_count += 1

        return (
            match.group(
                "label"
            )
            + ": "
            + _mask_name(
                match.group(
                    "value"
                )
            )
        )

    masked_text = name_pattern.sub(
        mask_name_match,
        masked_text,
    )

    _add_result(
        pii_found,
        "이름",
        name_count,
        "LOW",
    )

    # =====================================================
    # 9. 정형 부서
    # LOW
    #
    # 명시적인 필드 형식만 Regex가 담당한다.
    # 자연어 속 부서는 Department Detector가 담당한다.
    # =====================================================

    department_pattern = re.compile(
        r"(?P<label>"
        r"담당\s*부서|"
        r"작성\s*부서|"
        r"관리\s*부서|"
        r"접수\s*부서|"
        r"소속\s*부서|"
        r"부서"
        r")"
        r"\s*[:|]\s*"
        r"(?P<value>"
            r"[가-힣A-Za-z0-9·_-]{2,30}"
            r"(?:"
                r"사업부|"
                r"본부|"
                r"연구소|"
                r"센터|"
                r"그룹|"
                r"파트|"
                r"팀|"
                r"부|"
                r"실"
            r")"
        r")"
    )

    department_count = 0

    def mask_department(match):
        nonlocal department_count

        department_count += 1

        value = match.group(
            "value"
        )

        return (
            match.group(
                "label"
            )
            + ": "
            + "*" * len(value)
        )

    masked_text = department_pattern.sub(
        mask_department,
        masked_text,
    )

    _add_result(
        pii_found,
        "부서",
        department_count,
        "LOW",
    )

    # =====================================================
    # 10. 직급 / 직책
    # LOW
    # =====================================================

    position_pattern = re.compile(
        r"(?P<label>"
        r"직급|"
        r"직책"
        r")"
        r"\s*[:|]\s*"
        r"(?P<value>"
        r"[가-힣A-Za-z]{1,20}"
        r")"
    )

    position_count = 0

    def mask_position(match):
        nonlocal position_count

        position_count += 1

        value = match.group(
            "value"
        )

        return (
            match.group(
                "label"
            )
            + ": "
            + "*" * len(value)
        )

    masked_text = position_pattern.sub(
        mask_position,
        masked_text,
    )

    _add_result(
        pii_found,
        "직급",
        position_count,
        "LOW",
    )

    # =====================================================
    # 11. 비정형 개인정보 2차 탐지
    #
    # Regex 마스킹 결과를 넘긴다.
    #
    # NER:
    #   자연어 속 이름
    #
    # Department Detector:
    #   자연어 속 부서
    # =====================================================

    try:
        ner_result = detect_ner_pii(
            masked_text
        )

        for item in ner_result.get(
            "pii_found",
            [],
        ):
            _add_result(
                pii_found,
                item.get(
                    "type",
                    "미상",
                ),
                item.get(
                    "count",
                    0,
                ),
                item.get(
                    "risk_level",
                    "LOW",
                ),
            )

        masked_text = ner_result.get(
            "masked_text",
            masked_text,
        )

    except Exception as e:
        # NER이 실패해도 기존 Regex 결과는 유지
        logger.warning(
            "비정형 개인정보 탐지 실패 "
            "- Regex 결과만 사용: %s",
            e,
        )

    return {
        "pii_found": pii_found,
        "masked_text": masked_text,
    }


# =========================================================
# Secret 탐지
# =========================================================

def detect_secret(text):
    """
    Secret 탐지

    HIGH
        api_key
        password

    LOW
        내부IP
    """

    if not isinstance(
        text,
        str
    ):
        raise TypeError(
            "text는 문자열이어야 합니다."
        )

    secret_found = []
    masked_text = text

    # =====================================================
    # 1. OpenAI 형태 API Key
    # =====================================================

    api_key_pattern = re.compile(
        r"\b"
        r"sk-[A-Za-z0-9_-]{20,}"
        r"\b"
    )

    masked_text, count1 = (
        api_key_pattern.subn(
            "sk-********",
            masked_text,
        )
    )

    # =====================================================
    # 2. 변수명 형태 API Key / Token
    # =====================================================

    named_key_pattern = re.compile(
        r"\b"
        r"("
            r"api[_-]?key|"
            r"secret[_-]?key|"
            r"access[_-]?token"
        r")"
        r"(\s*[:=]\s*)"
        r"[\"']?"
        r"([A-Za-z0-9_\-./+=]{8,})"
        r"[\"']?",
        re.IGNORECASE,
    )

    def mask_named_key(match):
        return (
            match.group(1)
            + match.group(2)
            + "********"
        )

    masked_text, count2 = (
        named_key_pattern.subn(
            mask_named_key,
            masked_text,
        )
    )

    api_key_count = (
        count1
        + count2
    )

    if api_key_count > 0:
        secret_found.append({
            "type": "api_key",
            "count": api_key_count,
            "risk_level": "HIGH",
            "masked": True,
        })

    # =====================================================
    # 3. Password
    # =====================================================

    password_pattern = re.compile(
        r"\b"
        r"("
            r"password|"
            r"passwd|"
            r"pwd"
        r")"
        r"(\s*[:=]\s*)"
        r"[\"']?"
        r"([^\s,\"']+)"
        r"[\"']?",
        re.IGNORECASE,
    )

    def mask_password(match):
        return (
            match.group(1)
            + match.group(2)
            + "********"
        )

    masked_text, password_count = (
        password_pattern.subn(
            mask_password,
            masked_text,
        )
    )

    if password_count > 0:
        secret_found.append({
            "type": "password",
            "count": password_count,
            "risk_level": "HIGH",
            "masked": True,
        })

    # =====================================================
    # 4. 내부 IP
    #
    # RFC1918 사설 주소만 탐지
    # =====================================================

    private_networks = (
        ipaddress.ip_network(
            "10.0.0.0/8"
        ),
        ipaddress.ip_network(
            "172.16.0.0/12"
        ),
        ipaddress.ip_network(
            "192.168.0.0/16"
        ),
    )

    ip_pattern = re.compile(
        r"\b"
        r"(?:\d{1,3}\.){3}"
        r"\d{1,3}"
        r"\b"
    )

    internal_ip_count = 0

    def mask_internal_ip(match):
        nonlocal internal_ip_count

        ip_text = match.group()

        try:
            ip = ipaddress.ip_address(
                ip_text
            )

        except ValueError:
            return ip_text

        is_internal = any(
            ip in network
            for network in private_networks
        )

        if not is_internal:
            return ip_text

        internal_ip_count += 1

        return "***.***.***.***"

    masked_text = ip_pattern.sub(
        mask_internal_ip,
        masked_text,
    )

    if internal_ip_count > 0:
        secret_found.append({
            "type": "내부IP",
            "count": internal_ip_count,
            "risk_level": "LOW",
            "masked": True,
        })

    return {
        "secret_found": secret_found,
        "masked_text": masked_text,
    }