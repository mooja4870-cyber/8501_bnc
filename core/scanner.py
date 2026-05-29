"""
전종목 실시간 스캐너 (비동기 엔터프라이즈 버전)
Binance USDT 선물 전종목 순환 스캔 → 신호 감지
"""
import asyncio
import logging
import pandas as pd
from typing import List, Dict, Callable, Optional, Awaitable, Union
from datetime import datetime

from core.exchange import BinanceClient
from core.strategy import StrategyEngine, Signal
from core.config import CFG

logger = logging.getLogger(__name__)


class Scanner:
    """
    비동기 전종목 스캐너
    - 전종목을 순환 스캔하며 신호 포착
    """

    def __init__(self, client: BinanceClient):
        self.client = client
        self.strategy = StrategyEngine()
        self.cfg = CFG
        self.ws_client = None

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        # 공유 상태
        self.scan_results: List[Dict] = []
        self.last_scan_time: Optional[datetime] = None
        self.scan_count: int = 0
        self.log_buffer: List[str] = []

        self._ohlcv_cache: Dict[str, pd.DataFrame] = {}
        self._ohlcv_cache_ts: Dict[str, int] = {}

        # 콜백: 신호 발생 시 (async/sync 겸용)
        self.on_signal: Optional[Union[Callable[[Signal], None], Callable[[Signal], Awaitable[None]]]] = None
        # 콜백: 스캔 1회 완료 시
        self.on_scan_complete: Optional[Union[Callable[[], None], Callable[[], Awaitable[None]]]] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._scan_loop())
        self._log_sync("[SCANNER] 스캔 엔진 시작 (Async)")
        
        # 실시간 웹소켓 구독 감시 태스크 가동
        try:
            symbols = self.client.get_all_usdt_swap_symbols()
            asyncio.create_task(self._start_ws_client_async(symbols))
        except Exception as e:
            logger.error(f"[SCANNER] 웹소켓 시작 실패: {e}")

    async def _start_ws_client_async(self, symbols: List[str]):
        try:
            tickers = await self.client.get_tickers()
            if tickers and self.cfg.SCAN_TOP_N > 0:
                symbols = sorted(
                    symbols,
                    key=lambda s: tickers.get(s, {}).get("volume", 0),
                    reverse=True
                )[:self.cfg.SCAN_TOP_N]
            
            from core.websocket_client import WebSocketClient
            self.ws_client = WebSocketClient(self)
            self.ws_client.start(symbols)
        except Exception as e:
            logger.error(f"[WS INIT] 웹소켓 초기 설정 및 기동 실패: {e}")

    async def stop(self):
        self._running = False
        if self.ws_client:
            try:
                await self.ws_client.stop()
            except Exception as wse:
                logger.error(f"웹소켓 클라이언트 중지 실패: {wse}")
            self.ws_client = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._log_sync("[SCANNER] 스캔 엔진 중지")

    @property
    def is_running(self) -> bool:
        return self._running

    async def _get_ohlcv_cached(self, sym: str) -> pd.DataFrame:
        # [Hybrid Fallback] 웹소켓 클라이언트가 정상 작동하여 캐시 데이터가 들어있다면 REST 조회 우회
        if self.ws_client and self.ws_client._running:
            async with self._lock:
                cached = self._ohlcv_cache.get(sym)
            if cached is not None and not cached.empty:
                return cached

        cached = self._ohlcv_cache.get(sym)

        if cached is None or cached.empty:
            df = await self.client.get_ohlcv(sym, limit=300)
            if not df.empty:
                self._ohlcv_cache[sym] = df
                last_ts = df.index[-1]
                self._ohlcv_cache_ts[sym] = int(last_ts.timestamp() * 1000)
                self._log_sync(f"[CACHE] {sym} 초기 로드 {len(df)}봉")
            return df

        try:
            new_df = await self.client.get_ohlcv(sym, limit=3)
            if new_df.empty:
                return cached

            merged = pd.concat([cached, new_df])
            merged = merged[~merged.index.duplicated(keep='last')]
            merged = merged.sort_index().tail(300)
            self._ohlcv_cache[sym] = merged
            last_ts = merged.index[-1]
            self._ohlcv_cache_ts[sym] = int(last_ts.timestamp() * 1000)

            return merged
        except Exception as e:
            logger.warning(f"[CACHE] {sym} 증분 업데이트 실패, 캐시 사용: {e}")
            return cached

    async def clear_cache(self):
        async with self._lock:
            self._ohlcv_cache.clear()
            self._ohlcv_cache_ts.clear()
        self._log_sync("[CACHE] OHLCV 캐시 초기화 완료")

    async def _scan_loop(self):
        while self._running:
            try:
                await self._run_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"스캔 루프 오류: {e}")
                self._log_sync(f"[ERR] 스캔 오류: {e}")
            await asyncio.sleep(self.cfg.SCAN_INTERVAL_SEC)

    async def _run_once(self):
        # 스캔 회차 동안 고정된 설정을 바라보도록 스냅샷 생성 및 전략 모듈에 바인딩
        cfg_snap = self.cfg.copy()
        self.strategy.cfg = cfg_snap

        symbols = self.client.get_all_usdt_swap_symbols()

        try:
            tickers = await self.client.get_tickers()
        except Exception as e:
            self._log_sync(f"[ERR] Ticker 일괄 조회 예외 발생: {e}")
            return

        if not tickers:
            self._log_sync("[WARN] 일괄 조회된 Ticker가 없습니다. 스캔 건너뜀.")
            return

        if cfg_snap.SCAN_TOP_N > 0:
            symbols = sorted(
                symbols,
                key=lambda s: tickers.get(s, {}).get("volume", 0),
                reverse=True
            )[:cfg_snap.SCAN_TOP_N]

        self._log_sync(f"[SCAN] 스캔 시작: {len(symbols)}개 페어 (캐시 {len(self._ohlcv_cache)}개 보유)")

        results = []
        signal_count = 0
        cache_hit = 0
        api_calls = 0
        
        for sym in symbols:
            if not self._running:
                break
            try:
                ticker = tickers.get(sym)
                if not ticker:
                    ticker = tickers.get(sym.split(":")[0])

                if not ticker:
                    continue

                vol = ticker.get("volume", 0)
                if vol < cfg_snap.MIN_VOLUME_USDT:
                    continue

                bid = ticker.get("bid", 0)
                ask = ticker.get("ask", 0)
                if bid and ask and ask > 0:
                    spread_pct = (ask - bid) / ask * 100
                    if spread_pct > cfg_snap.MAX_SPREAD_PCT:
                        continue

                was_cached = sym in self._ohlcv_cache
                df = await self._get_ohlcv_cached(sym)
                if was_cached:
                    cache_hit += 1
                else:
                    api_calls += 1

                if df.empty:
                    continue

                sig = self.strategy.generate_signal(df, sym)
                results.append({
                    "symbol": sym,
                    "price": ticker.get("last", 0),
                    "change_pct": ticker.get("change_pct", 0),
                    "volume_m": round(vol / 1_000_000, 1),
                    "signal": sig.direction,
                    "strength": sig.strength,
                    "ema_ok": sig.ema_ok,
                    "macd_ok": sig.macd_ok,
                    "bb_ok": sig.bb_ok,
                    "rsi": round(sig.rsi, 1),
                    "rsi_ok": sig.rsi_ok,
                    "ema200": round(sig.ema200, 2) if sig.ema200 is not None else 0.0,
                    "ema200_ok": sig.ema200_ok,
                    "reason": sig.reason,
                    "timestamp": datetime.now(),
                })

                if sig.direction in ("long", "short"):
                    signal_count += 1
                    self._log_sync(f"[SIG] {sym} {sig.direction.upper()} 신호 포착 (강도 {sig.strength}%)")
                    if self.on_signal:
                        import inspect
                        if inspect.iscoroutinefunction(self.on_signal):
                            await self.on_signal(sig)
                        else:
                            self.on_signal(sig)

                if not was_cached:
                    await asyncio.sleep(0.1)
                else:
                    await asyncio.sleep(0.05)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"종목 스캔 오류 ({sym}): {e}")
                continue

        results.sort(key=lambda x: x["strength"], reverse=True)

        async with self._lock:
            self.scan_results = results
            self.last_scan_time = datetime.now()
            self.scan_count += 1

        self._log_sync(
            f"[SCAN] 완료: {len(results)}개 종목 · 신호 {signal_count}개 · "
            f"API 호출 {api_calls}회 · 캐시 히트 {cache_hit}회"
        )

        if self.on_scan_complete:
            try:
                import inspect
                if inspect.iscoroutinefunction(self.on_scan_complete):
                    await self.on_scan_complete()
                else:
                    self.on_scan_complete()
            except Exception as e:
                logger.warning(f"on_scan_complete 콜백 오류: {e}")

    def _log_sync(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self.log_buffer.append(entry)
        if len(self.log_buffer) > 200:
            self.log_buffer = self.log_buffer[-200:]
        logger.info(msg)

    async def get_logs(self, last_n: int = 50) -> List[str]:
        async with self._lock:
            return list(self.log_buffer[-last_n:])

    async def get_results(self) -> List[Dict]:
        async with self._lock:
            return list(self.scan_results)
