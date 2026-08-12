import streamlit as st
import time

# from pipeline import run_pipeline
# result = run_pipeline(uploaded_file)

# 파일이 바뀌거나 새로 업로드되면 분석 상태를 False로 리셋하는 함수
def reset_analysis():
    st.session_state.analysis_done = False

# 세션 저장
if "analysis_done" not in st.session_state:
    reset_analysis()

# 파일 업로드 기능
st.title("🔍 파일 분석하기")
st.write('---')
st.subheader("분석 할 파일을 업로드 해주세요.")

# 파일 처리 
try:
    uploaded_file = st.file_uploader(
        "가능한 파일 형식 : .TXT / .DOCX / .PDF", 
        type=["txt", "pdf", "docx"],
        on_change=reset_analysis
    )
except ValueError:
    st.error('파일이 정상적으로 처리 되지 않았습니다.')

    # 파일 내용 읽기 (필요시 사용)
    # string = uploaded_file.getvalue().decode("utf-8", errors='ignore')
    # st.text(string)

# 파일이 정상적으로 업로드 되면 분석 시작
if uploaded_file:
    if st.button("파일 분석 시작하기"):
        status_text = st.empty()
        # 4초간 분석 애니메이션 작동
        for i in range(12):
            dots = "." * (i % 4)
            status_text.markdown(f"**분석 중{dots}**")
            time.sleep(0.33)  # 약 0.3초마다 점이 바뀜

        status_text.write("")
        st.success("분석 완료. 분석 결과를 확인하시려면 버튼을 눌러주세요.")
        st.session_state.analysis_done = True

    if st.session_state.analysis_done:
        # 분석한 파일 이름과 내용을 결과 화면으로 이동 (아직 파일 내용 이동 미구현)

        # 파일 이름
        st.session_state.shared_result = f"\"{uploaded_file.name}\" 파일의 분석 리포트입니다."

        # 버튼 눌렀을 시 결과 화면 (result.py) 으로 이동
        if st.button("결과 페이지로 이동하기"):
            time.sleep(2) # 2초 대기
            # result.py 페이지로 이동
            st.switch_page("pages/result.py")