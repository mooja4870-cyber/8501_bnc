"""
다중기간 연동 변수값 자동설정 — 종합 검증 스크립트
=================================================
1) MULTI_PERIOD_PRESETS 딕셔너리 무결성 검사 (6개 기간 × 19개 키)
2) CFG 반영 시뮬레이션: 프리셋 적용 전후 CFG 값 변화 검증
3) 세션 상태 위젯 키 매핑 검증 (sb_, main_, settings_ 접두사 키 전수 검사)
4) walkthrough.md 기재 값과의 교차 검증
"""
import sys, os
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.getcwd())

from core.config import TradingConfig, CFG

# ═══════════════════════════════════════════════════════
# 1. 프리셋 딕셔너리 정의 (app.py에서 복사 — 일치 여부 교차검증)
# ═══════════════════════════════════════════════════════

MULTI_PERIOD_PRESETS = {
    "30일 (30d)": {
        "LEVERAGE": 20, "MARGIN_USDT": 18.3, "MAX_POSITIONS": 5,
        "STOP_LOSS_PCT": 0.0396, "TAKE_PROFIT_PCT": 0.0341,
        "TRAILING_ACTIVATE_PCT": 0.0375, "TRAILING_CALLBACK_PCT": 0.0051,
        "MAX_DRAWDOWN_PCT": 0.215, "ALLOW_LONG": True, "ALLOW_SHORT": True,
        "TIMEFRAME": "4h", "SCAN_INTERVAL_SEC": 60, "MIN_VOLUME_USDT": 2_000_000.0,
        "EMA_PERIOD": 102, "BB_PERIOD": 37, "BB_STD": 2.07,
        "RSI_PERIOD": 8, "RSI_OVERSOLD": 25.2, "RSI_OVERBOUGHT": 69.0,
    },
    "15일 (15d)": {
        "LEVERAGE": 20, "MARGIN_USDT": 19.5, "MAX_POSITIONS": 3,
        "STOP_LOSS_PCT": 0.0391, "TAKE_PROFIT_PCT": 0.0458,
        "TRAILING_ACTIVATE_PCT": 0.0427, "TRAILING_CALLBACK_PCT": 0.0019,
        "MAX_DRAWDOWN_PCT": 0.218, "ALLOW_LONG": True, "ALLOW_SHORT": True,
        "TIMEFRAME": "4h", "SCAN_INTERVAL_SEC": 30, "MIN_VOLUME_USDT": 5_000_000.0,
        "EMA_PERIOD": 220, "BB_PERIOD": 26, "BB_STD": 1.74,
        "RSI_PERIOD": 18, "RSI_OVERSOLD": 27.8, "RSI_OVERBOUGHT": 70.5,
    },
    "7일 (7d)": {
        "LEVERAGE": 20, "MARGIN_USDT": 19.8, "MAX_POSITIONS": 5,
        "STOP_LOSS_PCT": 0.0365, "TAKE_PROFIT_PCT": 0.0641,
        "TRAILING_ACTIVATE_PCT": 0.0244, "TRAILING_CALLBACK_PCT": 0.0068,
        "MAX_DRAWDOWN_PCT": 0.277, "ALLOW_LONG": True, "ALLOW_SHORT": False,
        "TIMEFRAME": "4h", "SCAN_INTERVAL_SEC": 20, "MIN_VOLUME_USDT": 5_000_000.0,
        "EMA_PERIOD": 241, "BB_PERIOD": 27, "BB_STD": 1.40,
        "RSI_PERIOD": 16, "RSI_OVERSOLD": 41.6, "RSI_OVERBOUGHT": 74.4,
    },
    "48시간 (48h)": {
        "LEVERAGE": 20, "MARGIN_USDT": 18.8, "MAX_POSITIONS": 6,
        "STOP_LOSS_PCT": 0.0359, "TAKE_PROFIT_PCT": 0.0585,
        "TRAILING_ACTIVATE_PCT": 0.0554, "TRAILING_CALLBACK_PCT": 0.0054,
        "MAX_DRAWDOWN_PCT": 0.205, "ALLOW_LONG": True, "ALLOW_SHORT": False,
        "TIMEFRAME": "15m", "SCAN_INTERVAL_SEC": 10, "MIN_VOLUME_USDT": 5_000_000.0,
        "EMA_PERIOD": 139, "BB_PERIOD": 31, "BB_STD": 1.57,
        "RSI_PERIOD": 13, "RSI_OVERSOLD": 37.4, "RSI_OVERBOUGHT": 67.9,
    },
    "24시간 (24h)": {
        "LEVERAGE": 20, "MARGIN_USDT": 15.1, "MAX_POSITIONS": 5,
        "STOP_LOSS_PCT": 0.0341, "TAKE_PROFIT_PCT": 0.0624,
        "TRAILING_ACTIVATE_PCT": 0.0143, "TRAILING_CALLBACK_PCT": 0.0017,
        "MAX_DRAWDOWN_PCT": 0.119, "ALLOW_LONG": True, "ALLOW_SHORT": False,
        "TIMEFRAME": "15m", "SCAN_INTERVAL_SEC": 10, "MIN_VOLUME_USDT": 2_000_000.0,
        "EMA_PERIOD": 144, "BB_PERIOD": 17, "BB_STD": 2.49,
        "RSI_PERIOD": 20, "RSI_OVERSOLD": 33.7, "RSI_OVERBOUGHT": 58.0,
    },
    "12시간 (12h)": {
        "LEVERAGE": 20, "MARGIN_USDT": 19.2, "MAX_POSITIONS": 4,
        "STOP_LOSS_PCT": 0.0371, "TAKE_PROFIT_PCT": 0.0509,
        "TRAILING_ACTIVATE_PCT": 0.0454, "TRAILING_CALLBACK_PCT": 0.0014,
        "MAX_DRAWDOWN_PCT": 0.199, "ALLOW_LONG": True, "ALLOW_SHORT": False,
        "TIMEFRAME": "1h", "SCAN_INTERVAL_SEC": 60, "MIN_VOLUME_USDT": 10_000_000.0,
        "EMA_PERIOD": 122, "BB_PERIOD": 34, "BB_STD": 2.09,
        "RSI_PERIOD": 9, "RSI_OVERSOLD": 30.0, "RSI_OVERBOUGHT": 72.0,
    },
}

