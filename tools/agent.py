import json
import os

from dotenv import load_dotenv
from openai import OpenAI


# =========================================================
# T075 - OpenAI API 기본 연결
# =========================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")


# OpenAI에 전달할 정책 검색 결과 최대 개수
# 검색 자체의 횟수 제한은 tools/filesearch.py에서 처리해야 함
MAX_POLICY_REFS = 3


def _get_client():
    """
    OpenAI Client 생성
    """

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY가 .env에 설정되어 있지 않습니다."
        )

    return OpenAI(
        api_key=OPENAI_API_KEY
    )


# =========================================================
# T082 / T084
# System Prompt + Hallucination 방지
# =========================================================

SYSTEM_PROMPT = """
너는 SHIELD_DOC의 문서 보안 분석 설명 AI이다.

문서의 개인정보 탐지, Secret 탐지, ML 기밀 분류,
기업 정책 검색 및 Risk Engine 판정은 이미 외부 모듈에서 완료되었다.

너의 역할은 새로운 보안 판정을 수행하는 것이 아니라,
이미 제공된 분석 결과를 사용자가 이해하기 쉽게 설명하는 것이다.

입력으로 제공되는 정보:
- 개인정보 탐지 결과
- Secret 탐지 결과
- ML 기밀정보 분류 결과
- 기업 정책 검색 결과
- Risk Engine의 위험도 및 반출 판정

반드시 다음 규칙을 지켜라.

1. Risk Engine의 score와 action을 변경하거나 재판단하지 않는다.

2. ML의 label, label_name, confidence를
   변경하거나 다시 판단하지 않는다.

3. pii_found에 없는 개인정보를 만들어내지 않는다.

4. secret_found에 없는 Secret 또는 인증정보를 만들어내지 않는다.

5. policy.refs에 존재하지 않는 정책, 법률,
   규정 또는 조항을 만들어내지 않는다.

6. 추가 정책 검색이나 외부 검색이 필요하다고 판단하더라도
   새로운 검색을 요구하지 않는다.
   현재 제공된 policy.refs만 사용하여 설명한다.

7. 동일하거나 유사한 정책 근거가 여러 개 존재하는 경우
   동일한 내용을 반복해서 설명하지 않는다.

8. 정책 검색 결과가 없으면
   "확인된 관련 정책 없음"으로 설명하고
   임의로 정책을 생성하지 않는다.

9. 개인정보 및 Secret의 risk_level이 제공된 경우
   HIGH/LOW 값을 임의로 변경하지 않는다.

10. 검사 실패 또는 판정 실패로 인해 차단된 경우
    실제 민감정보가 발견되었다고 단정하지 않는다.
    안전성을 확인할 수 없어 예방적으로 차단되었다고 설명한다.

11. ML, PII, Secret, Policy 결과가 서로 다른 방향을
    나타내더라도 최종 판정은 Risk Engine의
    action과 score를 기준으로 설명한다.

12. 제공된 분석 결과에 없는 사실은 추측하지 않는다.

13. 근거를 과장하지 않는다.

14. 한국어로 간결하고 명확하게 작성한다.
"""


# =========================================================
# Policy 결과 중복 제거
# Query Hash Guard의 취지를 결과 단계에 적용
# =========================================================

def _deduplicate_policy_refs(policy):
    """
    policy.refs에서 동일/중복 정책을 제거한다.

    실제 검색 Query 중복 차단은 filesearch.py에서 처리해야 하며,
    여기서는 OpenAI에 동일한 검색 결과가 반복 전달되는 것을 방지한다.
    """

    if not isinstance(policy, dict):
        return {"refs": []}

    refs = policy.get("refs", [])

    if not isinstance(refs, list):
        return {"refs": []}

    unique_refs = []
    seen = set()

    for ref in refs:
        if not isinstance(ref, dict):
            continue

        title = str(ref.get("title", "")).strip()
        source = str(ref.get("source", "")).strip()
        snippet = str(ref.get("snippet", "")).strip()

        # title + source 기반 중복 판정
        key = (
            title.lower(),
            source.lower()
        )

        if key in seen:
            continue

        seen.add(key)

        unique_refs.append({
            "title": title,
            "snippet": snippet,
            "source": source,
        })

        # OpenAI에 전달할 정책 근거 개수 제한
        if len(unique_refs) >= MAX_POLICY_REFS:
            break

    return {
        "refs": unique_refs
    }


# =========================================================
# T080 / T081
# PII + Secret + ML + Policy + Risk 결과 통합
# =========================================================

