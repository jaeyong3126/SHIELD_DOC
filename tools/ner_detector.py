# NER + 문맥 기반 규칙으로 비정형 이름과 부서를 추가 탐지

import re


MODEL_NAME = "vmaca123/korean-pii-ner-v3"

# 이름은 모델 신뢰도가 충분히 높은 경우만 사용
NAME_THRESHOLD = 0.85

# ORG는 부서를 직접 결정하는 것이 아니라
# 부서 후보의 추가 근거로만 사용
ORG_THRESHOLD = 0.75


# =========================================================
# 부서 탐지 설정
# =========================================================

# 조직이라는 의미가 비교적 강한 표현
STRONG_DEPARTMENT_SUFFIXES = (
    "사업부",
    "본부",
    "팀",
    "파트",
)

# 조직일 수도 있지만 다른 의미로도 사용될 수 있음
MEDIUM_DEPARTMENT_SUFFIXES = (
    "연구소",
    "센터",
    "그룹",
)

# 오탐 가능성이 높은 표현
WEAK_DEPARTMENT_SUFFIXES = (
    "실",
    "부",
)


ALL_DEPARTMENT_SUFFIXES = (
    STRONG_DEPARTMENT_SUFFIXES
    + MEDIUM_DEPARTMENT_SUFFIXES
    + WEAK_DEPARTMENT_SUFFIXES
)


# =========================================================
# 장소 예외
#
# "~실"이라고 해서 전부 부서는 아니기 때문에
# 명확하게 장소로 사용되는 표현은 제외한다.
# =========================================================

PLACE_WORDS = {
    "회의실",
    "대기실",
    "휴게실",
    "강의실",
    "상담실",
    "접견실",
    "전시실",
    "수유실",
    "탈의실",

    # 실제 데이터 테스트에서 발견된 장소 오탐
    "협업실",
}


# =========================================================
# 조직성 단어
#
# "실", "부"처럼 애매한 suffix를 가진 후보 중
# 기업 조직에서 자주 사용되는 단어가 포함되면
# 부서 가능성을 조금 높인다.
#
# 특정 기업의 실제 부서명을 저장하는 것이 아니라
# 일반적인 기업 조직 표현만 사용한다.
# =========================================================

ORGANIZATION_HINT_WORDS = (
    "사업",
    "관리",
    "인사",
    "총무",
    "기획",
    "전략",
    "품질",
    "재무",
    "회계",
    "법무",
    "감사",
    "보안",
    "영업",
    "생산",
    "개발",
    "기술",
    "운영",
    "구매",
    "홍보",
    "지원",
    "혁신",
)


# 부서 주변에서 등장하면 부서 가능성을 높이는 단어
DEPARTMENT_CONTEXT_WORDS = (
    "담당",
    "소속",
    "부서",
    "조직",
    "협업",
    "협의",
    "근무",
    "배치",
    "인사",
)


# 업무 조직과 함께 자주 사용되는 표현
WORK_CONTEXT_WORDS = (
    "검토",
    "공유",
    "보고",
    "확인",
    "담당",
    "협의",
    "진행",
    "작성",
    "전달",
    "요청",
    "회의",
    "운영",
    "관리",
    "지원",
    "점검",
    "분석",
)


_ner = None


# =========================================================
# NER 모델
# =========================================================

def _get_ner():
    """
    NER 모델은 최초 실행 시 한 번만 로드한다.
    """

    global _ner

    if _ner is None:
        # transformers가 설치되지 않아도
        # 파일 import 자체가 바로 실패하지 않도록 함수 안에서 import
        from transformers import (
            AutoTokenizer,
            AutoModelForTokenClassification,
            pipeline,
        )

        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            use_fast=True,
        )

        model = AutoModelForTokenClassification.from_pretrained(
            MODEL_NAME,
        )

        _ner = pipeline(
            "ner",
            model=model,
            tokenizer=tokenizer,
            aggregation_strategy="simple",
        )

    return _ner


# =========================================================
# 공통 함수
# =========================================================

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


def _remove_duplicate_spans(spans):
    """
    동일한 위치의 탐지 결과 중복 제거
    """

    unique = {}

    for item in spans:
        key = (
            item["type"],
            item["start"],
            item["end"],
        )

        old = unique.get(key)

        if old is None:
            unique[key] = item

        elif item.get("score", 0) > old.get(
            "score",
            0
        ):
            unique[key] = item

    return list(
        unique.values()
    )


