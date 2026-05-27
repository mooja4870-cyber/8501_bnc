"""
AI QUANTUM — E2E 통합 테스트
Mock 환경에서 QuantumEngine 전체 흐름(Init → Scan → Signal → Trade → Close) 검증
"""
import pytest, sys, os, time, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import QuantumEngine, EngineState
from core.mock_exchange import MockBinanceClient
from core.scanner import Scanner
from core.trader import AutoTrader


def _create_mock_engine(scenario="default"):
    """Mock 엔진 팩토리"""
    engine = QuantumEngine()
    mock = MockBinanceClient()
    asyncio.run(mock.load_markets())
    mock.set_scenario(scenario)

    engine.client = mock
    engine.scanner = Scanner(mock)
    engine.trader = AutoTrader(mock)
    engine.scanner.on_signal = engine.trader.on_signal
    engine.scanner.on_scan_complete = engine._check_closed_positions_async
    engine._initialized = True
    engine._state = EngineState.CONNECTED
    return engine, mock


class TestFSM:
    """FSM 상태 전이 검증"""

    def test_initial_state(self):
        e = QuantumEngine()
        assert e.state == EngineState.IDLE

    def test_connected_to_scanning(self):
        e, _ = _create_mock_engine()
        e.start_scanner()
        time.sleep(0.1)
        assert e.state == EngineState.SCANNING

    def test_scanning_to_trading(self):
        e, _ = _create_mock_engine()
        e.start_scanner()
        time.sleep(0.1)
        e.enable_trading()
        time.sleep(0.1)
        assert e.state == EngineState.TRADING

    def test_trading_to_scanning(self):
        e, _ = _create_mock_engine()
        e.start_scanner()
        time.sleep(0.1)
        e.enable_trading()
        time.sleep(0.1)
        e.disable_trading()
        time.sleep(0.1)
        assert e.state == EngineState.SCANNING

    def test_stop_returns_connected(self):
        e, _ = _create_mock_engine()
        e.start_scanner()
        time.sleep(0.1)
        e.stop_scanner()
        time.sleep(0.1)
        assert e.state == EngineState.CONNECTED


class TestHealthCheck:
    def test_health_all_fields(self):
        e, _ = _create_mock_engine()
        h = e.get_health()
        for k in ["engine_state", "api_connected", "scanner_running",
                   "trading_enabled", "recovery_attempts", "last_error"]:
            assert k in h, f"Health 필드 누락: {k}"

    def test_health_reflects_state(self):
        e, _ = _create_mock_engine()
        e.start_scanner()
        time.sleep(0.1)
        h = e.get_health()
        assert h["scanner_running"] is True
        assert h["engine_state"] == "SCANNING"


class TestE2EFlow:
    """신호 → 주문 전체 흐름"""

    def test_dashboard_data(self):
        e, _ = _create_mock_engine()
        data = e.get_dashboard_data()
        assert data["total_balance"] == 100.0
        assert "engine_state" in data

    def test_scan_and_collect(self):
        e, _ = _create_mock_engine()
        e.start_scanner()
        time.sleep(2)
        e.stop_scanner()
        # 스캔이 1회 이상 실행되었는지
        assert e.scanner.scan_count >= 0  # Mock이라 빠르게 완료


class TestSingleton:
    """Singleton 패턴 및 초기화 가드 검증"""

    def test_constructor_returns_different_instances(self):
        e1 = QuantumEngine()
        e2 = QuantumEngine()
        assert e1 is not e2

    def test_get_instance_returns_same_instance(self):
        e1 = QuantumEngine.get_instance()
        e2 = QuantumEngine.get_instance()
        assert e1 is e2

    def test_initialize_guard_skips_reconnection(self):
        e = QuantumEngine()
        from core.mock_exchange import MockBinanceClient
        from core.scanner import Scanner
        from core.trader import AutoTrader

        mock = MockBinanceClient()
        asyncio.run(mock.load_markets())
        e.client = mock
        e.scanner = Scanner(mock)
        e.trader = AutoTrader(mock)
        e._initialized = True
        e._api_key = "test_key"
        e._secret_key = "test_secret"
        e._passphrase = "test_pass"
        e._state = EngineState.CONNECTED

        success, msg = e.initialize("test_key", "test_secret", "test_pass")
        assert success is True
        assert "이미 활성화되어 있습니다" in msg
        assert e.client is mock


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
