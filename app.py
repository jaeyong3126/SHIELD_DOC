import streamlit as st
import time

# 메인 화면, 분석 화면, 분석 결과 화면 분리
main_pg = st.Page("pages/main.py", title="홈")
analyze_pg = st.Page("pages/analyze.py", title="파일 분석")
result_pg = st.Page("pages/result.py", title="결과 보기")

pg = st.navigation([
    main_pg, 
    analyze_pg,
    result_pg
])

pg.run()



st.write("임시 테스트")