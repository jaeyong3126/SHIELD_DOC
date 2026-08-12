import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")


def search_policy(text):
    try:
        response = client.responses.create(
            model="gpt-5.5",
            input=[
                {
                    "role": "system",
                    "content": (
                        "너는 한빛반도체 외부 정보 반출 보안 정책 검사기다. "
                        "입력 문서가 정책을 위반하는 경우에만 관련 정책 조항을 찾아라. "
                        "단순히 관련 있는 조항은 반환하지 말고, 실제 위반에 해당하는 경우만 판단하라."
                    )
                },
                {
                    "role": "user",
                    "content": f"""
다음 문서의 외부 반출 내용이 한빛반도체 보안정책을 위반하는지 확인해라.

문서:
{text}

위반이 있다면 관련 정책 조항을 근거로 설명하고,
위반이 없다면 '위반 없음'이라고 답해라.
"""
                }
            ],
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [VECTOR_STORE_ID]
                }
            ],
            include=["file_search_call.results"]
        )

        print(response)
        return {
            "refs": []
        }

    except Exception as e:
        print("File Search 오류:", e)
        return {
            "refs": []
        }




# if __name__ == "__main__":
#     test_text = """
#     신규 반도체 공정 조건과 시험 결과를
#     개인 이메일을 이용해 외부 협력사에 전달하려고 한다.
#     """

#     result = search_policy(test_text)

#     print("최종 반환값:", result)