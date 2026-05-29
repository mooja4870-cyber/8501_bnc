# AI QUANTUM - Test Harness (v2 Async Compatible)
# 실제 UI(Streamlit) 없이 엔진의 핵심 로직을 독립적으로 검증하는 하네스
# --mock 플래그로 실 API 없이 전체 흐름 테스트 가능
import time
import os
import argparse
import asyncio
from dotenv import load_dotenv
from core.engine import QuantumEngine

def run_harness(use_mock: bool = False):
    print("=" * 60)
    print(f"  AI QUANTUM - Test Harness {'[MOCK MODE]' if use_mock else '[LIVE MODE]'}")
    print("=" * 60)

    engine = QuantumEngine()
    # 엔진의 백그라운드 이벤트 루프가 뜰 때까지 잠시 대기
    time.sleep(0.5)

    if use_mock:
        from core.mock_exchange import MockBinanceClient
        mock = MockBinanceClient()
        # mock.load_markets()는 async 메서드이므로 엔진 루프에서 실행 후 대기
        asyncio.run_coroutine_threadsafe(mock.load_markets(), engine._loop).result()
        mock.set_scenario("default")

        engine.client = mock
        from core.scanner import Scanner
        from core.trader import AutoTrader
        engine.scanner = Scanner(mock)
        engine.trader = AutoTrader(mock)
        engine.scanner.on_signal = engine.trader.on_signal
        engine.scanner.on_scan_complete = engine._check_closed_positions_async
        engine._initialized = True
        print("[INIT] Mock Engine Initialized (Async)")
    else:
        load_dotenv(override=True)
        api_key = os.getenv("BINANCE_API_KEY")
        secret_key = os.getenv("BINANCE_SECRET_KEY")
        passphrase = os.getenv("BINANCE_PASSPHRASE") or ""
        if not api_key or not secret_key:
            print("[ERR] BINANCE_API_KEY and BINANCE_SECRET_KEY not found in .env.")
            return
        success, msg = engine.initialize(api_key, secret_key, passphrase)
        print(f"[INIT] {msg}")
        if not success:
            return

    # -- 테스트 1: 대시보드 데이터 --
    print(f"\n{'-' * 40}")
    print("[TEST 1] Dashboard Data")
    data = engine.get_dashboard_data()
    print(f"  Balance: ${data.get('total_balance', 0):,.2f} USDT")
    print(f"  Free:    ${data.get('free_margin', 0):,.2f} USDT")
    print(f"  Positions: {len(data.get('positions', []))}")
    print(f"  Engine State: {engine.state.name}")
    assert data.get("total_balance", 0) > 0, "잔고가 0"
    print("  PASS")

    # -- 테스트 2: 스캐너 구동 --
    print(f"\n{'-' * 40}")
    print("[TEST 2] Scanner Run")
    engine.start_scanner()
    print(f"  Engine State: {engine.state.name}")
    time.sleep(3 if use_mock else 5)
    results = engine.get_scan_results()
    print(f"  Scan Results: {len(results)} items")
    if results:
        print(f"  Top: {results[0]['symbol']} (Strength: {results[0]['strength']}%)")
    print("  PASS")

    # -- 테스트 3: 자동매매 토글 --
    print(f"\n{'-' * 40}")
    print("[TEST 3] Trading Toggle")
    engine.enable_trading()
    assert engine.trader.enabled, "매매 활성화 실패"
    print(f"  Trading: ENABLED | State: {engine.state.name}")
    engine.disable_trading()
    assert not engine.trader.enabled, "매매 비활성화 실패"
    print(f"  Trading: DISABLED")
    print("  PASS")

    # -- 테스트 4: 엔진 종료 --
    print(f"\n{'-' * 40}")
    print("[TEST 4] Engine Shutdown")
    engine.stop_scanner()
    print(f"  Engine State: {engine.state.name}")
    print("  PASS")

    print(f"\n{'=' * 60}")
    print("  All harness tests completed! PASS")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI QUANTUM Test Harness")
    parser.add_argument("--mock", action="store_true", help="Mock 모드 (실 API 불필요)")
    args = parser.parse_args()
    run_harness(use_mock=args.mock)
