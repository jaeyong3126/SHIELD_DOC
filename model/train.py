# -*- coding: utf-8 -*-
"""모델 학습 및 아티팩트 저장.

    python model/train.py

산출물: model/artifacts/model.joblib
        (pickle 기반이므로 저장소에 커밋하지 않는다. .gitignore 확인)
"""
import datetime
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (CALIBRATION_CV, DATA_PATH, MAX_FEATURES, MIN_DF,
                    MODEL_PATH, MODEL_VERSION_PREFIX, NGRAM_RANGE, TEXT_COLUMN)


def build_vectorizer():
    return TfidfVectorizer(analyzer='word', ngram_range=NGRAM_RANGE,
                           min_df=MIN_DF, max_features=MAX_FEATURES)


def build_classifier():
    """LinearSVC는 predict_proba가 없다.
    confidence 필드가 필요하고, risk_engine이 0.8을 기준으로 점수를
    나누므로 확률 캘리브레이션은 선택이 아니라 필수다."""
    return CalibratedClassifierCV(LinearSVC(class_weight='balanced'),
                                  cv=CALIBRATION_CV)


def load_dataset(path=DATA_PATH):
    df = pd.read_csv(path, encoding='utf-8-sig')   # BOM 때문에 utf-8-sig
    if TEXT_COLUMN not in df.columns:
        raise KeyError(f"'{TEXT_COLUMN}' 컬럼이 없습니다. 있는 컬럼: {list(df.columns)}")
    # edge는 파일명 어디에나 올 수 있다 (prefix로 세면 77건, 실제 117건)
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
        'text_column': TEXT_COLUMN,   # 추론 시 입력 형태 검증용
        'n_train': len(df),
    }, MODEL_PATH)

    print(f'저장 완료: {MODEL_PATH}')
    print(f'  version={version}  n={len(df)}  입력컬럼={TEXT_COLUMN}')


if __name__ == '__main__':
    main()
