import re
import ipaddress


# 직급으로 판단할 표현
POSITION_WORDS = [
    "수석연구원",
    "주임연구원",
    "선임연구원",
    "책임연구원",
    "수석엔지니어",
    "책임엔지니어",
    "선임엔지니어",
    "책임매니저",
    "선임매니저",
    "점검위원",
    "감리위원",
    "파트장",
    "팀장",
    "차장",
    "과장",
    "대리",
    "주임",
    "사원",
    "연구원",
    "부장",
    "이사",
    "상무",
    "전무",
]


# 탐지 결과 추가
def _add_result(results, type_name, count, risk_level):

    if count > 0:
        results.append({
            "type": type_name,
            "count": count,
            "risk_level": risk_level,
            "masked": True
        })


# 중복값 제거
def _unique(values):

    result = []

    for value in values:
        if value not in result:
            result.append(value)

    return result


# 여러 값을 한 번에 마스킹
def _mask_values(text, values, replacement):

    # 긴 문자열부터 변경
    values = sorted(
        set(values),
        key=len,
        reverse=True
    )

    for value in values:

        if value:
            text = text.replace(
                value,
                replacement
            )

    return text


# 이름 마스킹
def _mask_name(name):

    # 외자 이름
    # 김철 -> 김*
    if len(name) == 2:
        return name[0] + "*"

    # 일반적인 3글자 이름
    # 홍길동 -> 홍*동
    if len(name) == 3:
        return (
            name[0]
            + "*"
            + name[-1]
        )

    # 4글자 이름
    # 남궁민수 -> 남**수
    if len(name) >= 4:
        return (
            name[0]
            + "*" * (len(name) - 2)
            + name[-1]
        )

    return "*"


# ==================================================
# 개인정보 탐지
# ==================================================

