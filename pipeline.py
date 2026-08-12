"""
SHIELD_DOC - 전체 파이프라인 (뼈대) v2
담당: 최재용
기준 스키마: shield_doc_common.json (v2)

[팀원 안내]
- 이 파일은 건드리지 마세요. 여러분은 tools/ 와 model/ 안의 자기 파일만 만들면 됩니다.
- 아직 아무도 안 만들었어도 이 파일은 그냥 돌아갑니다 (더미가 대신 답합니다).
- 자기 모듈을 푸시하면 다음 실행부터 자동으로 진짜 함수가 쓰입니다.
- 진짜/더미 중 뭐가 쓰이는지는 실행하면 화면 맨 위에 표로 나옵니다.

[내가 만들 함수 찾는 법]
  실행 → 상태표에서 자기 이름 찾기 → 이 파일에서 dummy_함수이름 검색
  → 그 반환값이 곧 입출력 정답지입니다. 키 이름을 똑같이 맞춰주세요.

실행:  python pipeline.py            (샘플로 한 바퀴)
       python pipeline.py 파일경로   (실제 파일로 한 바퀴)
       python pipeline.py 파일1 파일2 ...   (여러 건 = batch)
"""

import copy
import json
from datetime import datetime

# 판정 경계 - 오후에 실제 점수 분포 보고 조정 (최재용)
BLOCK_THRESHOLD = 50


# =============================================================
# 1) 자동 교체 - 진짜 모듈이 있으면 쓰고, 없으면 더미를 씁니다
# =============================================================

STATUS = {}


def _load(module_path, func_name, owner):
    try:
        mod = __import__(module_path, fromlist=[func_name])
    except ModuleNotFoundError as e:
        # 모듈 파일 자체가 없음 = 아직 안 만든 것
        if getattr(e, "name", None) in (module_path, module_path.split(".")[0]):
            STATUS[func_name] = f"dummy ({owner} 대기중)"
        else:
            # 파일은 있는데 그 안에서 import가 실패 (라이브러리 미설치) - 반드시 알려야 함
            STATUS[func_name] = f"ERROR ({owner}) 라이브러리 없음: {e.name} → pip install {e.name}"
        return None
    except KeyboardInterrupt:
        raise
    except BaseException as e:
        # 파일은 있는데 안 읽힘 (문법 오류, sys.exit 등) - 이유를 보여줘야 함
        STATUS[func_name] = f"ERROR ({owner}) {type(e).__name__}: {e}"
        return None

    fn = getattr(mod, func_name, None)
    if fn is None:
        STATUS[func_name] = f"ERROR ({owner}) {module_path}.py 안에 {func_name} 함수가 없습니다"
        return None

    STATUS[func_name] = f"REAL  ({owner})"
    return fn


_parse_document       = _load("tools.parser",       "parse_document",       "한지웅")
_detect_pii           = _load("tools.pii_detector", "detect_pii",           "한지웅")
_detect_secret        = _load("tools.pii_detector", "detect_secret",        "한지웅")
_predict_confidential = _load("model.predict",      "predict_confidential", "이서영")
_search_policy        = _load("tools.filesearch",   "search_policy",        "윤경은")
_risk_engine          = _load("tools.risk_engine",  "risk_engine",          "최재용")
_analyze_final        = _load("tools.agent",        "analyze_final",        "조정인")

# 판정 경계는 tools/risk_engine.py 의 값을 따른다 (두 곳이 어긋나면 판정이 뒤집힘)
if _risk_engine is not None:
    try:
        from tools.risk_engine import BLOCK_THRESHOLD as _엔진경계
        BLOCK_THRESHOLD = _엔진경계
    except Exception:
        pass


# =============================================================
# 2) 더미 구현 = 입출력 정답지
#    ※ 반환값의 키 이름을 그대로 맞춰주세요. (shield_doc_common.json 기준)
#    ※ 결과 없으면 빈 배열 []. None 금지 (None은 파싱 실패일 때만)
# =============================================================

