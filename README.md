# SHIELD_DOC
AI 기반 문서 정보 유출 위험 분석 및 외부 반출 보안 점검 서비스
```
SHIELD_DOC/
├── app.py                      ← 정은환 (Streamlit 메인 화면)
├── pipeline.py                 ← 최재용 (전체 흐름 연결) ※수정 금지
├── requirements.txt            ← 전원 (새 패키지 쓰면 본인이 추가)
├── .env                        ← 각자 로컬에만 (API 키, 커밋 금지)
├── .env.example                ← 최재용 (키 이름 껍데기만)
├── data/
│   ├── raw/                    ← 최율호 (원본 문서 — git 제외, 드라이브가 원본)
│   │   └── pii_only/           ← 개인정보 전용 문서 (학습 제외, 정규식 테스트용)
│   └── processed/
│       └── dataset.csv        ← 최율호 (취합·정제 완료본)
│
├── model/
│   ├── train.py                ← 이서영 (학습·비교·평가 코드)
│   ├── predict.py              ← 이서영 (모델 로드 + 예측)
│   └── model.joblib            ← 이서영 (학습된 모델)
│
├── tools/
│   ├── parser.py               ← 한지웅 (문서 → 텍스트)
│   ├── pii_detector.py         ← 한지웅 (개인정보·Secret Regex 탐지 + 마스킹)
│   ├── ner_detector.py         ← 한지웅 (개인정보 NER 모델 탐지)
│   ├── filesearch.py           ← 윤경은 (File Search 연동, 정책 조항 검색)
│   ├── agent.py                ← 조정인 (OpenAI 종합 설명 생성)
│   └── risk_engine.py          ← 최재용 (위험도 판정)
│
├── pages/                      ← 정은환 (화면 늘어나면 사용)
│
└── docs/
    ├── shield_doc_common/      ← 공통 JSON 스키마 (전원 필독)
    ├── 정책/                   ← 윤경은 (한빛반도체 반출 정책 PDF)
    └── (기획서, 회의록 등)     ← 전원
```
