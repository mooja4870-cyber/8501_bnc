"""
AI QUANTUM — Chaos Engineering Test Harness
엔진의 복원력(Resilience) 및 서킷 브레이커 작동을 검증하는 카오스 테스트 하네스
"""
import pytest
import asyncio
import time
from unittest.mock import patch
from core.engine import QuantumEngine, EngineState
from core.mock_exchange import MockBinanceClient

@pytest.fixture
def engine():
    eng = QuantumEngine.get_instance()
    eng._state = EngineState.IDLE
    eng._initialized = False
    if eng.scanner:
        asyncio.run_coroutine_threadsafe(eng.scanner.stop(), eng._loop).result()
    if eng.trader:
        eng.trader.disable()
    yield eng

def test_engine_initialization_success(engine):
    """정상적인 상황에서의 초기화 성공 여부 검증 (Mock 주입)"""
    with patch('core.engine.BinanceClient') as MockClientClass:
        mock_instance = MockBinanceClient()
        asyncio.run_coroutine_threadsafe(mock_instance.load_markets(), engine._loop).result()
        mock_instance.set_scenario("default")
        
        MockClientClass.return_value = mock_instance
        
        success, msg = engine.initialize("API", "SEC", "PASS")
        
        assert success is True
        assert engine.state == EngineState.CONNECTED

def test_chaos_api_outage():
    """네트워크 단절(API Outage) 발생 시 에러 상태 전환 검증"""
    async def run_test():
        eng = QuantumEngine()
        
        mock = MockBinanceClient()
        await mock.load_markets()
        mock.set_scenario("default")
        
        eng.client = mock
        eng._initialized = True
        eng._state = EngineState.CONNECTED
        
        from core.scanner import Scanner
        from core.trader import AutoTrader
        eng.scanner = Scanner(mock)
        eng.trader = AutoTrader(mock)
        
        # 스캐너 구동 시도
        eng.scanner.start()
        
        try:
            # 카오스 주입: API 에러 발생 시나리오
            mock.set_scenario("api_error")
            
            # Dashboard 데이터를 가져올 때 에러가 발생하여 ERROR 상태로 전이되어야 함
            await eng._get_dashboard_data_async()
            
            assert eng.state == EngineState.ERROR
            assert "Mock API Error" in eng._error_msg
        finally:
            await eng.scanner.stop()

    asyncio.run(run_test())

def test_chaos_rate_limit_and_cooldown():
    """주문 실패 및 Rate Limit 발생 시 쿨다운 시스템 작동 검증"""
    async def run_test():
        eng = QuantumEngine()
        
        mock = MockBinanceClient()
        await mock.load_markets()
        mock.set_scenario("default")
        
        eng.client = mock
        eng._initialized = True
        eng._state = EngineState.CONNECTED
        
        from core.scanner import Scanner
        from core.trader import AutoTrader
        from core.strategy import Signal
        
        eng.trader = AutoTrader(mock)
        eng.trader.enable()
        
        # 쿨다운 트리거 (글로벌 10초)
        eng.trader.trigger_global_cooldown(10)
        
        sig = Signal(symbol="BTC/USDT:USDT", direction="long", strength=100, reason="test", 
                     ema_ok=True, macd_ok=True, bb_ok=True, rsi=40, rsi_ok=True, ema200=10, ema200_ok=True,
                     close=60000, bb_upper=61000, bb_lower=59000, macd_hist=100)
                     
        try:
            # 신호 전달
            await eng.trader.on_signal(sig)
            
            # 쿨다운 중이므로 주문이 거절되어야 함 (trade_log에 BLOCKED 기록)
            logs = await eng.trader.get_trade_log()
            assert len(logs) == 1
            assert logs[0]["status"] == "BLOCKED"
            assert "글로벌 쿨다운 진행 중" in logs[0]["reason"]
            
            # 종목별 쿨다운 테스트
            eng.trader.global_cooldown_until = None
            eng.trader.trigger_symbol_cooldown("BTC/USDT:USDT", 10)
            
            await eng.trader.on_signal(sig)
            logs = await eng.trader.get_trade_log()
            assert len(logs) == 2
            assert logs[0]["status"] == "BLOCKED"
            assert "종목별 쿨다운 진행 중" in logs[0]["reason"]
        finally:
            if eng.scanner:
                await eng.scanner.stop()

    asyncio.run(run_test())
