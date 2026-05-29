"""
AI QUANTUM — 포지션 진입 파라미터 개별 검증 테스트 (v2 Async)
각 파라미터가 진입을 올바르게 허용/차단하는지 격리 검증

[검증 대상]
 1단계 전략: EMA200 추세 필터, AKMCD 영선(모멘텀), AKMCD 점전환(스퀴즈 Fired), RSI 필터
 2단계 리스크: 잔고, 강도, 증거금, 일일손실한도, 중복포지션, MAX_POSITIONS, 방향허용
"""
import pytest
import sys
import os
import pandas as pd
import numpy as np
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mock_exchange import MockBinanceClient
from core.trader import AutoTrader
from core.strategy import StrategyEngine, Signal
from core.config import CFG


# ═══════════════════════════════════════════════════
#  헬퍼 함수 및 Fixture
# ═══════════════════════════════════════════════════

def _make_signal(symbol="TEST/USDT:USDT", direction="long", strength=100, **kw):
    defaults = dict(
        ema_ok=True, bb_ok=True, macd_ok=True,
        close=100.0, ema200=99.0, bb_upper=102.0,
        bb_lower=98.0, macd_hist=1.0, reason="test",
        rsi=50.0, rsi_ok=True, ema200_ok=True,
    )
    defaults.update(kw)
    return Signal(symbol=symbol, direction=direction, strength=strength, **defaults)


def _make_long_indicators(df_input, rsi=50.0, ema200=90.0, squeeze_on_seq=None):
    """롱 4대 조건 100% 충족 (EMA200, MACD_hist > 0, Squeeze Fired)"""
    res = df_input.copy()
    res['macd_hist'] = 1.5
    res['rsi'] = rsi
    res['ema200'] = ema200
    res['atr'] = 1.0
    
    # squeeze_on 상태 제어
    if squeeze_on_seq is not None:
        res['squeeze_on'] = squeeze_on_seq
    else:
        # 기본값: ON -> OFF (Fired 전환)
        res['squeeze_on'] = [True, True, True, True, False]
    return res


def _make_short_indicators(df_input, rsi=50.0, ema200=110.0, squeeze_on_seq=None):
    """숏 4대 조건 100% 충족 (EMA200, MACD_hist < 0, Squeeze Fired)"""
    res = df_input.copy()
    res['macd_hist'] = -1.5
    res['rsi'] = rsi
    res['ema200'] = ema200
    res['atr'] = 1.0
    
    if squeeze_on_seq is not None:
        res['squeeze_on'] = squeeze_on_seq
    else:
        # 기본값: ON -> OFF (Fired 전환)
        res['squeeze_on'] = [True, True, True, True, False]
    return res


@pytest.fixture
def base_df():
    # iloc[:-1] 슬라이싱을 감안하여 6개 행 생성 (최종 완성 봉이 5번째 봉이 되도록 함)
    ts = pd.date_range(end=pd.Timestamp.now(), periods=6, freq="15min")
    return pd.DataFrame({
        "open": [100.0] * 6, "high": [101.0] * 6,
        "low": [99.0] * 6, "close": [100.0] * 6,
        "volume": [10000.0] * 6,
    }, index=ts)


@pytest.fixture
def engine():
    return StrategyEngine()


async def get_setup():
    mock = MockBinanceClient()
    await mock.load_markets()
    mock.set_scenario("default")
    t = AutoTrader(mock)
    t.enable()
    return mock, t


# ═══════════════════════════════════════════════════
#  1단계: 전략 신호 조건 검증
# ═══════════════════════════════════════════════════

class TestEMA200Filter:
    """EMA 200 장기 추세 필터 (롱: close > ema200, 숏: close < ema200)"""

    def test_long_above_ema200_pass(self, engine, base_df, monkeypatch):
        """롱: 현재가(100) > EMA200(90) → 통과"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_long_indicators(df, ema200=90.0))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "long"
        assert sig.ema200_ok is True

    def test_long_below_ema200_blocks(self, engine, base_df, monkeypatch):
        """롱: 현재가(100) < EMA200(110) → 차단"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_long_indicators(df, ema200=110.0))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction != "long"

    def test_short_below_ema200_pass(self, engine, base_df, monkeypatch):
        """숏: 현재가(100) < EMA200(110) → 통과"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_short_indicators(df, ema200=110.0))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "short"
        assert sig.ema200_ok is True

    def test_short_above_ema200_blocks(self, engine, base_df, monkeypatch):
        """숏: 현재가(100) > EMA200(90) → 차단"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_short_indicators(df, ema200=90.0))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction != "short"


