"""
SHIELD_DOC - 기밀문서 분류
담당: 이서영
"""
 
LABEL_NAMES = {0: "NORMAL", 1: "CONFIDENTIAL"}
 
 
def predict_confidential(text):
    """
    입력: text (str)
    출력: dict
        label         int    0=NORMAL / 1=CONFIDENTIAL
        confidence    float  0~1
        label_name    str
        evidence      list   (선택)
        model_version str    (선택)
    """
    label = 0
    confidence = 0.0
 
    # TODO: 여기에 모델 예측
 
    return {
        "label": int(label),
        "label_name": LABEL_NAMES[int(label)],
        "confidence": float(confidence),
        "evidence": [],
        "model_version": "",
    }