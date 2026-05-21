"""
AI QUANTUM — Risk Gate 단위 테스트
AutoTrader의 리스크 체크 로직을 시나리오별로 검증
"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mock_exchange import MockBinanceClient
from core.trader import AutoTrader
from core.strategy import Signal
from core.config import CFG


def _sig(symbol="BTC/USDT:USDT", direction="long", strength=90):
    return Signal(
        symbol=symbol, direction=direction, strength=strength,
        ema_ok=True, bb_ok=True, macd_ok=True,
        close=67000.0, ema200=66500.0, bb_upper=68000.0,
        bb_lower=66000.0, macd_hist=50.0, reason="test",
    )


class TestRiskGate:
    def setup_method(self):
        self.mock = MockBinanceClient()
        self.mock.load_markets()
        self.trader = AutoTrader(self.mock)
        self.trader.enable()

    def test_pass_normal(self):
        self.mock.set_scenario("default")
        ok, r = self.trader._risk_check(_sig())
        assert ok and r == "OK"

    def test_block_low_balance(self):
        self.mock.set_scenario("low_balance")
        ok, r = self.trader._risk_check(_sig())
        assert not ok and "잔고 부족" in r

    def test_block_no_margin(self):
        self.mock.set_scenario("no_margin")
        ok, r = self.trader._risk_check(_sig())
        assert not ok and "증거금 부족" in r

    def test_block_weak_signal(self):
        self.mock.set_scenario("default")
        ok, r = self.trader._risk_check(_sig(strength=40))
        assert not ok and "강도 부족" in r

    def test_block_daily_loss(self):
        self.mock.set_scenario("default")
        self.trader.daily_pnl_usdt = -(CFG.DAILY_LOSS_LIMIT_USDT + 1)
        ok, r = self.trader._risk_check(_sig())
        assert not ok and "일일 손실 한도" in r


class TestPositionGuards:
    def setup_method(self):
        self.mock = MockBinanceClient()
        self.mock.load_markets()
        self.trader = AutoTrader(self.mock)
        self.trader.enable()

    def test_duplicate_skip(self):
        self.mock.set_scenario("with_positions")
        n = self.trader.orders_today
        self.trader.on_signal(_sig(symbol="BTC/USDT:USDT"))
        assert self.trader.orders_today == n

    def test_max_positions_skip(self):
        self.mock.set_scenario("max_positions")
        n = self.trader.orders_today
        self.trader.on_signal(_sig(symbol="NEW/USDT:USDT"))
        assert self.trader.orders_today == n

    def test_disabled_skip(self):
        self.mock.set_scenario("default")
        self.trader.disable()
        n = self.trader.orders_today
        self.trader.on_signal(_sig())
        assert self.trader.orders_today == n

    def test_long_blocked(self):
        self.mock.set_scenario("default")
        self.trader.allow_long = False
        n = self.trader.orders_today
        self.trader.on_signal(_sig(direction="long"))
        assert self.trader.orders_today == n

    def test_short_blocked(self):
        self.mock.set_scenario("default")
        self.trader.allow_short = False
        n = self.trader.orders_today
        self.trader.on_signal(_sig(direction="short"))
        assert self.trader.orders_today == n


class TestOrderExecution:
    def setup_method(self):
        self.mock = MockBinanceClient()
        self.mock.load_markets()
        self.trader = AutoTrader(self.mock)
        self.trader.enable()

    def test_long_order(self):
        self.mock.set_scenario("default")
        n = self.trader.orders_today
        self.trader.on_signal(_sig(direction="long"))
        assert self.trader.orders_today == n + 1
        assert self.mock._positions[0]["side"] == "long"

    def test_short_order(self):
        self.mock.set_scenario("default")
        n = self.trader.orders_today
        self.trader.on_signal(_sig(direction="short"))
        assert self.trader.orders_today == n + 1
        assert self.mock._positions[0]["side"] == "short"

    def test_api_failure(self):
        self.mock.set_scenario("default")
        self.mock._fail_next_order = True
        n = self.trader.orders_today
        self.trader.on_signal(_sig())
        assert self.trader.orders_today == n


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
