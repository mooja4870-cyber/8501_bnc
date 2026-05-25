"""
AI QUANTUM — Orchestration Engine (v2 Async Enterprise)
모든 모듈을 통합 관리하는 중앙 컨트롤러. 비동기 이벤트 루프를 백그라운드 스레드에서 구동하여 UI 블로킹 방지.
"""
import logging
import threading
import asyncio
import time
import inspect
from enum import Enum, auto
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta

from core.exchange import BinanceClient
from core.scanner import Scanner
from core.trader import AutoTrader
from core.config import CFG
import core.stats as stats_store
from core.logger import log_trade as csv_log
from core.history_helper import (
    compact_local_trade_history,
    get_position_direction,
    load_local_trade_history,
    _normalize_id,
    _trade_dedupe_key,
)

logger = logging.getLogger(__name__)

class EngineState(Enum):
    IDLE = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    SCANNING = auto()
    TRADING = auto()
    ERROR = auto()
    RECOVERING = auto()

_TRANSITIONS = {
    EngineState.IDLE:       {EngineState.CONNECTING},
    EngineState.CONNECTING: {EngineState.CONNECTED, EngineState.ERROR},
    EngineState.CONNECTED:  {EngineState.SCANNING, EngineState.IDLE, EngineState.CONNECTING, EngineState.ERROR},
    EngineState.SCANNING:   {EngineState.TRADING, EngineState.CONNECTED, EngineState.ERROR, EngineState.CONNECTING},
    EngineState.TRADING:    {EngineState.SCANNING, EngineState.CONNECTED, EngineState.ERROR, EngineState.CONNECTING},
    EngineState.ERROR:      {EngineState.RECOVERING, EngineState.IDLE, EngineState.CONNECTING},
    EngineState.RECOVERING: {EngineState.CONNECTED, EngineState.ERROR, EngineState.IDLE, EngineState.CONNECTING},
}

