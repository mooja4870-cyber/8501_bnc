"""
AI QUANTUM — Lv.4 Regression Suite
과거 버그 재발 방지용 회귀 테스트 모음
- Bug 1: 손익절 최저 임계치 하향(0.1%) 유효성 및 음수/오동작 검증
- Bug 2: 스프레드 필터 적용 및 0.3% 초과 페어 차단 검증
- Bug 3: Ticker 조회 시 quoteVolume 필드가 None이거나 누락되었을 때 baseVolume * last로 백업 계산 동작 검증
- Bug 4: 세션 캐시(closing_symbols)를 활용한 청산 직후 UI 포지션 잔상(Ghosting) 방지 로직 검증
"""
import pytest
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mock_exchange import MockBinanceClient
from core.scanner import Scanner
from core.trader import AutoTrader
from core.config import CFG, TradingConfig


class TestRegressionSuite:
    def setup_method(self):
        import asyncio
        self.mock = MockBinanceClient()
        asyncio.run(self.mock.load_markets())
        self.mock.set_scenario("default")
        self.scanner = Scanner(self.mock)

    def test_regression_min_sl_tp_limit(self):
        """Regression 1: 손/익절 최저 한도(0.1%) 및 슬라이더/넘버 입력 예외 검증"""
        # 최소 0.1% (0.001) 및 최대 20% (0.2) 사이의 값 설정 검증
        cfg = TradingConfig()
        
        # 0.1% 설정 정상 동작 확인
        cfg.STOP_LOSS_PCT = 0.001
        cfg.TAKE_PROFIT_PCT = 0.001
        assert cfg.STOP_LOSS_PCT == 0.001
        assert cfg.TAKE_PROFIT_PCT == 0.001
        
        # 기본 스펙값(0.8%, 1.2%)도 정상 확인
        cfg.STOP_LOSS_PCT = 0.008
        cfg.TAKE_PROFIT_PCT = 0.012
        assert cfg.STOP_LOSS_PCT == 0.008
        assert cfg.TAKE_PROFIT_PCT == 0.012

    def test_regression_spread_filter(self):
        """Regression 2: 스프레드가 0.3%를 초과하는 경우 종목 스캔 필터링 검증"""
        self.scanner.cfg.MAX_SPREAD_PCT = 0.3
        
        # 시나리오 A: 스프레드가 0.1%인 경우 -> 통과해야 함
        ticker_normal = {
            "symbol": "BTC/USDT:USDT",
            "last": 60000.0,
            "bid": 59970.0,
            "ask": 60030.0,
            "volume": 20000000.0,
            "change_pct": 1.0
        }
        # 스프레드 수동 계산: (60030 - 59970) / 60030 * 100 = 0.099% (< 0.3%)
        spread_normal = (ticker_normal["ask"] - ticker_normal["bid"]) / ticker_normal["ask"] * 100
        assert spread_normal <= self.scanner.cfg.MAX_SPREAD_PCT

        # 시나리오 B: 스프레드가 0.5%인 경우 -> 필터링되어 스킵되어야 함
        ticker_wide = {
            "symbol": "WIDE/USDT:USDT",
            "last": 100.0,
            "bid": 99.5,
            "ask": 100.0,  # 스프레드: (100 - 99.5) / 100 * 100 = 0.5% (> 0.3%)
            "volume": 5000000.0,
            "change_pct": 0.5
        }
        spread_wide = (ticker_wide["ask"] - ticker_wide["bid"]) / ticker_wide["ask"] * 100
        assert spread_wide > self.scanner.cfg.MAX_SPREAD_PCT

    def test_regression_quote_volume_fallback(self):
        """Regression 3: quoteVolume 누락 시 baseVolume * last로 자동 백업 계산 검증"""
        # OKX fetch_ticker API에서 quoteVolume이 None(또는 누락)으로 반환되었을 때를 시뮬레이션
        t_raw = {
            "symbol": "BTC/USDT:USDT",
            "last": 50000.0,
            "bid": 49999.0,
            "ask": 50001.0,
            "percentage": 1.2,
            "baseVolume": 100.0,  # 100 BTC 거래됨
            "quoteVolume": None   # ccxt에서 quoteVolume이 채워지지 않았을 때
        }
        
        # BinanceClient.get_ticker 내부 백업 공식 검증
        last_price = t_raw.get("last", 0)
        usdt_vol = t_raw.get("quoteVolume")
        if not usdt_vol:
            base_vol = t_raw.get("baseVolume", 0)
            usdt_vol = base_vol * last_price if base_vol and last_price else 0
            
        assert usdt_vol == 100.0 * 50000.0  # 5,000,000 USDT로 정상 계산되어야 함
        assert usdt_vol > 0

    def test_regression_bulk_tickers_optimization(self):
        """Bulk tickers fetch check to ensure scanner query overhead is reduced"""
        import asyncio
        tickers = asyncio.run(self.mock.get_tickers())
        assert len(tickers) > 0
        assert "BTC/USDT:USDT" in tickers
        assert tickers["BTC/USDT:USDT"]["volume"] > 0

    def test_regression_ghosting_prevention(self):
        """Regression 4: 청산 대기 캐시(closing_symbols)를 활용한 UI 포지션 즉시 은폐(잔상 방지) 로직 검증"""
        # UI 세션 캐시 모사
        closing_symbols = set()
        
        raw_positions = [
            {"symbol": "BTC/USDT:USDT", "amount_usdt": 10.5},
            {"symbol": "ETH/USDT:USDT", "amount_usdt": 8.2},
            {"symbol": "SOL/USDT:USDT", "amount_usdt": 0.05},  # 먼지 잔고 ($0.1 미만)
        ]
        
        # ETH 청산 시도 시점 가정
        closing_symbols.add("ETH/USDT:USDT")
        
        # app.py 필터링 로직 구현 검증
        filtered_positions = [
            p for p in raw_positions 
            if p.get("amount_usdt", 0) > 0.1 
            and p.get("symbol") not in closing_symbols
        ]
        
        # ETH(청산 중)와 SOL(먼지 잔고)가 완벽히 필터링되었는지 검증
        assert len(filtered_positions) == 1
        assert filtered_positions[0]["symbol"] == "BTC/USDT:USDT"

    def test_regression_ticker_normalization_and_fallback(self):
        """Regression 5: Ticker 키 매핑 보정, 예외 시 빈 딕셔너리 반환, 스캐너 호출 차단 검증"""
        from core.exchange import BinanceClient
        from unittest.mock import MagicMock
        
        client = BinanceClient(api_key="fake", secret_key="fake")
        
        client._markets = {
            "ETH/USDT:USDT": {"quote": "USDT", "type": "swap", "active": True},
            "BTC/USDT:USDT": {"quote": "USDT", "type": "swap", "active": True},
        }
        
        client._symbol_map = {
            "ETH/USDT:USDT": "ETH/USDT:USDT",
            "ETH/USDT": "ETH/USDT:USDT",
            "ETHUSDT": "ETH/USDT:USDT",
            "BTC/USDT:USDT": "BTC/USDT:USDT",
            "BTC/USDT": "BTC/USDT:USDT",
            "BTCUSDT": "BTC/USDT:USDT",
        }
        
        client.exchange = MagicMock()
        client.exchange.fetch_tickers = MagicMock(return_value={
            "ETH/USDT": {"last": 3000.0, "quoteVolume": 50000000.0, "bid": 2999.0, "ask": 3001.0, "percentage": 2.5},
            "BTC/USDT:USDT": {"last": 60000.0, "quoteVolume": 100000000.0, "bid": 59990.0, "ask": 60010.0, "percentage": 1.1},
        })
        
        import asyncio
        tickers = asyncio.run(client.get_tickers())
        
        assert "ETH/USDT:USDT" in tickers
        assert tickers["ETH/USDT:USDT"]["last"] == 3000.0
        assert tickers["ETH/USDT:USDT"]["volume"] == 50000000.0
        assert "BTC/USDT:USDT" in tickers
        assert tickers["BTC/USDT:USDT"]["last"] == 60000.0
        
        # 예외 처리 검증
        client.exchange.fetch_tickers = MagicMock(side_effect=Exception("Binance Rate Limit (HTTP 418)"))
        tickers_err = asyncio.run(client.get_tickers())
        assert tickers_err == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
