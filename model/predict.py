"""
SHIELD_DOC - 기밀문서 분류
담당: 이서영
"""

import re
from pathlib import Path

import joblib

LABEL_NAMES = {0: "NORMAL", 1: "CONFIDENTIAL"}
_MODEL_PATH = Path(__file__).resolve().parent / "artifacts" / "model.joblib"

_state = {"loaded": False, "tfidf": None, "clf": None, "version": ""}


def normalize(t):
    """학습 때와 동일한 전처리 (반드시 train 쪽과 같게 유지)"""
    t = re.sub(r'20\d{2}\s*년?', ' ', t)
    t = re.sub(r'\d+\s*[월일]', ' ', t)
    t = re.sub(r'[\$￦]?\s?\d[\d,]*\s*(원|만원|억원|달러)', ' ', t)
    t = re.sub(r'\d+\s*%p?', ' ', t)
    t = re.sub(r'\d[\d,.]*', ' ', t)
    return re.sub(r'\s+', ' ', t)


def _load_once():
    if _state["loaded"]:
        return
    _state["loaded"] = True
    if not _MODEL_PATH.exists():
        return
    try:
        b = joblib.load(_MODEL_PATH)
        _state["tfidf"] = b["tfidf"]
        _state["clf"] = b["clf"]
        _state["version"] = b.get("version", "lr-tfidf")
    except Exception as e:
        print(f"[predict] 모델 로드 실패: {e}")


def _evidence(vec, top_k=5):
    names = _state["tfidf"].get_feature_names_out()
    coefs = _state["clf"].coef_[0]
    out = []
    for i in vec.nonzero()[1]:
        w = float(vec[0, i]) * float(coefs[i])
        if w > 0:
            out.append((names[i], w))
    out.sort(key=lambda x: -x[1])
    return [{"term": t, "weight": round(w, 3)} for t, w in out[:top_k]]


def predict_confidential(text):
    """
    입력: text (str) - 마스킹된 본문
    출력: label / label_name / confidence / evidence / model_version
    """
    if not text or not text.strip():
        return {"label": 0, "label_name": "NORMAL", "confidence": 0.0,
                "evidence": [], "model_version": _state["version"]}

    _load_once()

    if _state["clf"] is None:
        return {"label": 0, "label_name": "NORMAL", "confidence": 0.0,
                "evidence": [], "model_version": "not-trained"}

    vec = _state["tfidf"].transform([normalize(text)])
    proba = _state["clf"].predict_proba(vec)[0]
    label = int(proba.argmax())

    return {
        "label": label,
        "label_name": LABEL_NAMES[label],
        "confidence": round(float(proba[label]), 4),
        "evidence": _evidence(vec),
        "model_version": _state["version"],
    }
