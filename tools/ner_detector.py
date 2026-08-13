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


# 명확하게 장소 성격이 강한 단어
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
    "협업실",
}


# 기업 조직명에서 자주 사용되는 일반적인 표현
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
    "연구",
    "설계",
    "공정",
    "플랫폼",
    "데이터",
    "서비스",
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
    "직원",
    "구성원",
    "팀원",
    "팀장",
    "본부장",
    "센터장",
    "실장",
    "부서장",
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


# 부서명이 아니라 시상/평가/모집 등의 분류값일 가능성이 높은 문맥
NON_DEPARTMENT_CONTEXT_PHRASES = (
    "추천 부문",
    "시상 부문",
    "포상 부문",
    "수상 부문",
    "평가 부문",
    "선정 부문",
    "참가 부문",
    "모집 부문",
)


# "~팀" 형태이지만 실제 조직명보다는
# 분류/선정 결과를 나타낼 가능성이 높은 앞부분
NON_DEPARTMENT_PREFIX_WORDS = (
    "모범",
    "우수",
    "최우수",
    "우승",
    "참가",
    "후보",
    "수상",
    "대상",
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
            0,
        ):
            unique[key] = item

    return list(
        unique.values()
    )


def _mask_spans(text, spans):
    """
    탐지 위치를 뒤에서부터 마스킹한다.
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
                "",
            )
        ).upper()

        score = float(
            entity.get(
                "score",
                0,
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
    조직 단위 표현을 이용해 후보만 추출한다.
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
    size=35,
):
    """
    후보 앞뒤의 문맥을 가져온다.
    """

    left = text[
        max(
            0,
            start - size,
        ):
        start
    ]

    right = text[
        end:
        min(
            len(text),
            end + size,
        )
    ]

    return left, right


def _has_organization_hint(value):
    """
    부서 후보 안에 기업 조직에서 자주 사용되는
    표현이 포함되어 있는지 확인한다.
    """

    return any(
        word in value
        for word in ORGANIZATION_HINT_WORDS
    )


def _department_evidence(
    text,
    candidate,
    names,
    orgs,
):
    """
    후보가 실제 조직이라는 긍정적인 근거를 정리한다.
    """

    left, right = _get_context(
        text,
        candidate["start"],
        candidate["end"],
    )

    context = (
        left
        + right
    )

    return {
        "organization_hint": _has_organization_hint(
            candidate["text"]
        ),
        "department_context": any(
            word in context
            for word in DEPARTMENT_CONTEXT_WORDS
        ),
        "work_context": any(
            word in context
            for word in WORK_CONTEXT_WORDS
        ),
        "nearby_name": _nearby_name(
            candidate,
            names,
        ),
        "org_overlap": _overlaps_org(
            candidate,
            orgs,
        ),
    }


def _has_positive_department_evidence(evidence):
    """
    suffix 자체를 제외하고
    실제 조직이라고 볼 수 있는 근거가 하나라도 있는지 확인한다.
    """

    return any(
        evidence.values()
    )


def _has_strong_department_evidence(evidence):
    """
    추천/시상처럼 애매한 문맥에서도
    실제 조직이라고 판단할 만한 강한 근거가 있는지 확인한다.
    """

    return (
        evidence["department_context"]
        or evidence["nearby_name"]
        or evidence["org_overlap"]
    )


def _is_non_department_context(
    text,
    candidate,
    evidence,
):
    """
    부서명이 아니라 시상/평가/추천 등의
    분류값으로 사용된 표현인지 확인한다.

    예:
        추천 부문: 우수사원, 모범팀, 혁신아이디어
        -> 모범팀은 부서로 처리하지 않음
    """

    value = candidate[
        "text"
    ]

    left, right = _get_context(
        text,
        candidate["start"],
        candidate["end"],
        size=45,
    )

    # 추천 부문, 시상 부문 등 목록 안에서 등장한 경우
    category_context = any(
        phrase in left
        for phrase in NON_DEPARTMENT_CONTEXT_PHRASES
    )

    # 모범팀, 우수팀, 참가팀처럼
    # 조직명보다는 분류 표현일 가능성이 높은 경우
    category_prefix = any(
        value.startswith(prefix)
        for prefix in NON_DEPARTMENT_PREFIX_WORDS
    )

    # 실제 부서라는 강한 근거가 있다면
    # 단순 키워드만으로 제외하지 않는다.
    if _has_strong_department_evidence(
        evidence
    ):
        return False

    if category_context:
        return True

    if category_prefix:
        return True

    return False


def _department_score(
    text,
    candidate,
    names,
    orgs,
):
    """
    부서 후보의 점수를 계산한다.

    suffix 하나만으로 결정하지 않고
    조직성 표현, 주변 문맥, 이름, ORG 등을 함께 사용한다.
    """

    value = candidate[
        "text"
    ]

    suffix = candidate[
        "suffix"
    ]

    # 명확한 장소는 부서 처리하지 않음
    if value in PLACE_WORDS:
        return -100

    evidence = _department_evidence(
        text,
        candidate,
        names,
        orgs,
    )

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
    # 3. 조직성 표현
    # -----------------------------------------------------

    if evidence[
        "organization_hint"
    ]:
        score += 1

    # -----------------------------------------------------
    # 4. 후보 뒤 조사
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
    # 5. 부서 문맥
    # -----------------------------------------------------

    if evidence[
        "department_context"
    ]:
        score += 2

    # -----------------------------------------------------
    # 6. 업무 문맥
    # -----------------------------------------------------

    if evidence[
        "work_context"
    ]:
        score += 1

    # -----------------------------------------------------
    # 7. 근처 사람 이름
    # -----------------------------------------------------

    if evidence[
        "nearby_name"
    ]:
        score += 2

    # -----------------------------------------------------
    # 8. NER ORG와 겹침
    # -----------------------------------------------------

    if evidence[
        "org_overlap"
    ]:
        score += 2

    return score


def _is_department(
    text,
    candidate,
    names,
    orgs,
):
    """
    부서 후보를 최종 판정한다.

    핵심:
    1. suffix만으로는 부서 확정하지 않음
    2. 실제 조직이라는 긍정적 근거가 최소 하나 필요
    3. 추천/시상/평가 문맥이면 오탐 가능성을 확인
    """

    value = candidate[
        "text"
    ]

    suffix = candidate[
        "suffix"
    ]

    # 장소는 바로 제외
    if value in PLACE_WORDS:
        return False

    evidence = _department_evidence(
        text,
        candidate,
        names,
        orgs,
    )

    # suffix 말고 실제 조직이라는 근거가 하나도 없으면 제외
    if not _has_positive_department_evidence(
        evidence
    ):
        return False

    # 추천/시상/평가 등의 문맥이면 부서가 아닐 가능성이 높음
    if _is_non_department_context(
        text,
        candidate,
        evidence,
    ):
        return False

    score = _department_score(
        text,
        candidate,
        names,
        orgs,
    )

    # 강한 suffix도 이제 suffix 하나만으로 통과하지 않는다.
    if suffix in STRONG_DEPARTMENT_SUFFIXES:
        return score >= 4

    # 센터 / 연구소 / 그룹
    if suffix in MEDIUM_DEPARTMENT_SUFFIXES:
        return score >= 4

    # 실 / 부
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
        str,
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
                0,
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