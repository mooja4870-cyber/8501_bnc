"""
AI QUANTUM — 포지션 진입 파라미터 개별 검증 테스트
각 파라미터가 진입을 올바르게 허용/차단하는지 격리 검증

[검증 대상]
 1단계 스캐너: MIN_VOLUME_USDT, MAX_SPREAD_PCT
 2단계 전략: SSL 추세, 캔들 색상, AKMCD 영선, AKMCD 점전환, EMA200, RSI, ADX 스위칭
 3단계 리스크: 잔고, 강도, 증거금, 일일손실한도, 중복포지션, MAX_POSITIONS, 방향허용
"""
import pytest
import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mock_exchange import MockBinanceClient
from core.trader import AutoTrader
from core.strategy import StrategyEngine, Signal
from core.config import CFG


# ═══════════════════════════════════════════════════
#  헬퍼
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


def _make_long_indicators(df_input, rsi=50.0, ema200=90.0):
    """롱 4대 조건 100% 충족 + 커스텀 RSI/EMA200"""
    res = df_input.copy()
    res['ssl_up'] = 90.0
    res['ssl_down'] = 85.0
    res['macd_hist'] = 1.5
    res['dot_color'] = ['red'] * (len(res) - 1) + ['green']
    res['candle_color'] = ['blue'] * len(res)
    res['bb_upper'] = 2.0
    res['bb_lower'] = -2.0
    res['rsi'] = rsi
    res['ema200'] = ema200
    res['adx'] = 30.0
    res['price_bb_upper'] = 200.0
    res['price_bb_lower'] = 0.0
    return res


def _make_short_indicators(df_input, rsi=50.0, ema200=110.0):
    """숏 4대 조건 100% 충족 + 커스텀 RSI/EMA200"""
    res = df_input.copy()
    res['ssl_up'] = 115.0
    res['ssl_down'] = 110.0
    res['macd_hist'] = -1.5
    res['dot_color'] = ['green'] * (len(res) - 1) + ['red']
    res['candle_color'] = ['red'] * len(res)
    res['bb_upper'] = 2.0
    res['bb_lower'] = -2.0
    res['rsi'] = rsi
    res['ema200'] = ema200
    res['adx'] = 30.0
    res['price_bb_upper'] = 200.0
    res['price_bb_lower'] = 0.0
    return res


@pytest.fixture
def base_df():
    ts = pd.date_range(end=pd.Timestamp.now(), periods=5, freq="15min")
    return pd.DataFrame({
        "open": [100.0] * 5, "high": [101.0] * 5,
        "low": [99.0] * 5, "close": [100.0] * 5,
        "volume": [10000.0] * 5,
    }, index=ts)


@pytest.fixture
def engine():
    return StrategyEngine()


@pytest.fixture
def trader():
    mock = MockBinanceClient()
    mock.load_markets()
    mock.set_scenario("default")
    t = AutoTrader(mock)
    t.enable()
    return t


# ═══════════════════════════════════════════════════
#  2단계: 전략 신호 — 4대 필수 조건 개별 검증
# ═══════════════════════════════════════════════════

class TestSSLTrendCondition:
    """조건 ①: SSL 추세 (35점)"""

    def test_long_ssl_pass(self, engine, base_df, monkeypatch):
        """현재가 > ssl_up → 롱 SSL 조건 충족"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_long_indicators(df))
        sig = engine.generate_signal(base_df, "T")
        assert sig.ema_ok == True  # SSL 추세 = ema_ok 필드

    def test_long_ssl_fail(self, engine, base_df, monkeypatch):
        """현재가 < ssl_up → 롱 SSL 조건 불충족"""
        def mock(df):
            res = _make_long_indicators(df)
            res['ssl_up'] = 200.0  # 현재가(100) < ssl_up(200)
            return res
        monkeypatch.setattr(engine, "calculate_indicators", mock)
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "none"

    def test_short_ssl_pass(self, engine, base_df, monkeypatch):
        """현재가 < ssl_down → 숏 SSL 조건 충족"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_short_indicators(df))
        sig = engine.generate_signal(base_df, "T")
        assert sig.ema_ok == True

    def test_short_ssl_fail(self, engine, base_df, monkeypatch):
        """현재가 > ssl_down → 숏 SSL 조건 불충족"""
        def mock(df):
            res = _make_short_indicators(df)
            res['ssl_down'] = 50.0  # 현재가(100) > ssl_down(50)
            return res
        monkeypatch.setattr(engine, "calculate_indicators", mock)
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction != "short"


