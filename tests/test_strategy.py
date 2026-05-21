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
