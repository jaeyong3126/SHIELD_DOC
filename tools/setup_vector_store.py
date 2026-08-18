# =========================================================
# OpenAI File Search용 Vector Store 초기 설정
#
# 정책 PDF 업로드 및 Vector Store 생성 시 최초 1회 실행
# 일반적인 Pipeline 실행에서는 사용하지 않음
# 기존 VECTOR_STORE_ID가 있으면 새 Vector Store를 생성하지 않음
# =========================================================

import os

from dotenv import load_dotenv
from openai import OpenAI


# =========================================================
# 1. 환경 설정
# =========================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")

pdf_path = "docs/policy/hanbit_security_policy.pdf"


# =========================================================
# 2. 기존 Vector Store 확인
#
# 팀 공용 VECTOR_STORE_ID가 이미 존재하면
# 실수로 새로운 Vector Store가 생성되지 않도록 종료
# =========================================================

if VECTOR_STORE_ID:
    print("기존 VECTOR_STORE_ID가 이미 설정되어 있습니다.")
    print("새 Vector Store를 생성하지 않습니다.")
    raise SystemExit


# API Key 확인
if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY가 .env에 설정되어 있지 않습니다."
    )


client = OpenAI(
    api_key=OPENAI_API_KEY
)


# =========================================================
# 3. 정책 PDF OpenAI 업로드
# =========================================================

with open(pdf_path, "rb") as f:
    uploaded_file = client.files.create(
        file=f,
        purpose="assistants"
    )

print("파일 업로드 완료")
print("File ID:", uploaded_file.id)

# =========================================================
# 4. Vector Store 생성
# =========================================================

vector_store = client.vector_stores.create(
    name="hanbit_security_policy"
)

print("Vector Store 생성 완료")
print("Vector Store ID:", vector_store.id)


# =========================================================
# 5. 정책 PDF를 Vector Store에 연결
#
# 파일 처리가 완료될 때까지 기다린 뒤 상태 확인
# =========================================================

vector_store_file = client.vector_stores.files.create_and_poll(
    vector_store_id=vector_store.id,
    file_id=uploaded_file.id
)

print("Vector Store 파일 상태:", vector_store_file.status)


# =========================================================
# 6. 생성된 ID 안내
#
# 생성된 VECTOR_STORE_ID를 .env에 직접 저장해서 사용
# =========================================================

print("\n.env에 다음 값을 설정하세요.")
print(f"VECTOR_STORE_ID={vector_store.id}")