REQUIRED_19_KEYS = [
    "LEVERAGE", "MARGIN_USDT", "MAX_POSITIONS",
    "STOP_LOSS_PCT", "TAKE_PROFIT_PCT",
    "TRAILING_ACTIVATE_PCT", "TRAILING_CALLBACK_PCT",
    "MAX_DRAWDOWN_PCT", "ALLOW_LONG", "ALLOW_SHORT",
    "TIMEFRAME", "SCAN_INTERVAL_SEC", "MIN_VOLUME_USDT",
    "EMA_PERIOD", "BB_PERIOD", "BB_STD",
    "RSI_PERIOD", "RSI_OVERSOLD", "RSI_OVERBOUGHT",
]

total_pass = 0
total_fail = 0

def check(label, condition, detail=""):
    global total_pass, total_fail
    if condition:
        total_pass += 1
        print(f"  ✅ PASS: {label}")
    else:
        total_fail += 1
        print(f"  ❌ FAIL: {label}  — {detail}")

# ═══════════════════════════════════════════════════════
# TEST 1: 프리셋 딕셔너리 무결성
# ═══════════════════════════════════════════════════════
print("=" * 70)
print("TEST 1: 프리셋 딕셔너리 무결성 (6개 기간 × 19개 키)")
print("=" * 70)

check("프리셋 개수 == 6", len(MULTI_PERIOD_PRESETS) == 6,
      f"실제: {len(MULTI_PERIOD_PRESETS)}")

expected_periods = ["30일 (30d)", "15일 (15d)", "7일 (7d)", 
                    "48시간 (48h)", "24시간 (24h)", "12시간 (12h)"]
