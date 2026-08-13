# import streamlit as st


# st.set_page_config(
#     page_title="문서 분석 시스템 - 쉴드 독 (SHEILD DOC)",
#     page_icon='',
#     layout='wide'
# )

# # 제목
# st.markdown("<h1 style='text-align: center;'>🛡️ 쉴드 독 (SHEILD DOC)</h1>", unsafe_allow_html=True)
# st.write('---')

# st.subheader("쉴드 독 (Sheild Doc) 이란?\n")
# st.text("쉴드 독 (Sheild Doc)은 파일 내에 중요한 데이터가 있는지 판별하는 시스템입니다.\n")
# st.write('''  
#     쉴드 독은 파일 내에서 다음과 같은 정보들을 판별합니다.\n
#     - 민감한 개인정보\n 
#     - 회사 별 기밀 정보\n
#     - 기업 규정 적용 확인\n
#     회사나 개인의 중요한 정보들이 유출되지 않도록 머신러닝 모델로 탐지하고 판단하여 종합 위험 점수를 매기고, 외부로 반출이 가능한지 판단합니다.
# ''')
# st.write('---')

import streamlit as st

# 1. 페이지 기본 설정
st.set_page_config(
    page_title="문서 분석 시스템 - 쉴드 독 (SHIELD DOC)",
    page_icon="🛡️",
    layout="wide"
)

# Custom CSS (상단 타이틀/서브타이틀 정렬)
st.markdown("""
    <style>
    .main-title { text-align: center; font-size: 2.6rem; font-weight: 800; margin-bottom: 0px; }
    .sub-title { text-align: center; color: #6c757d; font-size: 1.1rem; margin-bottom: 1.5rem; }
    </style>
""", unsafe_allow_html=True)

# 2. 헤더 섹션
st.markdown("<h1 class='main-title'>🛡️ 쉴드 독 (SHIELD DOC)</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>AI 기반 문서 보안 탐지 및 반출 위험도 분석 시스템</p>", unsafe_allow_html=True)
st.divider()

# 3. 핵심 가치 요약 (Metrics)
m_col1, m_col2, m_col3 = st.columns(3)
with m_col1:
    st.metric(label="탐지 레이어", value="3단계 검증", delta="민감/기밀/규정")
with m_col2:
    st.metric(label="분석 방식", value="ML/DL Hybrid", delta="실시간 종합 위험 점수")
with m_col3:
    st.metric(label="보안 목적", value="반출 통제", delta="유출 사고 사전 예방")

st.write("")
st.write("")

# 4. 주요 탐지 기능 소개 (3열 카드 레이아웃)
st.subheader("💡 주요 탐지 영역")
f_col1, f_col2, f_col3 = st.columns(3)

with f_col1:
    with st.container(border=True):
        st.markdown("### 👤 민감 개인정보")
        st.caption("Personal Data Leak Prevention")
        st.write("주민등록번호, 전화번호, 이메일, 계좌번호 등 외부 유출 시 법적 문제가 발생하는 개인 식별 정보를 자동 탐지합니다.")

with f_col2:
    with st.container(border=True):
        st.markdown("### 🏢 기업 기밀 정보")
        st.caption("Corporate Secret Detection")
        st.write("영업 비밀, 미공개 재무 실적, 내부 프로젝트 자산 등 기업 내부 기밀 문서 여부를 검사합니다.\n\n")

with f_col3:
    with st.container(border=True):
        st.markdown("### 📜 기업 규정 준수")
        st.caption("Compliance Policy Standard")
        st.write("사내 정보보안 가이드라인 및 반출 금지 정책에 위배되는 내용이 포함되어 있는지 정밀 검증합니다.")

st.divider()

# 5. 이용 프로세스 안내
st.subheader("🔄 분석 프로세스")
p_col1, p_col2, p_col3 = st.columns(3)

with p_col1:
    st.info("**1. 문서 업로드**\n\n분석할 문서 파일(PDF, TXT, DOCX 등)을 시스템에 전달합니다.")
with p_col2:
    st.warning("**2. AI 스캐닝 & 위험도 산출**\n\n머신러닝 모델이 문맥을 분석하여 종합 위험 점수를 계산합니다.")
with p_col3:
    st.success("**3. 반출 승인 판정 및 리포트**\n\n최종 반출 가능 여부 결과와 detailed JSON 리포트를 확인합니다.")

st.divider()

# 6. 하단 바로가기 안내
st.subheader("🚀 분석 시작하기")
st.write("버튼을 누르시면 분석 화면으로 이동합니다.")
if st.button("분석 시작하기"):
    st.switch_page("pages/analyze.py")