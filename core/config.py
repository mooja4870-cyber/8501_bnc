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
    MAX_HOLDING_HOURS: float = 4.0        # 강제 청산 타임아웃 (4시간 - 15m 봉 16개 분량)
    ALLOW_LONG: bool = True
    ALLOW_SHORT: bool = True


    # ── 손익 설정 ──────────────────────────────────────
    STOP_LOSS_PCT: float = 0.008           # 손절 0.8% (10배 레버리지 기준 -8% ROI)
    TAKE_PROFIT_PCT: float = 0.012          # 익절 1.2% (10배 레버리지 기준 +12% ROI)
    TRAILING_STOP_PCT: float = 0.01        # 추적 손절 (1.0%)
    PROFIT_FACTOR_MIN: float = 1.0        # Profit Factor 최소 기준 (1:1)

    # ── 리스크 한도 ────────────────────────────────────
    MAX_DRAWDOWN_PCT: float = 0.10        # 최대 낙폭 10% 초과 시 전략 중단
    DAILY_LOSS_LIMIT_USDT: float = 25.0  # 일일 손실 한도 (5회 진입분)
    MAX_DAILY_TRADES: int = 20            # 일일 최대 거래 횟수
    VOLATILITY_FILTER: bool = True        # 변동성 필터 활성화


    # ── 스캐너 설정 ────────────────────────────────────
    SCAN_INTERVAL_SEC: int = 30           # 스캔 주기(초)
    MIN_VOLUME_USDT: float = 1_000_000.0   # 최소 24h 거래대금 (1백만 USDT)
    QUOTE_CURRENCY: str = "USDT"
    MARKET_TYPE: str = "swap"             # 선물(영구 계약)

    # ── 지표 파라미터 ──────────────────────────────────
    EMA_PERIOD: int = 100
    BB_PERIOD: int = 20
    BB_STD: float = 1.8
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    TIMEFRAME: str = "15m"                 # 캔들 타임프레임 (사용자 조정 가능)

    # ── 백테스트 설정 ──────────────────────────────────
    BT_COMMISSION: float = 0.0005         # 수수료 0.05%
    BT_SLIPPAGE: float = 0.0003          # 슬리피지 0.03%


# ── 전역 설정 인스턴스 ────────────────────────────────
CFG = TradingConfig()
