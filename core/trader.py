"""
자동매매 실행 엔진
리스크 관리 + 포지션 관리 + 주문 실행 통합
"""
import threading
import logging
from typing import Optional, List, Dict
from datetime import datetime, date, timedelta, timezone

from core.exchange import BinanceClient
from core.strategy import Signal
from core.config import CFG
import core.stats as stats_store
from core.logger import log_trade as csv_log

logger = logging.getLogger(__name__)


class AutoTrader:
    """
    자동매매 엔진
    Scanner.on_signal 콜백으로 신호를 받아 리스크 체크 후 실거래 실행
    """

    def __init__(self, client: BinanceClient):
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

        # API 갱신 지연(Execution/Replication Lag) 방지를 위한 최근 주문 종목 대기열
        self.recently_entered: Dict[str, datetime] = {}

        # 쿨다운 시스템 — 일괄청산 후 1분 글로벌 쿨다운 + 개별 청산 후 1분 종목별 쿨다운
        self.global_cooldown_until: Optional[datetime] = None
        self.symbol_cooldown_until: Dict[str, datetime] = {}

    # ── 제어 ───────────────────────────────────────────

    def enable(self):
        self.enabled = True
        logger.info("[TRADER] 자동매매 활성화")

    def disable(self):
        self.enabled = False
        logger.info("[TRADER] 자동매매 비활성화")

    def trigger_global_cooldown(self, seconds: int = 60):
        """일괄청산 시 1분간 글로벌 쿨다운 트리거"""
        self.global_cooldown_until = datetime.now() + timedelta(seconds=seconds)
        logger.info(f"[COOLDOWN] 글로벌 쿨다운 설정 완료 ({seconds}초간 새로운 진입 전면 차단)")

    def trigger_symbol_cooldown(self, symbol: str, seconds: int = 60):
        """개별 청산 시 1분간 종목별 쿨다운 트리거"""
        self.symbol_cooldown_until[symbol] = datetime.now() + timedelta(seconds=seconds)
        logger.info(f"[COOLDOWN] {symbol} 종목별 쿨다운 설정 완료 ({seconds}초간 진입 차단)")

    # ── 신호 처리 ──────────────────────────────────────

    def on_signal(self, sig: Signal):
        """Scanner 콜백 — 신호 수신 후 리스크 체크 → 주문"""
        if not self.enabled:
            return
        if sig.direction == "none":
            return

        with self._lock:
            self._reset_daily_if_needed()

            # ── 리스크 게이트 ─────────────────────────
            try:
                passed, reason = self._risk_check(sig)
                if not passed:
                    logger.warning(f"[RISK BLOCK] {sig.symbol} — {reason}")
                    self._log_trade(sig, status="BLOCKED", reason=reason)
                    return
            except Exception as e:
                logger.error(f"[RISK ERROR] {sig.symbol} 리스크 체크 중 예외 발생: {e}")
                self._log_trade(sig, status="FAILED", reason=f"API 조회 오류 ({e})")
                return

            # ── 방향 허용 체크 ────────────────────────
            if sig.direction == "long" and not self.allow_long:
                return
            if sig.direction == "short" and not self.allow_short:
                return

            # ── 최근 진입 중복 방지 캐시 정리 (120초 경과건 삭제) ───────
            now_time = datetime.now()
            self.recently_entered = {
                sym: ts for sym, ts in self.recently_entered.items()
                if (now_time - ts).total_seconds() < 120
            }

            # ── 중복 포지션 체크 ──────────────────────
            try:
                positions = self.client.get_positions()
                symbols_held = {p["symbol"] for p in positions}
                
                # 이미 실제로 포지션 목록에 올라와 있다면 대기열에서 삭제
                for sym in list(self.recently_entered.keys()):
                    if sym in symbols_held:
                        self.recently_entered.pop(sym, None)

                if sig.symbol in symbols_held or sig.symbol in self.recently_entered:
                    logger.info(f"[SKIP] {sig.symbol} — 이미 포지션 보유 중이거나 진입 주문이 전송되었습니다.")
                    return

                # ── 최대 포지션 수 체크 ───────────────────
                effective_count = len(symbols_held) + len(self.recently_entered)
                if effective_count >= self.cfg.MAX_POSITIONS:
                    logger.info(f"[SKIP] 최대 포지션 수 도달: {effective_count}/{self.cfg.MAX_POSITIONS} (보유: {len(symbols_held)}, 진입진행중: {len(self.recently_entered)})")
                    return
            except Exception as e:
                logger.error(f"[TRADER ERROR] 포지션 체크 중 예외 발생: {e}")
                self._log_trade(sig, status="FAILED", reason=f"포지션 조회 오류 ({e})")
                return

            # ── 주문 실행 ─────────────────────────────
            side = "buy" if sig.direction == "long" else "sell"
            
            margin_usdt = self.cfg.MARGIN_USDT

            if margin_usdt < 1.0:
                logger.warning(f"[SKIP] 증거금 설정 오류 (최소 $1): {margin_usdt:.2f} USDT")
                return

            result = self.client.place_order(
                symbol=sig.symbol,
                side=side,
                margin_usdt=margin_usdt,
            )

            if result:
                self.recently_entered[sig.symbol] = datetime.now()
                self.orders_today += 1
                stats_store.record_order()
                self._log_trade(sig, status="EXECUTED", result=result)
                logger.info(f"[ORDER] {sig.symbol} {sig.direction.upper()} 실행 완료")
                # CSV 영구 기록
                csv_log({
                    "timestamp": datetime.now(timezone(timedelta(hours=9))),
                    "symbol": sig.symbol,
                    "type": "진입",
                    "side": sig.direction,
                    "price": result.get("entry_price", 0),
                    "amount": result.get("amount", 0),
                    "pnl_usdt": 0,
                    "pnl_pct": 0,
                    "leverage": self.cfg.LEVERAGE,
                    "order_id": result.get("order_id", ""),
                })
            else:
                self._log_trade(sig, status="FAILED", reason="주문 API 오류")

    # ── 리스크 관리 ────────────────────────────────────

    def _risk_check(self, sig: Signal) -> tuple[bool, str]:
        """다층 리스크 게이트"""

        # 0. 쿨다운 체크
        now = datetime.now()
        if self.global_cooldown_until and now < self.global_cooldown_until:
            remaining = (self.global_cooldown_until - now).total_seconds()
            return False, f"글로벌 쿨다운 진행 중 (남은 시간: {remaining:.1f}초)"

        if sig.symbol in self.symbol_cooldown_until:
            until = self.symbol_cooldown_until[sig.symbol]
            if now < until:
                remaining = (until - now).total_seconds()
                return False, f"{sig.symbol} 종목별 쿨다운 진행 중 (남은 시간: {remaining:.1f}초)"
            else:
                self.symbol_cooldown_until.pop(sig.symbol, None)

        # 1. 일일 손실 한도
        if self.daily_pnl_usdt <= -self.cfg.DAILY_LOSS_LIMIT_USDT:
            return False, f"일일 손실 한도 초과: {self.daily_pnl_usdt:.2f} USDT"

        # 2. 계좌 잔고 체크
        balance = self.client.get_balance()
        total = balance.get("total", 0)
        if total < self.cfg.MIN_REQUIRED_BALANCE_USDT:
            return False, f"잔고 부족 (< {self.cfg.MIN_REQUIRED_BALANCE_USDT} USDT)"

        # 3. MAX_DRAWDOWN_PCT — 초기 자금 대비 낙폭 체크
        try:
            _stats = stats_store.load_stats()
            seed_money = _stats.get("seed_money", 0)
            if seed_money > 0:
                drawdown_pct = (seed_money - total) / seed_money
                if drawdown_pct >= self.cfg.MAX_DRAWDOWN_PCT:
                    return False, (
                        f"최대 낙폭 초과: {drawdown_pct*100:.1f}% "
                        f"(한도 {self.cfg.MAX_DRAWDOWN_PCT*100:.0f}%, "
                        f"시드 {seed_money:.2f} → 현재 {total:.2f} USDT)"
                    )
        except Exception as e:
            logger.warning(f"[RISK] MDD 체크 중 예외: {e}")

        # 4. 신호 강도 — 4대 조건 모두 충족(100%) 필수
        if sig.strength < 100:
            return False, f"신호 강도 부족: {sig.strength}% (4대 조건 모두 충족 필요)"

        # 5. 가용 증거금 확인
        free = balance.get("free", 0)
        required_margin = self.cfg.MARGIN_USDT
        if free < required_margin:
            return False, f"가용 증거금 부족: {free:.2f} < {required_margin:.2f}"

        return True, "OK"

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
            "timestamp": datetime.utcnow() + timedelta(hours=9),
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