def _mask_spans(text, spans):
    """
    탐지 위치를 뒤에서부터 마스킹한다.

    뒤에서부터 처리해야 앞쪽 문자열 변경으로 인해
    뒤쪽 start/end 위치가 틀어지지 않는다.
    """

    masked_text = text

    for item in sorted(
        spans,
        key=lambda x: x["start"],
        reverse=True,
    ):
        start = item["start"]
        end = item["end"]

        value = masked_text[
            start:end
        ]

        if item["type"] == "이름":
            replacement = _mask_name(
                value
            )

        else:
            replacement = (
                "*" * len(value)
            )

        masked_text = (
            masked_text[:start]
            + replacement
            + masked_text[end:]
        )

    return masked_text


# =========================================================
# NER 결과 처리
# =========================================================

def _extract_ner_entities(text):
    """
    NER 원본 결과에서 NAME과 ORG를 분리한다.

    NAME:
        실제 개인정보 탐지에 사용

    ORG:
        부서 여부 판단의 보조 근거로만 사용
    """

    ner = _get_ner()

    entities = ner(
        text,
        stride=64,
    )

    names = []
    orgs = []

    for entity in entities:
        entity_type = str(
            entity.get(
                "entity_group",
                ""
            )
        ).upper()

        score = float(
            entity.get(
                "score",
                0
            )
        )

        start = entity.get(
            "start"
        )

        end = entity.get(
            "end"
        )

        if start is None or end is None:
            continue

        raw_value = text[
            start:end
        ]

        # 앞쪽 공백이 포함된 경우 실제 위치 보정
        left_space = (
            len(raw_value)
            - len(
                raw_value.lstrip()
            )
        )

        value = raw_value.strip()

        start = (
            start
            + left_space
        )

        end = (
            start
            + len(value)
        )

        if not value:
            continue

        # 이미 Regex에서 마스킹된 데이터 제외
        if "*" in value:
            continue

        # -------------------------------------------------
        # NAME
        # -------------------------------------------------

        if entity_type == "NAME":
            if score < NAME_THRESHOLD:
                continue

            # 현재 프로젝트에서는 한국어 인명만 대상으로 사용
            if not re.fullmatch(
                r"[가-힣]{2,5}",
                value,
            ):
                continue

            names.append({
                "type": "이름",
                "text": value,
                "start": start,
                "end": end,
                "score": score,
            })

        # -------------------------------------------------
        # ORG
        #
        # 바로 부서로 판단하지 않는다.
        # -------------------------------------------------

        elif entity_type == "ORG":
            if score < ORG_THRESHOLD:
                continue

            orgs.append({
                "text": value,
                "start": start,
                "end": end,
                "score": score,
            })

    # =====================================================
    # 동일 이름 반복 등장 보완
    #
    # NER이 문서 안에서 한 번이라도 NAME으로 확인했다면
    # 같은 이름이 다른 위치에 등장해도 마스킹한다.
    # =====================================================

    confirmed_names = {
        item["text"]
        for item in names
    }

    for name in confirmed_names:
        for match in re.finditer(
            re.escape(name),
            text,
        ):
            names.append({
                "type": "이름",
                "text": name,
                "start": match.start(),
                "end": match.end(),
                "score": 1.0,
            })

    names = _remove_duplicate_spans(
        names
    )

    return names, orgs


# =========================================================
# 부서 후보 추출
# =========================================================

def _get_department_suffix(candidate):
    """
    후보가 어떤 조직 단위로 끝나는지 반환한다.
    """

    for suffix in sorted(
        ALL_DEPARTMENT_SUFFIXES,
        key=len,
        reverse=True,
    ):
        if candidate.endswith(
            suffix
        ):
            return suffix

    return None


def _extract_department_candidates(text):
    """
    특정 기업의 부서 목록을 사용하지 않고
    조직 단위 표현을 이용해 '후보'만 추출한다.

    여기서는 아직 부서로 확정하지 않는다.
    """

    suffix_pattern = "|".join(
        re.escape(suffix)
        for suffix in sorted(
            ALL_DEPARTMENT_SUFFIXES,
            key=len,
            reverse=True,
        )
    )

    pattern = re.compile(
        rf"(?P<value>"
        rf"[가-힣A-Za-z0-9·_-]{{2,30}}"
        rf"(?:{suffix_pattern})"
        rf")"
        rf"(?="
            rf"의|"
            rf"에서|"
            rf"에서는|"
            rf"에게|"
            rf"으로|"
            rf"로|"
            rf"이|"
            rf"가|"
            rf"은|"
            rf"는|"
            rf"과|"
            rf"와|"
            rf"을|"
            rf"를|"
            rf"\s|"
            rf"[,./:;()\[\]{{}}]|"
            rf"$"
        rf")"
    )

    candidates = []

    for match in pattern.finditer(
        text
    ):
        value = match.group(
            "value"
        )

        if "*" in value:
            continue

        suffix = _get_department_suffix(
            value
        )

        if suffix is None:
            continue

        candidates.append({
            "text": value,
            "start": match.start(
                "value"
            ),
            "end": match.end(
                "value"
            ),
            "suffix": suffix,
        })

    return candidates