class TestAKMCDZeroLineCondition:
    """AKMCD 영선 (히스토그램 방향) 필터"""

    def test_long_above_zero(self, engine, base_df, monkeypatch):
        """롱: macd_hist > 0 → 충족"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_long_indicators(df))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "long"

    def test_long_below_zero_blocks(self, engine, base_df, monkeypatch):
        """롱: macd_hist < 0 → 차단"""
        def mock(df):
            res = _make_long_indicators(df)
            res['macd_hist'] = -0.5
            return res
        monkeypatch.setattr(engine, "calculate_indicators", mock)
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction != "long"


class TestAKMCDDotTransitionCondition:
    """AKMCD 점 색상 전환 (스퀴즈 해제/Fired 상태) 필터"""

    def test_long_dot_transition(self, engine, base_df, monkeypatch):
        """스퀴즈 ON(True) -> OFF(False) 전환 포착 시 squeeze_fired(macd_ok) True"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_long_indicators(df))
        sig = engine.generate_signal(base_df, "T")
        assert sig.macd_ok is True  # macd_ok가 squeeze_fired와 매핑됨

    def test_long_no_transition_blocks(self, engine, base_df, monkeypatch):
        """스퀴즈 계속 해제 상태이며 최근 lookback 내 ON 이력이 없으면 차단"""
        def mock(df):
            # 계속 OFF(False) 상태여서 Fired 전환이 없음
            return _make_long_indicators(df, squeeze_on_seq=[False] * 5)
        monkeypatch.setattr(engine, "calculate_indicators", mock)
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction != "long"


class TestRSIFilter:
    """RSI 필터 (스퀴즈 미발생 상황에서만 작동)"""

    def test_long_rsi_normal_pass(self, engine, base_df, monkeypatch):
        """RSI=50 < 75 → 통과"""
        def mock(df):
            # 스퀴즈 Fired가 아닌 일반 상황 (RSI 필터 작동하도록 squeeze_on=False 고정 및 lookback 이력 없음)
            return _make_long_indicators(df, rsi=50.0, squeeze_on_seq=[False]*5)
        monkeypatch.setattr(engine, "calculate_indicators", mock)
        sig = engine.generate_signal(base_df, "T")
        assert bool(sig.rsi_ok) is True

    def test_long_rsi_overbought_blocks(self, engine, base_df, monkeypatch):
        """RSI=80 >= 75 → 차단 (스퀴즈 Fired가 아닌 경우)"""
        def mock(df):
            return _make_long_indicators(df, rsi=80.0, squeeze_on_seq=[False]*5)
        monkeypatch.setattr(engine, "calculate_indicators", mock)
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "none"
        assert bool(sig.rsi_ok) is False

    def test_rsi_filter_disabled_bypass(self, engine, base_df, monkeypatch):
        """RSI 필터 비활성화 시 초과해도 바이패스 통과"""
        engine.cfg.USE_RSI_FILTER = False
        def mock(df):
            return _make_long_indicators(df, rsi=80.0, squeeze_on_seq=[False]*5)
        monkeypatch.setattr(engine, "calculate_indicators", mock)
        sig = engine.generate_signal(base_df, "T")
        # RSI 필터가 꺼져있으므로 rsi_ok는 True가 됨
        assert sig.rsi_ok is True
        engine.cfg.USE_RSI_FILTER = True  # 원복


# ═══════════════════════════════════════════════════
#  2단계: 리스크 게이트 및 포지션 가드 검증
# ═══════════════════════════════════════════════════

class TestRiskGateParameters:
    """리스크 체크 개별 파라미터 검증 (비동기)"""

    @pytest.mark.asyncio
    async def test_balance_minimum(self):
        """잔고 < MIN_REQUIRED_BALANCE_USDT → 차단"""
        mock, trader = await get_setup()
        mock._balance = {"total": 0.5, "free": 0.5, "used": 0.0}
        ok, reason = await trader._risk_check(_make_signal())
        assert ok is False
        assert "잔고 부족" in reason

    @pytest.mark.asyncio
    async def test_signal_strength_minimum(self):
        """신호 강도 < 100% → 차단 (4대 조건 미충족)"""
        mock, trader = await get_setup()
        ok, reason = await trader._risk_check(_make_signal(strength=80))
        assert ok is False
        assert "강도 부족" in reason

    @pytest.mark.asyncio
    async def test_signal_strength_100_pass(self):
        """신호 강도 = 100% → 통과"""
        mock, trader = await get_setup()
        ok, reason = await trader._risk_check(_make_signal(strength=100))
        assert ok is True

    @pytest.mark.asyncio
    async def test_max_drawdown_blocks(self):
        """MAX_DRAWDOWN_PCT 초과 → 차단"""
        mock, trader = await get_setup()
        import core.stats as stats_store
        original_load = stats_store.load_stats
        stats_store.load_stats = lambda: {"seed_money": 100.0}
        mock._balance = {"total": 85.0, "free": 80.0, "used": 5.0}  # 15% 낙폭 > 10%
        ok, reason = await trader._risk_check(_make_signal())
        assert ok is False
        assert "최대 낙폭" in reason
        stats_store.load_stats = original_load  # 원복

    @pytest.mark.asyncio
    async def test_available_margin_insufficient(self):
        """가용 증거금 < MARGIN_USDT → 차단"""
        mock, trader = await get_setup()
        mock._balance = {"total": 50.0, "free": 1.0, "used": 49.0}
        ok, reason = await trader._risk_check(_make_signal())
        assert ok is False
        assert "증거금 부족" in reason

    @pytest.mark.asyncio
    async def test_daily_loss_limit(self):
        """일일 손실 한도 초과 → 차단"""
        mock, trader = await get_setup()
        trader.daily_pnl_usdt = -(CFG.DAILY_LOSS_LIMIT_USDT + 1)
        ok, reason = await trader._risk_check(_make_signal())
        assert ok is False
        assert "일일 손실 한도" in reason


