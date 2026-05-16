"""
AI QUANTUM — OKX Auto-Trading System
핵심 설정 파라미터 (슬라이드 설계안 기준)
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class TradingConfig:
    # ── 거래소 ──────────────────────────────────────────
    EXCHANGE_ID: str = "okx"
    BASE_URL: str = "https://www.okx.com"

    # ── 포지션 설정 ──────────────────────────────────────
    LEVERAGE: int = 10                     # 10배 고정
    MARGIN_MODE: str = "isolated"          # 격리 마진
    MARGIN_USDT: float = 5.0               # 1회 진입 증거금 (USDT)
    MAX_POSITIONS: int = 5                # 최대 동시 보유 종목 수
    MAX_HOLDING_HOURS: float = 3.0        # 강제 청산 타임아웃 (3시간)
    ALLOW_LONG: bool = True
    ALLOW_SHORT: bool = True


    # ── 손익 설정 ──────────────────────────────────────
    STOP_LOSS_PCT: float = 0.02           # 손절 2.0% (사용자 요청)
    TAKE_PROFIT_PCT: float = 0.02          # 익절 2.0% (사용자 요청)
    TRAILING_STOP_PCT: float = 0.01        # 추적 손절 (1.0%)
    PROFIT_FACTOR_MIN: float = 1.0        # Profit Factor 최소 기준 (1:1)

    # [v1.2.99] 투자 기준점 설정
    INITIAL_CAPITAL: float = 22.06
    BASELINE_DATE: str = "2026-05-16 23:57"
    
    # ── [v1.2.90] 신규 파라미터 ────────────────────────
    MAX_HOLDING_HOURS: int = 12         # 최대 보유 시간 (초과 시 자동청산)
    DAILY_LOSS_LIMIT_USDT: float = 25.0  # 일일 손실 한도 (5회 진입분)
    MAX_DAILY_TRADES: int = 20            # 일일 최대 거래 횟수
    VOLATILITY_FILTER: bool = True        # 변동성 필터 활성화


    # ── 스캐너 설정 ────────────────────────────────────
    SCAN_INTERVAL_SEC: int = 30           # 스캔 주기(초)
    MIN_VOLUME_USDT: float = 1_000_000.0   # 최소 24h 거래대금 (1백만 USDT)
    QUOTE_CURRENCY: str = "USDT"
    MARKET_TYPE: str = "swap"             # 선물(영구 계약)

    # ── 지표 파라미터 ──────────────────────────────────
    EMA_PERIOD: int = 200
    BB_PERIOD: int = 20
    BB_STD: float = 2.0
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    TIMEFRAME: str = "1h"                 # 캔들 타임프레임

    # ── 백테스트 설정 ──────────────────────────────────
    BT_COMMISSION: float = 0.0005         # 수수료 0.05%
    BT_SLIPPAGE: float = 0.0003          # 슬리피지 0.03%


# ── 전역 설정 인스턴스 ────────────────────────────────
CFG = TradingConfig()