def detect_pii(text):

    pii_found = []
    masked_text = text


    # ==================================================
    # 1. 이름 - LOW
    # ==================================================

    name_pattern = re.compile(
        r"(?P<label>"
        r"고객\s*담당자\s*성\s*명|"
        r"담당자\s*성\s*명|"
        r"담당자|"
        r"작성자|"
        r"신청자|"
        r"결재자|"
        r"프로젝트\s*팀원|"
        r"팀원|"
        r"성\s*명|"
        r"이\s*름|"
        r"예금주"
        r")"
        r"\s*[:|]?\s*"
        r"(?P<name>[가-힣]{2,4})"
        r"(?P<extra>\s*\((?P<paren>[^)]*)\))?"
    )

    name_matches = list(
        name_pattern.finditer(text)
    )

    names = []
    english_names = []

    for match in name_matches:

        name = match.group("name")

        names.append(name)

        paren = match.group("paren")

        # 괄호 안에 영문 이름이 있는 경우
        # 홍길동 (Hong Gil-dong)
        if (
            paren
            and re.search(r"[A-Za-z]", paren)
        ):
            english_names.append(paren)


    # 한글 이름 마스킹
    for name in _unique(names):

        masked_name = _mask_name(name)

        masked_text = masked_text.replace(
            name,
            masked_name
        )


    # 영문 이름은 전체 마스킹
    for english_name in _unique(english_names):

        masked_text = masked_text.replace(
            english_name,
            "*" * len(english_name)
        )


    _add_result(
        pii_found,
        "이름",
        len(_unique(names)),
        "LOW"
    )


    # ==================================================
    # 2. 주민등록번호 - HIGH
    # ==================================================

    rrn_pattern = re.compile(
        r"\b\d{6}[- ]?[1-4]\d{6}\b"
    )

    rrns = _unique([
        match.group()
        for match in rrn_pattern.finditer(
            masked_text
        )
    ])

    for value in rrns:

        masked_text = masked_text.replace(
            value,
            "******-*******"
        )


    _add_result(
        pii_found,
        "주민등록번호",
        len(rrns),
        "HIGH"
    )


    # ==================================================
    # 3. 여권번호 - HIGH
    # ==================================================

    # 여권번호: M12345678
    # 여권 번호 | PM1234567
    #
    # 문서번호 등의 오탐 방지를 위해
    # "여권번호" 라벨이 있는 경우만 탐지
    passport_pattern = re.compile(
        r"(?P<label>"
        r"여권\s*번호"
        r")"
        r"\s*[:|]\s*"
        r"(?P<value>[A-Z]{1,2}\d{7,8})",
        re.IGNORECASE
    )

    passports = _unique([
        match.group("value")
        for match in passport_pattern.finditer(
            masked_text
        )
    ])

    for value in passports:

        masked_text = masked_text.replace(
            value,
            "*" * len(value)
        )


    _add_result(
        pii_found,
        "여권번호",
        len(passports),
        "HIGH"
    )


    # ==================================================
    # 4. 개인 휴대폰(010) - HIGH
    # ==================================================

    mobile_pattern = re.compile(
        r"\b010[- ]?\d{3,4}[- ]?\d{4}\b"
    )

    mobiles = _unique([
        match.group()
        for match in mobile_pattern.finditer(
            masked_text
        )
    ])

    for value in mobiles:

        digits = re.sub(
            r"\D",
            "",
            value
        )

        masked_mobile = (
            f"010-****-{digits[-4:]}"
        )

        masked_text = masked_text.replace(
            value,
            masked_mobile
        )


    _add_result(
        pii_found,
        "개인휴대폰",
        len(mobiles),
        "HIGH"
    )


    # ==================================================
    # 5. 업무 이메일 - LOW
    # ==================================================

    email_pattern = re.compile(
        r"\b"
        r"([A-Za-z0-9._%+-]+)"
        r"@"
        r"([A-Za-z0-9.-]+\.[A-Za-z]{2,})"
        r"\b"
    )

    emails = _unique([
        match.group()
        for match in email_pattern.finditer(
            masked_text
        )
    ])

    for value in emails:

        username, domain = value.split(
            "@",
            1
        )

        if len(username) <= 2:

            masked_username = (
                "*" * len(username)
            )

        else:

            masked_username = (
                username[:2]
                + "*" * (len(username) - 2)
            )

        masked_email = (
            f"{masked_username}@{domain}"
        )

        masked_text = masked_text.replace(
            value,
            masked_email
        )


    _add_result(
        pii_found,
        "업무이메일",
        len(emails),
        "LOW"
    )


    # ==================================================
    # 6. 자택 주소 - HIGH
    # ==================================================

    # 사업장 주소는 개인정보가 아니므로 포함하지 않음
    #
    # PDF의 경우 텍스트가 한 줄로 붙을 수 있으므로
    # 다음 필드가 시작되는 부분을 주소의 끝으로 판단
    address_pattern = re.compile(
        r"(?P<label>"
        r"자택\s*주소|"
        r"집\s*주\s*소|"
        r"집\s*주소|"
        r"거주지|"
        r"현\s*주소|"
        r"주소지"
        r")"
        r"\s*[:|]\s*"
        r"(?P<value>.*?)"
        r"(?="
            r"\s*\|"
            r"|\r?\n"
            r"|\s*-\s*(?:"
                r"지정\s*계좌|"
                r"급여\s*계좌|"
                r"정산\s*계좌|"
                r"수령\s*계좌|"
                r"비상\s*정산\s*계좌|"
                r"입금\s*계좌|"
                r"계좌\s*번호|"
                r"주민등록번호|"
                r"연락처|"
                r"전화번호|"
                r"이메일|"
                r"담당\s*부서|"
                r"작성\s*부서|"
                r"관리\s*부서|"
                r"접수\s*부서|"
                r"소속"
            r")"
            r"|\s*■"
            r"|$"
        r")"
    )

    addresses = []

    for match in address_pattern.finditer(
        masked_text
    ):

        address = (
            match.group("value")
            .strip()
        )

        if address:
            addresses.append(address)


    addresses = _unique(addresses)

    masked_text = _mask_values(
        masked_text,
        addresses,
        "********"
    )


    _add_result(
        pii_found,
        "자택주소",
        len(addresses),
        "HIGH"
    )


    # ==================================================
    # 7. 계좌번호 - HIGH
    # ==================================================

    # 문서번호 등을 계좌번호로 오탐하지 않도록
    # 계좌라는 문맥이 있는 경우에만 탐지
    account_pattern = re.compile(
        r"(?P<label>"
        r"비상\s*정산\s*계좌|"
        r"급여\s*계좌|"
        r"정산\s*계좌|"
        r"수령\s*계좌|"
        r"지정\s*계좌|"
        r"입금\s*계좌|"
        r"계좌\s*번호|"
        r"계좌"
        r")"
        r"\s*[:|]\s*"
        r"(?:(?P<bank>"
            r"[가-힣A-Za-z0-9]+"
            r"(?:은행|뱅크)"
        r")\s*)?"
        r"(?P<account>"
            r"\d{2,6}"
            r"(?:-\d{2,6}){1,3}"
        r")"
    )

    accounts = _unique([
        match.group("account")
        for match in account_pattern.finditer(
            masked_text
        )
    ])

    for value in accounts:

        masked_account = "-".join(
            "*" * len(part)
            for part in value.split("-")
        )

        masked_text = masked_text.replace(
            value,
            masked_account
        )


    _add_result(
        pii_found,
        "계좌번호",
        len(accounts),
        "HIGH"
    )


    # ==================================================
    # 8. 회사 전화번호 - LOW
    # ==================================================

    # 02
    # 031 ~ 033
    # 041 ~ 044
    # 051 ~ 055
    # 061 ~ 064
    company_phone_pattern = re.compile(
        r"\b"
        r"0(?:"
            r"2|"
            r"3[1-3]|"
            r"4[1-4]|"
            r"5[1-5]|"
            r"6[1-4]"
        r")"
        r"[- ]?"
        r"\d{3,4}"
        r"[- ]?"
        r"\d{4}"
        r"\b"
    )

    company_phones = _unique([
        match.group()
        for match in company_phone_pattern.finditer(
            masked_text
        )
    ])

    for value in company_phones:

        digits = re.sub(
            r"\D",
            "",
            value
        )

        if digits.startswith("02"):
            area_code = "02"

        else:
            area_code = digits[:3]

        masked_phone = (
            f"{area_code}-****-{digits[-4:]}"
        )

        masked_text = masked_text.replace(
            value,
            masked_phone
        )


    # 내선번호
    # 내선 1234
    extension_pattern = re.compile(
        r"(?P<label>"
        r"내선"
        r")"
        r"\s*[:|]?\s*"
        r"(?P<number>\d{3,5})"
    )

    extensions = _unique([
        match.group("number")
        for match in extension_pattern.finditer(
            masked_text
        )
    ])

    masked_text = extension_pattern.sub(
        lambda match:
            f"{match.group('label')} ****",
        masked_text
    )


    _add_result(
        pii_found,
        "회사전화번호",
        len(company_phones)
        + len(extensions),
        "LOW"
    )


    # ==================================================
    # 9. 부서 / 직급 - LOW
    # ==================================================

    department_count = 0
    position_count = 0


    position_text = "|".join(
        re.escape(word)
        for word in sorted(
            POSITION_WORDS,
            key=len,
            reverse=True
        )
    )


    # --------------------------------------------------
    # 소속 / 직급 | 시설관리팀 / 점검위원
    # 소속 및 직급: 개발팀 / 과장
    # --------------------------------------------------

    combined_pattern = re.compile(
        r"(?P<label>"
        r"소속\s*/\s*직급|"
        r"소속\s*및\s*직급"
        r")"
        r"\s*[:|]\s*"
        r"(?P<department>[^/|\r\n]+?)"
        r"\s*/\s*"
        r"(?P<position>[^|\r\n]+?)"
        r"(?="
            r"\s*\|"
            r"|\r?\n"
            r"|\s*-\s*"
            r"|$"
        r")"
    )

    combined_matches = list(
        combined_pattern.finditer(
            masked_text
        )
    )

    department_count += len(
        combined_matches
    )

    position_count += len(
        combined_matches
    )


    masked_text = combined_pattern.sub(
        lambda match:
            f"{match.group('label')} | ******** / ****",
        masked_text
    )


    # --------------------------------------------------
    # 소속 및 직급: 품질보증실 신뢰성평가그룹 주임연구원
    # '/'가 없는 경우
    # --------------------------------------------------

    combined_no_slash_pattern = re.compile(
        rf"(?P<label>"
        rf"소속\s*및\s*직급"
        rf")"
        rf"\s*[:|]\s*"
        rf"(?P<department>.*?)"
        rf"\s+"
        rf"(?P<position>{position_text})"
        rf"(?="
            rf"\r?\n"
            rf"|\s*-\s*"
            rf"|\s*■"
            rf"|$"
        rf")"
    )

    no_slash_matches = list(
        combined_no_slash_pattern.finditer(
            masked_text
        )
    )

    department_count += len(
        no_slash_matches
    )

    position_count += len(
        no_slash_matches
    )


    masked_text = (
        combined_no_slash_pattern.sub(
            lambda match:
                f"{match.group('label')}: ******** / ****",
            masked_text
        )
    )


    # --------------------------------------------------
    # 담당 부서 / 작성 부서 / 관리 부서 등
    # --------------------------------------------------

    department_pattern = re.compile(
        r"(?P<label>"
        r"담당\s*부서|"
        r"작성\s*부서|"
        r"관리\s*부서|"
        r"접수\s*부서|"
        r"소속\s*부서|"
        r"소속|"
        r"부서"
        r")"
        r"\s*[:|]?\s*"
        r"(?P<value>.*?)"
        r"(?="
            r"\s*\|"
            r"|\r?\n"
            r"|\s*(?:"
                r"담당자|"
                r"작성자|"
                r"성명|"
                r"이름|"
                r"직급|"
                r"주민등록번호|"
                r"연락처|"
                r"전화번호|"
                r"이메일|"
                r"자택\s*주소|"
                r"집\s*주\s*소|"
                r"계좌|"
                r"사번|"
                r"작성일자|"
                r"공정코드|"
                r"문서번호|"
                r"본인\s*확인|"
                r"개인정보"
            r")"
            r"|\s*■"
            r"|$"
        r")"
    )

    departments = []

    for match in department_pattern.finditer(
        masked_text
    ):

        department = (
            match.group("value")
            .strip()
        )

        if department:
            departments.append(
                department
            )


    departments = _unique(
        departments
    )

    masked_text = _mask_values(
        masked_text,
        departments,
        "********"
    )

    department_count += len(
        departments
    )


    # --------------------------------------------------
    # 성명: 홍길동 (차장)
    # --------------------------------------------------

    position_pattern = re.compile(
        rf"\((?P<position>"
        rf"{position_text}"
        rf")\)"
    )

    positions = _unique([
        match.group("position")
        for match in position_pattern.finditer(
            masked_text
        )
    ])


    masked_text = position_pattern.sub(
        "(****)",
        masked_text
    )

    position_count += len(
        positions
    )


    _add_result(
        pii_found,
        "부서",
        department_count,
        "LOW"
    )

    _add_result(
        pii_found,
        "직급",
        position_count,
        "LOW"
    )


    return {
        "pii_found": pii_found,
        "masked_text": masked_text
    }