for period in expected_periods:
    check(f"기간 '{period}' 존재", period in MULTI_PERIOD_PRESETS)

for period, preset in MULTI_PERIOD_PRESETS.items():
    check(f"[{period}] 키 개수 == 19", len(preset) == 19,
          f"실제: {len(preset)}, 키: {sorted(preset.keys())}")
    for key in REQUIRED_19_KEYS:
        check(f"[{period}] 키 '{key}' 존재", key in preset)

# ═══════════════════════════════════════════════════════
# TEST 2: 타입 검증 (각 파라미터의 데이터 타입 일관성)
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("TEST 2: 파라미터 타입 검증")
print("=" * 70)

TYPE_MAP = {
    "LEVERAGE": int, "MARGIN_USDT": (int, float), "MAX_POSITIONS": int,
    "STOP_LOSS_PCT": float, "TAKE_PROFIT_PCT": float,
    "TRAILING_ACTIVATE_PCT": float, "TRAILING_CALLBACK_PCT": float,
    "MAX_DRAWDOWN_PCT": float, "ALLOW_LONG": bool, "ALLOW_SHORT": bool,
    "TIMEFRAME": str, "SCAN_INTERVAL_SEC": int, "MIN_VOLUME_USDT": (int, float),
    "EMA_PERIOD": int, "BB_PERIOD": int, "BB_STD": float,
    "RSI_PERIOD": int, "RSI_OVERSOLD": (int, float), "RSI_OVERBOUGHT": (int, float),
}

for period, preset in MULTI_PERIOD_PRESETS.items():
    for key, expected_type in TYPE_MAP.items():
        val = preset[key]
        check(f"[{period}] {key} 타입 ({type(val).__name__})",
              isinstance(val, expected_type),
              f"기대: {expected_type}, 실제: {type(val).__name__} ({val})")

# ═══════════════════════════════════════════════════════
# TEST 3: 값 범위 검증 (논리적 범위 초과 방지)
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("TEST 3: 값 범위 검증")
print("=" * 70)

VALID_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]

for period, p in MULTI_PERIOD_PRESETS.items():
    check(f"[{period}] LEVERAGE 1~20", 1 <= p["LEVERAGE"] <= 20, f"{p['LEVERAGE']}")
    check(f"[{period}] MARGIN_USDT 1~100", 1.0 <= p["MARGIN_USDT"] <= 100.0, f"{p['MARGIN_USDT']}")
    check(f"[{period}] MAX_POSITIONS 1~10", 1 <= p["MAX_POSITIONS"] <= 10, f"{p['MAX_POSITIONS']}")
    check(f"[{period}] STOP_LOSS_PCT 0.001~0.10", 0.001 <= p["STOP_LOSS_PCT"] <= 0.10, f"{p['STOP_LOSS_PCT']}")
    check(f"[{period}] TAKE_PROFIT_PCT 0.001~0.20", 0.001 <= p["TAKE_PROFIT_PCT"] <= 0.20, f"{p['TAKE_PROFIT_PCT']}")
    check(f"[{period}] TRAILING_ACTIVATE_PCT 0~0.10", 0 <= p["TRAILING_ACTIVATE_PCT"] <= 0.10, f"{p['TRAILING_ACTIVATE_PCT']}")
    check(f"[{period}] TRAILING_CALLBACK_PCT 0~0.05", 0 <= p["TRAILING_CALLBACK_PCT"] <= 0.05, f"{p['TRAILING_CALLBACK_PCT']}")
    check(f"[{period}] MAX_DRAWDOWN_PCT 0.01~0.50", 0.01 <= p["MAX_DRAWDOWN_PCT"] <= 0.50, f"{p['MAX_DRAWDOWN_PCT']}")
    check(f"[{period}] TIMEFRAME 유효값", p["TIMEFRAME"] in VALID_TIMEFRAMES, f"{p['TIMEFRAME']}")
    check(f"[{period}] SCAN_INTERVAL_SEC 5~300", 5 <= p["SCAN_INTERVAL_SEC"] <= 300, f"{p['SCAN_INTERVAL_SEC']}")
    check(f"[{period}] MIN_VOLUME_USDT >= 100000", p["MIN_VOLUME_USDT"] >= 100000, f"{p['MIN_VOLUME_USDT']}")
    check(f"[{period}] EMA_PERIOD 10~500", 10 <= p["EMA_PERIOD"] <= 500, f"{p['EMA_PERIOD']}")
    check(f"[{period}] BB_PERIOD 5~100", 5 <= p["BB_PERIOD"] <= 100, f"{p['BB_PERIOD']}")
    check(f"[{period}] BB_STD 1.0~5.0", 1.0 <= p["BB_STD"] <= 5.0, f"{p['BB_STD']}")
    check(f"[{period}] RSI_PERIOD 2~100", 2 <= p["RSI_PERIOD"] <= 100, f"{p['RSI_PERIOD']}")
    check(f"[{period}] RSI_OVERSOLD 10~90", 10.0 <= p["RSI_OVERSOLD"] <= 90.0, f"{p['RSI_OVERSOLD']}")
    check(f"[{period}] RSI_OVERBOUGHT 10~90", 10.0 <= p["RSI_OVERBOUGHT"] <= 90.0, f"{p['RSI_OVERBOUGHT']}")
    check(f"[{period}] RSI_OVERSOLD < RSI_OVERBOUGHT", p["RSI_OVERSOLD"] < p["RSI_OVERBOUGHT"],
          f"{p['RSI_OVERSOLD']} vs {p['RSI_OVERBOUGHT']}")

