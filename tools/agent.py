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


# import 시점에 에러를 발생시키지 않기 위해
# client는 함수에서 실제 사용할 때 생성
def _get_client():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY가 .env에 설정되어 있지 않습니다.")

    return OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# T082 - System Prompt
# 현재는 1차 버전
# =========================================================

SYSTEM_PROMPT = """
너는 SHIELD_DOC의 문서 보안 분석 설명 AI이다.

문서의 보안 분석과 최종 반출 판정은 이미 외부 모듈에서 완료되었다.
너는 입력으로 제공되는 분석 결과를 변경하지 말고,
사용자가 이해하기 쉽게 최종 판정의 근거를 설명해야 한다.

입력으로 제공되는 정보:
- 개인정보 탐지 결과
- Secret 탐지 결과
- ML 기밀정보 분류 결과
- 기업 정책 검색 결과
- Risk Engine의 위험도 및 반출 판정

반드시 다음 규칙을 지켜라.

1. Risk Engine의 score와 action을 변경하지 않는다.
2. ML의 label과 confidence를 변경하거나 재판단하지 않는다.
3. 탐지 결과에 없는 개인정보나 Secret을 만들어내지 않는다.
4. policy.refs에 없는 정책이나 법령을 만들어내지 않는다.
5. 제공된 결과만 근거로 설명한다.
6. 근거가 없는 내용은 추측하지 않는다.
7. 한국어로 간결하고 명확하게 작성한다.
"""


# =========================================================
# T080 / T081
# PII + Secret + ML + Policy + Risk 결과를
# OpenAI에 전달하기 좋은 형태로 정리
# =========================================================

def build_analysis_context(doc):
    """
    pipeline.py에서 받은 전체 doc 중
    OpenAI 설명에 필요한 값만 추출한다.
    """

    return {
        "filename": doc.get("filename", ""),
        "text": doc.get("text", ""),  # 이미 pipeline에서 마스킹된 본문
        "pii_found": doc.get("pii_found", []),
        "secret_found": doc.get("secret_found", []),
        "ml": doc.get("ml", {}),
        "policy": doc.get("policy", {"refs": []}),
        "risk": doc.get("risk", {}),
    }


# =========================================================
# T083 - 최종 설명 Format
# =========================================================

def _build_user_prompt(context):
    return f"""
다음은 SHIELD_DOC가 문서를 분석한 결과이다.

[분석 결과]
{json.dumps(context, ensure_ascii=False, indent=2)}

위 결과를 바탕으로 사용자에게 최종 보안 분석을 설명하라.

출력 형식:

[분석 요약]
최종 판정을 한 문장으로 요약

[주요 근거]
- 개인정보 및 Secret 탐지 결과
- ML 기밀 분류 결과
- 관련 정책 검색 결과
- Risk Engine의 판정 이유

[최종 판정]
위험도 점수와 반출 허용/차단 결과

[권고 조치]
필요한 경우 사용자가 취할 수 있는 조치를 간단히 설명

중요:
Risk Engine이 결정한 action과 score를 그대로 사용하라.
새로운 판정을 만들지 마라.
"""


# =========================================================
# pipeline.py가 실제로 호출하는 함수
#
# 중요:
# 함수명 analyze_final 변경 금지
# 반환값은 반드시 str
# =========================================================

def analyze_final(doc):
    """
    입력:
        pipeline.py에서 생성한 doc 전체 dict

    출력:
        최종 보안 분석 설명문(str)
    """

    client = _get_client()

    context = build_analysis_context(doc)
    user_prompt = _build_user_prompt(context)

    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=SYSTEM_PROMPT,
        input=user_prompt,
    )

    explanation = response.output_text

    if not explanation:
        raise RuntimeError("OpenAI 응답에 설명 텍스트가 없습니다.")

    return explanation