"""
SHIELD_DOC - Risk Engine (위험도 판정)  v3
담당: 최재용

탐지 결과 4종을 받아서 점수를 매기고, 반출 허용/차단을 판정합니다.

입력  : pii_found(list), secret_found(list), ml(dict), policy(dict)
출력  : {"score": 0~100, "action": "허용"|"차단", "reasons": [str, ...]}

설계 요점
  - 개인정보를 민감도로 나눠서 봅니다 (risk_level: HIGH / LOW)
    · HIGH(주민번호·개인휴대폰 등) → 1건만 나와도 즉시 차단
    · LOW(업무이메일·부서·직급 등) → 탐지는 하되 점수는 거의 안 줌
    사내 공개용 직원 명부처럼 "개인정보 패턴은 잡히지만 위험하지 않은" 문서를
    무조건 차단하지 않기 위한 장치입니다.

[v2 → v3 변경점]
  - LOW_TOTAL_CAP(15)이 pii_low와 secret_low를 함께 묶는 바람에
    secret_low(20)가 상한보다 커서 도달 불가능한 죽은 값이었습니다.
    → PII_LOW_CAP 으로 이름을 바꾸고 저위험 '개인정보'에만 적용합니다.
    → 저위험 '인증정보'(내부IP 등)는 상한 밖에서 그대로 가산됩니다.
    영향: 내부IP + ML기밀(확신낮음) = 20+30 = 50점 → 허용에서 차단으로 바뀝니다.
  - 자체 점검표가 action만 비교해서 위 버그를 못 잡았습니다.
    → 기대 점수까지 함께 검사하도록 강화하고 회귀 케이스를 추가했습니다.

단독 실행:  python tools/risk_engine_v3.py     ← 판정 기준 점검표 출력
"""

# =============================================================
# 판정 기준 - 여기 숫자만 바꾸면 판정이 바뀝니다
# =============================================================

BLOCK_THRESHOLD = 50        # 이 점수 이상이면 차단

WEIGHTS = {
    "pii_high": 100,        # 고위험 개인정보 (주민번호, 개인휴대폰, 계좌번호 등) → 단독 차단
    "pii_low": 5,           # 저위험 개인정보 (업무이메일, 내선번호, 부서, 직급)
    "secret_high": 100,     # API 키, 비밀번호 → 단독 차단
    "secret_low": 20,       # 내부 IP 등
    "ml_high": 60,          # ML 기밀 분류 + 확신 높음(80% 이상) → 단독 차단
    "ml_low": 30,           # ML 기밀 분류 + 확신 낮음
    "policy": 25,           # 정책 위반 조항 발견
}

ML_CONFIDENT = 0.8          # 이 확률 이상이면 "확신 높음"

# 저위험 '개인정보' 총점 상한.
#   목적: 직원명부처럼 업무이메일·부서·직급이 잔뜩 잡히는 문서가 개수만으로 차단되지 않게.
#   ※ 저위험 '인증정보'(내부IP 등)에는 적용하지 않습니다.
#      pii_low(5)는 개수가 쉽게 불어나지만 secret_low(20)는 종류가 3가지뿐이고
#      건당 위험도가 달라서, 같은 상한에 묶으면 secret_low 값이 사장됩니다.
#   ※ 전제: detect_secret이 종류별로 1건씩 묶어서 반환합니다
#      ({"type": "내부IP", "count": N} 형태). 만약 발생 건수마다 항목을 따로 주도록
#      바뀌면 여기에도 상한이 필요합니다.
PII_LOW_CAP = 15

# v2 호환용 별칭 (예전 이름을 import하는 코드가 있어도 깨지지 않도록)
LOW_TOTAL_CAP = PII_LOW_CAP

# risk_level이 없는 항목은 이 키워드로 판단 (지웅님 모듈이 등급을 안 주는 경우 대비)
# 부분 일치 + 대소문자 무시로 비교합니다 ("주민번호(뒷자리)", "AWS API KEY" 등도 잡힘)
HIGH_KEYWORDS = {
    "주민", "여권", "면허", "외국인등록", "계좌", "카드번호",
    "휴대폰", "핸드폰", "개인전화", "자택", "집주소", "resident", "passport",
}
SECRET_HIGH_KEYWORDS = {
    "api", "key", "token", "password", "passwd", "pwd",
    "secret", "credential", "비밀번호", "인증키", "액세스",
}


# =============================================================
# 등급 판단
# =============================================================

