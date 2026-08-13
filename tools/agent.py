import json
import os

from dotenv import load_dotenv
from openai import OpenAI


# =========================================================
# 1. OpenAI API 설정
# =========================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

# OpenAI에 전달할 정책 근거 최대 개수
# 검색 횟수 및 중복 제거는 filesearch.py에서 처리
MAX_POLICY_REFS = 3


def _get_client():
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY가 .env에 설정되어 있지 않습니다."
        )

    return OpenAI(
        api_key=OPENAI_API_KEY
    )


# =========================================================
# 2. System Prompt
# =========================================================

SYSTEM_PROMPT = """
너는 SHIELD_DOC의 문서 보안 분석 설명 AI이다.

개인정보 탐지, Secret 탐지, ML 기밀 분류,
기업 정책 검색 및 Risk Engine 판정은 이미 완료되었다.

너의 역할은 새로운 보안 판정을 수행하는 것이 아니라,
이미 제공된 분석 결과를 사용자가 이해하기 쉽게 설명하는 것이다.

반드시 다음 규칙을 지켜라.

1. Risk Engine의 score와 action을 변경하거나 재판단하지 않는다.

2. ML의 label, label_name, confidence를 변경하거나 재판단하지 않는다.

3. pii_found에 없는 개인정보를 만들어내지 않는다.

4. secret_found에 없는 Secret 또는 인증정보를 만들어내지 않는다.

5. policy.refs에 없는 정책, 법률, 규정 또는 조항을 만들어내지 않는다.

6. 추가 정책 검색이나 외부 검색을 수행하거나 요구하지 않는다.

7. 정책 검색 결과가 없으면
   "확인된 관련 정책 없음"이라고 설명한다.

8. 개인정보 및 Secret의 risk_level이 존재하면
   HIGH/LOW 값을 변경하지 않는다.

9. 검사 실패 또는 판정 실패로 차단된 경우
   실제 민감정보가 발견되었다고 단정하지 않는다.
   안전성을 확인할 수 없어 예방적으로 차단되었다고 설명한다.

10. PII, Secret, ML, Policy 결과가 서로 다른 방향을 나타내더라도
    최종 판정은 Risk Engine의 score와 action을 따른다.

11. 제공되지 않은 사실을 추측하지 않는다.

12. 근거를 과장하거나 새로운 판단 근거를 만들어내지 않는다.

13. 한국어로 간결하고 명확하게 작성한다.
"""


# =========================================================
# 3. Pipeline 분석 결과 정리
#
# 원문 text는 OpenAI에 전달하지 않음
# 정책 중복 제거는 filesearch.py에서 수행
# =========================================================

def build_analysis_context(doc):
    if not isinstance(doc, dict):
        raise TypeError(
            "analyze_final 입력값은 dict 형식이어야 합니다."
        )

    policy = doc.get("policy", {"refs": []})

    if not isinstance(policy, dict):
        policy = {"refs": []}

    refs = policy.get("refs", [])

    if not isinstance(refs, list):
        refs = []

    # 검색 결과 자체의 중복 제거는 filesearch.py 담당
    # Agent에서는 토큰 방지를 위해 최대 3개만 사용
    policy_for_ai = {
        "refs": refs[:MAX_POLICY_REFS]
    }

    return {
        "filename": doc.get("filename", ""),
        "pii_found": doc.get("pii_found", []),
        "secret_found": doc.get("secret_found", []),
        "ml": doc.get("ml", {}),
        "policy": policy_for_ai,
        "risk": doc.get("risk", {}),
    }


# =========================================================
# 4. 차단 문서용 OpenAI Prompt
# =========================================================

