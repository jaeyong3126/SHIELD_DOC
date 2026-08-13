# import streamlit as st
# import time
# # import threading
# import json




# # 파일이 바뀌거나 새로 업로드되면 분석 상태를 False로 리셋하는 함수
# def reset_analysis():
#     st.session_state.analysis_done = False

# # 파일 분석 함수 
# def analyze_file(uploaded_file):
#     # 실제 파일 분석 모델 로직
#     # result = run_pipeline(uploaded_file)
#     analysis_result = {
#         "filename": uploaded_file.name,
#         "status": "success",
#         "metrics": {"lines": 150, "errors": 0}
#     }
#     # streamlit 세션에 분석된 결과 (예시: 딕셔너리)를 JSON으로 저장
#     st.session_state["analysis_json"] = json.dumps(analysis_result, indent=4, ensure_ascii=False)
#     # 딕셔너리 형태의 반환 예상 
#     return analysis_result

# st.markdown("""
#     <style>
#     .main-title { text-align: center; font-size: 2.6rem; font-weight: 800; margin-bottom: 0px; }
#     .sub-title { text-align: center; color: #6c757d; font-size: 1.1rem; margin-bottom: 1.5rem; }
#     </style>
# """, unsafe_allow_html=True)


# # 세션 저장
# if "analysis_done" not in st.session_state:
#     reset_analysis()

# # 파일 업로드 기능
# # st.title("🔍 파일 분석하기")
# st.markdown("<h1 class='main-title'>🔍 파일 분석하기</h1>", unsafe_allow_html=True)
# st.write('---')
# st.subheader("분석 할 파일을 업로드 해주세요.")

# # 파일 처리 
# try:
#     uploaded_file = st.file_uploader(
#         "가능한 파일 형식 : .TXT / .DOCX / .PDF", 
#         type=["txt", "pdf", "docx"],
#         on_change=reset_analysis
#     )
# except ValueError:
#     st.error('파일이 정상적으로 처리 되지 않았습니다.')

# # 파일이 정상적으로 업로드 되면 분석 시작
# if uploaded_file:
#     if st.button("파일 분석 시작하기"):
#         with st.spinner("분석 중..."):
#             time.sleep(6)
#             result = analyze_file(uploaded_file)
        
#         st.success("분석 완료. 분석 결과를 확인하시려면 버튼을 눌러주세요.")
#         st.session_state.analysis_done = True

#     if st.session_state.analysis_done:
#         # 분석한 파일 이름과 내용을 결과 화면으로 이동 (아직 파일 내용 이동 미구현)

#         # 파일 이름
#         st.session_state.analyze_result_name = f"분석한 파일 명: \"{uploaded_file.name}\""

#         # 버튼 눌렀을 시 결과 화면 (result.py) 으로 이동
#         if st.button("결과 페이지로 이동하기"):
#             time.sleep(2) # 2초 대기
#             # result.py 페이지로 이동
#             st.switch_page("pages/result.py")




import json
import time
import streamlit as st
from pipeline import run_pipeline

# 페이지 기본 설정
st.set_page_config(
    page_title="파일 분석 - SHIELD DOC", 
    page_icon="🔍", 
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main-title { text-align: center; font-size: 2.4rem; font-weight: 800; color: #1E293B; margin-bottom: 0px; }
    .sub-title { text-align: center; color: #64748B; font-size: 1.05rem; margin-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

# 1. 세션 상태 및 함수 정의
def reset_analysis():
    st.session_state.analysis_done = False

def analyze_file(uploaded_file):
    # pipeline.py 분석 모델 적용
    # analysis_result = run_pipeline(uploaded_file)

    # 기능 테스트 용 더미 데이터
    analysis_result = {
        "filename": uploaded_file.name,
        "status": "success",
        "metrics": {"lines": 150, "errors": 0}
    }
    st.session_state["analysis_json"] = json.dumps(analysis_result, indent=4, ensure_ascii=False)
    return analysis_result

if "analysis_done" not in st.session_state:
    reset_analysis()

# 2. 헤더 섹션
st.markdown("<h1 class='main-title'>🔍 파일 위험도 분석</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>문서 내 개인정보, 기밀사항 및 규정 위반 요소를 AI로 스캐닝합니다.</p>", unsafe_allow_html=True)

# 3. 파일 업로드 카드
with st.container(border=True):
    st.subheader("📁 분석할 파일 업로드")
    st.caption("지원 확장자: TXT, DOCX, PDF")
    
    try:
        uploaded_file = st.file_uploader(
            "문서 업로드", 
            type=["txt", "pdf", "docx"],
            on_change=reset_analysis,
            label_visibility="collapsed"
        )
    except ValueError:
        st.error('파일이 정상적으로 처리되지 않았습니다.')

# 4. 파일 업로드 후 대시보드 처리
if uploaded_file:
    st.write("")
    
    # 업로드된 파일 정보 메트릭 카드
    with st.container(border=True):
        st.markdown("### 📄 선택된 파일 정보")
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.metric(label="파일명", value=uploaded_file.name)
        with m_col2:
            file_size_kb = uploaded_file.size / 1024
            st.metric(label="파일 크기", value=f"{file_size_kb:.1f} KB")

        st.divider()

        # 분석 진행 상태별 버튼 제어
        if not st.session_state.analysis_done:
            if st.button("🚀 파일 분석 시작하기", type="primary", use_container_width=True):
                with st.spinner("모델이 문서를 분석 중입니다..."):
                    time.sleep(6)
                    result = analyze_file(uploaded_file)
                st.session_state.analysis_done = True
                st.rerun()

        else:
            st.success("✅ 파일 분석이 완료되었습니다. 아래 버튼을 눌러 리포트를 확인하세요.")
            # st.session_state.analyze_result_name = f"분석한 파일 명: \"{uploaded_file.name}\""
            st.session_state.analyze_result_name = uploaded_file.name
            
            if st.button("📊 분석 결과 리포트 확인하기", type="primary", use_container_width=True):
                st.switch_page("pages/result.py")


