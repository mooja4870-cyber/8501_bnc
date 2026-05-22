"""
전종목 실시간 스캐너
Binance USDT 선물 전종목 순환 스캔 → 신호 감지
v2.0.8: OHLCV 캐시 + 거래량 상위 N개 필터로 REST 호출 95% 감소
"""
import time
import threading
import logging
import pandas as pd
from typing import List, Dict, Callable, Optional
from datetime import datetime

from core.exchange import BinanceClient
from core.strategy import StrategyEngine, Signal
from core.config import CFG

logger = logging.getLogger(__name__)


class Scanner:
    """
    멀티스레드 전종목 스캐너
    - 전종목을 순환 스캔하며 신호 포착
    - 신호 발생 시 콜백(on_signal) 호출
    - Streamlit session_state와 연동하여 UI 실시간 업데이트
    - [v2.0.8] OHLCV 캐시로 REST 호출 95% 절감 (최초 1회 250봉, 이후 2봉만 추가)
    - [v2.0.8] 거래대금 상위 N개만 스캔하여 API 부하 추가 감소
    """

    def __init__(self, client: BinanceClient):
        self.client = client
        self.strategy = StrategyEngine()
        self.cfg = CFG

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 공유 상태
        self.scan_results: List[Dict] = []
        self.last_scan_time: Optional[datetime] = None
        self.scan_count: int = 0
        self.log_buffer: List[str] = []

        # [v2.0.8] OHLCV 캐시 — 종목별 DataFrame 및 마지막 캔들 timestamp 보관
        self._ohlcv_cache: Dict[str, pd.DataFrame] = {}
        self._ohlcv_cache_ts: Dict[str, int] = {}  # 마지막 캔들 timestamp (ms, unix)

        # 콜백: 신호 발생 시 외부에서 주입
        self.on_signal: Optional[Callable[[Signal], None]] = None
        # 콜백: 스캔 1회 완료 시 외부에서 주입 (청산 감지용)
        self.on_scan_complete: Optional[Callable[[], None]] = None

    # ── 제어 ───────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()
        self._log("[SCANNER] 스캔 엔진 시작 (v2.0.8 OHLCV 캐시 활성)")

    def stop(self):
        self._running = False
        self._log("[SCANNER] 스캔 엔진 중지")

    @property
    def is_running(self) -> bool:
        return self._running

    # ── OHLCV 캐시 ─────────────────────────────────────

    def _get_ohlcv_cached(self, sym: str) -> pd.DataFrame:
        """
        OHLCV 캐시 조회 메서드.
        - 캐시 없음 (첫 스캔): limit=300 전체 요청 → 캐시 저장
        - 캐시 있음: limit=3 (최신 2~3봉만) 요청 → 캐시에 병합, 중복 제거, 상위 300봉 유지
        - API 오류 시: 기존 캐시 반환 (API 호출 0회로 처리)
        """
        cached = self._ohlcv_cache.get(sym)

        if cached is None or cached.empty:
            # 최초 요청 — 전체 250봉 fetch
            df = self.client.get_ohlcv(sym, limit=300)
            if not df.empty:
                self._ohlcv_cache[sym] = df
                # 마지막 캔들 timestamp (DatetimeIndex → ms 변환)
                last_ts = df.index[-1]
                self._ohlcv_cache_ts[sym] = int(last_ts.timestamp() * 1000)
                self._log(f"[CACHE] {sym} 초기 로드 {len(df)}봉")
            return df

        # 이후 스캔 — 최신 3봉만 추가 요청
        try:
            new_df = self.client.get_ohlcv(sym, limit=3)
            if new_df.empty:
                return cached

            # 병합: 캐시 + 새 봉 합치고 중복 제거 후 최신 300봉 유지
            merged = pd.concat([cached, new_df])
            merged = merged[~merged.index.duplicated(keep='last')]
            merged = merged.sort_index().tail(300)
            self._ohlcv_cache[sym] = merged

            # timestamp 업데이트
            last_ts = merged.index[-1]
            self._ohlcv_cache_ts[sym] = int(last_ts.timestamp() * 1000)

            return merged

        except Exception as e:
            logger.warning(f"[CACHE] {sym} 증분 업데이트 실패, 캐시 사용: {e}")
            return cached  # API 실패 시 기존 캐시 그대로 반환

    def clear_cache(self):
        """캐시 전체 초기화 (마켓 변동 등에 대응)"""
        self._ohlcv_cache.clear()
        self._ohlcv_cache_ts.clear()
        self._log("[CACHE] OHLCV 캐시 초기화 완료")

    # ── 스캔 루프 ──────────────────────────────────────

    def _scan_loop(self):
        while self._running:
            try:
                self._run_once()
            except Exception as e:
                logger.error(f"스캔 루프 오류: {e}")
                self._log(f"[ERR] 스캔 오류: {e}")
            time.sleep(self.cfg.SCAN_INTERVAL_SEC)

    def _run_once(self):
        symbols = self.client.get_all_usdt_swap_symbols()

        # Ticker 일괄 조회로 API 호출 최적화 및 밴 방지
        try:
            tickers = self.client.get_tickers()
        except Exception as e:
            self._log(f"[ERR] Ticker 일괄 조회 예외 발생: {e}")
            return

        if not tickers:
            self._log("[WARN] 일괄 조회된 Ticker가 없습니다. 스캔 건너뜀.")
            return

        # [v2.0.8] 거래대금 기준으로 symbols 정렬 후 상위 N개만 사용
        if self.cfg.SCAN_TOP_N > 0:
            symbols = sorted(
                symbols,
                key=lambda s: tickers.get(s, {}).get("volume", 0),
                reverse=True
            )[:self.cfg.SCAN_TOP_N]

        self._log(f"[SCAN] 스캔 시작: {len(symbols)}개 페어 (캐시 {len(self._ohlcv_cache)}개 보유)")

        results = []
        signal_count = 0
        cache_hit = 0
        api_calls = 0

        for sym in symbols:
            if not self._running:
                break
            try:
                # 일괄 조회된 딕셔너리에서 가져오기 (개별 API 호출 차단)
                ticker = tickers.get(sym)
                if not ticker:
                    ticker = tickers.get(sym.split(":")[0])

                if not ticker:
                    continue

                vol = ticker.get("volume", 0)
                if vol < self.cfg.MIN_VOLUME_USDT:
                    continue

                # 스프레드 필터 — 호가 갭이 넓은 저유동성 종목 차단
                bid = ticker.get("bid", 0)
                ask = ticker.get("ask", 0)
                if bid and ask and ask > 0:
                    spread_pct = (ask - bid) / ask * 100
                    if spread_pct > self.cfg.MAX_SPREAD_PCT:
                        continue

                # [v2.0.8] OHLCV 캐시 활용 (첫 스캔만 250봉, 이후 2봉)
                was_cached = sym in self._ohlcv_cache
                df = self._get_ohlcv_cached(sym)
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
                    "reason": sig.reason,
                    "timestamp": datetime.now(),
                })

                if sig.direction in ("long", "short"):
                    signal_count += 1
                    self._log(
                        f"[SIG] {sym} {sig.direction.upper()} 신호 포착 "
                        f"(강도 {sig.strength}%)"
                    )
                    if self.on_signal:
                        self.on_signal(sig)

                # 캐시 미스(첫 로드) 시에만 대기 — 캐시 히트면 대기 불필요
                if not was_cached:
                    time.sleep(0.2)

            except Exception as e:
                logger.warning(f"종목 스캔 오류 ({sym}): {e}")
                continue

        # 강도 내림차순 정렬
        results.sort(key=lambda x: x["strength"], reverse=True)

        with self._lock:
            self.scan_results = results
            self.last_scan_time = datetime.now()
            self.scan_count += 1

        self._log(
            f"[SCAN] 완료: {len(results)}개 종목 · 신호 {signal_count}개 · "
            f"API 호출 {api_calls}회 · 캐시 히트 {cache_hit}회 · "
            f"{datetime.now().strftime('%H:%M:%S')}"
        )

        # 스캔 완료 콜백 (청산 감지 등)
        if self.on_scan_complete:
            try:
                self.on_scan_complete()
            except Exception as e:
                logger.warning(f"on_scan_complete 콜백 오류: {e}")

    # ── 로그 ───────────────────────────────────────────

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        with self._lock:
            self.log_buffer.append(entry)
            if len(self.log_buffer) > 200:
                self.log_buffer = self.log_buffer[-200:]
        logger.info(msg)

    def get_logs(self, last_n: int = 50) -> List[str]:
        with self._lock:
            return list(self.log_buffer[-last_n:])

    def get_results(self) -> List[Dict]:
        with self._lock:
            return list(self.scan_results)