def dummy_parse_document(file):
    """
    입력: 파일경로(str) 또는 Streamlit 업로드 파일객체

    출력: 아래 둘 중 편한 쪽으로 하세요. 둘 다 받습니다.
      (A) {"filename": "hr_001.txt", "text": "본문..."}   ← 권장
      (B) "본문..."  (문자열만)  ← 파일명은 파이프라인이 알아서 뽑습니다

    실패 시: 예외를 그냥 raise 하세요. 파이프라인이 status="error"로 처리합니다.
    """
    return {
        "filename": "notice_kjm_156.txt",
        "text": "[사내 공지] 11월 둘째 주 방문객 주차 구획 운영 안내 ... (더미 본문)",
    }


def dummy_detect_pii(text):
    """
    입력: 원문
    출력: {"pii_found": list[dict], "masked_text": str}
          - pii_found : type / count / risk_level / masked
              risk_level = "HIGH" : 주민번호, 개인휴대폰, 계좌번호, 자택주소 등
              risk_level = "LOW"  : 업무이메일, 내선번호, 부서, 직급 등
              ※ HIGH는 1건만 나와도 즉시 차단됩니다
          - masked_text : 개인정보를 가린 본문
    마스킹을 아직 안 만들었으면 목록만 반환해도 됩니다
          (그땐 탐지·판정은 정상 동작하고, 화면에 뜨는 본문만 비공개 처리됩니다).
    """
    return {
        "pii_found": [
            {"type": "개인휴대폰", "count": 1, "risk_level": "HIGH", "masked": True},
            {"type": "업무이메일", "count": 1, "risk_level": "LOW", "masked": True},
        ],
        "masked_text": "담당자 연락처는 010-****-5678입니다. (더미 마스킹본)",
    }


def dummy_detect_secret(text):
    """
    입력: detect_pii가 가린 본문 (원문 아님)
    출력: {"secret_found": list[dict], "masked_text": str}
          - type은 api_key / password / 내부IP
          - risk_level: api_key·password = "HIGH", 내부IP = "LOW"
    자기가 받은 텍스트에서 Secret만 추가로 가려서 돌려주면 됩니다.
    """
    return {
        "secret_found": [{"type": "내부IP", "count": 1, "risk_level": "LOW", "masked": False}],
        "masked_text": text,
    }


def dummy_predict_confidential(text):
    """
    출력: label 0=NORMAL / 1=CONFIDENTIAL
          confidence 0~1 소수
          evidence, model_version 은 선택 (못 채우면 [] 와 "")
    """
    return {
        "label": 1,
        "label_name": "CONFIDENTIAL",
        "confidence": 0.87,
        "evidence": [
            {"term": "실사팀", "weight": 0.42},
            {"term": "임원단", "weight": 0.28},
        ],
        "model_version": "lr-tfidf-v1",
    }


def dummy_search_policy(text):
    """출력: {"refs": [...]} — 위반 없으면 refs: []"""
    return {
        "refs": [
            {
                "title": "사내 정보보호 지침 제12조 (미공개 경영정보)",
                "snippet": "인수합병, 신규 투자 등 공시 전 경영 사항은 사외 반출을 금지한다.",
                "source": "사내정보보호지침_v3.pdf",
            }
        ]
    }


def dummy_analyze_final(doc):
    """
    입력: 지금까지 채워진 결과 dict 전체 (text, pii_found, ml, policy, risk 포함)
    출력: 문자열 하나 (설명문)
    """
    return "더미 설명입니다. 조정인님 모듈이 연결되면 실제 분석 문장이 들어갑니다."


# =============================================================
# 2-B) 안전장치 - 모듈 출력이 형식에서 벗어나도 앱이 죽지 않게 보정
#      ※ 보정이 일어나면 경고를 찍습니다. 경고 뜨면 해당 담당자가 고쳐야 합니다.
# =============================================================

WARNINGS = []

_실패 = object()      # 모듈 실행이 죽었음을 나타내는 표식 ("결과 없음"과 구분하기 위함)


def _warn(msg):
    WARNINGS.append(msg)


def _as_list(value):
    """numpy 배열·DataFrame 등이 와도 안전하게 list인지 판정 (x or [] 쓰면 터짐)"""
    return value if isinstance(value, list) else []


