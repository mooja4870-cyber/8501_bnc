"""
AI QUANTUM — Risk Gate 단위 테스트
AutoTrader의 리스크 체크 로직을 시나리오별로 검증
"""
import pytest
import sys
import os
import asyncio
import datetime as dt_mod

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


async def get_setup():
    mock = MockBinanceClient()
    await mock.load_markets()
    trader = AutoTrader(mock)
    trader.enable()
    return mock, trader


class TestRiskGate:

    @pytest.mark.asyncio
    async def test_pass_normal(self):
        mock, trader = await get_setup()
        mock.set_scenario("default")
        ok, r = await trader._risk_check(_sig())
        assert ok
        assert r == "OK"

    @pytest.mark.asyncio
    async def test_block_low_balance(self):
        mock, trader = await get_setup()
        mock.set_scenario("low_balance")
        ok, r = await trader._risk_check(_sig())
        assert not ok
        assert "잔고 부족" in r

    @pytest.mark.asyncio
    async def test_block_no_margin(self):
        mock, trader = await get_setup()
        mock.set_scenario("no_margin")
        ok, r = await trader._risk_check(_sig())
        assert not ok
        assert "증거금 부족" in r

    @pytest.mark.asyncio
    async def test_block_weak_signal(self):
        mock, trader = await get_setup()
        mock.set_scenario("default")
        ok, r = await trader._risk_check(_sig(strength=40))
        assert not ok
        assert "강도 부족" in r

    @pytest.mark.asyncio
    async def test_block_daily_loss(self):
        mock, trader = await get_setup()
        mock.set_scenario("default")
        trader.daily_pnl_usdt = -(CFG.DAILY_LOSS_LIMIT_USDT + 1)
        ok, r = await trader._risk_check(_sig())
        assert not ok
        assert "일일 손실 한도" in r

    @pytest.mark.asyncio
    async def test_risk_gate_api_failure(self):
        mock, trader = await get_setup()
        mock.set_scenario("api_error")
        with pytest.raises(Exception, match="잔고 조회 실패"):
            await trader._risk_check(_sig())

    @pytest.mark.asyncio
    async def test_global_cooldown_blocks_entry(self):
        mock, trader = await get_setup()
        mock.set_scenario("default")
        trader.trigger_global_cooldown(60)
        ok, r = await trader._risk_check(_sig())
        assert not ok
        assert "글로벌 쿨다운" in r

        # 쿨다운 만료 후 통과하는지 확인
        trader.global_cooldown_until = dt_mod.datetime.now() - dt_mod.timedelta(seconds=1)
        ok, r = await trader._risk_check(_sig())
        assert ok
        assert r == "OK"

    @pytest.mark.asyncio
    async def test_symbol_cooldown_blocks_entry(self):
        mock, trader = await get_setup()
        mock.set_scenario("default")
        trader.trigger_symbol_cooldown("BTC/USDT:USDT", 60)
        
        # 해당 종목은 쿨다운으로 진입 차단
        ok, r = await trader._risk_check(_sig(symbol="BTC/USDT:USDT"))
        assert not ok
        assert "종목별 쿨다운" in r

        # 다른 종목은 쿨다운 미발생하여 통과
        ok, r = await trader._risk_check(_sig(symbol="ETH/USDT:USDT"))
        assert ok
        assert r == "OK"

        # 쿨다운 만료 후 통과하는지 확인
        trader.symbol_cooldown_until["BTC/USDT:USDT"] = dt_mod.datetime.now() - dt_mod.timedelta(seconds=1)
        ok, r = await trader._risk_check(_sig(symbol="BTC/USDT:USDT"))
        assert ok
        assert r == "OK"


class TestPositionGuards:

    @pytest.mark.asyncio
    async def test_duplicate_skip(self):
        mock, trader = await get_setup()
        mock.set_scenario("with_positions")
        n = trader.orders_today
        await trader.on_signal(_sig(symbol="BTC/USDT:USDT"))
        assert trader.orders_today == n

    @pytest.mark.asyncio
    async def test_max_positions_skip(self):
        mock, trader = await get_setup()
        mock.set_scenario("max_positions")
        n = trader.orders_today
        await trader.on_signal(_sig(symbol="NEW/USDT:USDT"))
        assert trader.orders_today == n

    @pytest.mark.asyncio
    async def test_disabled_skip(self):
        mock, trader = await get_setup()
        mock.set_scenario("default")
        trader.disable()
        n = trader.orders_today
        await trader.on_signal(_sig())
        assert trader.orders_today == n

    @pytest.mark.asyncio
    async def test_long_blocked(self):
        mock, trader = await get_setup()
        mock.set_scenario("default")
        trader.allow_long = False
        n = trader.orders_today
        await trader.on_signal(_sig(direction="long"))
        assert trader.orders_today == n

    @pytest.mark.asyncio
    async def test_short_blocked(self):
        mock, trader = await get_setup()
        mock.set_scenario("default")
        trader.allow_short = False
        n = trader.orders_today
        await trader.on_signal(_sig(direction="short"))
        assert trader.orders_today == n

    @pytest.mark.asyncio
    async def test_position_check_api_failure(self):
        mock, trader = await get_setup()
        mock.set_scenario("api_error")
        await trader.on_signal(_sig())
        log = await trader.get_trade_log()
        assert len(log) == 1
        assert log[0]["status"] == "FAILED"
        assert "조회 오류" in log[0]["reason"]


class TestOrderExecution:

    @pytest.mark.asyncio
    async def test_long_order(self):
        mock, trader = await get_setup()
        mock.set_scenario("default")
        n = trader.orders_today
        await trader.on_signal(_sig(direction="long"))
        assert trader.orders_today == n + 1
        positions = await mock.get_positions()
        assert positions[0]["side"] == "long"

    @pytest.mark.asyncio
    async def test_short_order(self):
        mock, trader = await get_setup()
        mock.set_scenario("default")
        n = trader.orders_today
        await trader.on_signal(_sig(direction="short"))
        assert trader.orders_today == n + 1
        positions = await mock.get_positions()
        assert positions[0]["side"] == "short"

    @pytest.mark.asyncio
    async def test_api_failure(self):
        mock, trader = await get_setup()
        mock.set_scenario("default")
        mock._fail_next_order = True
        n = trader.orders_today
        await trader.on_signal(_sig())
        assert trader.orders_today == n
