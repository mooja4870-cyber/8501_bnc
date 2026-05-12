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
from core.strategy import StrategyEngine, Signal
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
        self.strategy = StrategyEngine() # 시장 성격 판별용

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
            
            # ── 중복 실행 방지 락 (심볼 단위) ──
            self._pending_entries[sig.symbol] = now
            self._last_entry_at[sig.symbol] = now # 쿨다운 즉시 시작
            
            result = None
            try:
                # 실제로 주문을 넣기 직전에 한 번 더 포지션 체크 (네트워크 지연 대비)
                # 이 시점에는 이미 self._lock을 쥐고 있으므로 안전함
                result = self.client.place_order(
                    symbol=sig.symbol,
                    side=side,
                    margin_usdt=margin_usdt,
                )
                
                # v2.0.0: 진입 즉시 시장 성격에 따른 SL/TP/Trailing 설정
                if result:
                    size = result.get("amount", 0)
                    entry_price = result.get("entry_price", 0)
                    if size > 0:
                        use_trailing = (sig.regime == "Trend")
                        self.client.place_sl_tp_orders(
                            symbol=sig.symbol,
                            side=sig.direction,
                            amount=size,
                            entry_price=entry_price,
                            sl_pct=self.cfg.STOP_LOSS_PCT,
                            tp_pct=self.cfg.TAKE_PROFIT_PCT,
                            use_trailing=use_trailing,
                            callback_pct=self.cfg.TRAILING_CALLBACK_PCT,
                            activate_pct=self.cfg.TRAILING_ACTIVATE_PCT
                        )
            except Exception as e:
                logger.error(f"[ERR] 주문 실행 중 예외 발생: {e}")
            finally:
                # 락을 바로 풀지 않고 약간의 여유를 두어 거래소 반영 시간을 확보
                # (주문 성공 시에는 pop하지 않고 쿨다운에 의존)
                if not result:
                    self._pending_entries.pop(sig.symbol, None)
                    self._last_entry_at.pop(sig.symbol, None)

            if result:
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

        # 만료된 펜딩 제거
        expired = [
            sym for sym, ts in self._pending_entries.items()
            if now - ts > pending_ttl
        ]
        for sym in expired:
            self._pending_entries.pop(sym, None)

        # 1. 펜딩 체크
        pending_at = self._pending_entries.get(symbol)
        if pending_at and now - pending_at <= pending_ttl:
            return True, "동일 티커 주문 진행 중", []

        # 2. 쿨다운 체크
        last_entry_at = self._last_entry_at.get(symbol)
        if last_entry_at and now - last_entry_at < cooldown:
            remain = int((cooldown - (now - last_entry_at)).total_seconds())
            return True, f"동일 티커 재진입 쿨다운 {remain}초 남음", []

        # 3. 실제 포지션 체크 (API)
        positions = self.client.get_positions()
        if any(p["symbol"] == symbol for p in positions):
            return True, "이미 포지션 보유", positions

        # 4. 미체결 주문 체크 (API)
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

    def sync_sl_tp(self):
        """
        [v1.1.57] 실시간 SL/TP 동기화
        보유 포지션의 손절/익절가가 현재 설정(CFG)과 다를 경우 주문을 취소하고 재전송한다.
        """
        if not self.enabled:
            return
            
        try:
            positions = self.client.get_positions()
            if not positions:
                return
                
            open_orders = self.client.get_open_orders()
            
            for p in positions:
                symbol = p["symbol"]
                side = p["side"]
                size = p["size"]
                entry_price = p["entry_price"]
                
                # 1. 현재 설정에 따른 목표가 계산
                target_sl = entry_price * (1 - self.cfg.STOP_LOSS_PCT) if side == "long" else entry_price * (1 + self.cfg.STOP_LOSS_PCT)
                target_tp = entry_price * (1 + self.cfg.TAKE_PROFIT_PCT) if side == "long" else entry_price * (1 - self.cfg.TAKE_PROFIT_PCT)
                
                # 2. 현재 걸려있는 SL/TP 주문 확인
                existing_stops = [
                    o for o in open_orders 
                    if o["symbol"] == symbol and o["type"] in ("stop", "trigger")
                ]
                
                # 만약 주문이 2개가 아니거나 가격 차이가 0.5% 이상 나면 갱신
                needs_update = len(existing_stops) != 2
                if not needs_update:
                    for stop in existing_stops:
                        # 가격 비교 (오차 범위 0.1% 내외면 유지)
                        price = float(stop.get("price") or stop.get("stopPrice") or 0)
                        if price == 0: continue
                        
                        target = target_sl if (side == "long" and price < entry_price) or (side == "short" and price > entry_price) else target_tp
                        if abs(price - target) / target > 0.005: # 0.5% 차이 시 갱신
                            needs_update = True
                            break
                
                # 3. v2.0.0: 현재 시장 성격 재판별
                ticker_df = self.client.get_ohlcv(symbol, timeframe=self.cfg.TIMEFRAME, limit=100)
                ticker_df = self.strategy.calculate_indicators(ticker_df)
                current_regime = self.strategy.get_market_regime(ticker_df)
                use_trailing = (current_regime == "Trend")

                if needs_update:
                    logger.info(f"[SYNC] {symbol} 설정 변경 감지 ({current_regime}) -> SL/TP/Trailing 주문 갱신")
                    self.client.cancel_sl_tp_orders(symbol)
                    self.client.place_sl_tp_orders(
                        symbol, side, size, entry_price,
                        self.cfg.STOP_LOSS_PCT, self.cfg.TAKE_PROFIT_PCT,
                        use_trailing=use_trailing,
                        callback_pct=self.cfg.TRAILING_CALLBACK_PCT,
                        activate_pct=self.cfg.TRAILING_ACTIVATE_PCT
                    )
                    
        except Exception as e:
            logger.error(f"SL/TP 동기화 오류: {e}")