def build_analysis_context(doc):
    """
    pipeline.py에서 받은 전체 doc 중
    OpenAI 설명에 필요한 결과만 추출한다.
    """

    if not isinstance(doc, dict):
        raise TypeError(
            "analyze_final 입력값은 dict 형식이어야 합니다."
        )

    policy = _deduplicate_policy_refs(
        doc.get(
            "policy",
            {"refs": []}
        )
    )

    return {
        "filename": doc.get("filename", ""),

        "pii_found": doc.get(
            "pii_found",
            []
        ),

        "secret_found": doc.get(
            "secret_found",
            []
        ),

        "ml": doc.get(
            "ml",
            {}
        ),

        "policy": policy,

        "risk": doc.get(
            "risk",
            {}
        ),
    }


# =========================================================
# T083 - 최종 설명 Format
# =========================================================

def _build_user_prompt(context):
    """
    OpenAI에 전달할 Prompt 생성
    """

    # indent를 사용하지 않아 불필요한 입력 토큰 감소
    analysis_json = json.dumps(
        context,
        ensure_ascii=False,
        separators=(",", ":")
    )

    return f"""
다음은 SHIELD_DOC의 보안 분석 결과이다.

[분석 데이터]
{analysis_json}

위 데이터만 사용하여 최종 보안 분석을 작성하라.

[분석 요약]
최종 반출 판정을 한 문장으로 요약한다.

[주요 근거]
실제로 제공된 결과만 사용하여 다음 내용을 설명한다.
- 개인정보 및 Secret 탐지 결과
- ML 기밀 분류 결과
- 관련 정책 검색 결과
- Risk Engine의 판정 이유

탐지되지 않은 항목이나 검색되지 않은 정책을
새롭게 만들어내지 않는다.

[최종 판정]
Risk Engine의 score와 action을 그대로 표시한다.

형식 예시:
위험도 70점 / 반출 차단

[권고 조치]
실제 탐지된 결과와 Risk Engine의 판정 이유를 기반으로
필요한 조치를 짧게 제안한다.

중요:
- 새로운 보안 판정을 만들지 않는다.
- 추가 검색을 수행하거나 요청하지 않는다.
- 제공된 policy.refs만 정책 근거로 사용한다.
- Risk Engine의 score와 action을 변경하지 않는다.
"""


# =========================================================
# Token Usage 출력
# =========================================================

def _print_token_usage(response):
    """
    OpenAI API 요청 1회의 Token Usage 출력
    """

    usage = response.usage

    print("\n===== OpenAI Token Usage =====")

    if usage is None:
        print("토큰 사용량 정보를 확인할 수 없습니다.")
        print("==============================")
        return

    input_tokens = getattr(
        usage,
        "input_tokens",
        0
    )

    output_tokens = getattr(
        usage,
        "output_tokens",
        0
    )

    total_tokens = getattr(
        usage,
        "total_tokens",
        0
    )

    reasoning_tokens = 0

    output_details = getattr(
        usage,
        "output_tokens_details",
        None
    )

    if output_details is not None:
        reasoning_tokens = (
            getattr(
                output_details,
                "reasoning_tokens",
                0
            )
            or 0
        )

    print(f"Input Tokens     : {input_tokens}")
    print(f"Output Tokens    : {output_tokens}")
    print(f"Reasoning Tokens : {reasoning_tokens}")
    print(f"Total Tokens     : {total_tokens}")
    print("==============================")


# =========================================================
# pipeline.py가 실제로 호출하는 함수
#
# 함수명 analyze_final 변경 금지
# 반환값 반드시 str
# =========================================================

def analyze_final(doc):
    """
    입력:
        pipeline.py에서 생성한 전체 분석 결과 dict

    출력:
        OpenAI가 생성한 최종 보안 분석 설명문(str)
    """

    # 1. 분석 결과 정리
    context = build_analysis_context(doc)

    # 2. Prompt 생성
    user_prompt = _build_user_prompt(context)

    # 3. OpenAI Client 생성
    client = _get_client()

    try:

        # 4. OpenAI Responses API 호출
        #
        # tools를 전달하지 않는다.
        # 따라서 이 Agent는 추가 검색이나
        # Function Calling을 수행할 수 없다.
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
        )

        # 5. Token Usage 확인
        _print_token_usage(response)

        # 6. 설명 추출
        explanation = response.output_text

        if not explanation:
            raise RuntimeError(
                "OpenAI 응답에 설명 텍스트가 없습니다."
            )

        return explanation.strip()

    except RuntimeError:
        raise

    except Exception as e:
        raise RuntimeError(
            f"OpenAI 설명 생성 실패 ({type(e).__name__})"
        ) from