class TestPositionGuardParameters:
    """포지션 가드 개별 파라미터 검증 (비동기)"""

    @pytest.mark.asyncio
    async def test_duplicate_position_blocked(self):
        """이미 보유 중인 종목 → 스킵"""
        mock, trader = await get_setup()
        mock.set_scenario("with_positions")
        before = trader.orders_today
        await trader.on_signal(_make_signal(symbol="BTC/USDT:USDT"))
        assert trader.orders_today == before

    @pytest.mark.asyncio
    async def test_max_positions_blocked(self):
        """MAX_POSITIONS 도달 → 스킵"""
        mock, trader = await get_setup()
        mock.set_scenario("max_positions")
        before = trader.orders_today
        await trader.on_signal(_make_signal(symbol="NEW/USDT:USDT"))
        assert trader.orders_today == before

    @pytest.mark.asyncio
    async def test_recently_entered_guard(self):
        """동일 종목 연속 진입 방지 (recently_entered 캐시)"""
        mock, trader = await get_setup()
        sig = _make_signal(symbol="SOL/USDT:USDT")
        await trader.on_signal(sig)
        assert trader.orders_today == 1
        # 같은 종목 재진입 시도 → 블락
        before = trader.orders_today
        await trader.on_signal(sig)
        assert trader.orders_today == before

    @pytest.mark.asyncio
    async def test_long_direction_blocked(self):
        """allow_long = False → 롱 스킵"""
        mock, trader = await get_setup()
        trader.allow_long = False
        before = trader.orders_today
        await trader.on_signal(_make_signal(direction="long"))
        assert trader.orders_today == before

    @pytest.mark.asyncio
    async def test_short_direction_blocked(self):
        """allow_short = False → 숏 스킵"""
        mock, trader = await get_setup()
        trader.allow_short = False
        before = trader.orders_today
        await trader.on_signal(_make_signal(direction="short"))
        assert trader.orders_today == before

    @pytest.mark.asyncio
    async def test_disabled_trader_blocked(self):
        """자동매매 비활성 → 전체 스킵"""
        mock, trader = await get_setup()
        trader.disable()
        before = trader.orders_today
        await trader.on_signal(_make_signal())
        assert trader.orders_today == before

    @pytest.mark.asyncio
    async def test_none_signal_ignored(self):
        """direction=none → 무시"""
        mock, trader = await get_setup()
        before = trader.orders_today
        await trader.on_signal(_make_signal(direction="none"))
        assert trader.orders_today == before

    @pytest.mark.asyncio
    async def test_margin_below_1_blocked(self):
        """증거금 설정 < $1 → 스킵"""
        mock, trader = await get_setup()
        original = CFG.MARGIN_USDT
        CFG.MARGIN_USDT = 0.5
        before = trader.orders_today
        await trader.on_signal(_make_signal())
        assert trader.orders_today == before
        CFG.MARGIN_USDT = original  # 원복


class TestMaxPositionsRaceCondition:
    """MAX_POSITIONS 레이스 컨디션 방지 검증 (비동기)"""

    @pytest.mark.asyncio
    async def test_sequential_signals_respect_max(self):
        """연속 신호 5개 → 정확히 MAX_POSITIONS(5)개만 진입"""
        mock, trader = await get_setup()
        symbols = [f"SYM{i}/USDT:USDT" for i in range(7)]
        # 7개 종목을 모두 마켓에 추가
        for sym in symbols:
            mock._markets[sym] = {
                "quote": "USDT", "type": "swap", "active": True,
                "contractSize": 1.0,
                "limits": {"leverage": {"max": 20}},
            }
        # 잔고를 넉넉하게 설정
        mock._balance = {"total": 500.0, "free": 400.0, "used": 100.0}

        for sym in symbols:
            await trader.on_signal(_make_signal(symbol=sym))

        assert trader.orders_today == CFG.MAX_POSITIONS
        assert len(await mock.get_positions()) == CFG.MAX_POSITIONS
