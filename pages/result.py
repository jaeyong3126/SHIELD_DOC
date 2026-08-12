import streamlit as st
import time

# def result_page():
st.set_page_config(layout="wide")
st.title("📊 파일 분석 리포트")

# 메인 페이지에서 넘어온 데이터가 있는지 확인
if "shared_result" in st.session_state and st.session_state.shared_result:
    message = st.empty()
    message.success("데이터를 성공적으로 불러왔습니다.")
    time.sleep(3)
    message.write("")
    st.write(st.session_state.shared_result)
    # st.write("분석 화면 테스트입니다")

    pii_tab, secret_tab, policy_tab, fianl_score_tab = st.tabs(['개인정보 탐지 결과', 'ML 기밀 판정 결과', '기업 정책 근거', '최종 결과'])

    # 개인정보 탐지 결과
    with pii_tab:
        pass

    # ML 기밀 판정 결과
    with secret_tab:
        pass

    # 기업 정책 근거
    with policy_tab:
        pass

    # 최종 결과
    with fianl_score_tab:
        pass
else:
    st.warning("먼저 메인 페이지에서 파일을 업로드하고 분석을 진행해 주세요.")
    
if st.button("메인화면으로 이동"):
    st.session_state.analysis_done = False
    st.switch_page("pages/main.py")

