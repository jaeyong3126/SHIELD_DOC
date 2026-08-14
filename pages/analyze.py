import json
import streamlit as st
from pipeline import run_pipeline

# 페이지 기본 설정
st.set_page_config(
    page_title="파일 분석 - SHIELD DOC", 
    page_icon="🔍", 
    layout="wide"
)

# 커스텀 CSS
st.markdown("""
    <style>
    .main-title { text-align: center; font-size: 2.4rem; font-weight: 800; color: #1E293B; margin-bottom: 0px; }
    .sub-title { text-align: center; color: #64748B; font-size: 1.05rem; margin-bottom: 2rem; }
    </style>
""", unsafe_allow_html=True)

# 세션 초기화 함수
def reset_analysis():
    st.session_state.analysis_done = False
    st.session_state["analysis_json"] = None

# 파일 분석 함수 (run_pipeline)
def analyze_file(uploaded_file):
    # pipeline.py의 run_pipeline 분석 모델 실행
    analysis_result = run_pipeline(uploaded_file)

    # 나온 결과는 세션에 "analysis_json" 로 저장
    st.session_state["analysis_json"] = json.dumps(analysis_result, indent=4, ensure_ascii=False)
    return analysis_result

# 세션에 분석 결과 기록 자체가 없으면 오류 발생하기 때문에 세션 초기화 함수 사용 (False 할당 및 데이터 초기화) 
if "analysis_done" not in st.session_state:
    reset_analysis()

# 1. 헤더 섹션
st.markdown("<h1 class='main-title'>🔍 파일 위험도 분석</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>문서 내 개인정보, 기밀사항 및 규정 위반 요소를 AI로 스캐닝합니다.</p>", unsafe_allow_html=True)

# 2. 파일 업로드 카드
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

# 3. 파일 업로드 후 대시보드 처리
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
        # 분석을 시작하지 않았을 때 if 문 실행
        if not st.session_state.analysis_done:
            if st.button("🚀 파일 분석 시작하기", type="primary", use_container_width=True):
                with st.spinner("모델이 문서를 분석 중입니다..."):
                    st.text("시간이 다소 소요될 수 있습니다. 페이지를 나가지 말고 잠시만 기다려 주세요.")
                    # 분석 
                    result = analyze_file(uploaded_file)
                st.session_state.analysis_done = True
                # 상태 갱신을 위해 새로고침
                st.rerun()
        # 분석이 끝나게 되면 "analysis_done" 이 세션에 할당되기 때문에 rerun()과 함께 else문으로 넘어가 실행된다.
        else:
            st.success("✅ 파일 분석이 완료되었습니다. 아래 버튼을 눌러 리포트를 확인하세요.")
            if st.button("📊 분석 결과 리포트 확인하기", type="primary", use_container_width=True):
                st.switch_page("pages/result.py")