def _as_text(value, default=""):
    """문자열만 통과. bytes·None·숫자 등은 default"""
    return value if isinstance(value, str) else default


def _as_int(value, default=1):
    """numpy 정수·문자열 숫자도 파이썬 int로 (JSON 직렬화 안전)"""
    try:
        return int(value)
    except Exception:
        return default


def _as_bool(value):
    """문자열 'false'가 True가 되는 사고 방지"""
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "y", "t")
    try:
        return bool(value)
    except Exception:
        return False


def _guess_filename(file):
    """파일경로(str) 또는 업로드 파일객체에서 파일명만 뽑아낸다."""
    if file is None:
        return "unknown"
    name = getattr(file, "name", None) or str(file)   # Streamlit 업로드객체는 .name 보유
    return name.replace("\\", "/").rsplit("/", 1)[-1]


def _norm_parsed(value, file):
    """
    파서 출력 보정 - 두 가지 방식 모두 허용합니다.
      (A) {"filename": "...", "text": "..."}  ← 권장
      (B) "본문 텍스트만"  ← 문자열만 반환해도 됨. 파일명은 파이프라인이 알아서 뽑습니다.
    """
    if isinstance(value, str):
        return {"filename": _guess_filename(file), "text": value}

    if not isinstance(value, dict):
        raise TypeError(f"파서는 dict 또는 str을 반환해야 합니다 (받은 값: {type(value).__name__})")

    text = value.get("text")
    if text is None:
        raise KeyError("파서 출력에 'text' 키가 없습니다 (한지웅)")

    return {
        "filename": value.get("filename") or _guess_filename(file),
        "text": str(text),
    }


