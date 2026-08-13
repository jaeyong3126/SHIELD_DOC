import os
import json

from dotenv import load_dotenv
from openai import OpenAI


# =========================================================
# 1. OpenAI File Search 환경 설정
# =========================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

# File Search에서 가져올 검색 결과 최대 개수
MAX_SEARCH_RESULTS = 3

# Pipeline에 최종 반환할 정책 근거 최대 개수
MAX_POLICY_REFS = 3


# =========================================================
# 2. OpenAI Client 생성
#
# API Key 또는 Vector Store ID가 없으면
# File Search를 실행하지 않고 오류를 발생시킴
# =========================================================

def _get_client():
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY가 .env에 설정되어 있지 않습니다."
        )

    if not VECTOR_STORE_ID:
        raise RuntimeError(
            "VECTOR_STORE_ID가 .env에 설정되어 있지 않습니다."
        )

    return OpenAI(
        api_key=OPENAI_API_KEY
    )


# =========================================================
# 3. File Search System Prompt
#
# 단순히 문서와 관련된 정책을 찾는 것이 아니라
# 실제 외부 반출 정책 위반에 해당하는 경우에만 refs 반환
# =========================================================

SYSTEM_PROMPT = (
    "너는 한빛반도체 외부 정보 반출 보안 정책 검사기다. "
    "입력 문서가 정책을 위반하는 경우에만 관련 정책 조항을 찾아라. "
    "단순히 관련 있는 조항은 반환하지 말고, 실제 위반에 해당하는 경우만 판단하라. "
    "반드시 JSON 형식으로만 답하고, "
    "위반 정책은 refs 배열에 title, snippet, source 형식으로 반환하라. "
    "위반이 없다면 {\"refs\": []}를 반환하라."
)


# =========================================================
# 4. File Search User Prompt 생성
# =========================================================

def _build_user_prompt(text):
    return f"""
다음 문서의 외부 반출 내용이 한빛반도체 보안정책을 위반하는지 확인해라.

문서:
{text}

반환 형식:

{{
    "refs": [
        {{
            "title": "정책 조항 제목",
            "snippet": "위반 근거가 되는 정책 내용을 1~2문장으로 요약",
            "source": "hanbit_security_policy.pdf"
        }}
    ]
}}

위반이 없다면:

{{
    "refs": []
}}
"""


# =========================================================
# 5. File Search Token Usage 출력
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

    print("\n===== File Search Token 사용량 =====")
    print(f"Input Tokens     : {usage.input_tokens}")
    print(f"Output Tokens    : {usage.output_tokens}")
    print(f"Reasoning Tokens : {reasoning_tokens}")
    print(f"Total Tokens     : {usage.total_tokens}")
    print("====================================")


# =========================================================
# 6. OpenAI 응답 JSON 변환
#
# 모델이 ```json 코드블록으로 응답하는 경우 제거한 뒤
# Python dict로 변환
# =========================================================

def _parse_response(response):
    result_text = response.output_text.strip()

    if not result_text:
        raise ValueError(
            "File Search 응답에 결과 텍스트가 없습니다."
        )

    if result_text.startswith("```"):
        result_text = result_text.replace("```json", "")
        result_text = result_text.replace("```", "")
        result_text = result_text.strip()

    result = json.loads(result_text)

    if not isinstance(result, dict):
        raise ValueError(
            "File Search 결과가 dict 형식이 아닙니다."
        )

    refs = result.get("refs", [])

    if not isinstance(refs, list):
        raise ValueError(
            "File Search 결과의 refs가 list 형식이 아닙니다."
        )

    return {
        "refs": refs[:MAX_POLICY_REFS]
    }


# =========================================================
# 7. Pipeline에서 호출하는 정책 검색 함수
#
# 입력:
#   PII / Secret이 마스킹된 문서 text
#
# 출력:
#   정책 위반 있음
#   {
#       "refs": [
#           {
#               "title": "...",
#               "snippet": "...",
#               "source": "..."
#           }
#       ]
#   }
#
#   정책 위반 없음
#   {"refs": []}
#
# 주의:
#   File Search 자체가 실패한 경우 refs=[]를 반환하지 않고
#   예외를 다시 발생시킨다.
#
#   최신 pipeline v3의 _safe()가 이 예외를 감지하여
#   "정책 위반 없음"과 "정책 검색 실패"를 구분한다.
# =========================================================

def search_policy(text):
    try:
        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                "search_policy 입력 text가 비어 있습니다."
            )

        client = _get_client()

        user_prompt = _build_user_prompt(text)

        response = client.responses.create(
            model=OPENAI_MODEL,

            input=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],

            # -------------------------------------------------
            # OpenAI Built-in File Search
            # -------------------------------------------------

            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [VECTOR_STORE_ID],
                    "max_num_results": MAX_SEARCH_RESULTS
                }
            ],

            # 한 Responses 요청에서
            # Built-in Tool 호출 최대 2회
            max_tool_calls=2,

            # Reasoning Token 사용량 절감
            reasoning={
                "effort": "low"
            },
        )

        # Token 사용량 확인
        _print_token_usage(response)

        # JSON 응답 변환 후 refs 반환
        return _parse_response(response)

    # =====================================================
    # JSON 응답 형식 오류
    #
    # pipeline v3에서 검색 실패로 인식할 수 있도록
    # 빈 refs를 반환하지 않고 예외를 다시 전달
    # =====================================================

    except json.JSONDecodeError as e:
        print("File Search JSON 변환 오류:", e)
        raise

    # =====================================================
    # 기타 File Search 오류
    #
    # API 오류, 환경변수 오류, 잘못된 응답 등도
    # pipeline v3의 _safe()가 처리하도록 다시 전달
    # =====================================================

    except Exception as e:
        print("File Search 오류:", e)
        raise