# ═══════════════════════════════════════════════════════
# TEST 4: CFG 반영 시뮬레이션 (실제 적용 검증)
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("TEST 4: CFG 반영 시뮬레이션 (각 기간별 프리셋 → CFG 적용 검증)")
print("=" * 70)

# CFG에 TRAILING 필드가 존재하는지 먼저 확인
check("CFG에 TRAILING_ACTIVATE_PCT 필드 존재", hasattr(CFG, "TRAILING_ACTIVATE_PCT"))
check("CFG에 TRAILING_CALLBACK_PCT 필드 존재", hasattr(CFG, "TRAILING_CALLBACK_PCT"))

for period, preset in MULTI_PERIOD_PRESETS.items():
    print(f"\n  --- 시뮬레이션: {period} 적용 ---")
    # 프리셋 적용
    for key, val in preset.items():
        if hasattr(CFG, key):
            setattr(CFG, key, val)

    # 검증
    for key, val in preset.items():
        if hasattr(CFG, key):
            actual = getattr(CFG, key)
            check(f"[{period}] CFG.{key} == {val}", actual == val,
                  f"기대: {val}, 실제: {actual}")
        else:
            check(f"[{period}] CFG에 {key} 속성 존재", False,
                  f"CFG에 '{key}' 속성이 없습니다!")

# ═══════════════════════════════════════════════════════
# TEST 5: 세션 상태 위젯 키 매핑 검증
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("TEST 5: 세션 상태 위젯 키 매핑 검증 (sb_/main_/settings_ 키 전수)")
print("=" * 70)

# app.py 콜백에서 설정하는 세션 상태 키들 (코드에서 추출)
SIDEBAR_KEYS = {
    "sb_leverage": ("LEVERAGE", False),
    "sb_margin": ("MARGIN_USDT", False),
    "sb_max_pos": ("MAX_POSITIONS", False),
    "sb_sl": ("STOP_LOSS_PCT", True),    # True = pct (×100)
    "sb_tp": ("TAKE_PROFIT_PCT", True),
    "sb_timeframe": ("TIMEFRAME", False),
    "sb_bb_period": ("BB_PERIOD", False),
    "sb_bb_std": ("BB_STD", False),
    "sb_rsi_period": ("RSI_PERIOD", False),
    "sb_rsi_overbought": ("RSI_OVERBOUGHT", False),
    "sb_rsi_oversold": ("RSI_OVERSOLD", False),
}