class QuantumEngine:
    _instance = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.client: Optional[BinanceClient] = None
        self.scanner: Optional[Scanner] = None
        self.trader: Optional[AutoTrader] = None
        self.cfg = CFG

        self._initialized = False
        self._prev_position_symbols: set = set()

        self._state = EngineState.IDLE
        self._state_lock = threading.Lock()
        self._error_msg = ""
        self._recovery_attempts = 0
        self._max_recovery_attempts = 3

        self._api_key = ""
        self._secret_key = ""
        self._passphrase = ""

        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._start_loop, daemon=True)
        self._loop_thread.start()
        
        self._async_lock = None 

    def _start_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    # --- Sync Wrappers for Streamlit UI ---

    def initialize(self, api_key: str, secret_key: str, passphrase: str) -> tuple[bool, str]:
        future = asyncio.run_coroutine_threadsafe(self._initialize_async(api_key, secret_key, passphrase), self._loop)
        return future.result()

    def start_scanner(self):
        asyncio.run_coroutine_threadsafe(self._start_scanner_async(), self._loop)

    def stop_scanner(self):
        future = asyncio.run_coroutine_threadsafe(self._stop_scanner_async(), self._loop)
        future.result()

    def enable_trading(self):
        asyncio.run_coroutine_threadsafe(self._enable_trading_async(), self._loop)

    def disable_trading(self):
        asyncio.run_coroutine_threadsafe(self._disable_trading_async(), self._loop)

    def attempt_recovery(self) -> tuple[bool, str]:
        future = asyncio.run_coroutine_threadsafe(self._attempt_recovery_async(), self._loop)
        return future.result()

    def get_dashboard_data(self) -> Dict:
        future = asyncio.run_coroutine_threadsafe(self._get_dashboard_data_async(), self._loop)
        return future.result()

    def get_scanner_logs(self, last_n: int = 50) -> list[str]:
        if not self.scanner:
            return ["[SYS] 엔진 미연결"]
        future = asyncio.run_coroutine_threadsafe(self.scanner.get_logs(last_n), self._loop)
        return future.result()

    def clear_scanner_cache(self) -> None:
        if self.scanner:
            future = asyncio.run_coroutine_threadsafe(self.scanner.clear_cache(), self._loop)
            future.result()

    def close_position(self, symbol: str, side: str) -> bool:
        if not self.is_ready:
            return False
        future = asyncio.run_coroutine_threadsafe(self.client.close_position(symbol, side), self._loop)
        return future.result()

    def close_all_positions(self) -> int:
        if not self.is_ready:
            return 0
        future = asyncio.run_coroutine_threadsafe(self.client.close_all_positions(), self._loop)
        return future.result()

    def get_scan_results(self) -> List[Dict]:
        if not self.scanner: return []
        future = asyncio.run_coroutine_threadsafe(self.scanner.get_results(), self._loop)
        return future.result()

    def get_system_logs(self, limit: int = 50) -> List[str]:
        if not self.scanner: return []
        future = asyncio.run_coroutine_threadsafe(self.scanner.get_logs(limit), self._loop)
        return future.result()

    def get_trade_history(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict]:
        if not self.client: return []
        future = asyncio.run_coroutine_threadsafe(self.client.get_trade_history(symbol, limit), self._loop)
        return future.result()

    def sync_trades_to_csv(self) -> int:
        if not self.is_ready:
            return 0
        future = asyncio.run_coroutine_threadsafe(self._sync_trades_to_csv_async(), self._loop)
        return future.result()

    def _check_closed_positions(self):
        if not self.is_ready:
            return
        future = asyncio.run_coroutine_threadsafe(self._check_closed_positions_async(), self._loop)
        return future.result()

    def get_health(self) -> Dict:
        return {
            "engine_state": self._state.name,
            "api_connected": self.is_ready,
            "scanner_running": self.scanner.is_running if self.scanner else False,
            "trading_enabled": self.trader.enabled if self.trader else False,
            "recovery_attempts": self._recovery_attempts,
            "last_error": self._error_msg,
            "scan_count": self.scanner.scan_count if self.scanner else 0,
        }

    @property
    def state(self) -> EngineState:
        return self._state
        
    @property
    def is_ready(self) -> bool:
        return self._initialized and self.client is not None

    def _transition(self, new_state: EngineState, reason: str = ""):
        with self._state_lock:
            allowed = _TRANSITIONS.get(self._state, set())
            if new_state not in allowed:
                logger.warning(f"[FSM] 유효하지 않은 전이: {self._state.name} → {new_state.name}")
                return False
            old = self._state
            self._state = new_state
            logger.info(f"[FSM] {old.name} → {new_state.name} | {reason}")
            return True

    # --- Async Implementations ---

    async def _initialize_async(self, api_key: str, secret_key: str, passphrase: str) -> tuple[bool, str]:
        if self._initialized and self._state != EngineState.ERROR and self._api_key == api_key and self._secret_key == secret_key:
            return True, "✅ 엔진이 이미 활성화되어 있습니다."

        self._transition(EngineState.CONNECTING, "API 연결 시도")
        self._api_key = api_key
        self._secret_key = secret_key
        self._passphrase = passphrase

        if self._async_lock is None:
            self._async_lock = asyncio.Lock()

        async with self._async_lock:
            try:
                self.client = BinanceClient(api_key, secret_key, passphrase)
                if await self.client.load_markets():
                    self.scanner = Scanner(self.client)
                    self.trader = AutoTrader(self.client)

                    self.scanner.on_signal = self.trader.on_signal
                    self.scanner.on_scan_complete = self._check_closed_positions_async

                    self._initialized = True
                    self._recovery_attempts = 0
                    self._transition(EngineState.CONNECTED, "마켓 로드 성공")
                    
                    asyncio.create_task(self._health_check_loop())
                    return True, "✅ 엔진 초기화 및 마켓 로드 성공"

                self._error_msg = "마켓 정보 로드 실패"
                self._transition(EngineState.ERROR, self._error_msg)
                return False, f"❌ {self._error_msg}"
            except Exception as e:
                self._error_msg = str(e)
                logger.error(f"엔진 초기화 실패: {e}")
                self._transition(EngineState.ERROR, f"초기화 예외: {e}")
                return False, f"❌ 엔진 초기화 오류: {e}"

    async def _start_scanner_async(self):
        if self.scanner and not self.scanner.is_running:
            self.scanner.start()
            self._transition(EngineState.SCANNING, "스캐너 시작")

    async def _stop_scanner_async(self):
        if self.scanner:
            await self.scanner.stop()
            if self._state == EngineState.TRADING:
                await self._disable_trading_async()
            if self.is_ready:
                self._transition(EngineState.CONNECTED, "스캐너 중지")

    async def _enable_trading_async(self):
        if self.trader:
            self.trader.enable()
            if self._state == EngineState.SCANNING:
                self._transition(EngineState.TRADING, "자동매매 활성화")

    async def _disable_trading_async(self):
        if self.trader:
            self.trader.disable()
            if self._state == EngineState.TRADING:
                self._transition(EngineState.SCANNING, "자동매매 비활성화")

    async def _attempt_recovery_async(self) -> tuple[bool, str]:
        if self._state != EngineState.ERROR:
            return False, "ERROR 상태가 아님"

        if self._recovery_attempts >= self._max_recovery_attempts:
            return False, f"최대 복구 횟수 초과 ({self._max_recovery_attempts}회)"

        self._transition(EngineState.RECOVERING, f"복구 시도 #{self._recovery_attempts + 1}")
        self._recovery_attempts += 1

        wait = min(2 ** self._recovery_attempts, 30)
        logger.info(f"[RECOVERY] {wait}초 대기 후 재연결...")
        await asyncio.sleep(wait)

        if self._api_key:
            success, msg = await self._initialize_async(self._api_key, self._secret_key, self._passphrase)
            if success:
                return True, f"✅ 복구 성공 (시도 #{self._recovery_attempts})"

        self._transition(EngineState.ERROR, "복구 실패")
        return False, f"❌ 복구 실패 (시도 #{self._recovery_attempts})"

    async def _get_dashboard_data_async(self) -> Dict:
        if not self.is_ready:
            return {}

        try:
            balance = await self.client.get_balance()
            positions = await self.client.get_positions()
        except Exception as e:
            logger.error(f"대시보드 데이터 조회 실패: {e}")
            self._error_msg = str(e)
            if self._state not in (EngineState.ERROR, EngineState.RECOVERING):
                self._transition(EngineState.ERROR, f"데이터 조회 실패: {e}")
            return {}

        return {
            "total_balance": balance.get("total", 0),
            "free_margin": balance.get("free", 0),
            "used_margin": balance.get("used", 0),
            "realized_pnl": balance.get("pnl", 0),
            "positions": positions,
            "is_scanning": self.scanner.is_running if self.scanner else False,
            "is_trading": self.trader.enabled if self.trader else False,
            "engine_state": self._state.name,
        }

    async def _health_check_loop(self):
        while True:
            await asyncio.sleep(60)
            if not self.is_ready or self._state == EngineState.ERROR:
                continue
            try:
                await self.client.get_balance()
            except Exception as e:
                logger.error(f"[HEALTH CHECK] 연결 유실 감지: {e}")
                self._error_msg = str(e)
                self._transition(EngineState.ERROR, "Health Check 실패")
                await self._attempt_recovery_async()

    async def _check_closed_positions_async(self):
        if not self.is_ready:
            return
        try:
            raw_positions = await self._maybe_await(self.client.get_positions())
            current = {p["symbol"] for p in raw_positions}
            closed = self._prev_position_symbols - current

            if closed:
                for sym in closed:
                    pnl = 0.0
                    try:
                        recent_trades = await self._maybe_await(self.client.get_trade_history(symbol=sym, limit=5))
                        exit_trade = next((t for t in recent_trades if t.get("category") == "청산"), None)
                        if exit_trade and not self._is_trade_logged(exit_trade):
                            pnl = exit_trade.get("pnl", 0.0)
                            csv_log({
                                "timestamp": exit_trade.get("timestamp", datetime.now(timezone(timedelta(hours=9)))),
                                "symbol": sym,
                                "type": "청산",
                                "side": exit_trade.get("side", ""),
                                "price": exit_trade.get("price", 0),
                                "amount": exit_trade.get("amount", 0),
                                "pnl_usdt": pnl,
                                "pnl_pct": exit_trade.get("pnl_pct", 0),
                                "leverage": self.cfg.LEVERAGE,
                                "order_id": exit_trade.get("order_id", ""),
                                "trade_id": exit_trade.get("id", ""),
                            })
                        elif exit_trade:
                            pnl = exit_trade.get("pnl", 0.0)
                    except Exception as e:
                        logger.error(f"청산 CSV 기록 실패: {e}")

                    stats_store.record_result(pnl)
                    if self.trader:
                        self.trader.daily_pnl_usdt = round(self.trader.daily_pnl_usdt + pnl, 4)
                        self.trader.trigger_symbol_cooldown(sym, 60)
                    logger.info(f"[CLOSED] {sym} PnL={pnl:+.4f} -> {'WIN' if pnl >= 0 else 'LOSS'}")

            if self.cfg.MAX_HOLDING_HOURS > 0:
                now_ms = time.time() * 1000
                timeout_ms = self.cfg.MAX_HOLDING_HOURS * 3600 * 1000
                for p in raw_positions:
                    entry_ts = p.get("timestamp")
                    if entry_ts and (now_ms - entry_ts) > timeout_ms:
                        sym = p["symbol"]
                        side = p["side"]
                        logger.warning(f"[TIMEOUT] {sym} {side} - {self.cfg.MAX_HOLDING_HOURS}시간 초과 강제청산 실행")
                        await self._maybe_await(self.client.close_position(sym, side))
                        if self.trader:
                            self.trader.trigger_symbol_cooldown(sym, 60)

            self._prev_position_symbols = current
            await self._run_position_rotation_check_async(raw_positions)
        except Exception as e:
            logger.error(f"청산 감지 오류: {e}")

    async def _run_position_rotation_check_async(self, raw_positions: List[Dict]):
        if not self.cfg.ROTATION_ENABLED:
            return

        scan_results = await self._maybe_await(self.scanner.get_results())
        scan_signals = [s for s in scan_results if s.get("signal") in ("long", "short") and s.get("strength", 0) >= 60]
        if len(scan_signals) < self.cfg.ROTATION_MIN_SIGNALS:
            return

        now_ms = time.time() * 1000
        stale_limit_ms = self.cfg.ROTATION_STALE_HOURS * 3600 * 1000

        for p in raw_positions:
            entry_ts = p.get("timestamp")
            if not entry_ts:
                continue

            if (now_ms - entry_ts) > stale_limit_ms:
                if await self._is_flow_bad_async(p):
                    sym = p["symbol"]
                    side = p["side"]
                    pnl = float(p.get("pnl_usdt", 0.0))
                    pnl_pct = float(p.get("pnl_pct", 0.0))
                    
                    logger.warning(f"[ROTATION] {sym} {side} 정체 포지션 감지. 시장가 청산 실행.")
                    
                    close_res = await self._maybe_await(self.client.close_position(sym, side))
                    if close_res:
                        if self.trader:
                            self.trader.trigger_symbol_cooldown(sym, 60)
                        csv_log({
                            "timestamp": datetime.now(timezone(timedelta(hours=9))),
                            "symbol": sym,
                            "type": "청산(로테이션)",
                            "side": side,
                            "price": p.get("mark_price", 0.0),
                            "amount": p.get("size", 0.0),
                            "pnl_usdt": pnl,
                            "pnl_pct": pnl_pct,
                            "leverage": p.get("leverage", self.cfg.LEVERAGE),
                            "order_id": f"ROT-{int(now_ms)}",
                            "trade_id": f"ROT-{int(now_ms)}",
                        })
                        stats_store.record_result(pnl)
                        if self.trader:
                            self.trader.daily_pnl_usdt = round(self.trader.daily_pnl_usdt + pnl, 4)

    async def _maybe_await(self, value):
        if inspect.isawaitable(value):
            return await value
        return value

    def _logged_trade_keys(self) -> set:
        try:
            return {_trade_dedupe_key(t) for t in load_local_trade_history()}
        except Exception as e:
            logger.error(f"로컬 거래 키 로드 실패: {e}")
            return set()

    def _exchange_trade_key(self, trade: Dict):
        normalized = {
            "timestamp": trade.get("timestamp"),
            "symbol": trade.get("symbol"),
            "category": trade.get("category"),
            "side": trade.get("side"),
            "price": trade.get("price"),
            "amount": trade.get("amount"),
            "pnl": trade.get("pnl"),
            "order_id": _normalize_id(trade.get("order_id") or trade.get("order")),
            "trade_id": _normalize_id(trade.get("trade_id") or trade.get("id")),
        }
        return _trade_dedupe_key(normalized)

    def _is_trade_logged(self, trade: Dict) -> bool:
        return self._exchange_trade_key(trade) in self._logged_trade_keys()

    @staticmethod
    def _remaining_lots(local_trades: List[Dict]) -> Dict[tuple, float]:
        lots: Dict[tuple, float] = {}
        for trade in sorted(local_trades, key=lambda x: x["timestamp"]):
            direction = get_position_direction(trade["category"], trade["side"])
            key = (trade["symbol"], direction)
            amount = float(trade.get("amount") or 0)
            if trade["category"] in ("진입", "*진입"):
                lots[key] = lots.get(key, 0.0) + amount
            elif trade["category"] in ("청산", "청산(로테이션)"):
                lots[key] = max(0.0, lots.get(key, 0.0) - amount)
        return lots

    @staticmethod
    def _infer_trade_category(trade: Dict, lots: Dict[tuple, float]) -> str:
        reported = trade.get("category")
        if reported in ("청산", "청산(로테이션)"):
            return "청산"

        side = str(trade.get("side", "")).lower()
        symbol = trade.get("symbol")
        if side == "sell" and lots.get((symbol, "LONG"), 0.0) > 1e-8:
            return "청산"
        if side == "buy" and lots.get((symbol, "SHORT"), 0.0) > 1e-8:
            return "청산"
        return "진입"

    @staticmethod
    def _apply_trade_to_lots(trade: Dict, category: str, lots: Dict[tuple, float]) -> None:
        symbol = trade.get("symbol")
        amount = float(trade.get("amount") or 0)
        direction = get_position_direction(category, trade.get("side", ""))
        key = (symbol, direction)
        if category == "진입":
            lots[key] = lots.get(key, 0.0) + amount
        else:
            lots[key] = max(0.0, lots.get(key, 0.0) - amount)

    async def _sync_trades_to_csv_async(self) -> int:
        if not self.client:
            return 0

        removed = 0
        try:
            removed = compact_local_trade_history()
            if removed:
                logger.info(f"로컬 CSV 중복 거래 {removed}건 정리 완료")
        except Exception as e:
            logger.error(f"로컬 CSV 중복 정리 실패: {e}")

        local_trades = load_local_trade_history()
        logged_keys = {_trade_dedupe_key(t) for t in local_trades}
        lots = self._remaining_lots(local_trades)
        target_symbols = {t["symbol"] for t in local_trades[-80:]}

        try:
            positions = await self._maybe_await(self.client.get_positions())
            for p in positions:
                target_symbols.add(p["symbol"])
        except Exception as e:
            logger.error(f"동기화 대상 포지션 조회 실패: {e}")

        if not target_symbols:
            return removed

        exchange_trades = []
        for symbol in sorted(target_symbols):
            try:
                trades = await self._maybe_await(self.client.get_trade_history(symbol=symbol, limit=100))
                exchange_trades.extend(trades or [])
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"{symbol} 거래소 체결 이력 조회 실패: {e}")

        new_count = 0
        for trade in sorted(exchange_trades, key=lambda x: x.get("timestamp")):
            key = self._exchange_trade_key(trade)
            if key in logged_keys:
                continue

            category = self._infer_trade_category(trade, lots)
            leverage = self.cfg.LEVERAGE
            if category == "청산":
                for local in reversed(local_trades):
                    if local["symbol"] == trade["symbol"] and local["category"] in ("진입", "*진입"):
                        leverage = local.get("leverage") or leverage
                        break

            pnl = float(trade.get("pnl") or 0.0)
            cost = float(trade.get("cost") or 0.0)
            pnl_pct = float(trade.get("pnl_pct") or 0.0)
            if category == "청산" and cost > 0 and leverage:
                margin_est = cost / float(leverage)
                if margin_est > 0:
                    pnl_pct = round((pnl / margin_est) * 100, 2)

            csv_log({
                "timestamp": trade["timestamp"],
                "symbol": trade["symbol"],
                "type": category,
                "side": trade.get("side", ""),
                "price": trade.get("price", 0),
                "amount": trade.get("amount", 0),
                "pnl_usdt": pnl,
                "pnl_pct": pnl_pct,
                "leverage": leverage,
                "order_id": _normalize_id(trade.get("order_id") or trade.get("order")),
                "trade_id": _normalize_id(trade.get("trade_id") or trade.get("id")),
            })

            logged_keys.add(key)
            local_record = {
                "timestamp": trade["timestamp"],
                "symbol": trade["symbol"],
                "category": category,
                "side": trade.get("side", ""),
                "price": float(trade.get("price") or 0),
                "amount": float(trade.get("amount") or 0),
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "leverage": leverage,
                "order_id": _normalize_id(trade.get("order_id") or trade.get("order")),
                "trade_id": _normalize_id(trade.get("trade_id") or trade.get("id")),
            }
            local_trades.append(local_record)
            self._apply_trade_to_lots(local_record, category, lots)
            new_count += 1

        if new_count:
            logger.info(f"로컬 CSV에 {new_count}개의 새로운 거래 내역을 추가 동기화했습니다.")
        return removed + new_count

    async def _is_flow_bad_async(self, p: Dict) -> bool:
        symbol = p["symbol"]
        side = p["side"]
        entry_price = float(p.get("entry_price") or 0.0)
        current_price = float(p.get("mark_price") or p.get("current_price") or 0.0)
        
        if entry_price <= 0 or current_price <= 0:
            return False

        check_type = self.cfg.ROTATION_FLOW_CHECK
        if check_type == "momentum":
            try:
                df = await self._maybe_await(self.client.get_ohlcv(symbol, timeframe="15m", limit=50))
                if not df.empty and len(df) >= 20:
                    ema = df["close"].ewm(span=20, adjust=False).mean().iloc[-1]
                    if "long" in side.lower() or "buy" in side.lower():
                        return current_price < ema
                    else:
                        return current_price > ema
            except Exception:
                return False
        elif check_type == "flat":
            try:
                entry_ts = p.get("timestamp")
                if entry_ts:
                    now_ms = time.time() * 1000
                    duration_min = int((now_ms - entry_ts) / 60000)
                    limit = min(max(duration_min, 10), 200)
                    df = await self._maybe_await(self.client.get_ohlcv(symbol, timeframe="1m", limit=limit))
                    if not df.empty:
                        highs = df["high"].max()
                        lows = df["low"].min()
                        amplitude = (highs - lows) / entry_price
                        return amplitude < 0.0025
            except Exception:
                return False
        elif check_type == "time":
            pnl_pct = float(p.get("pnl_pct") or 0.0)
            return -2.0 <= pnl_pct <= 1.0

        return False
