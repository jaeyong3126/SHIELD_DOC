# SHIELD_DOC
**윤경은, 이서영, 정은환, 조정인, 최율호, 최재용, 한지웅**

SK 쉴더스 루키즈 1차 모듈 프로젝트

본 저장소는 AI 기반 문서 정보 유출 위험 분석 및 외부 반출 보안 점검 서비스의 공식 구현 저장소입니다.

---

## 프로젝트 개요

기업 내부 문서를 외부로 반출하는 과정에서 발생하는 정보 유출은 대부분 명시적인 대외비 문서가 아니라, 평범한 업무 문서에 기밀 정보가 섞여 있는 경우에서 발생한다. 회의실 예약 공지에 미공개 제품 성능 수치가 한 줄 포함되거나, 사내 안내 메일에 확정되지 않은 조직 개편 계획이 언급되는 식이다. 이러한 문서는 표면적으로 일상적인 내용이기 때문에 작성자와 검토자 모두 위험성을 인지하지 못한 채 외부로 전달되며, 기존의 키워드 기반 필터로는 탐지되지 않는다.

본 프로젝트는 이러한 문제를 해결하기 위해 문서 반출 전 보안 점검 시스템을 개발하였다. 사용자가 문서를 업로드하면 시스템은 텍스트를 추출하고 개인정보를 탐지·마스킹한 뒤, 기밀 패턴 탐지와 기계학습 기반 문서 분류를 병렬로 수행한다. 이후 사내 반출 정책 조항을 검색해 위험도를 종합 판정하고, 판단 근거를 자연어로 설명하여 사용자가 반출 여부를 스스로 검토할 수 있도록 지원한다.

본 시스템은 다음과 같은 네 가지 핵심 모듈로 구성된다.

- 문서 파싱 및 개인정보 탐지 모듈

- 기밀 문서 분류 모듈

- 정책 조항 검색 모듈

- 위험도 판정 및 설명 생성 모듈

이를 통해 의도하지 않은 정보 유출을 사전에 차단하고, 판단 근거를 함께 제시하여 실무자가 신뢰할 수 있는 보안 점검 환경을 제공하는 것을 목표로 한다.

#### 시스템 구조

<img width="2720" height="3120" alt="shield_doc_system_architecture_detailed" src="https://github.com/user-attachments/assets/747442d2-5c50-407e-8823-155a696bb0de" />

#### 실행 결과(여기다 테스트 영상 만드시면서 스크린샷 넣어주세요..)
- 초기 화면
- 문서 업로드 시
- 개인정보 탐지 결과 등등 볼 수 있는 ui는 다 넣어주세요

---

## 주요 기능

#### 문서 파싱 및 개인정보 탐지 모듈

#### 기밀 문서 분류 모듈

- TF-IDF + LinearSVC 기반 문서 기밀 확률 산출
- 비밀 유지 명시 표현(`대외 발표 전`, `외부 발설` 등) 탐지 규칙 계층 결합
- 판정 근거(evidence)와 신뢰도(confidence)를 함께 반환

- 문서 단위 벡터화만으로는 다음 유형을 탐지하지 못해 규칙 계층을 추가

  | 유형 | 예시 |
  | --- | --- |
  | 일상 문서 + 기밀 1문장 | 회의실 예약 공지에 미공개 성능 수치 포함 |
  | 기밀 형식 + 공개 내용 | 기술 사양서 형식이나 교육용 공개 데이터 |

**여기다 자신이 개발한 모듈 설명 개조식으로 한 2,3문장정도 적어주세요**

---

## 시스템 실행 방법

#### 개발 환경 및 패키지
- streamlit
- torchvision
- python-docx
- pypdf
- transformers==4.57.1
- torch
- scikit-learn==1.9.0
- pandas==3.0.5
- joblib==1.5.3
- openai
- python-dotenv

#### 실행

1. 저장소 복제
```bash
    git clone https://github.com/jaeyong3126/SHIELD_DOC.git
```
2. 프로젝트 폴더로 이동
```bash
    cd SHIELD_DOC
```
3. 가상환경 생성 및 활성화
```bash
    python -m venv .venv
    source .venv/Scripts/activate
```
4. 패키지 설치
```bash
    python -m pip install -r requirements.txt
```
5. `.env.example`을 참고해 `.env` 생성 후 API 키 입력