class TestCandleColorCondition:
    """조건 ②: 캔들 색상 (20점)"""

    def test_long_candle_blue(self, engine, base_df, monkeypatch):
        """롱: 캔들 파란색 → 진입"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_long_indicators(df))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "long"

    def test_long_candle_red_blocks(self, engine, base_df, monkeypatch):
        """롱: 캔들 빨간색 → 진입 차단"""
        def mock(df):
            res = _make_long_indicators(df)
            res['candle_color'] = ['red'] * len(res)
            return res
        monkeypatch.setattr(engine, "calculate_indicators", mock)
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction != "long"


class TestAKMCDZeroLineCondition:
    """조건 ③: AKMCD 영선 (25점)"""

    def test_long_above_zero(self, engine, base_df, monkeypatch):
        """롱: 히스토그램 > 0 → 충족"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_long_indicators(df))
        sig = engine.generate_signal(base_df, "T")
        assert sig.macd_ok == True

    def test_long_below_zero_blocks(self, engine, base_df, monkeypatch):
        """롱: 히스토그램 < 0 → 차단"""
        def mock(df):
            res = _make_long_indicators(df)
            res['macd_hist'] = -1.0
            return res
        monkeypatch.setattr(engine, "calculate_indicators", mock)
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction != "long"


class TestAKMCDDotTransitionCondition:
    """조건 ④: AKMCD 점 색상 전환 (20점)"""

    def test_long_dot_transition(self, engine, base_df, monkeypatch):
        """롱: 이전 빨강 → 현재 초록 → 충족"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_long_indicators(df))
        sig = engine.generate_signal(base_df, "T")
        assert sig.bb_ok is True  # dot_transition = bb_ok 필드

    def test_long_no_transition_blocks(self, engine, base_df, monkeypatch):
        """롱: 이전/현재 모두 초록 → 전환 없음 → 차단"""
        def mock(df):
            res = _make_long_indicators(df)
            res['dot_color'] = ['green'] * len(res)  # 전환 없음
            return res
        monkeypatch.setattr(engine, "calculate_indicators", mock)
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction != "long"


# ═══════════════════════════════════════════════════
#  2단계: 전략 신호 — 추가 필터 개별 검증
# ═══════════════════════════════════════════════════

class TestEMA200Filter:
    """EMA 200 장기추세 필터"""

    def test_long_above_ema200_pass(self, engine, base_df, monkeypatch):
        """롱: 현재가(100) > EMA200(90) → 통과"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_long_indicators(df, ema200=90.0))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "long"

    def test_long_below_ema200_blocks(self, engine, base_df, monkeypatch):
        """롱: 현재가(100) < EMA200(200) → 차단"""
        def mock(df):
            return _make_long_indicators(df, ema200=200.0)
        monkeypatch.setattr(engine, "calculate_indicators", mock)
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction != "long"

    def test_short_below_ema200_pass(self, engine, base_df, monkeypatch):
        """숏: 현재가(100) < EMA200(110) → 통과"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_short_indicators(df, ema200=110.0))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "short"

    def test_short_above_ema200_blocks(self, engine, base_df, monkeypatch):
        """숏: 현재가(100) > EMA200(50) → 차단"""
        def mock(df):
            return _make_short_indicators(df, ema200=50.0)
        monkeypatch.setattr(engine, "calculate_indicators", mock)
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction != "short"


class TestRSIFilter:
    """RSI 과열/과매도 필터"""

    def test_long_rsi_normal_pass(self, engine, base_df, monkeypatch):
        """롱: RSI=50 < 60 → 통과"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_long_indicators(df, rsi=50.0))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "long"
        assert sig.rsi_ok is True

    def test_long_rsi_overbought_blocks(self, engine, base_df, monkeypatch):
        """롱: RSI=70 >= 60 → 차단"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_long_indicators(df, rsi=70.0))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "none"
        assert sig.rsi_ok is False

    def test_short_rsi_normal_pass(self, engine, base_df, monkeypatch):
        """숏: RSI=50 > 40 → 통과"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_short_indicators(df, rsi=50.0))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "short"
        assert sig.rsi_ok is True

    def test_short_rsi_oversold_blocks(self, engine, base_df, monkeypatch):
        """숏: RSI=30 <= 40 → 차단"""
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_short_indicators(df, rsi=30.0))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "none"
        assert sig.rsi_ok is False

    def test_rsi_filter_disabled_bypass(self, engine, base_df, monkeypatch):
        """RSI 필터 OFF → RSI 과열이어도 진입 허용"""
        engine.cfg.USE_RSI_FILTER = False
        monkeypatch.setattr(engine, "calculate_indicators",
                            lambda df: _make_long_indicators(df, rsi=70.0))
        sig = engine.generate_signal(base_df, "T")
        assert sig.direction == "long"
        engine.cfg.USE_RSI_FILTER = True  # 원복


