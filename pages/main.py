import streamlit as st

st.set_page_config(
    page_title="문서 분석 시스템 - 쉴드 독 (SHEILD DOC)",
    page_icon='C:/Users/ez/Downloads/icons8-방패-48.png',
    layout='wide'
)

# 제목
st.markdown("<h1 style='text-align: center;'>🛡️ 쉴드 독 (SHEILD DOC)</h1>", unsafe_allow_html=True)
st.write('---')

st.subheader("쉴드 독 (Sheild Doc) 이란?\n")
st.text("쉴드 독 (Sheild Doc)은 파일 내에 중요한 데이터가 있는지 판별하는 시스템입니다.\n")
st.write('''  
    쉴드 독은 파일 내에서 다음과 같은 정보들을 판별합니다.\n
    - 민감한 개인정보\n 
    - 회사 별 기밀 정보\n
    - 기업 규정 적용 확인\n
    회사나 개인의 중요한 정보들이 유출되지 않도록 머신러닝 모델로 탐지하고 판단하여 종합 위험 점수를 매기고, 외부로 반출이 가능한지 판단합니다.
''')
st.write('---')