def _build_user_prompt(context):
    # JSON 공백 최소화 → Input Token 절감
    analysis_json = json.dumps(
        context,
        ensure_ascii=False,
        separators=(",", ":")
    )

    return f"""
다음은 SHIELD_DOC에서 반출 차단으로 판정된 문서의 보안 분석 결과이다.

[분석 데이터]
{analysis_json}

위 데이터만 사용하여 차단 사유를 설명하라.

출력 형식:

[분석 요약]
문서가 반출 차단된 이유를 한 문장으로 요약한다.

[주요 근거]
실제로 제공된 결과만 사용하여 설명한다.
- 개인정보 및 Secret 탐지 결과
- ML 기밀 분류 결과
- 관련 정책 검색 결과
- Risk Engine의 판정 이유

관련 결과가 없는 항목은 간단하게만 언급한다.

[최종 판정]
Risk Engine의 score와 action을 그대로 표시한다.

예:
위험도 100점 / 반출 차단

[권고 조치]
실제로 확인된 위험 요소를 기반으로
외부 반출 전에 필요한 조치를 간단하게 제안한다.

중요:
- 새로운 보안 판정을 만들지 않는다.
- 새로운 근거를 만들어내지 않는다.
- Risk Engine의 score와 action을 변경하지 않는다.
- 제공된 policy.refs 이외의 정책을 언급하지 않는다.
"""


# =========================================================
# 5. OpenAI Token Usage 출력
# =========================================================

def _print_token_usage(response):
    usage = response.usage

    if usage is None:
        return

    reasoning_tokens = 0

    if usage.output_tokens_details is not None:
        reasoning_tokens = (
            usage.output_tokens_details.reasoning_tokens or 0
        )

    print("\n===== OpenAI Token Usage =====")
    print(f"Input Tokens     : {usage.input_tokens}")
    print(f"Output Tokens    : {usage.output_tokens}")
    print(f"Reasoning Tokens : {reasoning_tokens}")
    print(f"Total Tokens     : {usage.total_tokens}")
    print("==============================")


# =========================================================
# 6. 허용 문서 설명
#
# OpenAI API 호출 없음 → 토큰 사용 0
# =========================================================

def _build_allow_explanation(context):
    risk = context.get("risk", {})

    score = risk.get("score", 0)
    reasons = risk.get("reasons", [])

    if not isinstance(reasons, list):
        reasons = []

    reason_text = "\n".join(
        f"- {reason}"
        for reason in reasons
        if reason
    )

    if not reason_text:
        reason_text = "- 특이사항 없음"

    # 위험 요소가 전혀 없는 정상 문서
    if score == 0:
        recommendation = (
            "현재 분석 결과 추가 확인이 필요한 "
            "위험 요소는 확인되지 않았습니다."
        )

    # 일부 저위험 요소는 있지만 차단 기준 미달
    else:
        recommendation = (
            "차단 기준에는 미달하였으나 탐지된 항목이 있으므로 "
            "외부 반출 전 내용을 확인하는 것을 권장합니다."
        )

    return f"""[분석 요약]
해당 문서는 현재 보안 분석 결과 외부 반출이 허용되었습니다.

[주요 근거]
{reason_text}

[최종 판정]
위험도 {score}점 / 반출 허용

[권고 조치]
{recommendation}"""


# =========================================================
# 7. Pipeline에서 호출하는 최종 함수
# =========================================================

def analyze_final(doc):
    """
    허용 문서:
        고정 설명 반환
        → OpenAI API 호출 없음
        → 토큰 사용 없음

    차단 문서:
        OpenAI API 호출
        → 상세 차단 사유 설명
    """

    context = build_analysis_context(doc)

    risk = context.get("risk", {})
    action = risk.get("action", "")

    # =====================================================
    # 허용 문서
    # =====================================================

    if action == "허용":
        return _build_allow_explanation(context)

    # =====================================================
    # 차단 문서
    # =====================================================

    if action == "차단":
        client = _get_client()

        user_prompt = _build_user_prompt(context)

        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=SYSTEM_PROMPT,
            input=user_prompt,

            # 멀티턴 대화 상태 저장 불필요
            store=False,

            # 결과 설명 작업이므로 낮은 추론 수준 사용
            # gpt-5 / gpt-5.5 모두 호환
            reasoning={
                "effort": "low"
            },

            # reasoning + 실제 출력 전체 상한
            max_output_tokens=1600,
        )

        # 차단 문서에서만 토큰 사용량 출력
        _print_token_usage(response)

        explanation = response.output_text

        if not explanation:
            raise RuntimeError(
                "OpenAI 응답에 설명 텍스트가 없습니다."
            )

        return explanation.strip()

    # =====================================================
    # Risk Engine 결과 비정상
    # =====================================================

    raise RuntimeError(
        f"알 수 없는 Risk Engine action입니다: {action}"
    )