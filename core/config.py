import os
"""
AI QUANTUM — OKX Auto-Trading System
핵심 설정 파라미터 (슬라이드 설계안 기준)
"""
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

# .env 파일을 최우선으로 로드 (시스템 환경변수보다 우선)
load_dotenv(override=True)


@dataclass
class TradingConfig:
    # ── 거래소 ──────────────────────────────────────────
    EXCHANGE_ID: str = "okx"
    BASE_URL: str = "https://www.okx.com"

    # ── 자산 관리 ──────────────────────────────────
    INITIAL_CAPITAL: float = float(os.getenv("INITIAL_CAPITAL", 1.0)) # 초기 자본금 (기본값 제거)

    # ── 포지션 설정 ──────────────────────────────────────
    LEVERAGE: int = 10                     # 10배 고정
    MARGIN_MODE: str = "isolated"          # 격리 마진
    MARGIN_USDT: float = 5.0               # 1회 진입 증거금 (USDT)
    MAX_POSITIONS: int = 5                # 최대 동시 보유 종목 수
    ENTRY_COOLDOWN_SEC: int = 180          # 동일 티커 재진입 최소 대기 시간
    PENDING_ENTRY_TTL_SEC: int = 120       # 주문 진행 상태 중복 방지 유지 시간
    ALLOW_LONG: bool = True
    ALLOW_SHORT: bool = True

    # ── 손익 설정 ──────────────────────────────────────
    STOP_LOSS_PCT: float = 0.015          # 손절 1.5%
    TAKE_PROFIT_PCT: float = 0.02         # 익절 2.0%
    PROFIT_FACTOR_MIN: float = 2.0        # Profit Factor 최소 기준

    # ── 리스크 한도 ────────────────────────────────────
    MAX_DRAWDOWN_PCT: float = 0.15        # 최대 낙폭 15% 초과 시 전략 중단
    DAILY_LOSS_LIMIT_USDT: float = 30.0  # 일일 손실 한도

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


    def refresh(self):
        """환경 변수로부터 설정을 최신화합니다."""
        self.INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", 1.0))
        self.MARGIN_USDT = float(os.getenv("MARGIN_USDT", 5.0))
        self.LEVERAGE = int(os.getenv("LEVERAGE", 10))
        self.MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", 5))
        self.STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", 0.015))
        self.TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", 0.02))
        self.SCAN_INTERVAL_SEC = int(os.getenv("SCAN_INTERVAL_SEC", 30))
        self.MIN_VOLUME_USDT = float(os.getenv("MIN_VOLUME_USDT", 1000000.0))
        self.MAX_DRAWDOWN_PCT = float(os.getenv("MAX_DRAWDOWN_PCT", 0.15))

# ── 전역 설정 인스턴스 ────────────────────────────────
CFG = TradingConfig()
CFG.refresh()
