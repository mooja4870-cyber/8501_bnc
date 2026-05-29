"""
AI QUANTUM — Binance Auto-Trading System
핵심 설정 파라미터 (하드코딩 제거 및 JSON 연동판)
"""
import json
import os
import logging

logger = logging.getLogger(__name__)

class TradingConfig:
    def __init__(self):
        # 당분간 UI 및 동작 안정성을 위해 현재 설정 탭 기준 디폴트 값을 명시적 하드코딩
        self.EXCHANGE_ID = "binance"
        self.BASE_URL = "https://www.binance.com"
        self.LEVERAGE = 10
        self.MARGIN_MODE = "isolated"
        self.MARGIN_USDT = 5.0
        self.USE_AUTO_COMPOUND = False
        self.MAX_POSITIONS = 5
        self.MAX_HOLDING_HOURS = 4.0
        self.ALLOW_LONG = True
        self.ALLOW_SHORT = True
        self.USE_EMA200_FILTER = True
        self.USE_RSI_FILTER = True
        self.USE_VOL_FILTER = False
        self.VOL_MA_PERIOD = 20
        self.VOL_SURGE_MULT = 1.5
        self.STOP_LOSS_PCT = 0.01
        self.TAKE_PROFIT_PCT = 0.015
        self.USE_TRAILING_STOP = True
        self.TRAILING_ACTIVATE_PCT = 0.015
        self.TRAILING_CALLBACK_PCT = 0.0045
        self.AUTO_TUNE_SL_TP = False
        self.USE_DYNAMIC_SLTP = True
        self.ATR_SL_MULT = 1.5
        self.ATR_TP_MULT = 2.0
        self.MAX_DRAWDOWN_PCT = 0.1
        self.DAILY_LOSS_LIMIT_USDT = 7.0
        self.DAILY_PROFIT_LIMIT_USDT = 0.8
        self.MIN_REQUIRED_BALANCE_USDT = 1.0
        self.ROTATION_ENABLED = False
        self.ROTATION_MIN_SIGNALS = 3
        self.ROTATION_STALE_HOURS = 1.5
        self.ROTATION_FLOW_CHECK = "momentum"
        self.SCAN_INTERVAL_SEC = 10
        self.MIN_VOLUME_USDT = 5000000.0
        self.MAX_SPREAD_PCT = 0.3
        self.SCAN_TOP_N = 25
        self.USE_LIMIT_ORDER = True
        self.LIMIT_TICK_OFFSET = 1
        self.LIMIT_ORDER_TIMEOUT_MINUTES = 3
        self.QUOTE_CURRENCY = "USDT"
        self.MARKET_TYPE = "swap"
        self.EMA_PERIOD = 139
        self.BB_PERIOD = 20
        self.BB_STD = 2.0
        self.TTM_KC_MULT = 1.5
        self.SQUEEZE_LOOKBACK = 8
        self.MACD_FAST = 12
        self.MACD_SLOW = 26
        self.MACD_SIGNAL = 9
        self.SSL_PERIOD = 10
        self.TIMEFRAME = "15m"
        self.RSI_PERIOD = 13
        self.RSI_OVERBOUGHT = 75.0
        self.RSI_OVERSOLD = 25.0
        self.MOMENTUM_WINDOW = 3
        self.TTM_MOM_PERIOD = 20
        self.BT_COMMISSION = 0.0005
        self.BT_SLIPPAGE = 0.0003
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
        self.AUTO_TRADING = True
        self.USE_CHANDELIER_EXIT = True
        self.CHANDELIER_MULT = 3.0
        self.MOMENTUM_SLOPE_THRESHOLD = 0.0

        self.load_settings()

    def copy(self):
        """현재 인스턴스의 얕은 복사본(Shallow Copy)을 반환합니다."""
        import copy
        return copy.copy(self)

    def load_settings(self):
        """settings.json에서 설정을 읽어들입니다."""
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    setattr(self, k, v)
            except Exception as e:
                logger.error(f"설정 파일 읽기 실패: {e}")
        else:
            logger.warning("settings.json 파일이 존재하지 않습니다. UI에서 값을 저장해주세요.")

    def save_settings(self):
        """현재 인스턴스의 설정값을 settings.json에 영구 저장합니다."""
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "settings.json")
        # 내부 변수(_로 시작하는 등)나 함수 제외하고 저장
        data = {k: v for k, v in self.__dict__.items() if not callable(v) and not k.startswith('_')}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"설정 파일 저장 실패: {e}")

    def reset_to_defaults(self):
        """
        모든 설정을 코드 내 하드코딩된 초기값으로 되돌리고 settings.json에 저장합니다.
        settings.json을 무시하고 __init__ 의 하드코딩 값만 적용합니다.
        """
        self.EXCHANGE_ID = "binance"
        self.BASE_URL = "https://www.binance.com"
        self.LEVERAGE = 10
        self.MARGIN_MODE = "isolated"
        self.MARGIN_USDT = 5.0
        self.USE_AUTO_COMPOUND = False
        self.MAX_POSITIONS = 5
        self.MAX_HOLDING_HOURS = 4.0
        self.ALLOW_LONG = True
        self.ALLOW_SHORT = True
        self.USE_EMA200_FILTER = True
        self.USE_RSI_FILTER = True
        self.USE_VOL_FILTER = False
        self.VOL_MA_PERIOD = 20
        self.VOL_SURGE_MULT = 1.5
        self.STOP_LOSS_PCT = 0.01
        self.TAKE_PROFIT_PCT = 0.015
        self.USE_TRAILING_STOP = True
        self.TRAILING_ACTIVATE_PCT = 0.015
        self.TRAILING_CALLBACK_PCT = 0.0045
        self.AUTO_TUNE_SL_TP = False
        self.USE_DYNAMIC_SLTP = True
        self.ATR_SL_MULT = 1.5
        self.ATR_TP_MULT = 2.0
        self.MAX_DRAWDOWN_PCT = 0.1
        self.DAILY_LOSS_LIMIT_USDT = 7.0
        self.DAILY_PROFIT_LIMIT_USDT = 0.8
        self.MIN_REQUIRED_BALANCE_USDT = 1.0
        self.ROTATION_ENABLED = False
        self.ROTATION_MIN_SIGNALS = 3
        self.ROTATION_STALE_HOURS = 1.5
        self.ROTATION_FLOW_CHECK = "momentum"
        self.SCAN_INTERVAL_SEC = 10
        self.MIN_VOLUME_USDT = 5000000.0
        self.MAX_SPREAD_PCT = 0.3
        self.SCAN_TOP_N = 25
        self.USE_LIMIT_ORDER = True
        self.LIMIT_TICK_OFFSET = 1
        self.LIMIT_ORDER_TIMEOUT_MINUTES = 3
        self.QUOTE_CURRENCY = "USDT"
        self.MARKET_TYPE = "swap"
        self.EMA_PERIOD = 139
        self.BB_PERIOD = 20
        self.BB_STD = 2.0
        self.TTM_KC_MULT = 1.5
        self.SQUEEZE_LOOKBACK = 8
        self.MACD_FAST = 12
        self.MACD_SLOW = 26
        self.MACD_SIGNAL = 9
        self.SSL_PERIOD = 10
        self.TIMEFRAME = "15m"
        self.RSI_PERIOD = 13
        self.RSI_OVERBOUGHT = 75.0
        self.RSI_OVERSOLD = 25.0
        self.MOMENTUM_WINDOW = 3
        self.TTM_MOM_PERIOD = 20
        self.BT_COMMISSION = 0.0005
        self.BT_SLIPPAGE = 0.0003
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
        self.AUTO_TRADING = True
        self.USE_CHANDELIER_EXIT = True
        self.CHANDELIER_MULT = 3.0
        self.MOMENTUM_SLOPE_THRESHOLD = 0.0
        self.save_settings()
        logger.info("[CONFIG] 모든 설정이 초기 기본값으로 리셋되었습니다.")

    def __getattr__(self, name: str):
        # 하위 호환성 및 안전 폴백을 위한 getattr 구현
        defaults = {
            "USE_LIMIT_ORDER": True,
            "LIMIT_TICK_OFFSET": 1,
            "LIMIT_ORDER_TIMEOUT_MINUTES": 3,
        }
        if name in defaults:
            return defaults[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

# ── 전역 설정 인스턴스 ────────────────────────────────
CFG = TradingConfig()
