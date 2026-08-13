# -*- coding: utf-8 -*-
"""SHIELD_DOC ML 모듈 설정.

임계값이나 스키마 값이 바뀌면 이 파일만 고친다.
"""
from pathlib import Path

# model/config.py -> 프로젝트 루트
ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'data' / 'final_datasets.csv'
MODEL_PATH = ROOT / 'model' / 'artifacts' / 'model.joblib'

# ---- 입력 컬럼 ----
# 파이프라인이 형태소 처리된 텍스트를 넘겨준다는 전제.
# 학습과 추론이 같은 형태여야 하므로 여기서만 바꾼다.
TEXT_COLUMN = 'final_tokens'

# ---- 벡터화 / 모델 ----
NGRAM_RANGE = (1, 2)
MIN_DF = 2
MAX_FEATURES = 20000
CALIBRATION_CV = 3      # LinearSVC는 predict_proba가 없어 감싸야 한다

# ---- 판정 ----
# confidence는 P(기밀)로 반환한다 (predict.py 참고).
# risk_engine이 confidence >= 0.8 이면 60점, 미만이면 30점을 준다.
# BLOCK_THRESHOLD가 50이므로 0.8이 단독 차단 여부를 가르는 지점이다.
#
# THRESHOLD는 label(0/1)을 가르는 값이며 confidence 값 자체는 바꾸지 않는다.
# 0.30 = 기밀 유출 최소화 우선. edge holdout 기준 recall 0.848 (놓친 기밀 5건),
#        정상 오탐 27/87. f1 최적은 0.5(recall 0.667)지만 DLP 특성상 recall 우선.
THRESHOLD = 0.30

# ---- 스키마 (pipeline.py dummy_predict_confidential 기준) ----
LABEL_NAMES = {0: 'NORMAL', 1: 'CONFIDENTIAL'}
EVIDENCE_TOP_K = 5      # evidence로 반환할 상위 기여 토큰 수
MODEL_VERSION_PREFIX = 'svc-tfidf'
