import streamlit as st
import io

st.set_page_config(layout='wide')

st.session_state.counter = 11

st.title('쉴드 독 (Sheild DOC)')
st.write('---')
st.write('쉴드 독은 업로드 된 파일을 분석하여 민감 개인정보 유출 가능성을 분석하고, '
'사내의 기밀 문서 내용이 있는지 판단하는 ML 모델을 적용해 기밀 유출 방지까지 실행합니다.')

# 사이드 바
st.sidebar.title("사이드 바 목록")
# st.sidebar.radio(
#     "라디오 버튼",
#     ['1', '2', '3']
# )
t1, t2 = st.sidebar.tabs(['1', '2'])
with t1:
    st.write("t1")
with t2:
    st.write("t2")


st.text("분석 할 파일을 선택해주세요.")

# 파일 업로드 기능
file = st.file_uploader("파일 업로드")


if file:
    stringio = io.StringIO(file.getvalue().decode("utf-8"))
    text_data = stringio.read()
    st.text(text_data)
else:
    st.warning("파일을 업로드 해주세요.")

