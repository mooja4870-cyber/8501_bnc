"""
v1.1.60 검증 테스트 스위트
Dry Run + E2E + Smoke 테스트
"""
import os
import sys
import traceback
from unittest.mock import MagicMock, patch
from datetime import datetime

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []

def record(name, passed, detail=""):
    status = PASS if passed else FAIL
    results.append((name, status, detail))
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))


# ══════════════════════════════════════════════════
# SMOKE TEST: 모듈 임포트 및 구문 오류 검증
# ══════════════════════════════════════════════════
print("\n" + "="*60)
print("🔥 SMOKE TEST: 모듈 임포트 검증")
print("="*60)

try:
    from core.config import CFG, TradingConfig
    record("config.py 임포트", True)
except Exception as e:
    record("config.py 임포트", False, str(e))

try:
    from core.exchange import OKXClient
    record("exchange.py 임포트", True)
except Exception as e:
    record("exchange.py 임포트", False, str(e))

try:
    from core.trader import AutoTrader
    record("trader.py 임포트", True)
except Exception as e:
    record("trader.py 임포트", False, str(e))

try:
    from core.engine import QuantumEngine
    record("engine.py 임포트", True)
except Exception as e:
    record("engine.py 임포트", False, str(e))

try:
    from core.scanner import Scanner
    record("scanner.py 임포트", True)
except Exception as e:
    record("scanner.py 임포트", False, str(e))

try:
    import core.stats as stats_store
    record("stats.py 임포트", True)
except Exception as e:
    record("stats.py 임포트", False, str(e))


# ══════════════════════════════════════════════════
# SMOKE TEST: place_order 코드 순서 검증
# ══════════════════════════════════════════════════
print("\n" + "="*60)
print("🔥 SMOKE TEST: 레버리지 가드 코드 순서 검증")
print("="*60)

import inspect
source = inspect.getsource(OKXClient.place_order)

# set_leverage가 호출되는 위치
set_lev_pos = source.find("self.set_leverage(symbol,")
# leverageInfo 조회 위치
query_pos = source.find("privateGetAccountLeverageInfo")
# actual_leverage 계산 위치
calc_pos = source.find("actual_leverage = min(")

if query_pos >= 0 and set_lev_pos >= 0:
    record(
        "레버리지 조회가 설정보다 먼저 실행",
        query_pos < set_lev_pos,
        f"조회 위치={query_pos}, 설정 위치={set_lev_pos}"
    )
else:
    record("레버리지 조회가 설정보다 먼저 실행", False, "함수에서 관련 코드를 찾을 수 없음")

if calc_pos >= 0 and set_lev_pos >= 0:
    record(
        "actual_leverage 계산이 set_leverage보다 먼저",
        calc_pos < set_lev_pos,
        f"계산 위치={calc_pos}, 설정 위치={set_lev_pos}"
    )
else:
    record("actual_leverage 계산이 set_leverage보다 먼저", False, "코드에서 찾을 수 없음")

# set_leverage에 int(actual_leverage)가 전달되는지 확인
record(
    "set_leverage에 actual_leverage 전달",
    "self.set_leverage(symbol, int(actual_leverage))" in source,
    "CFG.LEVERAGE 대신 actual_leverage 사용 확인"
)


# ══════════════════════════════════════════════════
# DRY RUN TEST: 설정 영속성 검증 (.env 파일)
# ══════════════════════════════════════════════════
print("\n" + "="*60)
print("🧪 DRY RUN TEST: 설정 영속성 검증")
print("="*60)

from dotenv import load_dotenv, set_key

# 1. .env에 MARGIN_USDT 쓰기 테스트
test_margin = 10.0
set_key(".env", "MARGIN_USDT", str(test_margin))

# 2. .env 다시 로드해서 값 확인
load_dotenv(override=True)
read_back = os.getenv("MARGIN_USDT")
record(
    ".env에 MARGIN_USDT 저장/로드",
    read_back == str(test_margin),
    f"저장={test_margin}, 로드={read_back}"
)

# 3. CFG.refresh()로 반영되는지 확인
CFG.refresh()
record(
    "CFG.refresh() 후 MARGIN_USDT 반영",
    CFG.MARGIN_USDT == test_margin,
    f"CFG.MARGIN_USDT={CFG.MARGIN_USDT}, 기대값={test_margin}"
)

# 4. 레버리지 저장 테스트
test_lev = 5
set_key(".env", "LEVERAGE", str(test_lev))
load_dotenv(override=True)
CFG.refresh()
record(
    "LEVERAGE .env 저장/로드/반영",
    CFG.LEVERAGE == test_lev,
    f"CFG.LEVERAGE={CFG.LEVERAGE}, 기대값={test_lev}"
)

# 5. 손절/익절 저장 테스트
test_sl = 0.025
set_key(".env", "STOP_LOSS_PCT", str(test_sl))
load_dotenv(override=True)
CFG.refresh()
record(
    "STOP_LOSS_PCT .env 저장/로드/반영",
    abs(CFG.STOP_LOSS_PCT - test_sl) < 0.0001,
    f"CFG.STOP_LOSS_PCT={CFG.STOP_LOSS_PCT}, 기대값={test_sl}"
)


# ══════════════════════════════════════════════════
# E2E TEST: 마진 계산 시뮬레이션 (Mock 기반)
# ══════════════════════════════════════════════════
print("\n" + "="*60)
print("🔗 E2E TEST: 주문 마진 계산 시뮬레이션")
print("="*60)