# =========================================================
# 부서 문맥 판단
# =========================================================

def _nearby_name(candidate, names):
    """
    부서 후보 주변에 NER이 찾은 사람이 있는지 확인한다.
    """

    start = candidate[
        "start"
    ]

    end = candidate[
        "end"
    ]

    for name in names:
        distance = min(
            abs(
                name["start"]
                - end
            ),
            abs(
                start
                - name["end"]
            ),
        )

        if distance <= 30:
            return True

    return False


def _overlaps_org(candidate, orgs):
    """
    NER이 ORG라고 판단한 영역과
    부서 후보가 겹치는지 확인한다.
    """

    c_start = candidate[
        "start"
    ]

    c_end = candidate[
        "end"
    ]

    for org in orgs:
        o_start = org[
            "start"
        ]

        o_end = org[
            "end"
        ]

        overlap = (
            c_start < o_end
            and c_end > o_start
        )

        if overlap:
            return True

    return False


def _get_context(
    text,
    start,
    end,
    size=35
):
    """
    후보 앞뒤의 문맥을 가져온다.
    """

    left = text[
        max(
            0,
            start - size
        ):
        start
    ]

    right = text[
        end:
        min(
            len(text),
            end + size
        )
    ]

    return left, right


def _has_organization_hint(value):
    """
    부서명 후보 안에 기업 조직에서 자주 사용되는
    표현이 포함되어 있는지 확인한다.

    예:
        사업관리실 -> True
        전략기획실 -> True
        품질혁신실 -> True
        회의실     -> False
    """

    return any(
        word in value
        for word in ORGANIZATION_HINT_WORDS
    )


def _department_score(
    text,
    candidate,
    names,
    orgs,
):
    """
    부서 후보의 점수를 계산한다.

    suffix 자체뿐만 아니라
    주변 문맥, NER 이름, ORG 여부를 함께 사용한다.
    """

    value = candidate[
        "text"
    ]

    suffix = candidate[
        "suffix"
    ]

    # =====================================================
    # 명확한 장소는 부서 처리하지 않음
    # =====================================================

    if value in PLACE_WORDS:
        return -100

    score = 0

    # -----------------------------------------------------
    # 1. suffix 자체의 신뢰도
    # -----------------------------------------------------

    if suffix in STRONG_DEPARTMENT_SUFFIXES:
        score += 3

    elif suffix in MEDIUM_DEPARTMENT_SUFFIXES:
        score += 2

    elif suffix in WEAK_DEPARTMENT_SUFFIXES:
        score += 1

    # -----------------------------------------------------
    # 2. 후보 길이
    # -----------------------------------------------------

    if len(value) >= 4:
        score += 1

    # -----------------------------------------------------
    # 3. 약한 suffix지만 조직성이 강한 단어가 포함된 경우
    #
    # 사업관리실 같은 실제 부서 미탐을 보완한다.
    #
    # 너무 짧은 "관리실" 같은 표현에 바로 점수를 주지 않도록
    # 길이가 5자 이상일 때만 적용한다.
    # -----------------------------------------------------

    if (
        suffix in WEAK_DEPARTMENT_SUFFIXES
        and len(value) >= 5
        and _has_organization_hint(value)
    ):
        score += 1

    # -----------------------------------------------------
    # 4. 후보 뒤의 조사
    # -----------------------------------------------------

    after = text[
        candidate["end"]:
        candidate["end"] + 5
    ]

    particles = (
        "의",
        "에서",
        "에서는",
        "이",
        "가",
        "은",
        "는",
        "과",
        "와",
        "으로",
        "로",
    )

    if after.startswith(
        particles
    ):
        score += 1

    # -----------------------------------------------------
    # 5. 주변 문맥
    # -----------------------------------------------------

    left, right = _get_context(
        text,
        candidate["start"],
        candidate["end"],
    )

    context = (
        left
        + right
    )

    if any(
        word in context
        for word in DEPARTMENT_CONTEXT_WORDS
    ):
        score += 2

    if any(
        word in context
        for word in WORK_CONTEXT_WORDS
    ):
        score += 1

    # -----------------------------------------------------
    # 6. 근처에 사람이 있는 경우
    # -----------------------------------------------------

    if _nearby_name(
        candidate,
        names,
    ):
        score += 2

    # -----------------------------------------------------
    # 7. NER ORG와 겹치는 경우
    # -----------------------------------------------------

    if _overlaps_org(
        candidate,
        orgs,
    ):
        score += 2

    return score


