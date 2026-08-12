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
    except ModuleNotFoundError:
        STATUS[func_name] = f"dummy ({owner} 대기중)"
        return None
    except Exception as e:
        # 파일은 있는데 안 읽힘 (문법 오류, import 오류 등) - 이유를 보여줘야 함
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
          - pii_found : type / count / masked
          - masked_text : 개인정보를 가린 본문
    마스킹을 아직 안 만들었으면 목록만 반환해도 됩니다 (그땐 원문이 그대로 흘러갑니다).
    """
    return {
        "pii_found": [{"type": "전화번호", "count": 1, "masked": True}],
        "masked_text": "담당자 전화번호는 010-****-5678입니다. (더미 마스킹본)",
    }


def dummy_detect_secret(text):
    """
    입력: detect_pii가 가린 본문 (원문 아님)
    출력: {"secret_found": list[dict], "masked_text": str}
          - type은 api_key / password / 내부IP
    자기가 받은 텍스트에서 Secret만 추가로 가려서 돌려주면 됩니다.
    """
    return {
        "secret_found": [{"type": "내부IP", "count": 1, "masked": False}],
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


def _warn(msg):
    WARNINGS.append(msg)


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


def _unwrap_detect(value, field, owner, current_text):
    """
    탐지 함수 출력에서 (탐지목록, 마스킹된본문) 을 꺼낸다.
    두 가지 반환 방식을 모두 허용:
      (A) {"pii_found": [...], "masked_text": "..."}   ← 권장 (마스킹 포함)
      (B) [...]                                        ← 목록만 (마스킹 없음)
    """
    if isinstance(value, dict) and ("masked_text" in value or field in value):
        found = value.get(field)
        if found is None:                       # 키 이름을 다르게 준 경우 구제
            for alt in ("found", "result", "items"):
                if alt in value:
                    _warn(f"{field}: 키 이름이 '{alt}'입니다 → '{field}'로 맞춰주세요 ({owner})")
                    found = value[alt]
                    break
        masked = value.get("masked_text")
        if masked is not None and not isinstance(masked, str):
            _warn(f"{field}: masked_text가 문자열이 아닙니다 → 무시 ({owner})")
            masked = None
        return _norm_list(found, field, owner), (masked if masked else current_text)

    # 목록만 반환한 경우 - 마스킹은 건너뛴다
    return _norm_list(value, field, owner), current_text


def _norm_list(value, field, owner):
    """탐지 결과는 list[dict] 여야 함. None이나 dict가 와도 살려낸다."""
    if value is None:
        _warn(f"{field}: None이 왔습니다 → 빈 배열로 처리 ({owner}: 없을 땐 [] 반환해주세요)")
        return []
    if isinstance(value, dict):
        # {"전화번호": ["010-..."]} 같은 옛 형식이 오면 새 형식으로 변환
        _warn(f"{field}: dict가 왔습니다 → list로 변환 ({owner}: [{{'type','count','masked'}}] 형식 확인)")
        return [
            {"type": k, "count": len(v) if isinstance(v, (list, tuple)) else 1, "masked": False}
            for k, v in value.items() if v
        ]
    if not isinstance(value, list):
        _warn(f"{field}: list가 아닌 {type(value).__name__}이 왔습니다 → 빈 배열로 처리 ({owner})")
        return []

    out = []
    for item in value:
        if not isinstance(item, dict):
            _warn(f"{field}: 항목이 dict가 아닙니다 → 건너뜀 ({owner})")
            continue
        out.append({
            "type": item.get("type", "미상"),
            "count": item.get("count", 1),
            "masked": bool(item.get("masked", False)),
        })
    return out


def _norm_ml(value):
    """label은 0/1 정수여야 함. 문자열로 와도 살려낸다. (제일 자주 나는 실수)"""
    if not isinstance(value, dict):
        _warn(f"ml: dict가 아닌 {type(value).__name__}이 왔습니다 → NORMAL로 처리 (이서영)")
        value = {}

    label = value.get("label")
    name = value.get("label_name")

    if isinstance(label, str):
        _warn(f"ml.label: 문자열 '{label}'이 왔습니다 → 숫자로 변환 (이서영: 0=NORMAL, 1=CONFIDENTIAL)")
        name = name or label
        label = 1 if label.upper().startswith("CONF") else 0
    elif label is None:
        if name:
            _warn("ml.label: 값이 없습니다 → label_name으로 추정 (이서영)")
            label = 1 if str(name).upper().startswith("CONF") else 0
        else:
            _warn("ml: label이 없습니다 → NORMAL로 처리 (이서영)")
            label = 0

    label = 1 if label == 1 else 0
    if not name:
        name = "CONFIDENTIAL" if label == 1 else "NORMAL"

    try:
        conf = float(value.get("confidence", 0))
    except (TypeError, ValueError):
        _warn("ml.confidence: 숫자가 아닙니다 → 0으로 처리 (이서영)")
        conf = 0.0
    if conf > 1:   # 87 처럼 퍼센트로 준 경우
        _warn(f"ml.confidence: {conf} → 0~1 소수로 변환 (이서영)")
        conf = conf / 100

    evidence = value.get("evidence") or []
    if not isinstance(evidence, list):
        evidence = []

    return {
        "label": label,
        "label_name": name,
        "confidence": round(conf, 4),
        "evidence": evidence,
        "model_version": value.get("model_version", ""),
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

    refs = value.get("refs") or []
    if not isinstance(refs, list):
        refs = []

    out = []
    for r in refs:
        if isinstance(r, str):      # 조항 제목만 문자열로 준 경우
            out.append({"title": r, "snippet": "", "source": ""})
        elif isinstance(r, dict):
            out.append({
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "source": r.get("source", ""),
            })
    return {"refs": out}


def _norm_risk(value):
    """{"score": int, "action": str, "reasons": list} 형식이어야 함."""
    if not isinstance(value, dict):
        _warn(f"risk: dict가 아닌 {type(value).__name__}이 왔습니다 → 허용 처리 (최재용)")
        return {"score": 0, "action": "허용", "reasons": ["판정 오류"]}

    try:
        score = int(value.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(score, 100))

    action = value.get("action")
    if action not in ("허용", "차단"):
        _warn(f"risk.action: '{action}'은 허용되지 않는 값 → 점수 기준으로 다시 판정 (최재용: 허용/차단만)")
        action = "차단" if score >= BLOCK_THRESHOLD else "허용"

    reasons = value.get("reasons") or []
    if not isinstance(reasons, list):
        reasons = [str(reasons)]

    return {"score": score, "action": action, "reasons": [str(x) for x in reasons] or ["특이사항 없음"]}


# =============================================================
# 3) Risk Engine (최재용) - 완성되면 tools/risk_engine.py 로 이동
#    action은 "허용" / "차단" 2단계. 경계 = BLOCK_THRESHOLD
# =============================================================

def temp_risk_engine(pii_found, secret_found, ml, policy):
    """
    입력: pii_found(list), secret_found(list), ml(dict), policy(dict)
    출력: {"score": int, "action": str, "reasons": list[str]}
    """
    score = 0
    reasons = []

    for item in pii_found:
        score += 30
        reasons.append(f"{item['type']} {item['count']}건 발견")

    for item in secret_found:
        score += 20
        reasons.append(f"{item['type']} {item['count']}건 발견")

    if ml.get("label") == 1:
        conf = ml.get("confidence", 0)
        score += 40 if conf >= 0.8 else 25
        reasons.append(f"ML 기밀 분류 ({conf:.0%})")

    refs = policy.get("refs", [])
    if refs:
        score += 20
        reasons.append(f"정책 위반 {len(refs)}건")

    score = min(score, 100)
    action = "차단" if score >= BLOCK_THRESHOLD else "허용"

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


def run_pipeline(file):
    """문서 1건 처리 → shield_doc_common.json 형식 dict 반환"""
    doc_id = _new_doc_id()

    # --- 파싱 (실패하면 여기서 종료) ---
    try:
        parsed = _norm_parsed(parse_document(file), file)
        filename = parsed["filename"]
        text = parsed["text"]
    except Exception as e:
        return _error_result(doc_id, _guess_filename(file), f"문서를 읽을 수 없습니다: {e}")

    # --- 탐지 (하나가 죽어도 나머지는 살린다) ---
    def _safe(fn, arg, fallback, name, owner):
        try:
            return fn(arg)
        except Exception as e:
            _warn(f"{name}: 실행 중 오류 → 결과 없음으로 처리 ({owner}) {type(e).__name__}: {e}")
            return fallback

    # 마스킹은 이어서 적용: 원문 → 개인정보 가림 → Secret 가림 → 최종 마스킹본
    pii_found, masked = _unwrap_detect(
        _safe(detect_pii, text, [], "detect_pii", "한지웅"), "pii_found", "한지웅", text)

    secret_found, masked = _unwrap_detect(
        _safe(detect_secret, masked, [], "detect_secret", "한지웅"), "secret_found", "한지웅", masked)

    # 이후 단계는 마스킹본만 사용 (원문은 여기서 버림)
    ml     = _norm_ml(_safe(predict_confidential, masked, {}, "predict_confidential", "이서영"))
    policy = _norm_policy(_safe(search_policy, masked, {"refs": []}, "search_policy", "윤경은"))

    # --- 판정 ---
    try:
        risk = _norm_risk(risk_engine(pii_found, secret_found, ml, policy))
    except Exception as e:
        _warn(f"risk_engine: 실행 중 오류 (최재용) {type(e).__name__}: {e}")
        risk = _norm_risk(temp_risk_engine(pii_found, secret_found, ml, policy))

    doc = {
        "doc_id": doc_id,
        "filename": filename,
        "status": "success",
        "text": masked,          # 마스킹된 본문 (원문은 저장하지 않음)
        "pii_found": pii_found,
        "secret_found": secret_found,
        "ml": ml,
        "policy": policy,
        "risk": risk,
        "explanation": "",
    }

    # --- 설명 생성 (실패해도 판정 결과는 살린다) ---
    try:
        result = analyze_final(doc)
        doc["explanation"] = result if isinstance(result, str) else str(result)
    except Exception as e:
        _warn(f"analyze_final: 실행 중 오류 (조정인) {type(e).__name__}: {e}")
        doc["explanation"] = "(설명 생성 실패 - 판정 결과는 유효합니다)"

    return doc


def run_batch(files):
    """여러 건 처리 → {"results": [...]} 형식"""
    return {"results": [run_pipeline(f) for f in files]}


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
