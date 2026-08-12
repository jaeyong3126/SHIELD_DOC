import streamlit as st
import time
# from pipeline import run_pipeline

# result = run_pipeline(uploaded_file)

# 메인 화면과 분석 결과 화면 분리
main_pg = st.Page("pages/main.py", title="Home")
analyze_pg = st.Page("pages/analyze.py", title="Start Analyze")
result_pg = st.Page("pages/result.py", title="View Result")

pg = st.navigation([
    main_pg, 
    analyze_pg,
    result_pg
])

pg.run()

# 사이드 바
# st.sidebar.title("사이드 바 목록")
# uploaded_file = st.sidebar.file_uploader("파일 업로드")

# if uploaded_file:
#     stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
#     text_data = stringio.read()
#     st.sidebar.text(text_data)
# else:
#     st.sidebar.warning("파일을 업로드 해주세요.")

# st.sidebar.radio(
#     "라디오 버튼",
#     ['1', '2', '3']
# )
# t1, t2 = st.sidebar.tabs(['1', '2'])
# with t1:
#     st.write("t1")
# with t2:
#     st.write("t2")


