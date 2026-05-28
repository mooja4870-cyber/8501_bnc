"""
AI QUANTUM — Binance Auto-Trading System
핵심 설정 파라미터 (사이드바 및 설정 탭 전용, .env 연동)
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env first to support dynamic configuration overrides
load_dotenv(override=True)

def get_env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val.strip("'\""))
    except ValueError:
        return default

def get_env_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val.strip("'\""))
    except ValueError:
        return default

def get_env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    val_clean = val.strip("'\"").lower()
    return val_clean in ("true", "1", "yes")

def update_env_value(key: str, value: any):
    """.env 파일 내의 변수 값을 실시간 업데이트 및 영구 저장"""
    env_path = ".env"
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            pass
            
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    found = False
    new_lines = []
    val_str = str(value)
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}='{val_str}'\n")
            found = True
        else:
            new_lines.append(line)
            
    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{key}='{val_str}'\n")
        
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    # 메모리에 로드된 환경 변수도 최신 상태로 유지
    os.environ[key] = val_str

def save_config_dict_to_env(config_dict: dict):
    """딕셔너리 형태의 설정을 .env 파일에 일괄 반영"""
    for k, v in config_dict.items():
        update_env_value(k, v)

@dataclass
class TradingConfig:
    # ── 포지션 및 운용 설정 ──────────────────────────────
    LEVERAGE: int = get_env_int("LEVERAGE", 10)                     # 레버리지 (기본 10x)
    MARGIN_USDT: float = get_env_float("MARGIN_USDT", 5.0)         # 1회 진입 증거금 (기본 5.0 USDT)
    MAX_POSITIONS: int = get_env_int("MAX_POSITIONS", 4)            # 최대 동시 보유 종목 수 (기본 4개)
    SCAN_INTERVAL_SEC: int = get_env_int("SCAN_INTERVAL_SEC", 30)   # 스캔 주기(초) (기본 30초)
    MIN_VOLUME_USDT: float = get_env_float("MIN_VOLUME_USDT", 1_000_000.0)   # 최소 24h 거래대금 (기본 1,000,000 USDT)
    USE_LIMIT_ORDER: bool = get_env_bool("USE_LIMIT_ORDER", True)   # 지정가 주문 여부 (기본 True)
    LIMIT_TICK_OFFSET: int = get_env_int("LIMIT_TICK_OFFSET", 1)   # 지정가 진입 틱 오프셋 (기본 1틱)
    LIMIT_ORDER_TIMEOUT_MINUTES: int = get_env_int("LIMIT_ORDER_TIMEOUT_MINUTES", 3) # 미체결 지정가 주문 자동취소 대기 시간(분) (기본 3분)

    # ── 손익 설정 ──────────────────────────────────────
    TAKE_PROFIT_PCT: float = get_env_float("TAKE_PROFIT_PCT", 0.015)          # 익절 1.5% (기본값)
    STOP_LOSS_PCT: float = get_env_float("STOP_LOSS_PCT", 0.01)               # 손절 1.0% (기본값)
    DAILY_LOSS_LIMIT_USDT: float = get_env_float("DAILY_LOSS_LIMIT_USDT", 7.0) # 일일 손실 한도 (기본 7.0 USDT)
    TRAILING_ACTIVATE_PCT: float = get_env_float("TRAILING_ACTIVATE_PCT", 0.015) # 트레일링 스탑 발동 1.5% (기본값)
    TRAILING_CALLBACK_PCT: float = get_env_float("TRAILING_CALLBACK_PCT", 0.0043) # 트레일링 스탑 콜백 0.43% (기본값)

    # ── 지표 파라미터 ──────────────────────────────────
    BB_PERIOD: int = get_env_int("BB_PERIOD", 20)                    # AKMCD 볼린저밴드 기간 (기본값 20)
    TIMEFRAME: str = os.getenv("TIMEFRAME", "1h").strip("'\"")      # 캔들 타임프레임 (기본값 1h)
    BB_STD: float = get_env_float("BB_STD", 2.0)                     # AKMCD 볼린저밴드 배수 (기본값 2.0)
    TTM_KC_MULT: float = get_env_float("TTM_KC_MULT", 1.5)            # TTM Squeeze 켈트너채널 배수 (기본값 1.5)
    TTM_MOM_PERIOD: int = get_env_int("TTM_MOM_PERIOD", 20)          # TTM Squeeze 모멘텀 선형회귀 기간 (기본값 20)

    # ── RSI 필터 ──────────────────────────────────────
    RSI_PERIOD: int = get_env_int("RSI_PERIOD", 14)                  # RSI 기간 (기본값 14)
    RSI_OVERBOUGHT: float = get_env_float("RSI_OVERBOUGHT", 75.0)    # 롱 진입 제한 RSI 상한선 (기본 75.0)
    RSI_OVERSOLD: float = get_env_float("RSI_OVERSOLD", 25.0)        # 숏 진입 제한 RSI 하한선 (기본 25.0)

    # ── 거래량 서지 필터 설정 ──────────────────────────
    USE_VOLUME_SURGE_FILTER: bool = get_env_bool("USE_VOLUME_SURGE_FILTER", True)     # 거래량 서지 필터 활성화 여부
    VOLUME_SURGE_PERIOD: int = get_env_int("VOLUME_SURGE_PERIOD", 20)                 # 거래량 서지 기간 (기본 20봉)
    VOLUME_SURGE_MULTIPLIER: float = get_env_float("VOLUME_SURGE_MULTIPLIER", 1.5)   # 거래량 서지 배수 (기본 1.5배)

    def snapshot(self):
        """설정의 스레드 안전한 불변 스냅샷 복사본 반환"""
        import copy
        return copy.deepcopy(self)

    def __getattr__(self, name: str):
        """삭제된 설정 파라미터에 대한 하위 호환성 및 기본값 지원"""
        defaults = {
            "EXCHANGE_ID": os.getenv("EXCHANGE_ID", "binance").strip("'\""),
            "BASE_URL": os.getenv("BASE_URL", "https://fapi.binance.com").strip("'\""),
            "MARGIN_MODE": os.getenv("MARGIN_MODE", "isolated").strip("'\""),
            "MAX_HOLDING_HOURS": get_env_float("MAX_HOLDING_HOURS", 4.0),
            "ALLOW_LONG": get_env_bool("ALLOW_LONG", True),
            "ALLOW_SHORT": get_env_bool("ALLOW_SHORT", True),
            "USE_EMA200_FILTER": get_env_bool("USE_EMA200_FILTER", True),
            "USE_RSI_FILTER": get_env_bool("USE_RSI_FILTER", True),
            "AUTO_TUNE_SL_TP": get_env_bool("AUTO_TUNE_SL_TP", False),
            "MAX_DRAWDOWN_PCT": get_env_float("MAX_DRAWDOWN_PCT", 0.10),
            "DAILY_PROFIT_LIMIT_USDT": get_env_float("DAILY_PROFIT_LIMIT_USDT", 0.8),
            "MIN_REQUIRED_BALANCE_USDT": get_env_float("MIN_REQUIRED_BALANCE_USDT", 1.0),
            "ROTATION_ENABLED": get_env_bool("ROTATION_ENABLED", False),
            "ROTATION_MIN_SIGNALS": get_env_int("ROTATION_MIN_SIGNALS", 3),
            "ROTATION_STALE_HOURS": get_env_float("ROTATION_STALE_HOURS", 1.5),
            "ROTATION_FLOW_CHECK": os.getenv("ROTATION_FLOW_CHECK", "momentum").strip("'\""),
            "MAX_SPREAD_PCT": get_env_float("MAX_SPREAD_PCT", 0.3),
            "SCAN_TOP_N": get_env_int("SCAN_TOP_N", 80),
            "QUOTE_CURRENCY": os.getenv("QUOTE_CURRENCY", "USDT").strip("'\""),
            "MARKET_TYPE": os.getenv("MARKET_TYPE", "swap").strip("'\""),
            "EMA_PERIOD": get_env_int("EMA_PERIOD", 200),
            "MACD_FAST": get_env_int("MACD_FAST", 12),
            "MACD_SLOW": get_env_int("MACD_SLOW", 26),
            "MACD_SIGNAL": get_env_int("MACD_SIGNAL", 9),
            "SSL_PERIOD": get_env_int("SSL_PERIOD", 10),
            "MOMENTUM_WINDOW": get_env_int("MOMENTUM_WINDOW", 3),
            "BT_COMMISSION": get_env_float("BT_COMMISSION", 0.0005),
            "BT_SLIPPAGE": get_env_float("BT_SLIPPAGE", 0.0003),
        }
        if name in defaults:
            return defaults[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


# ── 전역 설정 인스턴스 ────────────────────────────────
CFG = TradingConfig()