# ═══════════════════════════════════════════════════
#  3단계: 리스크 게이트 — 파라미터별 격리 검증
# ═══════════════════════════════════════════════════

class TestRiskGateParameters:
    """리스크 체크 개별 파라미터 검증"""

    def setup_method(self):
        self.mock = MockBinanceClient()
        self.mock.load_markets()
        self.mock.set_scenario("default")
        self.trader = AutoTrader(self.mock)
        self.trader.enable()

    def test_balance_minimum(self):
        """잔고 < 10 USDT → 차단"""
        self.mock._balance = {"total": 5.0, "free": 5.0, "used": 0.0}
        ok, reason = self.trader._risk_check(_make_signal())
        assert ok is False
        assert "잔고 부족" in reason

    def test_signal_strength_minimum(self):
        """신호 강도 < 100% → 차단 (4대 조건 미충족)"""
        ok, reason = self.trader._risk_check(_make_signal(strength=80))
        assert ok is False
        assert "강도 부족" in reason

    def test_signal_strength_100_pass(self):
        """신호 강도 = 100% → 통과"""
        ok, reason = self.trader._risk_check(_make_signal(strength=100))
        assert ok is True

    def test_max_drawdown_blocks(self):
        """MAX_DRAWDOWN_PCT 초과 → 차단"""
        import core.stats as stats_store
        original_load = stats_store.load_stats
        stats_store.load_stats = lambda: {"seed_money": 100.0}
        self.mock._balance = {"total": 85.0, "free": 80.0, "used": 5.0}  # 15% 낙폭 > 10%
        ok, reason = self.trader._risk_check(_make_signal())
        assert ok is False
        assert "최대 낙폭" in reason
        stats_store.load_stats = original_load  # 원복

    def test_available_margin_insufficient(self):
        """가용 증거금 < MARGIN_USDT → 차단"""
        self.mock._balance = {"total": 50.0, "free": 1.0, "used": 49.0}
        ok, reason = self.trader._risk_check(_make_signal())
        assert ok is False
        assert "증거금 부족" in reason

    def test_daily_loss_limit(self):
        """일일 손실 한도 초과 → 차단"""
        self.trader.daily_pnl_usdt = -(CFG.DAILY_LOSS_LIMIT_USDT + 1)
        ok, reason = self.trader._risk_check(_make_signal())
        assert ok is False
        assert "일일 손실 한도" in reason


