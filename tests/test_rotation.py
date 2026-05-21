"""
AI QUANTUM — 포지션 로테이션 단위 테스트
정체 포지션 감지 및 스캐너 신호 교체 청산 기능 검증
"""
import pytest
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mock_exchange import MockBinanceClient
from core.engine import QuantumEngine, EngineState
from core.scanner import Scanner
from core.trader import AutoTrader
from core.config import CFG
from core.strategy import Signal


class TestPositionRotation:
    def setup_method(self):
        self.mock = MockBinanceClient()
        self.mock.load_markets()
        
        # 엔진 및 의존성 주입 초기화
        self.engine = QuantumEngine()
        self.engine.client = self.mock
        self.engine.scanner = Scanner(self.mock)
        self.engine.trader = AutoTrader(self.mock)
        self.engine.scanner.on_signal = self.engine.trader.on_signal
        self.engine.scanner.on_scan_complete = self.engine._check_closed_positions
        self.engine._initialized = True
        self.engine._state = EngineState.CONNECTED
        
        # 로테이션 강제 테스트 세팅
        self.cfg = CFG
        self.cfg.ROTATION_ENABLED = True
        self.cfg.ROTATION_MIN_SIGNALS = 3
        self.cfg.ROTATION_STALE_HOURS = 1.5
        self.cfg.ROTATION_FLOW_CHECK = "momentum"

    def test_rotation_executed_on_bad_momentum(self):
        """1안 모멘텀 이탈에 따라 정체 포지션 로테이션 청산이 성공적으로 수행되는지 검증"""
        # 1. 3개 이상의 진입 신호 생성 (교체 진입 대상)
        self.engine.scanner.scan_results = [
            {"symbol": "BTC/USDT:USDT", "signal": "long", "strength": 75},
            {"symbol": "ETH/USDT:USDT", "signal": "long", "strength": 70},
            {"symbol": "SOL/USDT:USDT", "signal": "long", "strength": 65},
        ]
        
        # 2. 2시간 경과된 롱 포지션 추가 (임계값 1.5시간 초과)
        two_hours_ago_ms = int(time.time() * 1000) - (2 * 3600 * 1000)
        pos = self.mock._make_position(
            symbol="DOGE/USDT:USDT",
            side="long",
            entry=0.15,
            mark=0.13,  # 현재가 < 진입가 (손실 상태)
            size=100.0,
        )
        pos["timestamp"] = two_hours_ago_ms
        self.mock._positions = [pos]
        
        # 3. 15분 EMA(20) 세팅 (EMA보다 가격이 아래에 있도록 가격 0.13 설정하고 EMA는 0.14로 생성)
        def mock_get_ohlcv(symbol, timeframe="15m", limit=50):
            import pandas as pd
            df = pd.DataFrame({
                "open": [0.14] * limit,
                "high": [0.14] * limit,
                "low": [0.14] * limit,
                "close": [0.14] * limit,
                "volume": [1000.0] * limit
            })
            return df
        
        self.mock.get_ohlcv = mock_get_ohlcv
        
        # 초기 포지션 1개 존재
        assert len(self.mock._positions) == 1
        
        # 4. 로테이션 감지 체크 실행
        self.engine._check_closed_positions()
        
        # 5. 로테이션으로 인해 포지션이 청산되었는지 확인
        assert len(self.mock._positions) == 0

    def test_no_rotation_on_insufficient_signals(self):
        """대기 중인 신호 개수가 부족하면 로테이션이 실행되지 않는지 검증"""
        # 대기 중인 신호가 1개뿐 (최소 3개 설정)
        self.engine.scanner.scan_results = [
            {"symbol": "BTC/USDT:USDT", "signal": "long", "strength": 75},
        ]
        
        two_hours_ago_ms = int(time.time() * 1000) - (2 * 3600 * 1000)
        pos = self.mock._make_position(
            symbol="DOGE/USDT:USDT",
            side="long",
            entry=0.15,
            mark=0.13,
            size=100.0,
        )
        pos["timestamp"] = two_hours_ago_ms
        self.mock._positions = [pos]
        
        # 15분 EMA 모의 반환
        def mock_get_ohlcv(symbol, timeframe="15m", limit=50):
            import pandas as pd
            return pd.DataFrame({
                "open": [0.14] * limit,
                "high": [0.14] * limit,
                "low": [0.14] * limit,
                "close": [0.14] * limit,
                "volume": [1000.0] * limit
            })
        self.mock.get_ohlcv = mock_get_ohlcv
        
        self.engine._check_closed_positions()
        
        # 신호 부족으로 청산되지 않고 유지되어야 함
        assert len(self.mock._positions) == 1

    def test_no_rotation_on_recent_position(self):
        """보유한지 얼마 되지 않은 포지션은 로테이션되지 않는지 검증"""
        self.engine.scanner.scan_results = [
            {"symbol": "BTC/USDT:USDT", "signal": "long", "strength": 75},
            {"symbol": "ETH/USDT:USDT", "signal": "long", "strength": 70},
            {"symbol": "SOL/USDT:USDT", "signal": "long", "strength": 65},
        ]
        
        # 30분 전 진입한 포지션 (임계값 1.5시간 미만)
        thirty_min_ago_ms = int(time.time() * 1000) - (30 * 60 * 1000)
        pos = self.mock._make_position(
            symbol="DOGE/USDT:USDT",
            side="long",
            entry=0.15,
            mark=0.13,
            size=100.0,
        )
        pos["timestamp"] = thirty_min_ago_ms
        self.mock._positions = [pos]
        
        # 15분 EMA 모의 반환
        def mock_get_ohlcv(symbol, timeframe="15m", limit=50):
            import pandas as pd
            return pd.DataFrame({
                "open": [0.14] * limit,
                "high": [0.14] * limit,
                "low": [0.14] * limit,
                "close": [0.14] * limit,
                "volume": [1000.0] * limit
            })
        self.mock.get_ohlcv = mock_get_ohlcv
        
        self.engine._check_closed_positions()
        
        # 보유시간 미달로 청산되지 않고 유지되어야 함
        assert len(self.mock._positions) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
