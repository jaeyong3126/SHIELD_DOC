# -*- coding: utf-8 -*-
"""SHIELD_DOC 문서 기밀 등급 분류 모듈. (담당: 이서영)

파이프라인 계약 (pipeline.py / shield_doc_common.json v2):
    predict_confidential(text) -> {
        "label": 0 | 1,
        "label_name": "NORMAL" | "CONFIDENTIAL",
        "confidence": 0.0 ~ 1.0,
        "evidence": [{"term": str, "weight": float}, ...],
        "model_version": str,
    }

주의: 모델은 학습 때 본 형태의 텍스트만 이해한다.
      TEXT_COLUMN(config.py)과 같은 전처리 상태로 들어와야 한다.
"""
import sys
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (EVIDENCE_TOP_K, LABEL_NAMES, MODEL_PATH, THRESHOLD)

_ARTIFACT = None


def _load():
    """아티팩트를 한 번만 읽고 재사용 (문서마다 로드하면 느리다)."""
    global _ARTIFACT
    if _ARTIFACT is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f'모델 파일이 없습니다: {MODEL_PATH}\n'
                f'먼저 `python model/train.py`를 실행하세요.')
        _ARTIFACT = joblib.load(MODEL_PATH)
    return _ARTIFACT


def _empty_result(version, reason=''):
    return {
        'label': 0,
        'label_name': LABEL_NAMES[0],
        'confidence': 0.0,
        'evidence': [],
        'model_version': version,
    }


def _extract_evidence(tfidf, clf, vec, top_k=EVIDENCE_TOP_K):
    """기밀 판정에 기여한 토큰을 뽑는다.

    기여도 = (문서의 TF-IDF 값) x (분류기 계수)
    CalibratedClassifierCV는 내부에 여러 개의 보정된 추정기를 갖고 있어
    각 추정기의 계수를 평균해 사용한다.
    """
    coefs = []
    for cc in getattr(clf, 'calibrated_classifiers_', []):
        est = getattr(cc, 'estimator', None)
        if est is not None and hasattr(est, 'coef_'):
            coefs.append(est.coef_[0])
    if not coefs:
        return []

    coef = np.mean(coefs, axis=0)
    names = tfidf.get_feature_names_out()

    row = vec.toarray()[0]
    contrib = row * coef                      # 문서에 실제로 등장한 토큰만 0이 아님
    idx = np.argsort(contrib)[::-1][:top_k]

    return [{'term': str(names[i]), 'weight': round(float(contrib[i]), 4)}
            for i in idx if contrib[i] > 0]


def predict_confidential(text):
    """문서 텍스트를 받아 기밀 여부를 판정한다.

    입력: str (config.TEXT_COLUMN과 같은 전처리 상태)
    출력: 위 계약의 dict. 어떤 경우에도 예외를 던지지 않는다.
    """
    try:
        art = _load()
    except FileNotFoundError:
        raise      # 모델 부재는 조용히 넘기면 안 된다 (파이프라인이 경고로 잡아줌)

    version = art['version']

    if not isinstance(text, str) or not text.strip():
        return _empty_result(version)

    vec = art['tfidf'].transform([text])

    # 어휘가 하나도 안 맞으면 판정 근거가 없다.
    # 학습/추론 전처리 불일치일 가능성이 높으므로 NORMAL로 단정하지 않는다.
    if vec.nnz == 0:
        return _empty_result(version)

    prob = float(art['clf'].predict_proba(vec)[0, 1])
    label = int(prob >= THRESHOLD)

    # confidence = P(기밀). risk_engine이 confidence>=0.8이면 60점을 주므로,
    # "예측 클래스 확신도(0.5~1)"가 아니라 "기밀일 확률(0~1)"이어야 한다.
    # 그래야 임계값을 낮춰도 (낮은 확률로 label=1이 되어도) 차단 강도가
    # 확률에 비례한다. 정상 문서는 자연히 낮은 confidence를 갖는다.
    return {
        'label': label,
        'label_name': LABEL_NAMES[label],
        'confidence': round(prob, 4),
        'evidence': _extract_evidence(art['tfidf'], art['clf'], vec) if label == 1 else [],
        'model_version': version,
    }