class TestPositionGuardParameters:
    """포지션 가드 개별 파라미터 검증"""

    def setup_method(self):
        self.mock = MockBinanceClient()
        self.mock.load_markets()
        self.mock.set_scenario("default")
        self.trader = AutoTrader(self.mock)
        self.trader.enable()

    def test_duplicate_position_blocked(self):
        """이미 보유 중인 종목 → 스킵"""
        self.mock.set_scenario("with_positions")
        before = self.trader.orders_today
        self.trader.on_signal(_make_signal(symbol="BTC/USDT:USDT"))
        assert self.trader.orders_today == before

    def test_max_positions_blocked(self):
        """MAX_POSITIONS 도달 → 스킵"""
        self.mock.set_scenario("max_positions")
        before = self.trader.orders_today
        self.trader.on_signal(_make_signal(symbol="NEW/USDT:USDT"))
        assert self.trader.orders_today == before

    def test_recently_entered_guard(self):
        """동일 종목 연속 진입 방지 (recently_entered 캐시)"""
        sig = _make_signal(symbol="SOL/USDT:USDT")
        self.trader.on_signal(sig)
        assert self.trader.orders_today == 1
        # 같은 종목 재진입 시도 → 블락
        before = self.trader.orders_today
        self.trader.on_signal(sig)
        assert self.trader.orders_today == before

    def test_long_direction_blocked(self):
        """allow_long = False → 롱 스킵"""
        self.trader.allow_long = False
        before = self.trader.orders_today
        self.trader.on_signal(_make_signal(direction="long"))
        assert self.trader.orders_today == before

    def test_short_direction_blocked(self):
        """allow_short = False → 숏 스킵"""
        self.trader.allow_short = False
        before = self.trader.orders_today
        self.trader.on_signal(_make_signal(direction="short"))
        assert self.trader.orders_today == before

    def test_disabled_trader_blocked(self):
        """자동매매 비활성 → 전체 스킵"""
        self.trader.disable()
        before = self.trader.orders_today
        self.trader.on_signal(_make_signal())
        assert self.trader.orders_today == before

    def test_none_signal_ignored(self):
        """direction=none → 무시"""
        before = self.trader.orders_today
        self.trader.on_signal(_make_signal(direction="none"))
        assert self.trader.orders_today == before

    def test_margin_below_1_blocked(self):
        """증거금 설정 < $1 → 스킵"""
        original = CFG.MARGIN_USDT
        CFG.MARGIN_USDT = 0.5
        before = self.trader.orders_today
        self.trader.on_signal(_make_signal())
        assert self.trader.orders_today == before
        CFG.MARGIN_USDT = original  # 원복


class TestMaxPositionsRaceCondition:
    """MAX_POSITIONS 레이스 컨디션 방지 검증"""

    def setup_method(self):
        self.mock = MockBinanceClient()
        self.mock.load_markets()
        self.mock.set_scenario("default")
        self.trader = AutoTrader(self.mock)
        self.trader.enable()

    def test_sequential_signals_respect_max(self):
        """연속 신호 5개 → 정확히 MAX_POSITIONS(5)개만 진입"""
        symbols = [f"SYM{i}/USDT:USDT" for i in range(7)]
        # 7개 종목을 모두 마켓에 추가
        for sym in symbols:
            self.mock._markets[sym] = {
                "quote": "USDT", "type": "swap", "active": True,
                "contractSize": 1.0,
                "limits": {"leverage": {"max": 20}},
            }
        # 잔고를 넉넉하게 설정
        self.mock._balance = {"total": 500.0, "free": 400.0, "used": 100.0}

        for sym in symbols:
            self.trader.on_signal(_make_signal(symbol=sym))

        assert self.trader.orders_today == CFG.MAX_POSITIONS
        assert len(self.mock.get_positions()) == CFG.MAX_POSITIONS


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
