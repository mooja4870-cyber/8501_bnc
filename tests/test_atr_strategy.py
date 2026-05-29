"""
AI QUANTUM — ATR TP/SL 및 Chandelier Exit 기능 단위/통합 테스트
"""
import pytest
import sys
import os
import asyncio
import pandas as pd
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.strategy import StrategyEngine, Signal
from core.trader import AutoTrader
from core.engine import QuantumEngine, EngineState
from core.mock_exchange import MockBinanceClient
from core.config import CFG

class TestATRAndChandelierExit:
    def setup_method(self):
        self.cfg = CFG
        # 초기 설정 백업 및 기본 셋팅
        self.orig_use_atr = getattr(self.cfg, "USE_ATR_SL_TP", True)
        self.orig_atr_tp = getattr(self.cfg, "ATR_TP_MULT", 1.8)
        self.orig_atr_sl = getattr(self.cfg, "ATR_SL_MULT", 1.2)
        self.orig_use_ch = getattr(self.cfg, "USE_CHANDELIER_EXIT", True)
        self.orig_ch_mult = getattr(self.cfg, "CHANDELIER_MULT", 3.0)
        self.orig_slope = getattr(self.cfg, "MOMENTUM_SLOPE_THRESHOLD", 0.0)

        # 싱글톤 상태 백업
        self.engine_inst = QuantumEngine.get_instance()
        self.orig_scanner = self.engine_inst.scanner
        self.orig_client = self.engine_inst.client

    def teardown_method(self):
        # 설정 원상복구
        self.cfg.USE_ATR_SL_TP = self.orig_use_atr
        self.cfg.ATR_TP_MULT = self.orig_atr_tp
        self.cfg.ATR_SL_MULT = self.orig_atr_sl
        self.cfg.USE_CHANDELIER_EXIT = self.orig_use_ch
        self.cfg.CHANDELIER_MULT = self.orig_ch_mult
        self.cfg.MOMENTUM_SLOPE_THRESHOLD = self.orig_slope

        # 싱글톤 상태 복구
        self.engine_inst.scanner = self.orig_scanner
        self.engine_inst.client = self.orig_client

    def test_momentum_slope_filter(self, monkeypatch):
        """TTM 모멘텀 기울기 필터가 임계치 미달 신호를 차단하는지 검증"""
        engine = StrategyEngine()
        self.cfg.MOMENTUM_SLOPE_THRESHOLD = 0.5  # 임계치를 0.5로 설정

        timestamps = pd.date_range(end=pd.Timestamp.now(), periods=6, freq="15min")
        df_base = pd.DataFrame({
            "open": [100.0] * 6,
            "high": [101.0] * 6,
            "low": [99.0] * 6,
            "close": [100.0] * 6,
            "volume": [10000.0] * 6,
        }, index=timestamps)

        # 1. 롱 진입조건 충족 + 모멘텀 상승 기울기가 0.1 인 경우 (임계치 0.5 미달 -> 차단되어야 함)
        def mock_calc_slope_low(df_input):
            res = df_input.copy()
            res['ssl_up'] = 90.0
            res['ssl_down'] = 85.0
            res['macd_hist'] = [1.1, 1.2, 1.3, 1.4, 1.5]  # 마지막 변화율 = 0.1
            res['dot_color'] = ['red', 'red', 'red', 'red', 'green'] # squeeze_fired
            res['bb_upper'] = 2.0
            res['bb_lower'] = -2.0
            res['rsi'] = 50.0
            res['volume'] = 10000.0
            res['vol_ma'] = 5000.0
            return res

        monkeypatch.setattr(engine, "calculate_indicators", mock_calc_slope_low)
        sig_blocked = engine.generate_signal(df_base, "BTC/USDT:USDT")
        assert sig_blocked.direction == "none"
        assert "모멘텀 기울기" in sig_blocked.reason

        # 2. 롱 진입조건 충족 + 모멘텀 상승 기울기가 1.0 인 경우 (임계치 0.5 초과 -> 진입 허용)
        def mock_calc_slope_high(df_input):
            res = df_input.copy()
            res['ssl_up'] = 90.0
            res['ssl_down'] = 85.0
            res['macd_hist'] = [1.0, 1.0, 1.0, 1.0, 2.0]  # 마지막 변화율 = 1.0
            res['dot_color'] = ['red', 'red', 'red', 'red', 'green']
            res['bb_upper'] = 2.0
            res['bb_lower'] = -2.0
            res['rsi'] = 50.0
            res['volume'] = 10000.0
            res['vol_ma'] = 5000.0
            return res

        monkeypatch.setattr(engine, "calculate_indicators", mock_calc_slope_high)
        sig_ok = engine.generate_signal(df_base, "BTC/USDT:USDT")
        assert sig_ok.direction == "long"
        assert sig_ok.strength == 100

    @pytest.mark.asyncio
    async def test_dynamic_atr_sltp_calculation(self):
        """trader가 place_order를 트리거할 때 ATR 기반 손익절 비율이 정확히 계산되는지 검증"""
        mock_client = AsyncMock()
        mock_client.place_order = AsyncMock(return_value={"entry_price": 10000, "amount": 0.1, "order_id": "test_order"})
        mock_client.get_balance = AsyncMock(return_value={"total": 100, "free": 100})
        mock_client.get_positions = AsyncMock(return_value=[])

        trader = AutoTrader(mock_client)
        trader.enabled = True
        self.cfg.USE_ATR_SL_TP = True
        self.cfg.ATR_SL_MULT = 1.2
        self.cfg.ATR_TP_MULT = 1.8

        # ATR이 100 이고 진입 종가가 10000인 경우
        # atr_pct = 100 / 10000 = 0.01 (1%)
        # dynamic_sl_pct = 1.2 * 1% = 0.012 (1.2%)
        # dynamic_tp_pct = 1.8 * 1% = 0.018 (1.8%)
        sig = Signal(
            symbol="BTC/USDT:USDT", direction="long", strength=100,
            ema_ok=True, bb_ok=True, macd_ok=True,
            close=10000.0, ema200=9500.0, bb_upper=10200.0, bb_lower=9800.0,
            macd_hist=10.0, reason="test", rsi=50.0, rsi_ok=True, ema200_ok=True, atr=100.0
        )

        await trader.on_signal(sig)

        mock_client.place_order.assert_called_once()
        kwargs = mock_client.place_order.call_args[1]
        assert pytest.approx(kwargs["stop_loss_pct"]) == 0.012
        assert pytest.approx(kwargs["take_profit_pct"]) == 0.018

    @pytest.mark.asyncio
    async def test_chandelier_exit_trigger(self):
        """Chandelier Exit 조건 도달 시 시장가 청산이 격발되는지 검증"""
        engine = QuantumEngine.get_instance()
        engine.client = AsyncMock()
        engine.client.close_position = AsyncMock(return_value=True)

        engine.scanner = MagicMock()
        engine.scanner.get_results = AsyncMock(return_value=[
            {"symbol": "BTC/USDT:USDT", "atr": 100.0}
        ])

        self.cfg.USE_CHANDELIER_EXIT = True
        self.cfg.CHANDELIER_MULT = 3.0

        positions = [{
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "entry_price": 10000.0,
            "mark_price": 10500.0,
            "size": 0.1
        }]

        # 1단계: 최고점 10500 저장 및 trigger 10200 확인 -> 청산 미동작
        await engine._run_chandelier_exit_check_async(positions)
        engine.client.close_position.assert_not_called()
        assert engine._trailing_highs["BTC/USDT:USDT"] == 10500.0

        # 2단계: mark_price가 10100으로 하락 -> 청산 동작
        positions[0]["mark_price"] = 10100.0
        await engine._run_chandelier_exit_check_async(positions)
        engine.client.close_position.assert_called_once_with("BTC/USDT:USDT", "long")
