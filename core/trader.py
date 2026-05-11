"""
자동매매 실행 엔진
리스크 관리 + 포지션 관리 + 주문 실행 통합
"""
import threading
import logging
from typing import Optional, List, Dict
from datetime import datetime, date, timedelta, timezone

from core.exchange import OKXClient
from core.strategy import Signal
from core.config import CFG
import core.stats as stats_store

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """timezone-aware UTC를 쓰되 기존 내부 비교 로직과 맞게 naive로 반환한다."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AutoTrader:
    """
    자동매매 엔진
    Scanner.on_signal 콜백으로 신호를 받아 리스크 체크 후 실거래 실행
    """

    def __init__(self, client: OKXClient):
        self.client = client
        self.cfg = CFG
        self._lock = threading.Lock()

        self.enabled: bool = False
        self.allow_long: bool = True
        self.allow_short: bool = True

        # 통계 — 파일에서 불러오기 (재시작 후에도 유지)
        _s = stats_store.load_stats()
        self.orders_today: int = _s.get("orders_today", 0)
        self.daily_pnl_usdt: float = _s.get("daily_pnl_usdt", 0.0)
        self.trade_log: List[Dict] = []
        self._today: date = date.today()
        self._pending_entries: Dict[str, datetime] = {}
        self._last_entry_at: Dict[str, datetime] = {}

    # ── 제어 ───────────────────────────────────────────

    def enable(self):
        self.enabled = True
        logger.info("[TRADER] 자동매매 활성화")

    def disable(self):
        self.enabled = False
        logger.info("[TRADER] 자동매매 비활성화")

    # ── 신호 처리 ──────────────────────────────────────

    def on_signal(self, sig: Signal):
        """Scanner 콜백 — 신호 수신 후 리스크 체크 → 주문"""
        if not self.enabled:
            return
        if sig.direction == "none":
            return

        with self._lock:
            self._reset_daily_if_needed()

            # ── 방향 허용 체크 ────────────────────────
            if sig.direction == "long" and not self.allow_long:
                return
            if sig.direction == "short" and not self.allow_short:
                return

            duplicate, reason, positions = self._duplicate_entry_check(sig.symbol)
            if duplicate:
                logger.info(f"[SKIP] {sig.symbol} — {reason}")
                self._log_trade(sig, status="SKIPPED", reason=reason)
                return

            # ── 최대 포지션 수 체크 ───────────────────
            if len(positions) >= self.cfg.MAX_POSITIONS:
                logger.info(f"[SKIP] 최대 포지션 수 도달: {len(positions)}/{self.cfg.MAX_POSITIONS}")
                return

            # ── 리스크 게이트 ─────────────────────────
            passed, reason = self._risk_check(sig)
            if not passed:
                logger.warning(f"[RISK BLOCK] {sig.symbol} — {reason}")
                self._log_trade(sig, status="BLOCKED", reason=reason)
                return

            # ── 주문 실행 ─────────────────────────────
            side = "buy" if sig.direction == "long" else "sell"
            
            margin_usdt = self.cfg.MARGIN_USDT

            if margin_usdt < 1.0:
                logger.warning(f"[SKIP] 증거금 설정 오류 (최소 $1): {margin_usdt:.2f} USDT")
                return

            now = _utc_now()
            self._pending_entries[sig.symbol] = now
            result = None
            try:
                result = self.client.place_order(
                    symbol=sig.symbol,
                    side=side,
                    margin_usdt=margin_usdt,
                )
            finally:
                self._pending_entries.pop(sig.symbol, None)

            if result:
                self._last_entry_at[sig.symbol] = now
                self.orders_today += 1
                stats_store.record_order()
                self._log_trade(sig, status="EXECUTED", result=result)
                logger.info(f"[ORDER] {sig.symbol} {sig.direction.upper()} 실행 완료")
            else:
                self._log_trade(sig, status="FAILED", reason="주문 API 오류")

    # ── 리스크 관리 ────────────────────────────────────

    def _risk_check(self, sig: Signal) -> tuple[bool, str]:
        """다층 리스크 게이트"""

        # 1. 일일 손실 한도
        if self.daily_pnl_usdt <= -self.cfg.DAILY_LOSS_LIMIT_USDT:
            return False, f"일일 손실 한도 초과: {self.daily_pnl_usdt:.2f} USDT"

        # 2. 계좌 MDD 체크
        balance = self.client.get_balance()
        total = balance.get("total", 0)
        # 초기 자금 대비 현재 낙폭 추정 (간략화)
        if total < 10:  # 잔고 임계값
            return False, "잔고 부족 (< 10 USDT)"

        # 3. 신호 강도 최소치
        if sig.strength < 60:
            return False, f"신호 강도 부족: {sig.strength}% (최소 60%)"

        # 4. 가용 증거금 확인
        free = balance.get("free", 0)
        required_margin = self.cfg.MARGIN_USDT
        if free < required_margin:
            return False, f"가용 증거금 부족: {free:.2f} < {required_margin:.2f}"

        return True, "OK"

    def _duplicate_entry_check(self, symbol: str) -> tuple[bool, str, List[Dict]]:
        """동일 티커 중복 진입을 주문 전 단계에서 차단한다."""
        now = _utc_now()
        pending_ttl = timedelta(seconds=self.cfg.PENDING_ENTRY_TTL_SEC)
        cooldown = timedelta(seconds=self.cfg.ENTRY_COOLDOWN_SEC)

        expired = [
            sym for sym, ts in self._pending_entries.items()
            if now - ts > pending_ttl
        ]
        for sym in expired:
            self._pending_entries.pop(sym, None)

        pending_at = self._pending_entries.get(symbol)
        if pending_at and now - pending_at <= pending_ttl:
            return True, "동일 티커 주문 진행 중", []

        last_entry_at = self._last_entry_at.get(symbol)
        if last_entry_at and now - last_entry_at < cooldown:
            remain = int((cooldown - (now - last_entry_at)).total_seconds())
            return True, f"동일 티커 재진입 쿨다운 {remain}초 남음", []

        positions = self.client.get_positions()
        if any(p["symbol"] == symbol for p in positions):
            return True, "이미 포지션 보유", positions

        open_orders = self.client.get_open_orders()
        if any(o["symbol"] == symbol for o in open_orders):
            return True, "동일 티커 미체결 주문 존재", positions

        return False, "OK", positions

    def _reset_daily_if_needed(self):
        today = date.today()
        if today != self._today:
            self.daily_pnl_usdt = 0.0
            self.orders_today = 0
            self._today = today
            # 파일에도 리셋 반영
            _s = stats_store.load_stats()
            _s["orders_today"] = 0
            _s["daily_pnl_usdt"] = 0.0
            stats_store.save_stats(_s)

    # ── 로그 ───────────────────────────────────────────

    def _log_trade(
        self,
        sig: Signal,
        status: str,
        reason: str = "",
        result: Optional[Dict] = None,
    ):
        entry = {
            "timestamp": _utc_now() + timedelta(hours=9),
            "symbol": sig.symbol,
            "direction": sig.direction,
            "strength": sig.strength,
            "status": status,
            "reason": reason,
            "entry_price": result.get("entry_price", 0) if result else 0,
            "sl_price": result.get("sl_price", 0) if result else 0,
            "tp_price": result.get("tp_price", 0) if result else 0,
        }
        self.trade_log.append(entry)
        if len(self.trade_log) > 500:
            self.trade_log = self.trade_log[-500:]

    def get_trade_log(self) -> List[Dict]:
        with self._lock:
            return list(reversed(self.trade_log))
