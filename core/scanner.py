"""
전종목 실시간 스캐너
OKX USDT 선물 전종목 순환 스캔 → 신호 감지
"""
import time
import threading
import logging
from typing import List, Dict, Callable, Optional
from datetime import datetime

from core.exchange import OKXClient
from core.strategy import StrategyEngine, Signal
from core.config import CFG

logger = logging.getLogger(__name__)


class Scanner:
    """
    멀티스레드 전종목 스캐너
    - 전종목을 순환 스캔하며 신호 포착
    - 신호 발생 시 콜백(on_signal) 호출
    - Streamlit session_state와 연동하여 UI 실시간 업데이트
    """

    def __init__(self, client: OKXClient):
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

        # 콜백: 신호 발생 시 외부에서 주입
        self.on_signal: Optional[Callable[[Signal], None]] = None
        # 콜백: 스캔 1회꽀 완료 시 외부에서 주입 (첨산 감지용)
        self.on_scan_complete: Optional[Callable[[], None]] = None

    # ── 제어 ───────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._thread.start()
        self._log("[SCANNER] 스캔 엔진 시작")

    def stop(self):
        self._running = False
        self._log("[SCANNER] 스캔 엔진 중지")

    @property
    def is_running(self) -> bool:
        return self._running

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
        self._log(f"[SCAN] 전종목 스캔 시작: {len(symbols)}개 페어")

        results = []
        signal_count = 0

        for sym in symbols:
            if not self._running:
                break
            try:
                # 최소 거래대금 필터
                ticker = self.client.get_ticker(sym)
                vol = ticker.get("volume", 0)
                if vol < self.cfg.MIN_VOLUME_USDT:
                    continue

                df = self.client.get_ohlcv(sym, limit=250)
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
                    "regime": sig.regime,
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

                # Rate limit 보호 (0.3s -> 0.1s 최적화)
                # 전종목 순환 속도를 높여 신호 포착 지연 최소화
                time.sleep(0.1)

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
            f"[SCAN] 완료: {len(results)}개 종목 · "
            f"신호 {signal_count}개 · "
            f"{datetime.now().strftime('%H:%M:%S')}"
        )

        # 스캔 완료 콜백 (첨산 감지 등)
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
