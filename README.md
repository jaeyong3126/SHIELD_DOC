# SHIELD_DOC
AI 기반 문서 정보 유출 위험 분석 및 외부 반출 보안 점검 서비스
SHIELD_DOC/
├── app.py                  ← 정은환 (Streamlit 메인 화면)
├── requirements.txt        ← 전원 (새 패키지 쓰면 본인이 추가)
├── .env                    ← 각자 로컬에만 (API 키, 커밋 금지·자동 차단됨)
├── .env.example            ← 최재용 (키 이름 껍데기만)
│
├── data/
│   ├── raw/                ← 최율호 (원본 1,050건 — git 제외, 드라이브가 원본)
│   └── processed/
│       └── dataset.csv     ← 최율호 (취합·정제 완료본)
│
├── model/
│   ├── train.py            ← 이서영 (학습·비교·평가 코드)
│   ├── predict.py          ← 이서영 (predict_confidential 함수)
│   ├── confidential_model.pkl  ← 이서영 (학습된 모델)
│   └── vectorizer.pkl      ← 이서영 (TF-IDF 변환기)
│
├── tools/
│   ├── parser.py           ← 한지웅 (문서 → 텍스트)
│   ├── pii_detector.py     ← 한지웅 (개인정보·Secret 탐지, 마스킹)
│   ├── filesearch.py       ← 윤경은 (File Search 연동)
│   ├── agent.py            ← 조정인 (커스텀 툴 등록, OpenAI 종합 분석)
│   └── risk_engine.py      ← 최재용 (위험도 판정)
│
├── pipeline.py             ← 최재용 (전체 흐름 연결) ※루트에 새로 생성
│
├── pages/                  ← 정은환 (화면 늘어나면 사용, 당분간 비워둠)
│
└── docs/
    ├── 정책/               ← 윤경은 (한빛반도체 반출 정책 PDF)
    └── (기획서, 회의록 등) ← 전원
