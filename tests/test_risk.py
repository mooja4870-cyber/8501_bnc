"""
AI QUANTUM — Risk Gate 단위 테스트
AutoTrader의 리스크 체크 로직을 시나리오별로 검증
"""
import pytest, sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mock_exchange import MockBinanceClient
from core.trader import AutoTrader
from core.strategy import Signal
from core.config import CFG


def _sig(symbol="BTC/USDT:USDT", direction="long", strength=100):
    return Signal(
        symbol=symbol, direction=direction, strength=strength,
        ema_ok=True, bb_ok=True, macd_ok=True,
        close=67000.0, ema200=66500.0, bb_upper=68000.0,
        bb_lower=66000.0, macd_hist=50.0, reason="test",
    )


class TestRiskGate:
    def setup_method(self):
        self.mock = MockBinanceClient()
        asyncio.run(self.mock.load_markets())
        self.trader = AutoTrader(self.mock)
        self.trader.enable()

    def test_pass_normal(self):
        self.mock.set_scenario("default")
        ok, r = asyncio.run(self.trader._risk_check(_sig()))
        assert ok and r == "OK"

    def test_block_low_balance(self):
        self.mock.set_scenario("low_balance")
        ok, r = asyncio.run(self.trader._risk_check(_sig()))
        assert not ok and "잔고 부족" in r

    def test_block_no_margin(self):
        self.mock.set_scenario("no_margin")
        ok, r = asyncio.run(self.trader._risk_check(_sig()))
        assert not ok and "증거금 부족" in r

    def test_block_weak_signal(self):
        self.mock.set_scenario("default")
        ok, r = asyncio.run(self.trader._risk_check(_sig(strength=40)))
        assert not ok and "강도 부족" in r

    def test_block_daily_loss(self):
        self.mock.set_scenario("default")
        self.trader.daily_pnl_usdt = -(CFG.DAILY_LOSS_LIMIT_USDT + 1)
        ok, r = asyncio.run(self.trader._risk_check(_sig()))
        assert not ok and "일일 손실 한도" in r

    def test_risk_gate_api_failure(self):
        self.mock.set_scenario("api_error")
        with pytest.raises(Exception, match="잔고 조회 실패"):
            asyncio.run(self.trader._risk_check(_sig()))

    def test_global_cooldown_blocks_entry(self):
        self.mock.set_scenario("default")
        self.trader.trigger_global_cooldown(60)
        ok, r = asyncio.run(self.trader._risk_check(_sig()))
        assert not ok and "글로벌 쿨다운" in r

        # 쿨다운 만료 후 통과하는지 확인
        import datetime as dt_mod
        self.trader.global_cooldown_until = dt_mod.datetime.now() - dt_mod.timedelta(seconds=1)
        ok, r = asyncio.run(self.trader._risk_check(_sig()))
        assert ok and r == "OK"

    def test_symbol_cooldown_blocks_entry(self):
        self.mock.set_scenario("default")
        self.trader.trigger_symbol_cooldown("BTC/USDT:USDT", 60)
        
        # 해당 종목은 쿨다운으로 진입 차단
        ok, r = asyncio.run(self.trader._risk_check(_sig(symbol="BTC/USDT:USDT")))
        assert not ok and "종목별 쿨다운" in r

        # 다른 종목은 쿨다운 미발생하여 통과
        ok, r = asyncio.run(self.trader._risk_check(_sig(symbol="ETH/USDT:USDT")))
        assert ok and r == "OK"

        # 쿨다운 만료 후 통과하는지 확인
        import datetime as dt_mod
        self.trader.symbol_cooldown_until["BTC/USDT:USDT"] = dt_mod.datetime.now() - dt_mod.timedelta(seconds=1)
        ok, r = asyncio.run(self.trader._risk_check(_sig(symbol="BTC/USDT:USDT")))
        assert ok and r == "OK"


class TestPositionGuards:
    def setup_method(self):
        self.mock = MockBinanceClient()
        asyncio.run(self.mock.load_markets())
        self.trader = AutoTrader(self.mock)
        self.trader.enable()

    def test_duplicate_skip(self):
        self.mock.set_scenario("with_positions")
        n = self.trader.orders_today
        asyncio.run(self.trader.on_signal(_sig(symbol="BTC/USDT:USDT")))
        assert self.trader.orders_today == n

    def test_max_positions_skip(self):
        self.mock.set_scenario("max_positions")
        n = self.trader.orders_today
        asyncio.run(self.trader.on_signal(_sig(symbol="NEW/USDT:USDT")))
        assert self.trader.orders_today == n

    def test_disabled_skip(self):
        self.mock.set_scenario("default")
        self.trader.disable()
        n = self.trader.orders_today
        asyncio.run(self.trader.on_signal(_sig()))
        assert self.trader.orders_today == n

    def test_long_blocked(self):
        self.mock.set_scenario("default")
        self.trader.allow_long = False
        n = self.trader.orders_today
        asyncio.run(self.trader.on_signal(_sig(direction="long")))
        assert self.trader.orders_today == n

    def test_short_blocked(self):
        self.mock.set_scenario("default")
        self.trader.allow_short = False
        n = self.trader.orders_today
        asyncio.run(self.trader.on_signal(_sig(direction="short")))
        assert self.trader.orders_today == n

    def test_position_check_api_failure(self):
        self.mock.set_scenario("api_error")
        asyncio.run(self.trader.on_signal(_sig()))
        log = asyncio.run(self.trader.get_trade_log())
        assert len(log) == 1
        assert log[0]["status"] == "FAILED"
        assert "조회 오류" in log[0]["reason"]


class TestOrderExecution:
    def setup_method(self):
        self.mock = MockBinanceClient()
        asyncio.run(self.mock.load_markets())
        self.trader = AutoTrader(self.mock)
        self.trader.enable()

    def test_long_order(self):
        self.mock.set_scenario("default")
        n = self.trader.orders_today
        asyncio.run(self.trader.on_signal(_sig(direction="long")))
        assert self.trader.orders_today == n + 1
        assert self.mock._positions[0]["side"] == "long"

    def test_short_order(self):
        self.mock.set_scenario("default")
        n = self.trader.orders_today
        asyncio.run(self.trader.on_signal(_sig(direction="short")))
        assert self.trader.orders_today == n + 1
        assert self.mock._positions[0]["side"] == "short"

    def test_api_failure(self):
        self.mock.set_scenario("default")
        self.mock._fail_next_order = True
        n = self.trader.orders_today
        asyncio.run(self.trader.on_signal(_sig()))
        assert self.trader.orders_today == n


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
