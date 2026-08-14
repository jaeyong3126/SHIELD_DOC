# -*- coding: utf-8 -*-
"""SHIELD_DOC 기밀 문서 분류 — 모델 학습. (담당: 이서영)

    python model/train.py

data/processed/dataset.csv 를 읽어 model/model.joblib 을 생성한다.
설정값은 아래 CONFIG에 모여 있으며 predict.py도 같은 값을 사용한다.
"""
import datetime
from pathlib import Path

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

# =============================================================
# CONFIG — 값이 바뀌면 여기만 고친다 
# =============================================================
ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'data' / 'final_datasets_2.csv'
MODEL_PATH = ROOT / 'model' / 'model.joblib'

# 앞 모듈(parser/pii)이 형태소 처리해 넘겨주는 컬럼.
# 학습과 추론의 입력 형태가 같아야 하므로 한 곳에서만 정의한다.
TEXT_COLUMN = 'final_tokens'

NGRAM_RANGE = (1, 2)
MIN_DF = 2
MAX_FEATURES = 20000
CALIBRATION_CV = 3      # LinearSVC엔 predict_proba가 없어 감싼다

# label(0/1)을 가르는 값. confidence 값 자체는 바꾸지 않는다.
# 0.30 = 기밀 유출 최소화 우선. 문서 보안 특성상 미탐(유출)이
# 오탐(사람 검토)보다 비용이 크므로 recall을 우선한다.
THRESHOLD = 0.30

# 규칙 계층이 단독으로 기밀 판정할 때 부여하는 confidence.
# risk_engine의 _ML_CONFIDENT(0.8) 이상이어야 60점을 받는다.
RULE_CONFIDENCE = 0.85

LABEL_NAMES = {0: 'NORMAL', 1: 'CONFIDENTIAL'}
EVIDENCE_TOP_K = 5
MODEL_VERSION_PREFIX = 'svc-tfidf-rule'


# =============================================================
def build_vectorizer():
    return TfidfVectorizer(analyzer='word', ngram_range=NGRAM_RANGE,
                           min_df=MIN_DF, max_features=MAX_FEATURES)


def build_classifier():
    """LinearSVC + 확률 보정.
    confidence 필드가 필요하고 risk_engine이 0.8을 기준으로 점수를
    나누므로 캘리브레이션은 선택이 아니라 필수다."""
    return CalibratedClassifierCV(
        LinearSVC(class_weight='balanced', random_state=42),
        cv=CALIBRATION_CV)


def load_dataset(path=DATA_PATH):
    df = pd.read_csv(path, encoding='utf-8-sig')   # BOM 때문에 utf-8-sig
    if TEXT_COLUMN not in df.columns:
        # 파이프라인이 모듈 실패를 조용히 NORMAL로 처리하므로,
        # 학습 단계에서 입력 스키마를 명시적으로 검증한다.
        raise KeyError(f"'{TEXT_COLUMN}' 컬럼이 없습니다. 있는 컬럼: {list(df.columns)}")
    return df


def main():
    df = load_dataset()
    tfidf, clf = build_vectorizer(), build_classifier()
    clf.fit(tfidf.fit_transform(df[TEXT_COLUMN]), df['label'])

    version = f'{MODEL_VERSION_PREFIX}-{datetime.date.today():%y%m%d}'
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        'tfidf': tfidf,
        'clf': clf,
        'version': version,
        'text_column': TEXT_COLUMN,
        'n_train': len(df),
    }, MODEL_PATH)

    print(f'저장 완료: {MODEL_PATH}')
    print(f'  version={version}  n={len(df)}  입력컬럼={TEXT_COLUMN}')


if __name__ == '__main__':
    main()
