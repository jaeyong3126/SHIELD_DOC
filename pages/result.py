# from pages.analyze import analyze_file
import streamlit as st
import time
import json

st.set_page_config(layout="wide")

st.markdown("""
    <style>
    .main-title { text-align: center; font-size: 2.6rem; font-weight: 800; margin-bottom: 0px; }
    .sub-title { text-align: center; color: #6c757d; font-size: 1.1rem; margin-bottom: 1.5rem; }
    </style>
""", unsafe_allow_html=True)


st.markdown("<h1 class='main-title'>📊 파일 분석 리포트</h1>", unsafe_allow_html=True)
# st.title("📊 파일 분석 리포트")

analyze_result_json = st.session_state.get("analysis_json")
analyze_result_name = st.session_state.get("analyze_result_name")

# 메인 페이지에서 넘어온 데이터가 있는지 확인
if analyze_result_name and analyze_result_json:
    message = st.empty()
    message.success("데이터를 성공적으로 불러왔습니다.")
    time.sleep(2)
    message.write("")

    with st.container(border=True):
        # 출력 내용 : "File Name" 파일의 분석 리포트입니다
        st.markdown(f"#### 분석한 파일 이름:  {analyze_result_name}")
        # 실제 결과 세션에서 가져와 data에 저장
        try:
            data = json.loads(analyze_result_json) if isinstance(analyze_result_json, str) else analyze_result_json
        except Exception:
            data = analyze_result_json


    with st.container(border=True):
        # 각 섹터 별로 탭으로 분리
        pii_tab, secret_tab, policy_tab, fianl_score_tab = st.tabs(['개인정보 탐지 결과', 'ML 기밀 판정 결과', '기업 정책 위반 유무', '최종 위험 점수'])

        # 개인정보 탐지 결과 탭
        with pii_tab:
            st.subheader("개인 정보 탐지 결과")
            st.write(data.get("filename", data))
            

        # ML 기밀 판정 결과 탭
        with secret_tab:
            st.subheader("기밀 정보 탐지 결과")
            st.write(data.get("status", data))

        # 기업 정책 근거 탭
        with policy_tab:
            st.subheader("기업 정책 위반 결과")
            st.write(data.get("metrics", data))

        # 최종 결과 탭
        with fianl_score_tab:
            st.subheader("최종 위험 점수")
            st.write(data.get("filename", data))

    with st.container(border=True):
        st.markdown("### 📋요약")
        st.markdown("임시 문자열입니다!------임시 문자열입니다!------임시 문자열입니다!------임시 문자열입니다!-----")
        st.write('---')

        # 요악 본
        # 개인정보 유무, 기밀정보 유무, 기업 정책 위반 유무, 최종 위험 분석 점수 등
        # st.markdown(f"#### \"{analyze_result_name}\" 파일은 외부 반출이 {accepct} 합니다.")


        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="파일명", value=analyze_result_name)
        with col2:
            is_allowed = True  

            # 전체를 감싸는 테두리 박스 생성
            with st.container(border=True):
                # 1. 메트릭의 라벨(제목) 표시
                st.caption("반출 여부")
                
                # 2. 조건에 따라 내부 내용과 스타일을 동적으로 변경
                if is_allowed:
                    # 반출 가능할 때: 초록색 글씨와 큰 텍스트
                    st.markdown(
                        "### <span style='color: #2ECC71;'>✅ 반출 가능</span>", 
                        unsafe_allow_html=True
                    )
                else:
                    # 반출 불가능할 때: 빨간색 글씨와 큰 텍스트
                    st.markdown(
                        "### <span style='color: #E74C3C;'>❌ 반출 불가</span>", 
                        unsafe_allow_html=True
                    )
            
            # accepct = ":green[가능]"
            # denied = ":red[불가능]"

            # st.metric(label="반출 여부") 
            # # value = 
            # #     # if 
            # with st.container(border=True): 
            #     st.markdown(f"✅ {accepct}")
            # #     # else
            # with st.container(border=True):
            #     st.markdown(f"❌ {denied}")

            

else:
    st.warning("먼저 분석 페이지에서 파일을 업로드하고 분석을 진행해 주세요.")
    if st.button("분석 페이지로 이동"):
        st.switch_page("pages/analyze.py")
    
if st.button("홈 페이지로 이동"):
    st.session_state.analysis_done = False
    st.session_state["analysis_json"] = None
    st.switch_page("pages/main.py")