6. `app.py` 실행
```bash
    python -m streamlit run app.py
```

---

## 모델 학습 방법

본 시스템에서 직접 학습한 모델은 문서 기밀 분류용 LinearSVC 모델이다. 개인정보 탐지에 사용하는 NER 모델은 사전 학습 모델을 그대로 사용하며, 별도의 학습은 진행하지 않았다.

#### 학습 목표

문서 텍스트로부터 기밀 여부를 판별하고 판단 근거와 신뢰도를 파이프라인에 전달하는 것을 목표로 한다. 문서 보안 특성상 기밀 문서를 놓치는 미탐은 유출로 직결되는 반면 오탐은 사람의 추가 검토로 해결되므로, precision보다 recall을 우선한다.

#### 데이터셋

- 한빛반도체(가상 기업) 문서를 합성하여 구축
- 총 1,740건 (학습 1,590 / 평가 150)

| 구분 | 건수 |
| --- | --- |
| 학습 | 1,590 
| 평가(edge) | 150 (기밀 63 / 정상 87) |

- `edge`는 문서의 주제와 기밀 여부가 어긋나도록 설계된 검증셋
    1. 회의실 예약 공지이나 미공개 성능 수치 1줄 포함 → 기밀

    2. 기술 사양서 형식이나 교육용 공개 데이터 → 정상

#### 학습 환경 및 설정

- Python 3.12
- scikit-learn 1.9.0

| 항목 | 값 |
| --- | --- |
| 입력 | final_tokens (형태소 처리된 텍스트) |
| 벡터화 | TF-IDF word (1,2), min_df=2, max_features=20000 |
| 분류기 | LinearSVC (class_weight=balanced) |
| 확률 보정 | CalibratedClassifierCV (cv=3) |
| 판정 임계값 | 0.30 |

#### 학습 절차

1. 데이터셋을 `data/` 에 배치

2. 학습 실행

```bash
    python model/train.py
```

3. `model/model.joblib` 생성 확인


#### 학습 결과

edge holdout(150건, 기밀 63건) 기준 성능은 다음과 같다.

| 구성 | recall | precision | f1 |
| --- | --- | --- | --- |
| ML 단독 | 0.841 | 0.662 | 0.741 |
| ML + 규칙 계층 | 0.937 | 0.670 | 0.781 |

모델 선정 과정에서 LinearSVC, SGD, ComplementNB, LogisticRegression, RandomForest, ExtraTrees, MLP를 비교하였다. SGD는 성능이 유사하나 seed에 따라 f1이 0.56~0.67로 변동하여 재현성 확보를 위해 제외하였고, 트리 계열은 TF-IDF의 희소 고차원 특성상 학습셋을 암기하는 경향이 강해 edge에서 성능이 크게 저하되었다.

규칙 계층은 단독 recall이 0.127에 불과하여 ML을 대체하지 않으며, 문서 단위 벡터화가 놓치는 사각지대만 보완한다.

#### 산출물

- 학습 결과 모델: `model/model.joblib`
- 이 모델을 분류 모듈(`model/predict.py`)이 기밀 판별에 사용한다.

---

## 기술 스택

| 구분 | 사용 기술 |
| --- | --- |
| Language | Python |
| UI | Streamlit |
| Machine Learning | scikit-learn |
| Data Processing | pandas |
| Model Serialization | joblib |
| LLM | OpenAI API |
| Collaboration | Git, GitHub, Notion, Google Drive |

---

## 팀 구성

| 이름 | 담당 |
|---|---|
| 최재용 | 파이프라인 연결, 위험도 판정 엔진 |
| 한지웅 | 문서 파싱, 개인정보·기밀 패턴 탐지, 마스킹 |
| 이서영 | ML 기반 기밀 문서 분류 모델 |
| 윤경은 | 기업 반출 정책 제작, File Search |
| 조정인 | PII, ML, Risk Engine 종합 결과 연동, AI 종합 분석 |
| 정은환 | Streamlit UI |
| 최율호 | 데이터셋 수집·정제 |
