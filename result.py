import json
import streamlit as st
from pipeline import get_warnings  # 파이프라인 경고 메시지 함수

st.set_page_config(layout="wide", page_title="📊 파일 분석 리포트")

# CSS 스타일
st.markdown("""
    <style>
    .main-title { text-align: center; font-size: 2.6rem; font-weight: 800; margin-bottom: 0px; }
    .sub-title { text-align: center; color: #6c757d; font-size: 1.1rem; margin-bottom: 1.5rem; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='main-title'>📊 파일 분석 리포트</h1>", unsafe_allow_html=True)
st.write('---')

# 세션에 저장된 분석 결과 데이터 로드
analyze_result_json = st.session_state.get("analysis_json")

# 세션에 데이터가 있을 때
if analyze_result_json:
    try:
        # 문자열인 경우 JSON 파싱
        if isinstance(analyze_result_json, str):
            parsed = json.loads(analyze_result_json)
            # 딕셔너리 형태면 그대로, 아니면 빈 딕셔너리 반환
            data = parsed if isinstance(parsed, dict) else {}
        # 이미 딕셔너리인 경우 그대로 사용
        elif isinstance(analyze_result_json, dict):
            data = analyze_result_json
    # 파일 형식이 잘못 되었을 때
    except (json.JSONDecodeError, TypeError):
        data = {}

    # 파이프라인 분석 실패/에러 처리
    if not data or data.get("status") == "error":
        st.error(f"🚨 분석 도중 오류가 발생했습니다: {data.get('error', '알 수 없는 오류')}")
        if st.button("분석 페이지로 돌아가기"):
            st.switch_page("pages/analyze.py")
        st.stop()

    # 핵심 변수 추출
    filename = data.get("filename") or "알 수 없음"
    full_text = data.get("text") or ""
    doc_id = data.get("doc_id", "-")
    risk = data.get("risk", {})
    action = risk.get("action", "알 수 없음")
    score = risk.get("score", 0)
    reasons = risk.get("reasons", [])
    is_allowed = (action == "허용")

    # -------------------------------------------------------------------
    # [섹션 1] 문서 기본 정보 및 반출 여부 배너
    # -------------------------------------------------------------------
    with st.container(border=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader(f"📄 파일명: {filename}")
            st.caption(f"문서 식별 ID: {doc_id}")
        with col2:
            with st.container(border=True):
                st.caption("외부 반출 판정")
                if is_allowed:
                    st.markdown("<h3 style='color: #2ECC71; margin:0;'>✅ 반출 가능</h3>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<h3 style='color: #E74C3C; margin:0;'>❌ 반출 불가 ({action})</h3>", unsafe_allow_html=True)

    # 추출된 파일 전체 내용 ( 마스킹 젹용 ) 확인하기
    with st.expander("📄 추출된 전체 본문 확인하기 (클릭하여 열기/접기)", expanded=False):
        if full_text:
            # disabled=True로 설정하면 사용자가 수정할 수 없고 읽기/복사만 가능합니다.
            st.text_area("문서 전체 텍스트", value=full_text, height=350, disabled=True)
        else:
            st.info("문서에서 추출된 텍스트가 없거나 비어 있습니다.")
    # -------------------------------------------------------------------
    # [섹션 2] 상세 분석 결과 (4개 탭)
    # -------------------------------------------------------------------
    with st.container(border=True):
        st.markdown("### 상세 분석 결과")
        pii_tab, secret_tab, policy_tab, final_score_tab = st.tabs([
            '개인정보 탐지 결과', 
            'ML 기밀 판정 결과', 
            '기업 정책 위반 유무', 
            '최종 위험 점수'
        ])

        # 탭 1: 개인정보 탐지 (pii_found)
        with pii_tab:
            st.subheader("개인 정보 (PII) 탐지 결과")
            pii_list = data.get("pii_found", [])
            if pii_list:
                st.dataframe(pii_list, width="stretch")
            else:
                st.success("탐지된 개인정보가 없습니다.")

        # 탭 2: ML 및 Secret 탐지 (secret_found, ml)
        with secret_tab:
            st.subheader("기밀 정보 및 ML 판단 결과")
            sec_col, ml_col = st.columns(2)
            
            with sec_col:
                st.markdown("**🔑 탐지된 비밀번호 / API Key (Secret)**")
                sec_list = data.get("secret_found", [])
                if sec_list:
                    st.dataframe(sec_list, width="stretch")
                else:
                    st.info("탐지된 Secret 키가 없습니다.")
            
            with ml_col:
                st.markdown("**🤖 ML 기밀 문서 분류**")
                ml = data.get("ml", {}) or {}
                conf = float(ml.get("confidence", 0))

                # 확신도에 따라 3단계로 구분
                # 0.8은 risk_engine이 단독 차단 여부를 가르는 기준과 동일하다
                if ml.get("label") == 1 and conf >= 0.8:
                    st.markdown("<h4 style='color:#E74C3C; margin:0;'>기밀 문서</h4>", unsafe_allow_html=True)
                    st.caption(f"기밀 확률 {conf:.0%} · 기밀 정보 포함 가능성이 높습니다")
                elif ml.get("label") == 1:
                    st.markdown("<h4 style='color:#E67E22; margin:0;'>기밀 의심</h4>", unsafe_allow_html=True)
                    st.caption(f"기밀 확률 {conf:.0%} · 검토가 필요합니다")
                else:
                    st.markdown("<h4 style='color:#2ECC71; margin:0;'>일반 문서</h4>", unsafe_allow_html=True)
                    st.caption(f"기밀 확률 {conf:.0%}")

                evidence = ml.get("evidence") or []
                if evidence:
                    st.markdown("**판단 근거**")
                    top = max(float(e["weight"]) for e in evidence)
                    for e in evidence:
                        c1, c2 = st.columns([1, 2])
                        c1.markdown(f"`{e['term']}`")
                        c2.progress(float(e["weight"]) / top)
        # 탭 3: 기업 정책 위반 (policy)
        with policy_tab:
            st.subheader("기업 보안 정책 위반 결과")

            refs = (data.get("policy") or {}).get("refs") or []

            if refs:
                st.error(f"기업 정책 위반 {len(refs)}건 확인")
                st.write(refs)
            else:
                st.success("확인된 기업 정책 위반 없음")

        # 탭 4: 최종 위험 점수 및 사유 (risk)
        with final_score_tab:
            st.subheader("최종 위험 평가 점수")
            st.metric(label="위험 점수 (Risk Score)", value=f"{score} 점")
            
            if reasons:
                st.markdown("**📌 상세 판정 사유:**")
                for reason in reasons:
                    st.write(f"- {reason}")
    # -------------------------------------------------------------------
    # [섹션 3] AI 종합 요약 설명 (explanation)
    # -------------------------------------------------------------------
    with st.container(border=True):
        st.markdown("### 📋 AI 분석 종합 요약")
        explanation = data.get("explanation")
        if explanation:
            st.write(explanation)
        else:
            st.caption("생성된 요약 설명이 없습니다.")
    # -------------------------------------------------------------------
    # [섹션 4] 디버깅용 파이프라인 경고 로그
    # -------------------------------------------------------------------
    warnings = get_warnings()
    if warnings:
        with st.expander("⚠️ 시스템 실행 경고 (디버깅 전용)"):
            for w in warnings:
                st.caption(f"- {w}")

else:   # 세션에 분석 결과 데이터가 없을 때 
    st.warning("먼저 분석 페이지에서 파일을 업로드하고 분석을 진행해 주세요.")

# 버튼 공통 기능 : 분석했던 내용 및 세션 상태 초기화
def clear_session():
    st.session_state.analysis_done = False
    st.session_state["analysis_json"] = None

b_col1, b_col2 = st.columns(2)
# 새로 분석하기 버튼 
with b_col1:
    if st.button("🔄️ 새로 분석하기", use_container_width=True):
        clear_session()
        st.switch_page("pages/analyze.py")
# 홈 페이지 이동 버튼
with b_col2:
    if st.button("🏠 홈 페이지로 이동", use_container_width=True):
        clear_session()
        st.switch_page("pages/main.py")