def _본문검사(text):
    """빈 문서는 '안전한 문서'가 아니라 '읽지 못한 문서'다."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("본문이 비어 있습니다 (이미지만 있는 PDF이거나 파싱에 실패했을 수 있습니다)")


def _unwrap_detect(value, field, owner, current_text):
    """
    탐지 함수 출력에서 (탐지목록, 마스킹된본문) 을 꺼낸다.
    두 가지 반환 방식을 모두 허용:
      (A) {"pii_found": [...], "masked_text": "..."}   ← 권장 (마스킹 포함)
      (B) [...]                                        ← 목록만 (마스킹 없음)
    """
    if isinstance(value, dict):
        found = value.get(field)
        if found is None:                       # 키 이름을 다르게 준 경우 구제
            for alt in (field, "found", "result", "items", "list"):
                if alt in value:
                    if alt != field:
                        _warn(f"{field}: 키 이름이 '{alt}'입니다 → '{field}'로 맞춰주세요 ({owner})")
                    found = value[alt]
                    break

        masked = value.get("masked_text")
        if masked is not None and not isinstance(masked, str):
            _warn(f"{field}: masked_text가 문자열이 아닙니다 ({owner})")
            masked = None

        items = _norm_list(found, field, owner)
        if masked:
            return items, masked

        if items:
            _warn(f"{field}: 탐지 결과는 있는데 masked_text가 없습니다 → 본문 비공개 처리 ({owner})")
            return items, None      # None = 마스킹 실패 (호출부가 처리)
        return items, current_text

    # 목록만 반환한 경우 - 마스킹 기능이 아직 없는 상태
    items = _norm_list(value, field, owner)
    if items:
        _warn(f"{field}: masked_text가 없습니다 → 본문 비공개 처리 ({owner}: 마스킹본을 같이 반환해주세요)")
        return items, None
    return items, current_text


def _norm_list(value, field, owner):
    """탐지 결과는 list[dict] 여야 함. None이나 dict가 와도 살려낸다."""
    if value is None:
        _warn(f"{field}: None이 왔습니다 → 빈 배열로 처리 ({owner}: 없을 땐 [] 반환해주세요)")
        return []
    if isinstance(value, dict):
        # {"전화번호": ["010-..."]} 같은 옛 형식이 오면 새 형식으로 변환
        _warn(f"{field}: dict가 왔습니다 → list로 변환 ({owner}: [{{'type','count','risk_level','masked'}}] 형식 확인)")
        return [
            {"type": str(k), "count": len(v) if isinstance(v, (list, tuple)) else 1,
             "risk_level": "", "masked": False}
            for k, v in value.items() if isinstance(v, (list, tuple)) and len(v) > 0
        ]
    if not isinstance(value, list):
        _warn(f"{field}: list가 아닌 {type(value).__name__}이 왔습니다 → 빈 배열로 처리 ({owner})")
        return []

    out = []
    for item in value:
        if not isinstance(item, dict):
            _warn(f"{field}: 항목이 dict가 아닙니다 → 건너뜀 ({owner})")
            continue

        원본등급 = item.get("risk_level")
        등급 = _as_text(원본등급).strip().upper()
        if 등급 not in ("HIGH", "LOW"):
            if 원본등급 not in (None, ""):    # 값을 주긴 했는데 HIGH/LOW가 아닌 경우
                _warn(f"{field}: risk_level '{원본등급}'은 HIGH/LOW만 가능 ({owner})")
            등급 = ""         # 빈 값 → Risk Engine이 항목 이름으로 등급을 추정합니다

        out.append({
            "type": _as_text(item.get("type"), "미상").strip() or "미상",
            "count": _as_int(item.get("count"), 1),
            "risk_level": 등급,
            "masked": _as_bool(item.get("masked", False)),
        })
    return out


def _norm_ml(value):
    """label은 0/1 정수여야 함. 문자열로 와도 살려낸다. (제일 자주 나는 실수)"""
    if not isinstance(value, dict):
        _warn(f"ml: dict가 아닌 {type(value).__name__}이 왔습니다 → NORMAL로 처리 (이서영)")
        value = {}

    # 기밀을 뜻하는 표기들 (한글/영문/숫자 문자열 전부 인정)
    기밀표기 = {"1", "CONF", "CONFIDENTIAL", "기밀", "CONFIDENTIAL문서", "SECRET", "기밀문서"}

    def _기밀인가(v):
        t = _as_text(v).strip().upper()
        return t in 기밀표기 or t.startswith("CONF")

    label = value.get("label")
    name = value.get("label_name")

    if isinstance(label, str):
        _warn(f"ml.label: 문자열 '{label}'이 왔습니다 → 숫자로 변환 (이서영: 0=NORMAL, 1=CONFIDENTIAL)")
        label = 1 if _기밀인가(label) else 0
    elif label is None:
        if name:
            _warn("ml.label: 값이 없습니다 → label_name으로 추정 (이서영)")
            label = 1 if _기밀인가(name) else 0
        else:
            _warn("ml: label이 없습니다 → NORMAL로 처리 (이서영)")
            label = 0
    else:
        label = _as_int(label, 0)

    label = 1 if label == 1 else 0

    # label_name은 항상 label에서 다시 만든다 (둘이 어긋나면 화면과 판정이 달라짐)
    정답이름 = "CONFIDENTIAL" if label == 1 else "NORMAL"
    if name and _as_text(name).strip().upper() != 정답이름:
        _warn(f"ml.label_name: '{name}' → '{정답이름}'으로 통일 (이서영: NORMAL/CONFIDENTIAL만 사용)")
    name = 정답이름

    try:
        conf = float(value.get("confidence", 0))
    except Exception:
        _warn("ml.confidence: 숫자가 아닙니다 → 0으로 처리 (이서영)")
        conf = 0.0
    if conf != conf or conf in (float("inf"), float("-inf")):   # NaN / 무한대
        _warn("ml.confidence: 계산 불가 값(NaN) → 0으로 처리 (이서영)")
        conf = 0.0
    if 1 < conf <= 100:   # 87 처럼 퍼센트로 준 경우
        _warn(f"ml.confidence: {conf} → 0~1 소수로 변환 (이서영)")
        conf = conf / 100
    if not 0 <= conf <= 1:
        _warn(f"ml.confidence: {conf}는 0~1 범위를 벗어남 → 잘라냄 (이서영)")
        conf = min(max(conf, 0.0), 1.0)

    return {
        "label": label,
        "label_name": name,
        "confidence": round(conf, 4),
        "evidence": _as_list(value.get("evidence")),
        "model_version": _as_text(value.get("model_version"), ""),
    }


def _norm_policy(value):
    """{"refs": [...]} 형식이어야 함."""
    if value is None:
        _warn("policy: None이 왔습니다 → 빈 결과로 처리 (윤경은: 없을 땐 {'refs': []})")
        return {"refs": []}
    if isinstance(value, list):
        _warn("policy: list가 왔습니다 → {'refs': [...]}로 감쌈 (윤경은)")
        value = {"refs": value}
    if not isinstance(value, dict):
        _warn(f"policy: dict가 아닌 {type(value).__name__}이 왔습니다 → 빈 결과로 처리 (윤경은)")
        return {"refs": []}

    out = []
    for r in _as_list(value.get("refs")):
        if isinstance(r, str):      # 조항 제목만 문자열로 준 경우
            out.append({"title": r, "snippet": "", "source": ""})
        elif isinstance(r, dict):
            out.append({
                "title": _as_text(r.get("title"), ""),
                "snippet": _as_text(r.get("snippet"), ""),
                "source": _as_text(r.get("source"), ""),
            })
    return {"refs": out}


def _판정실패(사유):
    """보안 도구는 판정이 실패하면 '허용'이 아니라 '차단'으로 떨어져야 한다."""
    _warn(f"risk: {사유} → 안전을 위해 차단 처리 (최재용)")
    return {"score": 100, "action": "차단", "reasons": [f"판정 실패 ({사유}) - 안전을 위해 차단"]}


def _norm_risk(value):
    """{"score": int, "action": str, "reasons": list} 형식이어야 함."""
    if not isinstance(value, dict):
        return _판정실패(f"dict가 아닌 {type(value).__name__}이 왔습니다")

    if "score" not in value and "action" not in value:
        return _판정실패("score도 action도 없습니다")

    score = _as_int(value.get("score"), None)
    if score is None:
        _warn(f"risk.score: 숫자가 아닌 '{value.get('score')}' → 0으로 처리 (최재용)")
        score = 0
    score = max(0, min(score, 100))

    action = _as_text(value.get("action")).strip()
    기대 = "차단" if score >= BLOCK_THRESHOLD else "허용"
    if action not in ("허용", "차단"):
        _warn(f"risk.action: '{value.get('action')}'은 허용되지 않는 값 → 점수 기준으로 재판정 (최재용: 허용/차단만)")
        action = 기대
    elif action != 기대:
        # 점수와 판정이 어긋남 - 더 안전한 쪽(차단)을 택한다
        _warn(f"risk: {score}점인데 판정이 '{action}'입니다 (기준 {BLOCK_THRESHOLD}점) → 차단으로 통일 (최재용)")
        action = "차단"

    reasons = value.get("reasons")
    if not isinstance(reasons, list):
        reasons = [] if reasons in (None, "") else [str(reasons)]

    return {
        "score": score,
        "action": action,
        "reasons": [str(x) for x in reasons] or ["특이사항 없음"],
    }


# =============================================================
# 3) Risk Engine 예비용 (최재용)
#    ※ 정식 버전은 tools/risk_engine.py 입니다. 그게 있으면 그쪽이 쓰입니다.
#      여기 있는 건 tools/risk_engine.py 가 없을 때만 쓰이는 예비 판정기이고,
#      정식 버전과 판정이 어긋나면 안 되므로 같은 기준(등급제)을 씁니다.
# =============================================================

# ※ tools/risk_engine.py 의 HIGH_KEYWORDS / SECRET_HIGH_KEYWORDS 와 같아야 합니다
_HIGH_PII = {"주민", "여권", "면허", "외국인등록", "계좌", "카드번호",
             "휴대폰", "핸드폰", "개인전화", "자택", "집주소", "resident", "passport"}
_HIGH_SECRET = {"api", "key", "token", "password", "passwd", "pwd",
                "secret", "credential", "비밀번호", "인증키", "액세스"}
_LOW_TOTAL_CAP = 15      # 저위험 항목 총점 상한


def _등급(item, 고위험키워드):
    """항목의 위험 등급 판정. risk_level이 있으면 그것을, 없으면 이름으로 추정."""
    level = _as_text(item.get("risk_level")).strip().upper()
    if level in ("HIGH", "LOW"):
        return level
    종류 = _as_text(item.get("type")).strip().lower()
    return "HIGH" if any(k in 종류 for k in 고위험키워드) else "LOW"


def temp_risk_engine(pii_found, secret_found, ml, policy):
    """
    입력: pii_found(list), secret_found(list), ml(dict), policy(dict)
    출력: {"score": int, "action": str, "reasons": list[str]}
    """
    score = 0
    저위험점수 = 0
    reasons = []
    치명적 = []
    저위험 = []

    for item in _as_list(pii_found):
        if not isinstance(item, dict):
            continue
        종류, 건수 = item.get("type", "개인정보"), item.get("count", 1)
        if _등급(item, _HIGH_PII) == "HIGH":
            score += 100
            reasons.append(f"[고위험] {종류} {건수}건 발견")
            치명적.append(종류)
        else:
            저위험점수 += 5
            저위험.append(f"{종류} {건수}건")

    if 저위험:
        reasons.append("[저위험] " + ", ".join(저위험))

    for item in _as_list(secret_found):
        if not isinstance(item, dict):
            continue
        종류, 건수 = item.get("type", "인증정보"), item.get("count", 1)
        if _등급(item, _HIGH_SECRET) == "HIGH":
            score += 100
            reasons.append(f"[고위험] {종류} {건수}건 발견")
            치명적.append(종류)
        else:
            저위험점수 += 20
            reasons.append(f"{종류} {건수}건 발견")

    score += min(저위험점수, _LOW_TOTAL_CAP)

    if (ml or {}).get("label") == 1:
        conf = ml.get("confidence", 0)
        score += 60 if conf >= 0.8 else 30
        reasons.append(f"ML 기밀 분류 ({conf:.0%})")

    refs = _as_list((policy or {}).get("refs"))
    if refs:
        score += 25
        reasons.append(f"정책 위반 {len(refs)}건")

    score = max(0, min(score, 100))
    action = "차단" if score >= BLOCK_THRESHOLD else "허용"

    if 치명적:
        reasons.insert(0, f"고위험 항목 검출로 즉시 차단 ({', '.join(dict.fromkeys(치명적))})")

    return {
        "score": score,
        "action": action,
        "reasons": reasons or ["특이사항 없음"],
    }


# 진짜가 없으면 더미/임시로 채우기
parse_document       = _parse_document       or dummy_parse_document
detect_pii           = _detect_pii           or dummy_detect_pii
detect_secret        = _detect_secret        or dummy_detect_secret
predict_confidential = _predict_confidential or dummy_predict_confidential
search_policy        = _search_policy        or dummy_search_policy
risk_engine          = _risk_engine          or temp_risk_engine
analyze_final        = _analyze_final        or dummy_analyze_final


# =============================================================
# 4) 메인 흐름
#    정은환: app.py 에서 이것만 부르면 됩니다.
#            from pipeline import run_pipeline
#            result = run_pipeline(uploaded_file)   # dict 반환
# =============================================================

_counter = 0


def _new_doc_id():
    global _counter
    _counter += 1
    return f"doc_{datetime.now():%Y%m%d}_{_counter:04d}"


def _error_result(doc_id, filename, message):
    """status=error면 text 이하 전부 null (규칙 1)"""
    return {
        "doc_id": doc_id,
        "filename": filename,
        "status": "error",
        "error": message,
        "text": None,
        "pii_found": None,
        "secret_found": None,
        "ml": None,
        "policy": None,
        "risk": None,
        "explanation": None,
    }


def run_pipeline(file, _경고초기화=True):
    """문서 1건 처리 → shield_doc_common.json 형식 dict 반환. 어떤 경우에도 예외를 던지지 않습니다."""
    if _경고초기화:
        WARNINGS.clear()      # 이전 문서의 경고가 섞이지 않도록
    try:
        return _run_pipeline(file)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:
        # 최후의 안전망 - 여기까지 오면 안 되지만, 화면이 죽는 것보다는 낫다
        _warn(f"파이프라인 내부 오류 (최재용) {type(e).__name__}: {e}")
        return _error_result(_new_doc_id(), _guess_filename(file),
                             f"처리 중 오류가 발생했습니다 ({type(e).__name__})")


def _run_pipeline(file):
    doc_id = _new_doc_id()

    # --- 파싱 (실패하면 여기서 종료) ---
    try:
        parsed = _norm_parsed(parse_document(file), file)
        filename = parsed["filename"]
        text = parsed["text"]
        _본문검사(text)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:
        # 예외 메시지에 문서 원문이 실려 나가지 않도록 길이를 제한한다
        사유 = str(e).replace("\n", " ")[:120]
        return _error_result(doc_id, _guess_filename(file),
                             f"문서를 읽을 수 없습니다 ({type(e).__name__}: {사유})")

    # --- 탐지 (하나가 죽어도 나머지는 살린다) ---
    def _safe(fn, arg, name, owner):
        try:
            return fn(arg)
        except (KeyboardInterrupt, SystemExit):
            raise                       # Ctrl+C 는 삼키지 않는다
        except BaseException as e:
            _warn(f"{name}: 실행 중 오류 → 결과 없음으로 처리 ({owner}) {type(e).__name__}: {str(e)[:120]}")
            return _실패

    # 분석용 텍스트와 화면 출력용 텍스트를 나눈다.
    #   분석용 : 마스킹본이 있으면 마스킹본, 없으면 원문 (탐지가 계속 돌아야 하므로)
    #   출력용 : 마스킹본. 마스킹 실패 시 비공개 문구 (원문이 화면·API로 새지 않도록)
    탐지실패 = False
    마스킹실패 = False

    pii결과 = _safe(detect_pii, text, "detect_pii", "한지웅")
    if pii결과 is _실패:
        탐지실패 = True
        pii_found, 마스킹본 = [], None
    else:
        pii_found, 마스킹본 = _unwrap_detect(pii결과, "pii_found", "한지웅", text)

    분석텍스트 = 마스킹본 if 마스킹본 is not None else text
    마스킹실패 = 마스킹본 is None

    sec결과 = _safe(detect_secret, 분석텍스트, "detect_secret", "한지웅")
    if sec결과 is _실패:
        탐지실패 = True
        secret_found = []
    else:
        secret_found, 다음마스킹본 = _unwrap_detect(sec결과, "secret_found", "한지웅", 분석텍스트)
        if 다음마스킹본 is None:
            마스킹실패 = True
        else:
            분석텍스트 = 다음마스킹본

    ml결과 = _safe(predict_confidential, 분석텍스트, "predict_confidential", "이서영")
    pol결과 = _safe(search_policy, 분석텍스트, "search_policy", "윤경은")
    if ml결과 is _실패 or pol결과 is _실패:
        탐지실패 = True
    ml     = _norm_ml({} if ml결과 is _실패 else ml결과)
    policy = _norm_policy({"refs": []} if pol결과 is _실패 else pol결과)

    # 화면·API로 나가는 본문
    출력텍스트 = "(마스킹 실패 - 본문 비공개)" if 마스킹실패 else 분석텍스트

    # --- 판정 ---
    try:
        risk = _norm_risk(risk_engine(pii_found, secret_found, ml, policy))
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:
        _warn(f"risk_engine: 실행 중 오류 (최재용) {type(e).__name__}: {str(e)[:120]}")
        try:
            risk = _norm_risk(temp_risk_engine(pii_found, secret_found, ml, policy))
        except Exception as e2:
            risk = _판정실패(f"예비 판정기도 실패 {type(e2).__name__}")

    # 검사 자체가 불완전했으면 "안전하다"고 말할 수 없다 → 차단으로 올린다
    if 탐지실패 and risk["action"] == "허용":
        _warn("일부 검사가 실패해 안전을 확인할 수 없습니다 → 차단으로 처리")
        risk = {
            "score": max(risk["score"], BLOCK_THRESHOLD),
            "action": "차단",
            "reasons": ["일부 검사 실패 - 안전을 확인할 수 없어 차단"] + risk["reasons"],
        }

    doc = {
        "doc_id": doc_id,
        "filename": filename,
        "status": "success",
        "text": 출력텍스트,       # 마스킹된 본문 (원문은 저장하지 않음)
        "pii_found": pii_found,
        "secret_found": secret_found,
        "ml": ml,
        "policy": policy,
        "risk": risk,
        "explanation": "",
    }

    # --- 설명 생성 (실패해도 판정 결과는 살린다) ---
    # 사본을 넘긴다 - 조정인님 모듈이 doc을 수정해도 최종 JSON 형식이 깨지지 않도록
    try:
        result = analyze_final(copy.deepcopy(doc))
        doc["explanation"] = result if isinstance(result, str) else str(result)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:
        _warn(f"analyze_final: 실행 중 오류 (조정인) {type(e).__name__}: {str(e)[:120]}")
        doc["explanation"] = "(설명 생성 실패 - 판정 결과는 유효합니다)"

    return doc


def get_warnings():
    """이번 실행에서 발생한 형식 경고 목록 (정은환: 화면 하단에 띄우면 디버깅이 쉬워집니다)"""
    return list(dict.fromkeys(WARNINGS))


def run_batch(files):
    """여러 건 처리 → {"results": [...]} 형식"""
    WARNINGS.clear()
    return {"results": [run_pipeline(f, _경고초기화=False) for f in files]}


# =============================================================
# 5) 단독 실행 - 터미널 확인용
# =============================================================

def _print_status():
    print("=" * 60)
    print(" SHIELD_DOC 파이프라인 v2 - 모듈 연결 상태")
    print("=" * 60)
    for name, state in STATUS.items():
        mark = "O" if state.startswith("REAL") else ("!" if state.startswith("ERROR") else "-")
        print(f" [{mark}] {name:<22} {state}")
    if _risk_engine is None:
        print("     ※ risk_engine은 pipeline.py 안의 임시 버전이 동작 중입니다 (최재용)")
    print("=" * 60)


def _print_warnings():
    if not WARNINGS:
        return
    print("\n" + "!" * 60)
    print(f" 형식 경고 {len(WARNINGS)}건 - 담당자가 고쳐야 합니다")
    print("!" * 60)
    for w in dict.fromkeys(WARNINGS):   # 중복 제거
        print(f" · {w}")
    print("!" * 60)


def _print_result(r):
    print(f"\n[{r['filename']}]  ({r['doc_id']})")
    if r["status"] == "error":
        print(f"  ! 처리 실패: {r['error']}")
        return
    pii = [f"{i['type']} {i['count']}건" for i in r["pii_found"]]
    sec = [f"{i['type']} {i['count']}건" for i in r["secret_found"]]
    refs = [x["title"] for x in r["policy"]["refs"]]
    print(f"  개인정보 : {', '.join(pii) or '없음'}")
    print(f"  인증정보 : {', '.join(sec) or '없음'}")
    print(f"  ML 분류  : {r['ml']['label_name']} ({r['ml']['confidence']:.0%})")
    print(f"  정책     : {', '.join(refs) or '위반 없음'}")
    print("  " + "-" * 56)
    print(f"  판정     : {r['risk']['action']}  ({r['risk']['score']}점)")
    for reason in r["risk"]["reasons"]:
        print(f"             · {reason}")
    print(f"  설명     : {r['explanation']}")


if __name__ == "__main__":
    import sys

    _print_status()
    args = sys.argv[1:]

    if len(args) > 1:
        out = run_batch(args)
        for r in out["results"]:
            _print_result(r)
    else:
        out = run_pipeline(args[0] if args else None)
        _print_result(out)

    _print_warnings()

    print("\n--- JSON 출력 ---")
    print(json.dumps(out, ensure_ascii=False, indent=2)[:600] + " ...")