def _level_of(item, 고위험키워드):
    """
    항목의 위험 등급을 HIGH / LOW 로 판정한다.
      1) risk_level이 HIGH/LOW면 그대로 사용
      2) 없으면 항목 이름에 고위험 키워드가 들어있는지로 추정
    """
    level = item.get("risk_level")
    level = level.strip().upper() if isinstance(level, str) else ""
    if level in ("HIGH", "LOW"):
        return level

    종류 = item.get("type")
    종류 = 종류.strip().lower() if isinstance(종류, str) else ""
    # 키워드도 소문자로 맞춰서 비교한다.
    # (종류만 소문자로 바꾸면 키워드에 대문자를 하나 추가하는 순간 영영 안 잡힘)
    return "HIGH" if any(str(k).lower() in 종류 for k in 고위험키워드) else "LOW"


# =============================================================
# 판정
# =============================================================

def risk_engine(pii_found, secret_found, ml, policy):
    def _목록(v):
        return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []

    score = 0
    pii저위험 = 0            # 상한 적용 대상
    secret저위험 = 0         # 상한 미적용
    reasons = []
    치명적 = []              # 단독으로 차단시킨 항목 (설명에 강조용)

    # 1. 개인정보 - 등급에 따라 점수가 크게 갈림
    low_pii = []
    for item in _목록(pii_found):
        종류 = item.get("type", "개인정보")
        건수 = item.get("count", 1)
        if _level_of(item, HIGH_KEYWORDS) == "HIGH":
            score += WEIGHTS["pii_high"]
            reasons.append(f"[고위험] {종류} {건수}건 발견")
            치명적.append(종류)
        else:
            pii저위험 += WEIGHTS["pii_low"]
            low_pii.append(f"{종류} {건수}건")

    if low_pii:
        reasons.append("[저위험] " + ", ".join(low_pii))

    # 2. 인증정보 - API 키·비밀번호는 치명적, 내부 IP는 중간
    for item in _목록(secret_found):
        종류 = item.get("type", "인증정보")
        건수 = item.get("count", 1)
        if _level_of(item, SECRET_HIGH_KEYWORDS) == "HIGH":
            score += WEIGHTS["secret_high"]
            reasons.append(f"[고위험] {종류} {건수}건 발견")
            치명적.append(종류)
        else:
            secret저위험 += WEIGHTS["secret_low"]
            reasons.append(f"{종류} {건수}건 발견")

    # 저위험 개인정보만 상한을 둔다 (직원명부에 이메일 10개 있다고 차단되면 안 됨).
    # 저위험 인증정보는 상한 밖 - 자세한 이유는 PII_LOW_CAP 주석 참고.
    score += min(pii저위험, PII_LOW_CAP)
    score += secret저위험

    # 3. ML 기밀 분류
    if isinstance(ml, dict) and ml.get("label") == 1:
        try:
            conf = float(ml.get("confidence", 0))
        except (TypeError, ValueError):
            conf = 0.0
        if conf >= ML_CONFIDENT:
            score += WEIGHTS["ml_high"]
            reasons.append(f"ML 기밀 분류 ({conf:.0%}) — 확신 높음")
        else:
            score += WEIGHTS["ml_low"]
            reasons.append(f"ML 기밀 분류 ({conf:.0%}) — 확신 낮음")

    # 4. 사내 정책 위반
    refs = _목록((policy or {}).get("refs") if isinstance(policy, dict) else None)
    if refs:
        score += WEIGHTS["policy"]
        titles = [r.get("title", "") for r in refs]
        reasons.append(f"정책 위반 {len(refs)}건" + (f" — {titles[0]}" if titles and titles[0] else ""))

    score = max(0, min(int(score), 100))
    action = "차단" if score >= BLOCK_THRESHOLD else "허용"

    if 치명적:
        reasons.insert(0, f"고위험 항목 검출로 즉시 차단 ({', '.join(dict.fromkeys(치명적))})")

    return {
        "score": score,
        "action": action,
        "reasons": reasons or ["특이사항 없음"],
    }


# =============================================================
# 단독 실행 - 기준이 적절한지 확인용
#   ※ action만 비교하면 점수가 틀려도 우연히 같은 판정이 나와 통과합니다.
#     (v2의 secret_low 버그가 정확히 그렇게 숨어 있었습니다)
#     그래서 기대 점수까지 같이 검사합니다.
# =============================================================