# ==================================================
# Secret 탐지
# ==================================================
# ==================================================
# Secret 탐지
# ==================================================

def detect_secret(text):

    secret_found = []
    masked_text = text


    # ==================================================
    # 1. API Key - HIGH
    # ==================================================

    # sk-xxxxxxxx 형태
    api_key_pattern = re.compile(
        r"\bsk-[A-Za-z0-9_-]{20,}\b"
    )

    masked_text, count1 = (
        api_key_pattern.subn(
            "sk-********",
            masked_text
        )
    )


    # api_key=...
    # secret_key=...
    # access_token=...
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
        re.IGNORECASE
    )


    def mask_named_key(match):

        return (
            f"{match.group(1)}"
            f"{match.group(2)}"
            f"********"
        )


    masked_text, count2 = (
        named_key_pattern.subn(
            mask_named_key,
            masked_text
        )
    )


    api_key_count = (
        count1 + count2
    )


    if api_key_count > 0:

        secret_found.append({
            "type": "api_key",
            "count": api_key_count,
            "risk_level": "HIGH",
            "masked": True
        })


    # ==================================================
    # 2. Password - HIGH
    # ==================================================

    password_pattern = re.compile(
        r"\b"
        r"(password|passwd|pwd)"
        r"(\s*[:=]\s*)"
        r"[\"']?"
        r"([^\s,\"']+)"
        r"[\"']?",
        re.IGNORECASE
    )


    def mask_password(match):

        return (
            f"{match.group(1)}"
            f"{match.group(2)}"
            f"********"
        )


    masked_text, password_count = (
        password_pattern.subn(
            mask_password,
            masked_text
        )
    )


    if password_count > 0:

        secret_found.append({
            "type": "password",
            "count": password_count,
            "risk_level": "HIGH",
            "masked": True
        })


    # ==================================================
    # 3. 내부 IP - LOW
    # ==================================================

    ip_pattern = re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
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


        if ip.is_private:

            internal_ip_count += 1

            return "***.***.***.***"


        return ip_text


    masked_text = ip_pattern.sub(
        mask_internal_ip,
        masked_text
    )


    if internal_ip_count > 0:

        secret_found.append({
            "type": "내부IP",
            "count": internal_ip_count,
            "risk_level": "LOW",
            "masked": True
        })


    return {
        "secret_found": secret_found,
        "masked_text": masked_text
    }