# -*- coding: utf-8 -*-
"""SHIELD_DOC 기밀 문서 분류 — 모델 로드 + 예측. (담당: 이서영)

파이프라인 계약 (pipeline.py / shield_doc_common):
    predict_confidential(text) -> {
        "label": 0 | 1,
        "label_name": "NORMAL" | "CONFIDENTIAL",
        "confidence": 0.0 ~ 1.0,          # P(기밀)
        "evidence": [{"term": str, "weight": float}, ...],
        "model_version": str,
    }

설정값(MODEL_PATH, THRESHOLD 등)은 train.py에서 그대로 가져온다.
학습과 추론이 같은 값을 쓰도록 한 곳(train.py)에서만 정의한다.
"""
import re
import sys
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import (MODEL_PATH, THRESHOLD, LABEL_NAMES, EVIDENCE_TOP_K,
                   RULE_CONFIDENCE)

_ARTIFACT = None

# =============================================================
# 규칙 계층
#   문서 단위 TF-IDF는 "평범한 문서 + 기밀 한 문장" 유형을 놓친다.
#   (본문의 95%가 일상 어휘라 기밀 문장이 희석됨)
#   아래는 작성자가 직접 비밀임을 명시한 표현만 잡는다. 기술 어휘가
#   아니라 메타 신호이므로 정상 문서에 나올 가능성이 낮다.
#   edge holdout 기준 기밀 6건 추가 탐지, 오탐 2건 (recall 0.841 -> 0.937).
# =============================================================
CONFIDENTIAL_MARKERS = [
    r'대외\s*(발표|공시)\s*전',
    r'외부\s*(발설|유출|언급)',
    r'언급\s*(삼가|마시)',
    r'보안\s*주의',
    r'취급\s*주의',
    r'이사회\s*통과\s*전',
    r'확정\s*전',
    r'대외\s*언급',
]
_MARKER_RE = re.compile('|'.join(CONFIDENTIAL_MARKERS))


def _load():
    """아티팩트를 한 번만 읽고 재사용."""
    global _ARTIFACT
    if _ARTIFACT is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f'모델 파일이 없습니다: {MODEL_PATH}\n'
                f'먼저 `python model/train.py`를 실행하세요.')
        _ARTIFACT = joblib.load(MODEL_PATH)
    return _ARTIFACT


def _empty(version):
    return {'label': 0, 'label_name': LABEL_NAMES[0], 'confidence': 0.0,
            'evidence': [], 'model_version': version}


def _find_markers(text):
    """비밀 유지 지시 표현을 찾아 evidence 형태로 반환.
    weight 1.0은 '규칙이 확정한 근거'라는 뜻 (ML 기여도와 구분된다)."""
    seen, out = set(), []
    for m in _MARKER_RE.finditer(text):
        term = m.group(0).strip()
        if term not in seen:
            seen.add(term)
            out.append({'term': term, 'weight': 1.0})
    return out


def _extract_evidence(tfidf, clf, vec, top_k=EVIDENCE_TOP_K):
    """기밀 판정에 기여한 토큰. 기여도 = TF-IDF값 x 분류기 계수.
    CalibratedClassifierCV는 내부에 여러 추정기를 갖고 있어 계수를 평균한다."""
    coefs = []
    for cc in getattr(clf, 'calibrated_classifiers_', []):
        est = getattr(cc, 'estimator', None)
        if est is not None and hasattr(est, 'coef_'):
            coefs.append(est.coef_[0])
    if not coefs:
        return []

    coef = np.mean(coefs, axis=0)
    names = tfidf.get_feature_names_out()
    contrib = vec.toarray()[0] * coef
    idx = np.argsort(contrib)[::-1][:top_k]
    return [{'term': str(names[i]), 'weight': round(float(contrib[i]), 4)}
            for i in idx if contrib[i] > 0]


def predict_confidential(text):
    """문서 텍스트(final_tokens 형태)를 받아 기밀 여부를 판정한다.
    어떤 경우에도 예외를 던지지 않는다 (모델 부재 제외)."""
    art = _load()
    version = art['version']

    if not isinstance(text, str) or not text.strip():
        return _empty(version)

    vec = art['tfidf'].transform([text])
    if vec.nnz == 0:      # 어휘가 하나도 안 맞음 → 근거 없음 (전처리 불일치 가능)
        return _empty(version)

    prob = float(art['clf'].predict_proba(vec)[0, 1])
    label = int(prob >= THRESHOLD)

    # confidence = P(기밀). risk_engine의 0.8 컷과 연동되도록 확률을 그대로 쓴다.
    # 정상 문서는 자연히 낮은 값을 갖는다.
    confidence = prob
    markers = _find_markers(text)

    if markers and label == 0:
        # ML이 놓친 경우에만 규칙이 승격시킨다 (ML 판정은 덮지 않는다).
        # 근거가 명시적이므로 confidence를 RULE_CONFIDENCE로 올려
        # risk_engine이 충분한 가중치를 주도록 한다.
        label = 1
        confidence = max(prob, RULE_CONFIDENCE)

    if label == 1:
        # 규칙이 잡은 문구를 앞에 둔다 (사람이 읽을 수 있는 근거).
        evidence = markers + _extract_evidence(art['tfidf'], art['clf'], vec)
        evidence = evidence[:EVIDENCE_TOP_K]
    else:
        evidence = []

    return {
        'label': label,
        'label_name': LABEL_NAMES[label],
        'confidence': round(confidence, 4),
        'evidence': evidence,
        'model_version': version,
    }
