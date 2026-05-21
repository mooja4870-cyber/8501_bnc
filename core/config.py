"""
AI QUANTUM — OKX Auto-Trading System
핵심 설정 파라미터 (슬라이드 설계안 기준)
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class TradingConfig:
    # ── 거래소 ──────────────────────────────────────────
    EXCHANGE_ID: str = "binance"
    BASE_URL: str = "https://fapi.binance.com"

    # ── 포지션 설정 ──────────────────────────────────────
    LEVERAGE: int = 5                      # 레버리지 (기본값 5)
    MARGIN_MODE: str = "isolated"          # 격리 마진
    MARGIN_USDT: float = 5.0               # 1회 진입 증거금 (USDT)
    MAX_POSITIONS: int = 5                # 최대 동시 보유 종목 수
    MAX_HOLDING_HOURS: float = 4.0        # 강제 청산 타임아웃 (4시간 - 15m 봉 16개 분량)
    ALLOW_LONG: bool = True
    ALLOW_SHORT: bool = True


    # ── 손익 설정 ──────────────────────────────────────
    STOP_LOSS_PCT: float = 0.01            # 손절 1.0% (기본값)
    TAKE_PROFIT_PCT: float = 0.015          # 익절 1.5% (기본값)
    AUTO_TUNE_SL_TP: bool = False          # 최근 매매 기반 익절/손절 자동 피팅 활성화 (Auto-Tuning)

    # ── 리스크 한도 ────────────────────────────────────
    MAX_DRAWDOWN_PCT: float = 0.10        # 최대 낙폭 10% 초과 시 전략 중단
    DAILY_LOSS_LIMIT_USDT: float = 25.0  # 일일 손실 한도 (5회 진입분)
    
    # ── 포지션 로테이션 (Stale Position Rotation) 설정 ──
    ROTATION_ENABLED: bool = False         # 정체 포지션 로테이션 활성화
    ROTATION_MIN_SIGNALS: int = 3          # 교체 진입을 위한 스캐너 최소 대기 신호 수
    ROTATION_STALE_HOURS: float = 1.5      # 정체 판단 시간 (시간 단위)
    ROTATION_FLOW_CHECK: str = "momentum"  # 흐름 판단 기준 ('momentum', 'flat', 'time')


    # ── 스캐너 설정 ────────────────────────────────────
    SCAN_INTERVAL_SEC: int = 30           # 스캔 주기(초)
    MIN_VOLUME_USDT: float = 1_000_000.0   # 최소 24h 거래대금 (1백만 USDT)
    MAX_SPREAD_PCT: float = 0.3            # 최대 허용 스프레드 (%) — 초과 시 진입 스킵
    QUOTE_CURRENCY: str = "USDT"
    MARKET_TYPE: str = "swap"             # 선물(영구 계약)

    # ── 지표 파라미터 ──────────────────────────────────
    BB_PERIOD: int = 20                    # AKMCD 볼린저밴드 기간 (기본값 20)
    BB_STD: float = 2.0                    # AKMCD 볼린저밴드 배수 (기본값 2.0)
    MACD_FAST: int = 12                    # AKMCD MACD Fast (기본값 12)
    MACD_SLOW: int = 26                    # AKMCD MACD Slow (기본값 26)
    MACD_SIGNAL: int = 9                   # AKMCD MACD Signal (기본값 9)
    SSL_PERIOD: int = 10                   # SSL 기간 (기본값 10)
    TIMEFRAME: str = "15m"                 # 캔들 타임프레임 (기본값 15m)

    # ── 백테스트 설정 ──────────────────────────────────
    BT_COMMISSION: float = 0.0005         # 수수료 0.05%
    BT_SLIPPAGE: float = 0.0003          # 슬리피지 0.03%


# ── 전역 설정 인스턴스 ────────────────────────────────
CFG = TradingConfig()
