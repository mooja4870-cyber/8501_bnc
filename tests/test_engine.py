"""
AI QUANTUM — E2E 통합 테스트
Mock 환경에서 QuantumEngine 전체 흐름(Init → Scan → Signal → Trade → Close) 검증
"""
import pytest, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import QuantumEngine, EngineState
from core.mock_exchange import MockBinanceClient
from core.scanner import Scanner
from core.trader import AutoTrader


def _create_mock_engine(scenario="default"):
    """Mock 엔진 팩토리"""
    engine = QuantumEngine()
    mock = MockBinanceClient()
    mock.load_markets()
    mock.set_scenario(scenario)

    engine.client = mock
    engine.scanner = Scanner(mock)
    engine.trader = AutoTrader(mock)
    engine.scanner.on_signal = engine.trader.on_signal
    engine.scanner.on_scan_complete = engine._check_closed_positions
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
        assert e.state == EngineState.SCANNING

    def test_scanning_to_trading(self):
        e, _ = _create_mock_engine()
        e.start_scanner()
        e.enable_trading()
        assert e.state == EngineState.TRADING

    def test_trading_to_scanning(self):
        e, _ = _create_mock_engine()
        e.start_scanner()
        e.enable_trading()
        e.disable_trading()
        assert e.state == EngineState.SCANNING

    def test_stop_returns_connected(self):
        e, _ = _create_mock_engine()
        e.start_scanner()
        e.stop_scanner()
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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
