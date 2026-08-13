import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")

def search_policy(text):
    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": (
                        "너는 한빛반도체 외부 정보 반출 보안 정책 검사기다. "
                        "입력 문서가 정책을 위반하는 경우에만 관련 정책 조항을 찾아라. "
                        "단순히 관련 있는 조항은 반환하지 말고, 실제 위반에 해당하는 경우만 판단하라. "
                        "반드시 JSON 형식으로만 답하고, "
                        "위반 정책은 refs 배열에 title, snippet, source 형식으로 반환하라. "
                        "위반이 없다면 {\"refs\": []}를 반환하라."
                    )
                },
                {
                    "role": "user",
                    "content": f"""
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
                }
            ],
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [VECTOR_STORE_ID],
                    "max_num_results": 3
                }
            ],
            # max_output_tokens=600   # gpt가 불필요한 긴 답 생성하지 않게 제한
        )

        print("File Search usage:", response.usage)
        print("output_text:", repr(response.output_text))

        result_text = response.output_text.strip()

        if result_text.startswith("```"):
            result_text = result_text.replace("```json", "")
            result_text = result_text.replace("```", "")
            result_text = result_text.strip()

        result = json.loads(result_text)

        return {
            "refs": result.get("refs", [])[:3]
        }

    except json.JSONDecodeError as e :
        print("File Search JSON 변환 오류:", e)
        return {
            "refs":[]
        }
    
    except Exception as e:
        print("File Search 오류:", e)
        return {
            "refs": []
        }

if __name__ == "__main__":
    test_text = """
    이번 주 사내 구내 식당 운영시간 안내입니다. 
    점심시간은 오전 11시 30분 부터 오후 1시 30분까지입니다.
    """

    result = search_policy(test_text)

    print("최종 반환값:", result)