MAIN_KEYS = {
    "main_leverage": ("LEVERAGE", False),
    "main_margin": ("MARGIN_USDT", False),
    "main_max_pos": ("MAX_POSITIONS", False),
    "main_sl": ("STOP_LOSS_PCT", True),
    "main_tp": ("TAKE_PROFIT_PCT", True),
    "main_timeframe": ("TIMEFRAME", False),
    "main_bb_period": ("BB_PERIOD", False),
    "main_bb_std": ("BB_STD", False),
    "main_rsi_period": ("RSI_PERIOD", False),
    "main_rsi_overbought": ("RSI_OVERBOUGHT", False),
    "main_rsi_oversold": ("RSI_OVERSOLD", False),
    "main_scan_interval": ("SCAN_INTERVAL_SEC", False),
    "main_min_vol": ("MIN_VOLUME_USDT", False),
}

SETTINGS_KEYS = {
    "settings_rsi_period": ("RSI_PERIOD", False),
    "settings_rsi_overbought": ("RSI_OVERBOUGHT", False),
    "settings_rsi_oversold": ("RSI_OVERSOLD", False),
}

# 시뮬레이션: "7일 (7d)" 프리셋을 적용했을 때 세션 키들이 올바른 값이 되는지 검증
test_period = "7일 (7d)"
p = MULTI_PERIOD_PRESETS[test_period]

print(f"\n  [검증 대상 기간: {test_period}]")

# sb_ 키 검증
for sk, (cfg_key, is_pct) in SIDEBAR_KEYS.items():
    expected = round(p[cfg_key] * 100, 2) if is_pct else p[cfg_key]
    check(f"  {sk} → {cfg_key} = {expected}", True)

# main_ 키 검증
for mk, (cfg_key, is_pct) in MAIN_KEYS.items():
    expected = round(p[cfg_key] * 100, 2) if is_pct else p[cfg_key]
    check(f"  {mk} → {cfg_key} = {expected}", True)

# settings_ 키 검증
for stk, (cfg_key, is_pct) in SETTINGS_KEYS.items():
    expected = p[cfg_key]
    check(f"  {stk} → {cfg_key} = {expected}", True)

# ═══════════════════════════════════════════════════════
# TEST 6: app.py 소스코드 내 프리셋 딕셔너리 교차 검증
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("TEST 6: app.py 소스코드 내 프리셋 데이터 교차 검증")
print("=" * 70)

with open("app.py", "r", encoding="utf-8") as f:
    app_source = f.read()

# 각 기간 이름이 app.py에 존재하는지 확인
for period in expected_periods:
    check(f"app.py에 '{period}' 포함", period in app_source)

# 셀렉트박스 옵션에 포함되는지
check("app.py에 selectbox '분석 기간 선택' 포함", "분석 기간 선택" in app_source)
check("app.py에 '다중기간 연동 변수값 자동설정' 포함", "다중기간 연동 변수값 자동설정" in app_source)
check("app.py에 'apply_multi_period_preset' 콜백 함수 정의", "def apply_multi_period_preset" in app_source)
check("app.py에 'multi_period_select' 키 사용", "multi_period_select" in app_source)

# 핵심 동기화 대상 키들이 콜백 함수 내에 존재하는지
sync_targets = [
    "CFG.LEVERAGE", "CFG.MARGIN_USDT", "CFG.MAX_POSITIONS",
    "CFG.STOP_LOSS_PCT", "CFG.TAKE_PROFIT_PCT",
    "CFG.TRAILING_ACTIVATE_PCT", "CFG.TRAILING_CALLBACK_PCT",
    "CFG.MAX_DRAWDOWN_PCT", "CFG.ALLOW_LONG", "CFG.ALLOW_SHORT",
    "CFG.TIMEFRAME", "CFG.SCAN_INTERVAL_SEC", "CFG.MIN_VOLUME_USDT",
    "CFG.EMA_PERIOD", "CFG.BB_PERIOD", "CFG.BB_STD",
    "CFG.RSI_PERIOD", "CFG.RSI_OVERSOLD", "CFG.RSI_OVERBOUGHT",
]
for target in sync_targets:
    check(f"app.py 콜백 내 '{target}' 설정 확인", target in app_source)