def _is_department(
    text,
    candidate,
    names,
    orgs,
):
    """
    suffix 종류에 따라 필요한 근거 수준을 다르게 적용한다.
    """

    score = _department_score(
        text,
        candidate,
        names,
        orgs,
    )

    suffix = candidate[
        "suffix"
    ]

    # 팀 / 본부 / 사업부 / 파트
    if suffix in STRONG_DEPARTMENT_SUFFIXES:
        return score >= 3

    # 센터 / 연구소 / 그룹
    if suffix in MEDIUM_DEPARTMENT_SUFFIXES:
        return score >= 3

    # 실 / 부
    #
    # threshold 자체는 낮추지 않는다.
    # 대신 조직성 단어가 있는 경우 점수를 추가한다.
    if suffix in WEAK_DEPARTMENT_SUFFIXES:
        return score >= 4

    return False


def _detect_departments(
    text,
    names,
    orgs,
):
    """
    부서 후보 추출
    -> 문맥 검증
    -> 반복 등장 보완
    """

    candidates = _extract_department_candidates(
        text
    )

    departments = []

    # -----------------------------------------------------
    # 1. 문맥을 이용해 최초 부서 확인
    # -----------------------------------------------------

    for candidate in candidates:
        if not _is_department(
            text,
            candidate,
            names,
            orgs,
        ):
            continue

        departments.append({
            "type": "부서",
            "text": candidate[
                "text"
            ],
            "start": candidate[
                "start"
            ],
            "end": candidate[
                "end"
            ],
            "score": _department_score(
                text,
                candidate,
                names,
                orgs,
            ),
        })

    # -----------------------------------------------------
    # 2. 한번 부서로 확인된 명칭은
    # 같은 문서 안의 동일 표현도 전부 탐지
    # -----------------------------------------------------

    detected_names = {
        item["text"]
        for item in departments
    }

    for department_name in detected_names:
        for match in re.finditer(
            re.escape(
                department_name
            ),
            text,
        ):
            value = match.group()

            if "*" in value:
                continue

            departments.append({
                "type": "부서",
                "text": department_name,
                "start": match.start(),
                "end": match.end(),
                "score": 1.0,
            })

    return _remove_duplicate_spans(
        departments
    )


# =========================================================
# 최종 비정형 개인정보 탐지
# =========================================================

def detect_ner_pii(text):
    """
    Regex 1차 마스킹 이후 실행한다.

    1. NER NAME
        -> 자연어 속 이름 탐지

    2. NER ORG
        -> 부서의 보조 근거

    3. Department Detector
        -> suffix + 문맥 + NAME + ORG를 이용하여
           기업 내부 부서 탐지

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

    if not text.strip():
        return {
            "pii_found": [],
            "masked_text": text,
        }

    # NER 실행
    names, orgs = _extract_ner_entities(
        text
    )

    # 부서 탐지
    departments = _detect_departments(
        text,
        names,
        orgs,
    )

    # 결과 합치기
    spans = (
        names
        + departments
    )

    spans = _remove_duplicate_spans(
        spans
    )

    # 마스킹
    masked_text = _mask_spans(
        text,
        spans,
    )

    # 타입별 건수 계산
    counts = {}

    for item in spans:
        pii_type = item[
            "type"
        ]

        counts[pii_type] = (
            counts.get(
                pii_type,
                0
            )
            + 1
        )

    pii_found = []

    for pii_type in (
        "이름",
        "부서",
    ):
        count = counts.get(
            pii_type,
            0,
        )

        if count <= 0:
            continue

        pii_found.append({
            "type": pii_type,
            "count": count,
            "risk_level": "LOW",
            "masked": True,
        })

    return {
        "pii_found": pii_found,
        "masked_text": masked_text,
    }