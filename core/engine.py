"""
AI QUANTUM — Orchestration Engine (v2 Async Enterprise)
모든 모듈을 통합 관리하는 중앙 컨트롤러. 비동기 이벤트 루프를 백그라운드 스레드에서 구동하여 UI 블로킹 방지.
"""
import logging
import threading
import asyncio
import time
import inspect
import concurrent.futures
from enum import Enum, auto
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta

from core.exchange import OKXClient
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
from core.alert import send_telegram_alert

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
        self.client: Optional[OKXClient] = None
        self.scanner: Optional[Scanner] = None
        self.trader: Optional[AutoTrader] = None
        self.cfg = CFG

        self._initialized = False
        self._prev_position_symbols: set = set()
        self._trailing_highs: Dict[str, float] = {}
        self._trailing_lows: Dict[str, float] = {}
        self._timeout_cooldowns: Dict[str, float] = {}
        # [v2.8.0] per-symbol 청산 중 락: 이중 클릭 및 스캔 루프와 충돌 방지
        self._closing_in_progress: Dict[str, float] = {}  # symbol -> 청산 시작 timestamp
        # 대시보드 API 캐싱 변수
        self._cached_balance = None
        self._cached_positions = None

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
        future = asyncio.run_coroutine_threadsafe(self._enable_trading_async(), self._loop)
        future.result()

    def disable_trading(self):
        future = asyncio.run_coroutine_threadsafe(self._disable_trading_async(), self._loop)
        future.result()

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

        # [v2.8.0] per-symbol 청산 진행 락: 10초 이내 동일 심볼 이중 청산 차단
        now_sec = time.time()
        last_close = self._closing_in_progress.get(symbol, 0.0)
        if (now_sec - last_close) < 10.0:
            logger.warning(f"[CLOSE GUARD] {symbol} 청산 진행 중 (이중 요청 차단, 남은: {10.0 - (now_sec - last_close):.1f}초)")
            return False
        self._closing_in_progress[symbol] = now_sec

        future = asyncio.run_coroutine_threadsafe(self.client.close_position(symbol, side), self._loop)
        try:
            res = future.result(timeout=15)  # [v2.5.6] 무한 블로킹 방지: 15초 타임아웃
            if res:
                self._trailing_highs.pop(symbol, None)
                self._trailing_lows.pop(symbol, None)
                self._timeout_cooldowns.pop(symbol, None)
                # 캐시 즉시 무효화
                self._cached_positions = None
                self._cached_balance = None
            # [v2.8.0] 성공/실패 모두 락 해제
            self._closing_in_progress.pop(symbol, None)
            return res
        except concurrent.futures.TimeoutError:
            logger.error(f"[CLOSE TIMEOUT] {symbol} 청산 API 응답 없음 (15초 초과) — 청산 실패 처리")
            self._closing_in_progress.pop(symbol, None)  # [v2.8.0] 락 해제
            return False
        except Exception as e:
            logger.error(f"[CLOSE ERROR] {symbol} 청산 중 예외: {e}")
            self._closing_in_progress.pop(symbol, None)  # [v2.8.0] 락 해제
            return False

    def close_all_positions(self) -> int:
        """
        [v2.8.0] 일괄청산 래퍼
        - exchange.close_all_positions가 asyncio.gather 병렬화되어 실제 N개 포지션도 ~18초 내 완료
        - timeout: 45초 (병렬 처리로 30초도 충분하지만 API 스파이크 대비 15초 여유)
        - timeout 발생 시 -1 반환: 부분 청산 가능성 시그널 (UI에서 ⚠️ 쯔피션 비교 권고)
        """
        if not self.is_ready:
            return 0
        future = asyncio.run_coroutine_threadsafe(self.client.close_all_positions(), self._loop)
        try:
            count = future.result(timeout=45)  # [v2.8.0] 30초 → 45초 (병렬화후 여유부 확장)
            if count > 0 or count == -1:
                self._trailing_highs.clear()
                self._trailing_lows.clear()
                self._timeout_cooldowns.clear()
                self._closing_in_progress.clear()  # [v2.8.0] 모든 락 해제
                # 캐시 즉시 무효화
                self._cached_positions = None
                self._cached_balance = None
            return count
        except concurrent.futures.TimeoutError:
            logger.error("[CLOSE ALL TIMEOUT] 일괄청산 API 응답 없음 (45초 초과) — 부분 청산 가능성 있음")
            self._closing_in_progress.clear()  # [v2.8.0] 타임아웃시도 락 해제
            return -1  # [v2.8.0] 0 → -1: 부분 청산 시그널
        except Exception as e:
            logger.error(f"[CLOSE ALL ERROR] 일괄청산 중 예외: {e}")
            self._closing_in_progress.clear()  # [v2.8.0] 예외시도 락 해제
            return 0

    def get_scan_results(self) -> List[Dict]:
        if not self.scanner: return []
        future = asyncio.run_coroutine_threadsafe(self.scanner.get_results(), self._loop)
        return future.result()

    def get_system_logs(self, limit: int = 50) -> List[str]:
        if not self.scanner: return []
        future = asyncio.run_coroutine_threadsafe(self.scanner.get_logs(limit), self._loop)
        return future.result()

    def get_trader_logs(self) -> List[Dict]:
        if not self.trader: return []
        future = asyncio.run_coroutine_threadsafe(self.trader.get_trade_log(), self._loop)
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
            
            # 텔레그램 메시지 알림 (핵심 상태 전이 대상)
            if new_state == EngineState.ERROR:
                send_telegram_alert(f"🚨 *[AI QUANTUM] 엔진 에러 상태 전이*\n이전 상태: {old.name}\n사유: {reason or self._error_msg}")
            elif new_state == EngineState.CONNECTED and old == EngineState.RECOVERING:
                send_telegram_alert(f"✅ *[AI QUANTUM] 엔진 자가 복구 성공*\n시도 횟수: {self._recovery_attempts}회")
            
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
                self.client = OKXClient(api_key, secret_key, passphrase)
                if await self.client.load_markets():
                    self.scanner = Scanner(self.client)
                    self.trader = AutoTrader(self.client)

                    self.scanner.on_signal = self.trader.on_signal
                    self.scanner.on_scan_complete = self._check_closed_positions_async

                    self._initialized = True
                    self._recovery_attempts = 0
                    self._transition(EngineState.CONNECTED, "마켓 로드 성공")
                    
                    # 초기 캐시 로드
                    try:
                        self._cached_balance = await self.client.get_balance()
                        self._cached_positions = await self.client.get_positions()
                    except Exception as ce:
                        logger.warning(f"초기 대시보드 데이터 캐싱 실패: {ce}")

                    # 당일 누적 PnL 동기화 및 복구 실행 (PnL Reconciler)
                    try:
                        await self._sync_trades_to_csv_async()
                        await self._reconcile_daily_pnl_async()
                    except Exception as re:
                        logger.error(f"초기 PnL Reconcile 실패: {re}")
                    
                    send_telegram_alert("🤖 *[AI QUANTUM]* Binance 자동매매 엔진 초기화 및 가동 성공")
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
            if self._cached_balance is None:
                self._cached_balance = await self.client.get_balance()
            if self._cached_positions is None:
                self._cached_positions = await self.client.get_positions()
        except Exception as e:
            logger.error(f"대시보드 데이터 조회 실패: {e}")
            self._error_msg = str(e)
            if self._state not in (EngineState.ERROR, EngineState.RECOVERING):
                self._transition(EngineState.ERROR, f"데이터 조회 실패: {e}")
            return {}

        return {
            "total_balance": self._cached_balance.get("total", 0) if self._cached_balance else 0.0,
            "free_margin": self._cached_balance.get("free", 0) if self._cached_balance else 0.0,
            "used_margin": self._cached_balance.get("used", 0) if self._cached_balance else 0.0,
            "realized_pnl": self._cached_balance.get("pnl", 0) if self._cached_balance else 0.0,
            "positions": self._cached_positions or [],
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
            self._cached_positions = raw_positions # 백그라운드 캐시 업데이트
            
            # 잔고도 백그라운드에서 실시간 동기 업데이트
            try:
                raw_balance = await self._maybe_await(self.client.get_balance())
                self._cached_balance = raw_balance
            except Exception as be:
                logger.error(f"백그라운드 잔고 동기화 실패: {be}")

            current = {p["symbol"] for p in raw_positions}
            closed = self._prev_position_symbols - current

            if closed:
                for sym in closed:
                    self._timeout_cooldowns.pop(sym, None)
                    pnl = 0.0
                    try:
                        recent_trades = await self._maybe_await(self.client.get_trade_history(symbol=sym, limit=5))
                        exit_trade = next((t for t in reversed(recent_trades) if t.get("category") == "청산"), None)
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
                    
                    # 청산 알림 발송
                    pnl_pct_val = exit_trade.get("pnl_pct", 0.0) if exit_trade else 0.0
                    side_str = exit_trade.get("side", "") if exit_trade else ""
                    price_str = exit_trade.get("price", 0.0) if exit_trade else 0.0
                    emoji = "🔥" if pnl >= 0 else "❄️"
                    send_telegram_alert(
                        f"{emoji} *[포지션 청산 완료]*\n"
                        f"종목: {sym}\n"
                        f"구분: {side_str.upper()} 청산\n"
                        f"청산가: {price_str}\n"
                        f"실현 손익: {pnl:+.4f} USDT\n"
                        f"수익률: {pnl_pct_val:+.2f}%"
                    )
                    logger.info(f"[CLOSED] {sym} PnL={pnl:+.4f} -> {'WIN' if pnl >= 0 else 'LOSS'}")

            if self.cfg.MAX_HOLDING_HOURS > 0:
                now_ms = time.time() * 1000
                timeout_ms = self.cfg.MAX_HOLDING_HOURS * 3600 * 1000
                for p in raw_positions:
                    entry_ts = p.get("timestamp")
                    if entry_ts and (now_ms - entry_ts) > timeout_ms:
                        sym = p["symbol"]
                        side = p["side"]
                        now_sec = time.time()
                        if sym in self._timeout_cooldowns and (now_sec - self._timeout_cooldowns[sym]) < 30.0:
                            logger.info(f"[TIMEOUT COOLDOWN] {sym} 강제청산 실패 쿨다운 대기 중... 남은 시간: {30.0 - (now_sec - self._timeout_cooldowns[sym]):.1f}초")
                            continue

                        logger.warning(f"[TIMEOUT] {sym} {side} - {self.cfg.MAX_HOLDING_HOURS}시간 초과 강제청산 실행")
                        success = await self._maybe_await(self.client.close_position(sym, side))
                        if success:
                            self._timeout_cooldowns.pop(sym, None)
                            if self.trader:
                                self.trader.trigger_symbol_cooldown(sym, 60)
                        else:
                            self._timeout_cooldowns[sym] = now_sec
                            logger.error(f"[TIMEOUT ERROR] {sym} 강제청산 실패 - 30초 쿨다운 적용")

            self._prev_position_symbols = current
            await self._run_position_rotation_check_async(raw_positions)
            await self._run_trailing_stop_check_async(raw_positions)
        except Exception as e:
            logger.error(f"청산 감지 오류: {e}")

    async def _run_trailing_stop_check_async(self, raw_positions: List[Dict]):
        if not getattr(self.cfg, "USE_TRAILING_STOP", False):
            return

        activate_pct = getattr(self.cfg, "TRAILING_ACTIVATE_PCT", 0.015)
        callback_pct = getattr(self.cfg, "TRAILING_CALLBACK_PCT", 0.003)

        current_symbols = {p["symbol"] for p in raw_positions}
        for sym in list(self._trailing_highs.keys()):
            if sym not in current_symbols:
                self._trailing_highs.pop(sym, None)
        for sym in list(self._trailing_lows.keys()):
            if sym not in current_symbols:
                self._trailing_lows.pop(sym, None)

        for p in raw_positions:
            sym = p["symbol"]
            side = p["side"]
            entry_price = float(p.get("entry_price", 0.0))
            mark_price = float(p.get("mark_price", 0.0))
            if entry_price <= 0 or mark_price <= 0:
                continue

            raw_move = (mark_price - entry_price) / entry_price
            if side == "short":
                raw_move = -raw_move

            if side == "long":
                if sym not in self._trailing_highs:
                    self._trailing_highs[sym] = mark_price
                else:
                    self._trailing_highs[sym] = max(self._trailing_highs[sym], mark_price)

                highest = self._trailing_highs[sym]
                highest_move = (highest - entry_price) / entry_price
                if highest_move >= activate_pct:
                    trigger_price = highest * (1 - callback_pct)
                    if mark_price <= trigger_price:
                        logger.warning(f"[TRAILING STOP] {sym} 롱 청산 발동! (최고수익률 {highest_move*100:.2f}%, 고점 {highest}, 현재 {mark_price} <= 트리거 {trigger_price})")
                        success = await self._maybe_await(self.client.close_position(sym, side))
                        if success:
                            self._trailing_highs.pop(sym, None)
                            if self.trader:
                                self.trader.trigger_symbol_cooldown(sym, 60)

            elif side == "short":
                if sym not in self._trailing_lows:
                    self._trailing_lows[sym] = mark_price
                else:
                    self._trailing_lows[sym] = min(self._trailing_lows[sym], mark_price)

                lowest = self._trailing_lows[sym]
                lowest_move = (entry_price - lowest) / entry_price
                if lowest_move >= activate_pct:
                    trigger_price = lowest * (1 + callback_pct)
                    if mark_price >= trigger_price:
                        logger.warning(f"[TRAILING STOP] {sym} 숏 청산 발동! (최저수익률 {lowest_move*100:.2f}%, 저점 {lowest}, 현재 {mark_price} >= 트리거 {trigger_price})")
                        success = await self._maybe_await(self.client.close_position(sym, side))
                        if success:
                            self._trailing_lows.pop(sym, None)
                            if self.trader:
                                self.trader.trigger_symbol_cooldown(sym, 60)

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
        # [v4.0.3] 이력 초기화 기준 시각 (stats.json perf_start_time) 이전 거래는 동기화 제외
        _st_cutoff = stats_store.load_stats()
        _cutoff_str = _st_cutoff.get("perf_start_time", "")
        _cutoff_dt = None
        if _cutoff_str:
            try:
                from datetime import timezone as _tz
                _cutoff_dt = datetime.strptime(_cutoff_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=None)
                logger.info(f"[SYNC CUTOFF] {_cutoff_str} 이전 거래는 동기화 제외")
            except Exception:
                _cutoff_dt = None

        for trade in sorted(exchange_trades, key=lambda x: x.get("timestamp")):
            key = self._exchange_trade_key(trade)
            if key in logged_keys:
                continue

            # [v4.0.3] 컷오프 이전 거래 필터링
            if _cutoff_dt is not None:
                trade_ts = trade.get("timestamp")
                if trade_ts is not None:
                    try:
                        if isinstance(trade_ts, datetime):
                            ts_naive = trade_ts.replace(tzinfo=None) if trade_ts.tzinfo else trade_ts
                        else:
                            ts_naive = pd.to_datetime(trade_ts).to_pydatetime().replace(tzinfo=None)
                        if ts_naive < _cutoff_dt:
                            continue
                    except Exception:
                        pass

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

            # [즉시 조치 3] 신규 발견된 청산 거래 PnL을 메모리 daily_pnl 및 로컬 통계에 즉시 반영
            if category == "청산":
                stats_store.record_result(pnl)
                trade_ts = trade.get("timestamp")
                if trade_ts:
                    if isinstance(trade_ts, datetime):
                        trade_date = trade_ts.date()
                    else:
                        trade_sec = trade_ts / 1000.0 if trade_ts > 10000000000 else trade_ts
                        trade_dt = datetime.fromtimestamp(trade_sec, timezone.utc) + timedelta(hours=9)
                        trade_date = trade_dt.date()
                    
                    today_kst = (datetime.utcnow() + timedelta(hours=9)).date()
                    if trade_date == today_kst and self.trader:
                        self.trader.daily_pnl_usdt = round(self.trader.daily_pnl_usdt + pnl, 4)

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

    async def _reconcile_daily_pnl_async(self):
        """
        [PnL Reconciler]
        봇 재기동 시 오늘(KST 기준) 발생한 모든 청산 거래 PnL을 합산하여
        trader.daily_pnl_usdt 상태를 복구합니다.
        """
        if not self.client or not self.trader:
            return
        try:
            logger.info("[RECONCILER] 당일 청산 PnL 복구 시작...")
            today_kst = (datetime.utcnow() + timedelta(hours=9)).date()
            local_trades = load_local_trade_history()
            daily_pnl = 0.0
            
            for t in local_trades:
                ts = t.get("timestamp")
                if isinstance(ts, str):
                    try:
                        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                        trade_date = dt.date()
                    except ValueError:
                        continue
                elif isinstance(ts, datetime):
                    trade_date = ts.date()
                else:
                    continue
                    
                if trade_date == today_kst and t.get("category") in ("청산", "청산(로테이션)"):
                    daily_pnl += float(t.get("pnl") or t.get("pnl_usdt") or 0.0)
            
            self.trader.daily_pnl_usdt = round(daily_pnl, 4)
            logger.info(f"[RECONCILER] 당일 청산 PnL 복구 완료: {self.trader.daily_pnl_usdt:.4f} USDT")
        except Exception as e:
            logger.error(f"[RECONCILER] PnL 복구 실패: {e}")
