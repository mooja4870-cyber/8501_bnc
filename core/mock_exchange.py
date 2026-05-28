"""
AI QUANTUM — Mock Exchange Client (Async)
"""
import pandas as pd
import numpy as np
import logging
import time
import asyncio
from typing import Optional, Dict, List
from core.config import CFG

logger = logging.getLogger(__name__)

class MockBinanceClient:
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

    def set_scenario(self, name: str):
        self._scenario = name
        self._fail_balance = False
        self._fail_positions = False
        if name == "default":
            self._balance = {"total": 100.0, "free": 80.0, "used": 20.0}
            self._positions = []
        elif name == "low_balance":
            self._balance = {"total": 0.5, "free": 0.3, "used": 0.2}
            self._positions = []
        elif name == "no_margin":
            self._balance = {"total": 50.0, "free": 0.5, "used": 49.5}
            self._positions = []
        elif name == "max_positions":
            self._balance = {"total": 100.0, "free": 30.0, "used": 70.0}
            self._positions = [self._make_position(f"MOCK{i}/USDT:USDT", "long", 10.0 + i) for i in range(CFG.MAX_POSITIONS)]
        elif name == "with_positions":
            self._balance = {"total": 100.0, "free": 60.0, "used": 40.0}
            self._positions = [
                self._make_position("BTC/USDT:USDT", "long", 67000.0),
                self._make_position("ETH/USDT:USDT", "short", 3800.0),
            ]
        elif name == "profitable":
            self._balance = {"total": 150.0, "free": 100.0, "used": 50.0}
            self._positions = [self._make_position("BTC/USDT:USDT", "long", 65000.0, mark=68000.0)]
        elif name == "losing":
            self._balance = {"total": 80.0, "free": 30.0, "used": 50.0}
            self._positions = [self._make_position("BTC/USDT:USDT", "long", 70000.0, mark=66000.0)]
        elif name == "api_error":
            self._fail_balance = True
            self._fail_positions = True
        logger.info(f"[MOCK] 시나리오 변경: {name}")

    def _make_position(self, symbol: str, side: str, entry: float, mark: float = None, size: float = 1.0) -> Dict:
        if mark is None:
            mark = entry * (1.005 if side == "long" else 0.995)
        lev = CFG.LEVERAGE
        raw = (mark - entry) / entry
        pct = raw * lev if side == "long" else -raw * lev
        return {
            "symbol": symbol, "side": side, "size": size, "coins": size,
            "entry_price": entry, "mark_price": mark, "pnl_pct": round(pct * 100, 2),
            "pnl_usdt": round(raw * entry * size, 4), "leverage": lev,
            "margin": round(entry * size / lev, 4),
            "timestamp": int(time.time() * 1000) - 3600_000,
            "amount_usdt": round(entry * size, 2),
        }

    async def load_markets(self) -> bool:
        self._markets = {
            "BTC/USDT:USDT": {"quote": "USDT", "type": "swap", "active": True, "contractSize": 0.01, "limits": {"leverage": {"max": 125}}},
            "ETH/USDT:USDT": {"quote": "USDT", "type": "swap", "active": True, "contractSize": 0.1, "limits": {"leverage": {"max": 100}}},
            "SOL/USDT:USDT": {"quote": "USDT", "type": "swap", "active": True, "contractSize": 1.0, "limits": {"leverage": {"max": 75}}},
            "DOGE/USDT:USDT": {"quote": "USDT", "type": "swap", "active": True, "contractSize": 100.0, "limits": {"leverage": {"max": 50}}},
            "XRP/USDT:USDT": {"quote": "USDT", "type": "swap", "active": True, "contractSize": 10.0, "limits": {"leverage": {"max": 75}}},
        }
        logger.info(f"[MOCK] 마켓 로드 완료: {len(self._markets)}개 종목")
        return True

    async def get_balance(self) -> Dict:
        if self._fail_balance: raise Exception("Mock API Error: 잔고 조회 실패")
        return dict(self._balance)

    async def get_positions(self) -> List[Dict]:
        if self._fail_positions: raise Exception("Mock API Error: 포지션 조회 실패")
        return list(self._positions)

    async def get_open_orders(self) -> List[Dict]:
        return list(self._orders)

    async def get_trade_history(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict]:
        trades = self._trade_history
        if symbol: trades = [t for t in trades if t["symbol"] == symbol]
        return trades[-limit:]

    async def get_closed_positions_pnl(self, limit=20) -> List[Dict]:
        return self._closed_pnl[-limit:]

    async def get_ohlcv(self, symbol: str, timeframe: Optional[str] = None, limit: int = 300) -> pd.DataFrame:
        np.random.seed(hash(symbol) % 2**31)
        n = max(limit, 250)
        base_prices = {"BTC/USDT:USDT": 67000.0, "ETH/USDT:USDT": 3800.0, "SOL/USDT:USDT": 170.0, "DOGE/USDT:USDT": 0.15, "XRP/USDT:USDT": 0.55}
        base = base_prices.get(symbol, 100.0)
        returns = np.random.normal(0.0002, 0.015, n)
        prices = base * np.cumprod(1 + returns)
        high = prices * (1 + np.abs(np.random.normal(0, 0.005, n)))
        low = prices * (1 - np.abs(np.random.normal(0, 0.005, n)))
        volume = np.random.uniform(1_000_000, 50_000_000, n)
        timestamps = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="15min")
        df = pd.DataFrame({"open": prices * (1 + np.random.normal(0, 0.001, n)), "high": high, "low": low, "close": prices, "volume": volume}, index=timestamps)
        df.index.name = "timestamp"
        return df.astype(float)

    async def get_tickers(self) -> Dict[str, Dict]:
        res = {}
        for sym in self.get_all_usdt_swap_symbols():
            res[sym] = await self.get_ticker(sym)
        return res

    async def get_ticker(self, symbol: str) -> Dict:
        base_prices = {"BTC/USDT:USDT": 67000.0, "ETH/USDT:USDT": 3800.0, "SOL/USDT:USDT": 170.0, "DOGE/USDT:USDT": 0.15, "XRP/USDT:USDT": 0.55}
        price = base_prices.get(symbol, 100.0)
        return {"symbol": symbol, "last": price, "bid": price * 0.9999, "ask": price * 1.0001, "volume": 15_000_000.0, "change_pct": 1.5}

    def get_all_usdt_swap_symbols(self) -> List[str]:
        return sorted([sym for sym, mkt in self._markets.items() if mkt.get("quote") == "USDT" and mkt.get("type") == "swap" and mkt.get("active", False)])

    async def set_margin_mode(self, symbol: str, margin_mode: str = "isolated") -> bool:
        return True

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        return True

    def get_market_max_leverage(self, symbol: str) -> int:
        market = self._markets.get(symbol, {})
        limits = market.get("limits", {})
        leverage = limits.get("leverage", {})
        return int(leverage.get("max", 20))

    async def fetch_order(self, id: str, symbol: str) -> Dict:
        for t in self._trade_history:
            if t.get("order_id") == id:
                return {
                    "id": id,
                    "symbol": symbol,
                    "status": "closed",
                    "filled": t.get("amount", 0.0),
                    "amount": t.get("amount", 0.0),
                    "price": t.get("price", 0.0)
                }
        for o in self._orders:
            if o.get("id") == id:
                return o
        return {"id": id, "symbol": symbol, "status": "open", "filled": 0.0, "amount": 1.0}

    async def cancel_all_orders(self, symbol: str) -> bool:
        self._orders = [o for o in self._orders if o["symbol"] != symbol]
        return True

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        self._orders = [o for o in self._orders if o["id"] != order_id]
        return True

    async def place_order(self, symbol: str, side: str, margin_usdt: float, stop_loss_pct: float = CFG.STOP_LOSS_PCT, take_profit_pct: float = CFG.TAKE_PROFIT_PCT) -> Optional[Dict]:
        if self._fail_next_order:
            self._fail_next_order = False
            return None
        ticker = await self.get_ticker(symbol)
        price = ticker["last"]
        policy_max = self.get_market_max_leverage(symbol)
        applied_leverage = min(CFG.LEVERAGE, policy_max)
        notional = margin_usdt * applied_leverage
        market = self._markets.get(symbol, {})
        contract_size = market.get("contractSize", 1.0) or 1.0
        amount = notional / (price * contract_size)
        self._order_counter += 1
        order_id = f"MOCK-{self._order_counter:06d}"
        sl_price = price * (1 - stop_loss_pct) if side == "buy" else price * (1 + stop_loss_pct)
        tp_price = price * (1 + take_profit_pct) if side == "buy" else price * (1 - take_profit_pct)
        pos = self._make_position(symbol, "long" if side == "buy" else "short", price, mark=price, size=amount)
        self._positions.append(pos)
        self._balance["free"] -= margin_usdt
        self._balance["used"] += margin_usdt
        result = {"order_id": order_id, "symbol": symbol, "side": "long" if side == "buy" else "short", "entry_price": price, "amount": round(amount, 6), "sl_price": round(sl_price, 6), "tp_price": round(tp_price, 6), "usdt_margin": margin_usdt}
        self._trade_history.append({"timestamp": pd.Timestamp.now(), "symbol": symbol, "category": "진입", "side": side, "price": price, "amount": amount, "cost": notional, "pnl": 0, "pnl_pct": 0, "fee": round(notional * 0.0005, 6), "order_id": order_id})
        return result

    async def close_position(self, symbol: str, side: str) -> bool:
        target_idx = None
        for i, p in enumerate(self._positions):
            if p["symbol"] == symbol:
                target_idx = i
                break
        if target_idx is None: return False
        closed = self._positions.pop(target_idx)
        pnl = closed["pnl_usdt"]
        margin = closed["margin"]
        self._balance["free"] += margin + pnl
        self._balance["used"] -= margin
        self._balance["total"] += pnl
        self._closed_pnl.append({"symbol": symbol, "pnl_usdt": pnl})
        return True

    async def close_all_positions(self) -> int:
        count = len(self._positions)
        for p in list(self._positions):
            await self.close_position(p["symbol"], p["side"])
        return count
