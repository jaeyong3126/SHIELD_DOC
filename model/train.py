# -*- coding: utf-8 -*-
"""SHIELD_DOC 기밀 문서 분류 — 학습 · 모델 비교 · 평가. (담당: 이서영)

    python model/train.py            # 학습 후 model/model.joblib 저장
    python model/train.py --compare  # 모델 비교표까지 출력 (선정 근거)

설정값은 이 파일 상단 CONFIG에 모여 있다. predict.py도 같은 값을 읽는다.
"""
import argparse
import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

# =============================================================
# CONFIG — 값이 바뀌면 여기만 고친다 (predict.py가 import해서 같은 값을 쓴다)
# =============================================================
ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'data' / 'processed' / 'dataset.csv'
MODEL_PATH = ROOT / 'model' / 'model.joblib'

TEXT_COLUMN = 'final_tokens'   # 앞 모듈(parser/pii)이 형태소 처리해 넘겨주는 컬럼

NGRAM_RANGE = (1, 2)
MIN_DF = 2
MAX_FEATURES = 20000
CALIBRATION_CV = 3             # LinearSVC엔 predict_proba가 없어 감싼다

# THRESHOLD: label(0/1)을 가르는 값. confidence 값 자체는 바꾸지 않는다.
#   0.30 = 기밀 유출 최소화 우선. edge holdout recall 0.848 (놓친 기밀 5건).
#   f1 최적은 0.5(recall 0.667)지만 DLP 특성상 recall을 우선한다.
THRESHOLD = 0.30

LABEL_NAMES = {0: 'NORMAL', 1: 'CONFIDENTIAL'}
EVIDENCE_TOP_K = 5
MODEL_VERSION_PREFIX = 'svc-tfidf'


# =============================================================
# 학습
# =============================================================
def build_vectorizer():
    return TfidfVectorizer(analyzer='word', ngram_range=NGRAM_RANGE,
                           min_df=MIN_DF, max_features=MAX_FEATURES)


def build_classifier():
    """LinearSVC + 확률 보정.
    confidence 필드가 필요하고 risk_engine이 0.8을 기준으로 점수를 나누므로
    캘리브레이션은 선택이 아니라 필수다."""
    return CalibratedClassifierCV(LinearSVC(class_weight='balanced', random_state=42),
                                  cv=CALIBRATION_CV)


def load_dataset(path=DATA_PATH):
    df = pd.read_csv(path, encoding='utf-8-sig')   # BOM 때문에 utf-8-sig
    if TEXT_COLUMN not in df.columns:
        raise KeyError(f"'{TEXT_COLUMN}' 컬럼이 없습니다. 있는 컬럼: {list(df.columns)}")
    # edge = 사람이 라벨링한 평가용 문서. 파일명 어디에나 'edge'가 올 수 있다.
    df['is_edge'] = df['filename'].str.contains('edge')
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


# =============================================================
# 모델 비교 (선정 근거) — python model/train.py --compare
#   학습 = non-edge, 평가 = edge holdout.
#   전체 정확도는 라벨-주제 상관 때문에 지표로 쓰지 않는다.
# =============================================================
def compare():
    import warnings
    from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
    from sklearn.linear_model import LogisticRegression, SGDClassifier
    from sklearn.naive_bayes import ComplementNB
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (classification_report, accuracy_score,
                                 recall_score, precision_score, f1_score)
    from sklearn.metrics.pairwise import cosine_similarity
    warnings.filterwarnings('ignore')
    pd.set_option('display.width', 200)

    df = load_dataset()
    tr, te = df[~df['is_edge']], df[df['is_edge']]
    print(f'학습 {len(tr)}건 / 평가 edge {len(te)}건 (기밀 {int(te.label.sum())}건)\n')

    models = {
        'LinearSVC':          lambda: CalibratedClassifierCV(LinearSVC(class_weight='balanced', random_state=42), cv=3),
        'SGD(hinge)':         lambda: CalibratedClassifierCV(SGDClassifier(loss='hinge', class_weight='balanced', random_state=42), cv=3),
        'ComplementNB':       lambda: ComplementNB(),
        'LogisticRegression': lambda: LogisticRegression(max_iter=1000, class_weight='balanced'),
        'RandomForest(500)':  lambda: RandomForestClassifier(n_estimators=500, class_weight='balanced', random_state=42, n_jobs=-1),
        'ExtraTrees(300)':    lambda: ExtraTreesClassifier(n_estimators=300, class_weight='balanced', random_state=42, n_jobs=-1),
    }

    def fit_prob(train_df, test_df, mk):
        tf = build_vectorizer()
        clf = mk()
        clf.fit(tf.fit_transform(train_df[TEXT_COLUMN]), train_df['label'])
        return clf.predict_proba(tf.transform(test_df[TEXT_COLUMN]))[:, 1]

    def sc(y, prob, th=0.5):
        p = (prob >= th).astype(int)
        return (recall_score(y, p, zero_division=0), precision_score(y, p, zero_division=0),
                f1_score(y, p, zero_division=0), accuracy_score(y, p))

    # (1) 모델별 성능
    print('=== 모델별 edge holdout 성능 (th=0.5) ===')
    rows = []
    for name, mk in models.items():
        r, p, f, a = sc(te['label'], fit_prob(tr, te, mk))
        rows.append((name, r, p, f, a))
    res = pd.DataFrame(rows, columns=['model', 'recall', 'prec', 'f1', 'acc']).sort_values('f1', ascending=False)
    print(res.to_string(index=False, float_format=lambda x: f'{x:.3f}'))

    # (2) 랜덤 split vs edge holdout — 평가 프로토콜 근거
    print('\n=== 랜덤 split vs edge holdout (평가 프로토콜 근거) ===')
    tr_r, te_r = train_test_split(df, test_size=0.2, random_state=42, stratify=df['label'])
    for name in ('LinearSVC', 'RandomForest(500)'):
        a = sc(te_r['label'], fit_prob(tr_r, te_r, models[name]))
        b = sc(te['label'], fit_prob(tr, te, models[name]))
        print(f'  {name:18s} 랜덤 acc={a[3]:.3f} recall={a[0]:.3f}  |  edge acc={b[3]:.3f} recall={b[0]:.3f}')

    # (3) 누수 검증 — edge가 학습셋과 독립인가
    print('\n=== edge 누수 검증 (코사인 유사도) ===')
    tf = TfidfVectorizer(min_df=1)
    sim = cosine_similarity(tf.fit(tr[TEXT_COLUMN]).transform(te[TEXT_COLUMN]),
                            tf.transform(tr[TEXT_COLUMN])).max(axis=1)
    print(f'  edge 최근접 유사도 중앙값 {np.median(sim):.3f} | 0.8이상 {int((sim>=0.8).sum())}건/{len(sim)}')

    # (4) 선정 조합 임계값 스윕
    print('\n=== 선정: LinearSVC / 1-2gram, 임계값 스윕 ===')
    prob = fit_prob(tr, te, models['LinearSVC'])
    for th in (0.3, 0.4, 0.5):
        r, p, f, a = sc(te['label'], prob, th)
        print(f'  th={th}: recall={r:.3f} prec={p:.3f} f1={f:.3f} acc={a:.3f}')
    print()
    print(classification_report(te['label'], (prob >= THRESHOLD).astype(int),
                                digits=3, target_names=['NORMAL', 'CONFIDENTIAL']))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--compare', action='store_true', help='모델 비교표 출력 (선정 근거)')
    args = ap.parse_args()
    if args.compare:
        compare()
    else:
        main()