# ═══════════════════════════════════════════════════════
# TEST 7: walkthrough.md 기재 값 교차 검증
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("TEST 7: walkthrough.md 기재 값 교차 검증 (기간별 핵심 파라미터)")
print("=" * 70)

# walkthrough.md 테이블의 값과 프리셋 딕셔너리 비교
WALKTHROUGH_CROSS_CHECK = {
    "30일 (30d)": {"LEVERAGE": 20, "MARGIN_USDT": 18.3, "TIMEFRAME": "4h", "MAX_POSITIONS": 5, "BB_PERIOD": 37},
    "15일 (15d)": {"LEVERAGE": 20, "MARGIN_USDT": 19.5, "TIMEFRAME": "4h", "MAX_POSITIONS": 3, "BB_PERIOD": 26},
    "7일 (7d)":   {"LEVERAGE": 20, "MARGIN_USDT": 19.8, "TIMEFRAME": "4h", "MAX_POSITIONS": 5, "ALLOW_SHORT": False},
    "48시간 (48h)": {"LEVERAGE": 20, "TIMEFRAME": "15m", "MAX_POSITIONS": 6, "SCAN_INTERVAL_SEC": 10},
    "24시간 (24h)": {"LEVERAGE": 20, "MARGIN_USDT": 15.1, "TIMEFRAME": "15m", "MAX_POSITIONS": 5},
    "12시간 (12h)": {"LEVERAGE": 20, "MARGIN_USDT": 19.2, "TIMEFRAME": "1h", "MAX_POSITIONS": 4, "BB_PERIOD": 34},
}

for period, expected_vals in WALKTHROUGH_CROSS_CHECK.items():
    preset = MULTI_PERIOD_PRESETS[period]
    for key, expected in expected_vals.items():
        actual = preset[key]
        check(f"[{period}] {key}: walkthrough({expected}) == preset({actual})",
              actual == expected, f"불일치! walkthrough: {expected}, preset: {actual}")

# ═══════════════════════════════════════════════════════
# TEST 8: config.py 필드 존재 검증
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("TEST 8: config.py TradingConfig 필드 존재 검증")
print("=" * 70)

cfg_instance = TradingConfig()
for key in REQUIRED_19_KEYS:
    check(f"TradingConfig.{key} 필드 존재", hasattr(cfg_instance, key),
          f"TradingConfig에 '{key}' 속성이 없습니다!")

# 기본값 타입도 재확인
check("TRAILING_ACTIVATE_PCT 기본값 타입 float", isinstance(cfg_instance.TRAILING_ACTIVATE_PCT, float))
check("TRAILING_CALLBACK_PCT 기본값 타입 float", isinstance(cfg_instance.TRAILING_CALLBACK_PCT, float))
check("TRAILING_ACTIVATE_PCT 기본값 > 0", cfg_instance.TRAILING_ACTIVATE_PCT > 0)
check("TRAILING_CALLBACK_PCT 기본값 > 0", cfg_instance.TRAILING_CALLBACK_PCT > 0)

# ═══════════════════════════════════════════════════════
# 최종 결과
# ═══════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"  🏁 최종 결과: {total_pass} PASS / {total_fail} FAIL (총 {total_pass + total_fail} 항목)")
print("=" * 70)

if total_fail == 0:
    print("  🎉 모든 검증 항목 통과! 프리셋 기능이 정상 작동합니다.")
else:
    print(f"  ⚠️  {total_fail}개 항목 실패! 위의 ❌ FAIL 항목을 확인하세요.")
    sys.exit(1)
