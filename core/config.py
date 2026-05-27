"""
AI QUANTUM — OKX Auto-Trading System
핵심 설정 파라미터 (사이드바 및 설정 탭 전용)
"""
from dataclasses import dataclass


@dataclass
class TradingConfig:
    # ── 포지션 및 운용 설정 ──────────────────────────────
    LEVERAGE: int = 10                     # 레버리지 (기본 10x)
    MARGIN_USDT: float = 10.0              # 1회 진입 증거금 (기본 10.0 USDT)
    MAX_POSITIONS: int = 4                # 최대 동시 보유 종목 수 (기본 4개)
    SCAN_INTERVAL_SEC: int = 30           # 스캔 주기(초) (기본 30초)
    MIN_VOLUME_USDT: float = 1_000_000.0   # 최소 24h 거래대금 (기본 1,000,000 USDT)

    # ── 손익 설정 ──────────────────────────────────────
    TAKE_PROFIT_PCT: float = 0.015          # 익절 1.5% (기본값)
    STOP_LOSS_PCT: float = 0.01            # 손절 1.0% (기본값)
    DAILY_LOSS_LIMIT_USDT: float = 7.0   # 일일 손실 한도 (기본 7.0 USDT)

    # ── 지표 파라미터 ──────────────────────────────────
    BB_PERIOD: int = 20                    # AKMCD 볼린저밴드 기간 (기본값 20)
    TIMEFRAME: str = "15m"                 # 캔들 타임프레임 (기본값 15m)
    BB_STD: float = 2.0                    # AKMCD 볼린저밴드 배수 (기본값 2.0)
    TTM_KC_MULT: float = 1.5               # TTM Squeeze 켈트너채널 배수 (기본값 1.5)
    TTM_MOM_PERIOD: int = 20               # TTM Squeeze 모멘텀 선형회귀 기간 (기본값 20)

    # ── RSI 필터 ──────────────────────────────────────
    RSI_PERIOD: int = 14                   # RSI 기간 (기본값 14)
    RSI_OVERBOUGHT: float = 75.0           # 롱 진입 제한 RSI 상한선 (기본 75.0)
    RSI_OVERSOLD: float = 25.0             # 숏 진입 제한 RSI 하한선 (기본 25.0)

    # ── 거래량 서지 필터 설정 ──────────────────────────
    USE_VOLUME_SURGE_FILTER: bool = True     # 거래량 서지 필터 활성화 여부
    VOLUME_SURGE_PERIOD: int = 20            # 거래량 서지 기간 (기본 20봉)
    VOLUME_SURGE_MULTIPLIER: float = 1.5     # 거래량 서지 배수 (기본 1.5배)

    def __getattr__(self, name: str):
        """삭제된 설정 파라미터에 대한 하위 호환성 및 기본값 지원"""
        defaults = {
            "EXCHANGE_ID": "binance",
            "BASE_URL": "https://fapi.binance.com",
            "MARGIN_MODE": "isolated",
            "MAX_HOLDING_HOURS": 4.0,
            "ALLOW_LONG": True,
            "ALLOW_SHORT": True,
            "USE_EMA200_FILTER": True,
            "USE_RSI_FILTER": True,
            "TRAILING_ACTIVATE_PCT": 0.015,
            "TRAILING_CALLBACK_PCT": 0.003,
            "AUTO_TUNE_SL_TP": False,
            "MAX_DRAWDOWN_PCT": 0.10,
            "DAILY_PROFIT_LIMIT_USDT": 0.8,
            "MIN_REQUIRED_BALANCE_USDT": 1.0,
            "ROTATION_ENABLED": False,
            "ROTATION_MIN_SIGNALS": 3,
            "ROTATION_STALE_HOURS": 1.5,
            "ROTATION_FLOW_CHECK": "momentum",
            "MAX_SPREAD_PCT": 0.3,
            "SCAN_TOP_N": 80,
            "QUOTE_CURRENCY": "USDT",
            "MARKET_TYPE": "swap",
            "EMA_PERIOD": 200,
            "MACD_FAST": 12,
            "MACD_SLOW": 26,
            "MACD_SIGNAL": 9,
            "SSL_PERIOD": 10,
            "MOMENTUM_WINDOW": 3,
            "BT_COMMISSION": 0.0005,
            "BT_SLIPPAGE": 0.0003,
        }
        if name in defaults:
            return defaults[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


# ── 전역 설정 인스턴스 ────────────────────────────────
CFG = TradingConfig()

