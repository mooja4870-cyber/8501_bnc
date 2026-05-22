"""
AI QUANTUM — Strategy Signal 단위 테스트
알려진 OHLCV 데이터 → 예상 신호 매칭 (Gold File Test)
"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mock_exchange import MockBinanceClient
from core.strategy import StrategyEngine


class TestStrategySignals:
    def setup_method(self):
        self.engine = StrategyEngine()
        self.mock = MockBinanceClient()

    def test_indicator_calculation(self):
        """지표 계산 정상 동작"""
        df = self.mock.get_ohlcv("BTC/USDT:USDT", limit=300)
        result = self.engine.calculate_indicators(df)
        assert not result.empty
        for col in ["ssl_up", "ssl_down", "bb_upper", "bb_lower", "macd_hist"]:
            assert col in result.columns, f"누락된 지표: {col}"

    def test_insufficient_data(self):
        """데이터 부족 시 빈 신호 반환"""
        df = self.mock.get_ohlcv("BTC/USDT:USDT", limit=300).head(10)
        sig = self.engine.generate_signal(df, "BTC/USDT:USDT")
        assert sig.direction == "none"
        assert sig.strength == 0

    def test_signal_structure(self):
        """신호 객체 구조 검증"""
        df = self.mock.get_ohlcv("BTC/USDT:USDT", limit=300)
        sig = self.engine.generate_signal(df, "BTC/USDT:USDT")
        assert sig.symbol == "BTC/USDT:USDT"
        assert sig.direction in ("long", "short", "none")
        assert 0 <= sig.strength <= 100
        assert isinstance(bool(sig.ema_ok), bool)
        assert isinstance(bool(sig.bb_ok), bool)
        assert isinstance(bool(sig.macd_ok), bool)

    def test_strength_range(self):
        """강도는 0~100 범위"""
        for sym in ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]:
            df = self.mock.get_ohlcv(sym, limit=300)
            sig = self.engine.generate_signal(df, sym)
            assert 0 <= sig.strength <= 100

    def test_no_signal_has_reason(self):
        """미진입 신호도 reason이 존재"""
        df = self.mock.get_ohlcv("BTC/USDT:USDT", limit=300)
        sig = self.engine.generate_signal(df, "BTC/USDT:USDT")
        assert sig.reason and len(sig.reason) > 0

    def test_entry_conditions_and_rsi_blocking(self, monkeypatch):
        """
        포지션 진입을 위한 5대 조건 및 RSI 차단 로직 검증:
        1. 롱 진입 조건 100% 충족 및 RSI 정상 (< 60) -> 롱 진입 성공
        2. 롱 진입 조건 100% 충족했으나 RSI 과열 (>= 60) -> 진입 차단 (direction = "none", rsi_ok = False)
        3. 숏 진입 조건 100% 충족 및 RSI 정상 (> 40) -> 숏 진입 성공
        4. 숏 진입 조건 100% 충족했으나 RSI 과매도 (<= 40) -> 진입 차단 (direction = "none", rsi_ok = False)
        """
        import pandas as pd
        import numpy as np

        timestamps = pd.date_range(end=pd.Timestamp.now(), periods=5, freq="15min")
        df_base = pd.DataFrame({
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.0] * 5,
            "volume": [10000.0] * 5,
        }, index=timestamps)

        # 1. 롱 진입 100% 만족하는 지표 결과 Mocking
        def mock_calc_long(df_input):
            res = df_input.copy()
            res['ssl_up'] = 90.0
            res['ssl_down'] = 85.0
            res['macd_hist'] = 1.5
            res['dot_color'] = ['red', 'red', 'red', 'red', 'green']
            res['candle_color'] = ['blue', 'blue', 'blue', 'blue', 'blue']
            res['bb_upper'] = 2.0
            res['bb_lower'] = -2.0
            res['rsi'] = 50.0 # 정상
            return res

        # 2. 롱 진입 100% 만족 + RSI 과열 Mocking
        def mock_calc_long_rsi_blocked(df_input):
            res = mock_calc_long(df_input)
            res.loc[res.index[-1], 'rsi'] = 65.0 # 과열
            return res

        # 3. 숏 진입 100% 만족하는 지표 결과 Mocking
        def mock_calc_short(df_input):
            res = df_input.copy()
            res['ssl_up'] = 115.0
            res['ssl_down'] = 110.0
            res['macd_hist'] = -1.5
            res['dot_color'] = ['green', 'green', 'green', 'green', 'red']
            res['candle_color'] = ['red', 'red', 'red', 'red', 'red']
            res['bb_upper'] = 2.0
            res['bb_lower'] = -2.0
            res['rsi'] = 50.0 # 정상
            return res

        # 4. 숏 진입 100% 만족 + RSI 과매도 Mocking
        def mock_calc_short_rsi_blocked(df_input):
            res = mock_calc_short(df_input)
            res.loc[res.index[-1], 'rsi'] = 35.0 # 과매도
            return res

        # Case 1: 롱 진입조건 충족 + RSI 정상 (50.0) -> long 진입
        monkeypatch.setattr(self.engine, "calculate_indicators", mock_calc_long)
        sig_long_ok = self.engine.generate_signal(df_base, "BTC/USDT:USDT")
        assert sig_long_ok.direction == "long"
        assert sig_long_ok.rsi_ok is True
        assert sig_long_ok.strength == 100

        # Case 2: 롱 진입조건 충족 + RSI 과열 (65.0) -> none 진입차단
        monkeypatch.setattr(self.engine, "calculate_indicators", mock_calc_long_rsi_blocked)
        sig_long_blocked = self.engine.generate_signal(df_base, "BTC/USDT:USDT")
        assert sig_long_blocked.direction == "none"
        assert sig_long_blocked.rsi_ok is False
        assert "RSI 과열" in sig_long_blocked.reason
        assert sig_long_blocked.strength == 80

        # Case 3: 숏 진입조건 충족 + RSI 정상 (50.0) -> short 진입
        monkeypatch.setattr(self.engine, "calculate_indicators", mock_calc_short)
        sig_short_ok = self.engine.generate_signal(df_base, "BTC/USDT:USDT")
        assert sig_short_ok.direction == "short"
        assert sig_short_ok.rsi_ok is True
        assert sig_short_ok.strength == 100

        # Case 4: 숏 진입조건 충족 + RSI 과매도 (35.0) -> none 진입차단
        monkeypatch.setattr(self.engine, "calculate_indicators", mock_calc_short_rsi_blocked)
        sig_short_blocked = self.engine.generate_signal(df_base, "BTC/USDT:USDT")
        assert sig_short_blocked.direction == "none"
        assert sig_short_blocked.rsi_ok is False
        assert "RSI 과매도" in sig_short_blocked.reason
        assert sig_short_blocked.strength == 80

        # Case 5: USE_RSI_FILTER = False 일 때, 롱 진입조건 충족 + RSI 과열(65.0) 임에도 진입 허용 -> long 진입
        self.engine.cfg.USE_RSI_FILTER = False
        monkeypatch.setattr(self.engine, "calculate_indicators", mock_calc_long_rsi_blocked)
        sig_long_bypass = self.engine.generate_signal(df_base, "BTC/USDT:USDT")
        assert sig_long_bypass.direction == "long"
        assert sig_long_bypass.rsi_ok is True

        # Case 6: USE_RSI_FILTER = False 일 때, 숏 진입조건 충족 + RSI 과매도(35.0) 임에도 진입 허용 -> short 진입
        monkeypatch.setattr(self.engine, "calculate_indicators", mock_calc_short_rsi_blocked)
        sig_short_bypass = self.engine.generate_signal(df_base, "BTC/USDT:USDT")
        assert sig_short_bypass.direction == "short"
        assert sig_short_bypass.rsi_ok is True

        # 원복
        self.engine.cfg.USE_RSI_FILTER = True



class TestMockDataGeneration:
    def setup_method(self):
        self.mock = MockBinanceClient()

    def test_ohlcv_shape(self):
        """OHLCV 데이터 형태 검증"""
        df = self.mock.get_ohlcv("BTC/USDT:USDT", limit=250)
        assert len(df) == 250
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in df.columns

    def test_signal_ohlcv_long(self):
        """롱 패턴 OHLCV 생성"""
        df = self.mock.generate_signal_ohlcv("long", 300)
        assert len(df) == 300
        # 상승 추세: 마지막 close > 첫 close
        assert df["close"].iloc[-1] > df["close"].iloc[0]

    def test_signal_ohlcv_short(self):
        """숏 패턴 OHLCV 생성"""
        df = self.mock.generate_signal_ohlcv("short", 300)
        assert len(df) == 300
        assert df["close"].iloc[-1] < df["close"].iloc[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