if __name__ == "__main__":
    def PII(종류, 등급, n=1):
        return {"type": 종류, "count": n, "risk_level": 등급, "masked": True}

    def SEC(종류, 등급, n=1):
        return {"type": 종류, "count": n, "risk_level": 등급, "masked": True}

    정상ML = {"label": 0, "confidence": 0.94}
    기밀ML = {"label": 1, "confidence": 0.87}
    애매ML = {"label": 1, "confidence": 0.62}
    무위반 = {"refs": []}
    위반 = {"refs": [{"title": "정보보호지침 제12조"}]}

    # (이름, pii, secret, ml, policy, 기대action, 기대score)
    사례들 = [
        ("정상 사내공지 (아무것도 없음)",           [], [], 정상ML, 무위반, "허용", 0),
        ("사내 공개용 직원명부 (업무이메일·부서·직급)",
         [PII("업무이메일", "LOW"), PII("부서", "LOW"), PII("직급", "LOW")], [], 정상ML, 무위반, "허용", 15),
        ("내선번호만 있는 조직도",                  [PII("내선번호", "LOW")], [], 정상ML, 무위반, "허용", 5),
        ("주민등록번호 1건",                        [PII("주민등록번호", "HIGH")], [], 정상ML, 무위반, "차단", 100),
        ("개인 휴대폰 1건",                         [PII("개인휴대폰", "HIGH")], [], 정상ML, 무위반, "차단", 100),
        ("API 키 노출",                             [], [SEC("api_key", "HIGH")], 정상ML, 무위반, "차단", 100),
        ("내부 IP만",                               [], [SEC("내부IP", "LOW")], 정상ML, 무위반, "허용", 20),
        ("ML 기밀 (확신 높음) 단독",                [], [], 기밀ML, 무위반, "차단", 60),
        ("ML 기밀 (확신 낮음) 단독",                [], [], 애매ML, 무위반, "허용", 30),
        ("ML 기밀(낮음) + 정책 위반",               [], [], 애매ML, 위반, "차단", 55),
        ("정책 위반만",                             [], [], 정상ML, 위반, "허용", 25),
        ("직원명부 + ML 기밀(높음)",
         [PII("업무이메일", "LOW")], [], 기밀ML, 무위반, "차단", 65),
        ("전부 걸림 (최악)",
         [PII("주민등록번호", "HIGH", 2)], [SEC("api_key", "HIGH")], 기밀ML, 위반, "차단", 100),

        # --- 등급 표기가 없거나 이름이 조금 다른 경우 (팀원 실수 대비) ---
        ("등급 없음 + '주민번호(뒷자리)'",         [{"type": "주민번호(뒷자리)", "count": 1}], [], 정상ML, 무위반, "차단", 100),
        ("등급 없음 + 'API_KEY' (대문자)",         [], [{"type": "API_KEY", "count": 1}], 정상ML, 무위반, "차단", 100),
        ("등급 없음 + 'AWS 액세스 키'",            [], [{"type": "AWS 액세스 키", "count": 1}], 정상ML, 무위반, "차단", 100),
        ("등급 'high ' (뒤 공백) + 여권",          [{"type": "여권", "count": 1, "risk_level": "high "}], [], 정상ML, 무위반, "차단", 100),
        ("업무이메일 10개 (타입별로 안 묶은 경우)",
         [PII("업무이메일", "LOW") for _ in range(10)], [], 정상ML, 무위반, "허용", 15),

        # --- v3 회귀 테스트: 저위험 상한 분리 ---
        # v2에서는 15+30=45로 '허용'이었습니다. secret_low(20)가 상한 15에 잘려서.
        ("[회귀] 내부IP + ML기밀(확신낮음)",
         [], [SEC("내부IP", "LOW")], 애매ML, 무위반, "차단", 50),
        # pii_low 상한은 그대로 살아 있어야 합니다 (15) + 내부IP(20) = 35
        ("[회귀] 업무이메일 10개 + 내부IP",
         [PII("업무이메일", "LOW") for _ in range(10)], [SEC("내부IP", "LOW")], 정상ML, 무위반, "허용", 35),
    ]

    print("=" * 78)
    print(f" Risk Engine v3 판정 기준 점검  (차단 기준: {BLOCK_THRESHOLD}점)")
    print("=" * 78)
    틀림 = 0
    for 이름, pii, sec, ml, pol, 기대action, 기대score in 사례들:
        r = risk_engine(pii, sec, ml, pol)
        action맞음 = r["action"] == 기대action
        score맞음 = r["score"] == 기대score
        if action맞음 and score맞음:
            표시 = "OK "
        else:
            표시 = "!! "
            틀림 += 1
        줄 = f" {표시} {r['score']:>3}점  [{r['action']}]  {이름}"
        if not score맞음:
            줄 += f"   ← 기대 {기대score}점"
        if not action맞음:
            줄 += f"   ← 기대 [{기대action}]"
        print(줄)
    print("=" * 78)
    if 틀림:
        print(f" !! 기대와 다른 결과 {틀림}건 — WEIGHTS / PII_LOW_CAP 을 확인하세요")
    else:
        print(f" 전부 의도대로 판정됩니다. ({len(사례들)}건)")
    print(" ※ 실제 문서로 돌려보고 이상하면 맨 위 WEIGHTS 숫자만 바꾸면 됩니다")
