"""
AI QUANTUM — Mock Exchange Client
실제 Binance API 없이 엔진 전체 흐름을 검증할 수 있는 가짜 거래소 클라이언트
하네스 및 단위 테스트에서 BinanceClient 대체용
"""
import pandas as pd
import numpy as np
import logging
import time
from typing import Optional, Dict, List
from core.config import CFG

logger = logging.getLogger(__name__)


class MockBinanceClient:
    """
    BinanceClient와 동일한 인터페이스를 제공하는 Mock 클라이언트
    - 고정 잔고/포지션/OHLCV 반환
    - 주문 시뮬레이션 (실 API 호출 없음)
    - 다양한 시나리오 프리셋 제공
    """

    def __init__(self, api_key: str = "", secret_key: str = "", passphrase: Optional[str] = None):
        self._markets: Dict = {}
        self._balance: Dict = {"total": 100.0, "free": 80.0, "used": 20.0}
        self._positions: List[Dict] = []
        self._orders: List[Dict] = []
        self._trade_history: List[Dict] = []
        self._closed_pnl: List[Dict] = []
        self._order_counter = 0
        self._fail_next_order = False
        self._scenario = "default"
        self._fail_balance = False
        self._fail_positions = False

    # ── 시나리오 프리셋 ──────────────────────────────────

    def set_scenario(self, name: str):
        """테스트 시나리오 설정"""
        self._scenario = name
        self._fail_balance = False
        self._fail_positions = False

        if name == "default":
            self._balance = {"total": 100.0, "free": 80.0, "used": 20.0}
            self._positions = []

        elif name == "low_balance":
            self._balance = {"total": 5.0, "free": 3.0, "used": 2.0}
            self._positions = []

        elif name == "no_margin":
            self._balance = {"total": 50.0, "free": 0.5, "used": 49.5}
            self._positions = []

        elif name == "max_positions":
            self._balance = {"total": 100.0, "free": 30.0, "used": 70.0}
            self._positions = [
                self._make_position(f"MOCK{i}/USDT:USDT", "long", 10.0 + i)
                for i in range(CFG.MAX_POSITIONS)
            ]

        elif name == "with_positions":
            self._balance = {"total": 100.0, "free": 60.0, "used": 40.0}
            self._positions = [
                self._make_position("BTC/USDT:USDT", "long", 67000.0),
                self._make_position("ETH/USDT:USDT", "short", 3800.0),
            ]

        elif name == "profitable":
            self._balance = {"total": 150.0, "free": 100.0, "used": 50.0}
            self._positions = [
                self._make_position("BTC/USDT:USDT", "long", 65000.0, mark=68000.0),
            ]

        elif name == "losing":
            self._balance = {"total": 80.0, "free": 30.0, "used": 50.0}
            self._positions = [
                self._make_position("BTC/USDT:USDT", "long", 70000.0, mark=66000.0),
            ]

        elif name == "api_error":
            self._fail_balance = True
            self._fail_positions = True

        logger.info(f"[MOCK] 시나리오 변경: {name}")

    def _make_position(
        self,
        symbol: str,
        side: str,
        entry: float,
        mark: float = None,
        size: float = 1.0,
    ) -> Dict:
        if mark is None:
            mark = entry * (1.005 if side == "long" else 0.995)
        lev = CFG.LEVERAGE
        raw = (mark - entry) / entry
        pct = raw * lev if side == "long" else -raw * lev
        return {
            "symbol": symbol,
            "side": side,
            "size": size,
            "coins": size,
            "entry_price": entry,
            "mark_price": mark,
            "pnl_pct": round(pct * 100, 2),
            "pnl_usdt": round(raw * entry * size, 4),
            "leverage": lev,
            "margin": round(entry * size / lev, 4),
            "timestamp": int(time.time() * 1000) - 3600_000,  # 1시간 전
            "amount_usdt": round(entry * size, 2),
        }

    # ── 초기화 ─────────────────────────────────────────

    def load_markets(self) -> bool:
        """마켓 정보 로드 (Mock: 항상 성공)"""
        self._markets = {
            "BTC/USDT:USDT": {
                "quote": "USDT", "type": "swap", "active": True,
                "contractSize": 0.01,
                "limits": {"leverage": {"max": 125}},
            },
            "ETH/USDT:USDT": {
                "quote": "USDT", "type": "swap", "active": True,
                "contractSize": 0.1,
                "limits": {"leverage": {"max": 100}},
            },
            "SOL/USDT:USDT": {
                "quote": "USDT", "type": "swap", "active": True,
                "contractSize": 1.0,
                "limits": {"leverage": {"max": 75}},
            },
            "DOGE/USDT:USDT": {
                "quote": "USDT", "type": "swap", "active": True,
                "contractSize": 100.0,
                "limits": {"leverage": {"max": 50}},
            },
            "XRP/USDT:USDT": {
                "quote": "USDT", "type": "swap", "active": True,
                "contractSize": 10.0,
                "limits": {"leverage": {"max": 75}},
            },
        }
        logger.info(f"[MOCK] 마켓 로드 완료: {len(self._markets)}개 종목")
        return True

    # ── 계좌 조회 ──────────────────────────────────────

    def get_balance(self) -> Dict:
        if self._fail_balance:
            raise Exception("Mock API Error: 잔고 조회 실패")
        return dict(self._balance)

    def get_positions(self) -> List[Dict]:
        if self._fail_positions:
            raise Exception("Mock API Error: 포지션 조회 실패")
        return list(self._positions)

    def get_open_orders(self) -> List[Dict]:
        return list(self._orders)

    def get_trade_history(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict]:
        trades = self._trade_history
        if symbol:
            trades = [t for t in trades if t["symbol"] == symbol]
        return trades[-limit:]

    def get_closed_positions_pnl(self, limit=20) -> List[Dict]:
        return self._closed_pnl[-limit:]

    # ── 시장 데이터 ────────────────────────────────────

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: Optional[str] = None,
        limit: int = 300,
    ) -> pd.DataFrame:
        """
        테스트용 합성 OHLCV 데이터 생성
        - 기본: 약한 상승 추세 + 볼린저 밴드 반등 패턴
        """
        np.random.seed(hash(symbol) % 2**31)
        n = max(limit, 250)

        # 기본 가격 (심볼별 다르게)
        base_prices = {
            "BTC/USDT:USDT": 67000.0,
            "ETH/USDT:USDT": 3800.0,
            "SOL/USDT:USDT": 170.0,
            "DOGE/USDT:USDT": 0.15,
            "XRP/USDT:USDT": 0.55,
        }
        base = base_prices.get(symbol, 100.0)

        # 랜덤 워크 + 트렌드
        returns = np.random.normal(0.0002, 0.015, n)
        prices = base * np.cumprod(1 + returns)

        high = prices * (1 + np.abs(np.random.normal(0, 0.005, n)))
        low = prices * (1 - np.abs(np.random.normal(0, 0.005, n)))
        volume = np.random.uniform(1_000_000, 50_000_000, n)

        timestamps = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="15min")

        df = pd.DataFrame({
            "open": prices * (1 + np.random.normal(0, 0.001, n)),
            "high": high,
            "low": low,
            "close": prices,
            "volume": volume,
        }, index=timestamps)
        df.index.name = "timestamp"

        return df.astype(float)

    def generate_signal_ohlcv(self, direction: str = "long", n: int = 300) -> pd.DataFrame:
        """
        특정 신호가 발생하도록 조작된 OHLCV 데이터 생성
        direction: "long" | "short" | "none"
        """
        base = 100.0
        np.random.seed(42)

        if direction == "long":
            # 상승 추세 + BB 하단 터치 후 반등 + MACD 양전환
            trend = np.linspace(0, 0.3, n)  # 약 30% 상승
            noise = np.random.normal(0, 0.008, n)
            prices = base * (1 + trend + noise)
            # 마지막 3봉: 급락 후 반등 패턴 (BB 하단 터치)
            prices[-3] = prices[-4] * 0.97  # 급락
            prices[-2] = prices[-3] * 0.985  # BB 하단 터치
            prices[-1] = prices[-2] * 1.02   # 반등

        elif direction == "short":
            # 하락 추세 + BB 상단 터치 후 반전
            trend = np.linspace(0, -0.3, n)
            noise = np.random.normal(0, 0.008, n)
            prices = base * (1 + trend + noise)
            prices[-3] = prices[-4] * 1.03
            prices[-2] = prices[-3] * 1.015
            prices[-1] = prices[-2] * 0.98

        else:  # none — 횡보
            noise = np.random.normal(0, 0.003, n)
            prices = base * (1 + noise.cumsum() * 0.01)

        high = prices * (1 + np.abs(np.random.normal(0, 0.003, n)))
        low = prices * (1 - np.abs(np.random.normal(0, 0.003, n)))
        volume = np.random.uniform(2_000_000, 30_000_000, n)

        timestamps = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="15min")

        df = pd.DataFrame({
            "open": prices * (1 + np.random.normal(0, 0.0005, n)),
            "high": high,
            "low": low,
            "close": prices,
            "volume": volume,
        }, index=timestamps)
        df.index.name = "timestamp"

        return df.astype(float)

    def get_tickers(self) -> Dict[str, Dict]:
        """전종목 현재가 일괄 조회 (Mock)"""
        res = {}
        for sym in self.get_all_usdt_swap_symbols():
            res[sym] = self.get_ticker(sym)
        return res

    def get_ticker(self, symbol: str) -> Dict:
        base_prices = {
            "BTC/USDT:USDT": 67000.0,
            "ETH/USDT:USDT": 3800.0,
            "SOL/USDT:USDT": 170.0,
            "DOGE/USDT:USDT": 0.15,
            "XRP/USDT:USDT": 0.55,
        }
        price = base_prices.get(symbol, 100.0)
        return {
            "symbol": symbol,
            "last": price,
            "bid": price * 0.9999,
            "ask": price * 1.0001,
            "volume": 15_000_000.0,
            "change_pct": 1.5,
        }

    def get_all_usdt_swap_symbols(self) -> List[str]:
        return sorted([
            sym for sym, mkt in self._markets.items()
            if mkt.get("quote") == "USDT"
            and mkt.get("type") == "swap"
            and mkt.get("active", False)
        ])

    # ── 주문 실행 (시뮬레이션) ──────────────────────────

    def set_margin_mode(self, symbol: str, margin_mode: str = "isolated") -> bool:
        logger.info(f"[MOCK] 마진 모드 설정: {symbol} {margin_mode}")
        return True

    def set_leverage(self, symbol: str, leverage: int) -> bool:
        logger.info(f"[MOCK] 레버리지 설정: {symbol} {leverage}x")
        return True

    def get_market_max_leverage(self, symbol: str) -> int:
        market = self._markets.get(symbol, {})
        limits = market.get("limits", {})
        leverage = limits.get("leverage", {})
        return int(leverage.get("max", 20))

    def cancel_all_orders(self, symbol: str) -> bool:
        logger.info(f"[MOCK] 주문 취소 완료: {symbol}")
        self._orders = [o for o in self._orders if o["symbol"] != symbol]
        return True

    def place_order(
        self,
        symbol: str,
        side: str,
        margin_usdt: float,
        stop_loss_pct: float = CFG.STOP_LOSS_PCT,
        take_profit_pct: float = CFG.TAKE_PROFIT_PCT,
    ) -> Optional[Dict]:
        """시뮬레이션 주문 — 실 API 호출 없음"""
        if self._fail_next_order:
            self._fail_next_order = False
            logger.warning(f"[MOCK] 주문 실패 시뮬레이션: {symbol}")
            return None

        ticker = self.get_ticker(symbol)
        price = ticker["last"]
        policy_max = self.get_market_max_leverage(symbol)
        applied_leverage = min(CFG.LEVERAGE, policy_max)

        notional = margin_usdt * applied_leverage
        market = self._markets.get(symbol, {})
        contract_size = market.get("contractSize", 1.0) or 1.0
        amount = notional / (price * contract_size)

        self._order_counter += 1
        order_id = f"MOCK-{self._order_counter:06d}"

        sl_price = (
            price * (1 - stop_loss_pct) if side == "buy"
            else price * (1 + stop_loss_pct)
        )
        tp_price = (
            price * (1 + take_profit_pct) if side == "buy"
            else price * (1 - take_profit_pct)
        )

        # 포지션 추가
        pos = self._make_position(
            symbol,
            "long" if side == "buy" else "short",
            price,
            mark=price,
            size=amount,
        )
        self._positions.append(pos)

        # 잔고 업데이트
        self._balance["free"] -= margin_usdt
        self._balance["used"] += margin_usdt

        result = {
            "order_id": order_id,
            "symbol": symbol,
            "side": "long" if side == "buy" else "short",
            "entry_price": price,
            "amount": round(amount, 6),
            "sl_price": round(sl_price, 6),
            "tp_price": round(tp_price, 6),
            "usdt_margin": margin_usdt,
        }

        self._trade_history.append({
            "timestamp": pd.Timestamp.now(),
            "symbol": symbol,
            "category": "진입",
            "side": side,
            "price": price,
            "amount": amount,
            "cost": notional,
            "pnl": 0,
            "pnl_pct": 0,
            "fee": round(notional * 0.0005, 6),
            "order_id": order_id,
        })

        logger.info(f"[MOCK] 주문 완료: {result}")
        return result

    def close_position(self, symbol: str, side: str) -> bool:
        """포지션 청산 시뮬레이션"""
        target_idx = None
        for i, p in enumerate(self._positions):
            if p["symbol"] == symbol:
                target_idx = i
                break

        if target_idx is None:
            return False

        closed = self._positions.pop(target_idx)
        pnl = closed["pnl_usdt"]
        margin = closed["margin"]

        self._balance["free"] += margin + pnl
        self._balance["used"] -= margin
        self._balance["total"] += pnl

        self._closed_pnl.append({
            "symbol": symbol,
            "pnl_usdt": pnl,
        })

        logger.info(f"[MOCK] 청산 완료: {symbol} PnL={pnl:+.4f}")
        return True

    def close_all_positions(self) -> int:
        count = len(self._positions)
        for p in list(self._positions):
            self.close_position(p["symbol"], p["side"])
        return count