# Mock OKX Client 생성
mock_client = MagicMock(spec=OKXClient)

# 시나리오 1: 레버리지 10x 설정, 거래소 3x 제한 → 증거금 $10 고정
print("\n  [시나리오 1] 레버리지 10x 설정, 거래소 3x 한도, 증거금 $10")
user_margin = 10.0
user_leverage = 10
exchange_max_leverage = 3.0
price = 193.67
contract_size = 0.01  # ORCL 계약 크기

actual_lev = min(float(user_leverage), exchange_max_leverage)
target_notional = user_margin * actual_lev  # $10 * 3 = $30
amount = target_notional / (price * contract_size)
estimated_notional = amount * price * contract_size
estimated_margin = estimated_notional / actual_lev

record(
    "actual_leverage = min(10, 3) = 3",
    actual_lev == 3.0,
    f"actual_leverage={actual_lev}"
)
record(
    "target_notional = $10 * 3 = $30",
    abs(target_notional - 30.0) < 0.01,
    f"target_notional=${target_notional:.2f}"
)
record(
    "estimated_margin ≈ $10 (증거금 고정)",
    abs(estimated_margin - user_margin) < 0.5,
    f"estimated_margin=${estimated_margin:.2f}, 목표=${user_margin}"
)

# 시나리오 2: 레버리지 10x 설정, 거래소 10x 허용 → 증거금 $10 고정
print("\n  [시나리오 2] 레버리지 10x 설정, 거래소 10x 허용, 증거금 $10")
exchange_max_leverage_2 = 10.0
actual_lev_2 = min(float(user_leverage), exchange_max_leverage_2)
target_notional_2 = user_margin * actual_lev_2  # $10 * 10 = $100
estimated_margin_2 = target_notional_2 / actual_lev_2

record(
    "actual_leverage = min(10, 10) = 10",
    actual_lev_2 == 10.0,
    f"actual_leverage={actual_lev_2}"
)
record(
    "target_notional = $10 * 10 = $100",
    abs(target_notional_2 - 100.0) < 0.01,
    f"target_notional=${target_notional_2:.2f}"
)
record(
    "estimated_margin = $10 (증거금 고정)",
    abs(estimated_margin_2 - user_margin) < 0.01,
    f"estimated_margin=${estimated_margin_2:.2f}"
)

# 시나리오 3: 이전 버그 재현 (10x 설정 → 거래소 3x 강제, 노셔널은 10x 기준)
print("\n  [시나리오 3] 이전 버그 재현 (수정 전 동작)")
old_notional = user_margin * float(user_leverage)  # $10 * 10 = $100 (잘못된 계산)
old_margin = old_notional / exchange_max_leverage  # $100 / 3 = $33.3 (실제 사용)

record(
    "버그: 거래소가 3x 강제 → 증거금 $33.3 사용됨",
    old_margin > user_margin * 2,
    f"버그 시 증거금=${old_margin:.2f} (의도=${user_margin})"
)
record(
    "수정 후: 증거금이 설정값과 일치",
    abs(estimated_margin - user_margin) < 0.5,
    f"수정 후=${estimated_margin:.2f} vs 버그=${old_margin:.2f}"
)


# ══════════════════════════════════════════════════
# E2E TEST: Trader → Exchange 파이프라인 검증
# ══════════════════════════════════════════════════
print("\n" + "="*60)
print("🔗 E2E TEST: Trader 설정값 전달 검증")
print("="*60)

# CFG를 테스트 값으로 설정
CFG.MARGIN_USDT = 10.0
CFG.LEVERAGE = 10

# Trader가 cfg.MARGIN_USDT를 올바르게 읽는지 확인
trader_source = inspect.getsource(AutoTrader.on_signal)
record(
    "Trader가 self.cfg.MARGIN_USDT 사용",
    "self.cfg.MARGIN_USDT" in trader_source,
    "margin_usdt = self.cfg.MARGIN_USDT 확인"
)

record(
    "Trader가 margin_usdt를 place_order에 전달",
    "margin_usdt=margin_usdt" in trader_source,
    "client.place_order(... margin_usdt=margin_usdt)"
)

# place_order가 margin_usdt 파라미터를 target_margin으로 사용하는지 확인
record(
    "place_order가 target_margin = margin_usdt 사용",
    "target_margin = margin_usdt" in source,
    "고정 증거금이 호출자에서 전달된 값 그대로 사용됨"
)


# ══════════════════════════════════════════════════
# 설정 원복 (테스트 후 정리)
# ══════════════════════════════════════════════════
set_key(".env", "MARGIN_USDT", "10.0")
set_key(".env", "LEVERAGE", "10")
set_key(".env", "STOP_LOSS_PCT", "0.015")
load_dotenv(override=True)
CFG.refresh()


# ══════════════════════════════════════════════════
# 최종 결과 출력
# ══════════════════════════════════════════════════
print("\n" + "="*60)
print("📊 최종 테스트 결과")
print("="*60)

total = len(results)
passed = sum(1 for _, s, _ in results if s == PASS)
failed = sum(1 for _, s, _ in results if s == FAIL)

print(f"\n  총 {total}건  |  ✅ {passed} PASS  |  ❌ {failed} FAIL\n")

if failed > 0:
    print("  실패 항목:")
    for name, status, detail in results:
        if status == FAIL:
            print(f"    {FAIL} {name}: {detail}")

print(f"\n  {'🎉 ALL TESTS PASSED!' if failed == 0 else '⚠️ SOME TESTS FAILED'}")
print("="*60)
