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
    LEVERAGE: int = 5                      # 레버리지 (잔고 $38.94 고려 안전한 5x 적용)
    MARGIN_MODE: str = "isolated"          # 격리 마진
    MARGIN_USDT: float = 4.0               # 1회 진입 증거금 (원금 대비 ~10% 수준인 $4.0 적용)
    MAX_POSITIONS: int = 3                # 최대 동시 보유 종목 수 (원금 고려 3개 적용)
    MAX_HOLDING_HOURS: float = 4.0        # 강제 청산 타임아웃 (4시간 - 15m 봉 16개 분량)
    ALLOW_LONG: bool = True
    ALLOW_SHORT: bool = True

    # ── 전략 필터 모드 ──────────────────────────────────
    USE_EMA200_FILTER: bool = True         # EMA 200 장기추세 필터 기본 활성화 (RSI+EMA200이 기본 전략)
    USE_RSI_FILTER: bool = True            # RSI 필터 활성화 여부 (기본 ON)


    # ── 손익 설정 ──────────────────────────────────────
    STOP_LOSS_PCT: float = 0.01            # 손절 1.0% (5x 레버리지 기준 마진의 5.0% 손실)
    TAKE_PROFIT_PCT: float = 0.015          # 익절 1.5% (5x 레버리지 기준 마진의 7.5% 수익)
    TRAILING_ACTIVATE_PCT: float = 0.015    # 트레일링 활성화 1.5% (기본값)
    TRAILING_CALLBACK_PCT: float = 0.003    # 트레일링 콜백 0.3% (기본값)
    AUTO_TUNE_SL_TP: bool = False          # 최근 매매 기반 익절/손절 자동 피팅 활성화 (Auto-Tuning)

    # ── 리스크 한도 ────────────────────────────────────
    MAX_DRAWDOWN_PCT: float = 0.10        # 최대 낙폭 10% 초과 시 전략 중단
    DAILY_LOSS_LIMIT_USDT: float = 4.0   # 일일 손실 한도 (원금 대비 ~10% 수준인 $4.0 적용)
    DAILY_PROFIT_LIMIT_USDT: float = 0.8  # 일일 익절 잠금 한도 (원금 대비 ~2% 수준인 $0.80 도달 시 진입 제한)
    MIN_REQUIRED_BALANCE_USDT: float = 1.0 # 최소 필요 잔고 (기본값 1.0 USDT)
    
    # ── 포지션 로테이션 (Stale Position Rotation) 설정 ──
    ROTATION_ENABLED: bool = False         # 정체 포지션 로테이션 활성화
    ROTATION_MIN_SIGNALS: int = 3          # 교체 진입을 위한 스캐너 최소 대기 신호 수
    ROTATION_STALE_HOURS: float = 1.5      # 정체 판단 시간 (시간 단위)
    ROTATION_FLOW_CHECK: str = "momentum"  # 흐름 판단 기준 ('momentum', 'flat', 'time')


    # ── 스캐너 설정 ────────────────────────────────────
    SCAN_INTERVAL_SEC: int = 30           # 스캔 주기(초)
    MIN_VOLUME_USDT: float = 1_000_000.0   # 최소 24h 거래대금 (1백만 USDT)
    MAX_SPREAD_PCT: float = 0.3            # 최대 허용 스프레드 (%) — 초과 시 진입 스킵
    SCAN_TOP_N: int = 80                   # 거래대금 상위 N개만 스캔 (0 = 전체)
    QUOTE_CURRENCY: str = "USDT"
    MARKET_TYPE: str = "swap"             # 선물(영구 계약)

    # ── 지표 파라미터 ──────────────────────────────────
    EMA_PERIOD: int = 200                  # EMA 트렌드 필터 기간 (기본값 200)
    BB_PERIOD: int = 20                    # AKMCD 볼린저밴드 기간 (기본값 20)
    BB_STD: float = 2.0                    # AKMCD 볼린저밴드 배수 (기본값 2.0)
    TTM_KC_MULT: float = 1.5               # TTM Squeeze 켈트너채널 배수 (기본값 1.5)
    MACD_FAST: int = 12                    # AKMCD MACD Fast (기본값 12)
    MACD_SLOW: int = 26                    # AKMCD MACD Slow (기본값 26)
    MACD_SIGNAL: int = 9                   # AKMCD MACD Signal (기본값 9)
    SSL_PERIOD: int = 10                   # SSL 기간 (기본값 10)
    TIMEFRAME: str = "15m"                 # 캔들 타임프레임 (기본값 15m)
    RSI_PERIOD: int = 14                   # RSI 기간 (기본값 14)
    RSI_OVERBOUGHT: float = 60.0           # 롱 진입 제한 RSI 상한선 (기본값 60.0)
    RSI_OVERSOLD: float = 40.0             # 숏 진입 제한 RSI 하한선 (기본값 40.0)
    MOMENTUM_WINDOW: int = 3               # AKMCD 모멘텀 전환 진입 유효 봉수 (기본값 3, 1일 시 기존 극단적 조건)
    TTM_MOM_PERIOD: int = 20               # TTM Squeeze 모멘텀 선형회귀 기간 (기본값 20)

    # ── 백테스트 설정 ──────────────────────────────────
    BT_COMMISSION: float = 0.0005         # 수수료 0.05%
    BT_SLIPPAGE: float = 0.0003          # 슬리피지 0.03%


# ── 전역 설정 인스턴스 ────────────────────────────────
CFG = TradingConfig()
