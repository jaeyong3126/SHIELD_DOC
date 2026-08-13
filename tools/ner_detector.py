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
}


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
    #
    # PDF 표나 줄바꿈 때문에 일부 위치에서
    # 문맥이 깨져 NER이 놓치는 문제를 보완한다.
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

    # suffix 뒤에는 일반적인 조사나 구분자가 나와야 한다.
    #
    # 품질혁신실에서는 -> 후보
    # 마스크기술팀의   -> 후보
    #
    # 부서마다
    # -> '부'를 잘못 탐지하지 않도록 제한
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

    예:
        마스크기술팀의 김현영
                     ↑ NAME
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
    NER이 ORG라고 판단한 영역과 부서 후보가
    겹치는지 확인한다.

    ORG 자체를 부서로 확정하지 않고
    추가 점수만 준다.
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

    # 명백한 장소는 부서 처리하지 않음
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
    # 2. 이름 길이
    # -----------------------------------------------------

    if len(value) >= 4:
        score += 1

    # -----------------------------------------------------
    # 3. 후보 뒤의 조사
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
    # 4. 주변 문맥
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
    # 5. 근처에 사람이 있는 경우
    # -----------------------------------------------------

    if _nearby_name(
        candidate,
        names,
    ):
        score += 2

    # -----------------------------------------------------
    # 6. NER ORG와 겹치는 경우
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

    # 팀 / 본부 / 사업부 / 파트는
    # 그 자체로 조직성이 매우 강함
    if suffix in STRONG_DEPARTMENT_SUFFIXES:
        return score >= 3

    # 센터 / 연구소 / 그룹
    if suffix in MEDIUM_DEPARTMENT_SUFFIXES:
        return score >= 3

    # 실 / 부는 장소/일반어와 혼동하기 쉬움
    if suffix in WEAK_DEPARTMENT_SUFFIXES:
        return score >= 4

    return False


def _detect_departments(
    text,
    names,
    orgs,
):
    """
    부서 후보 추출 -> 문맥 검증 -> 반복 등장 보완
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