"""
자동매매 실행 엔진 (비동기 엔터프라이즈 버전)
리스크 관리 + 포지션 관리 + 주문 실행 통합
"""
import asyncio
import logging
from typing import Optional, List, Dict
from datetime import datetime, date, timedelta, timezone

from core.exchange import BinanceClient
from core.strategy import Signal
from core.config import CFG
import core.stats as stats_store
from core.logger import log_trade as csv_log
from core.alert import send_telegram_alert

logger = logging.getLogger(__name__)


class AutoTrader:
    """
    비동기 자동매매 엔진
    Scanner.on_signal 콜백으로 신호를 받아 리스크 체크 후 실거래 실행
    """

    def __init__(self, client: BinanceClient):
        self.client = client
        self.cfg = CFG
        self._lock = asyncio.Lock()

        self.enabled: bool = False
        self.allow_long: bool = True
        self.allow_short: bool = True

        _s = stats_store.load_stats()
        self.orders_today: int = _s.get("orders_today", 0)
        self.daily_pnl_usdt: float = _s.get("daily_pnl_usdt", 0.0)
        self.trade_log: List[Dict] = []
        self._today: date = date.today()

        self.recently_entered: Dict[str, datetime] = {}
        self.global_cooldown_until: Optional[datetime] = None
        self.symbol_cooldown_until: Dict[str, datetime] = {}
        self._daily_loss_alert_sent = False

    def enable(self):
        self.enabled = True
        logger.info("[TRADER] 자동매매 활성화 (Async)")

    def disable(self):
        self.enabled = False
        logger.info("[TRADER] 자동매매 비활성화")

    def trigger_global_cooldown(self, seconds: int = 60):
        self.global_cooldown_until = datetime.now() + timedelta(seconds=seconds)
        logger.info(f"[COOLDOWN] 글로벌 쿨다운 설정 완료 ({seconds}초간 새로운 진입 차단)")

    def trigger_symbol_cooldown(self, symbol: str, seconds: int = 60):
        self.symbol_cooldown_until[symbol] = datetime.now() + timedelta(seconds=seconds)
        logger.info(f"[COOLDOWN] {symbol} 종목별 쿨다운 설정 완료 ({seconds}초간 진입 차단)")

    async def on_signal(self, sig: Signal):
        if not self.enabled:
            return
        if sig.direction == "none":
            return

        async with self._lock:
            self._reset_daily_if_needed()

            try:
                passed, reason = await self._risk_check(sig)
                if not passed:
                    logger.warning(f"[RISK BLOCK] {sig.symbol} — {reason}")
                    self._log_trade(sig, status="BLOCKED", reason=reason)
                    return
            except Exception as e:
                logger.error(f"[RISK ERROR] {sig.symbol} 리스크 체크 중 예외 발생: {e}")
                self._log_trade(sig, status="FAILED", reason=f"API 조회 오류 ({e})")
                return

            if sig.direction == "long" and not self.allow_long:
                return
            if sig.direction == "short" and not self.allow_short:
                return

            now_time = datetime.now()
            self.recently_entered = {
                sym: ts for sym, ts in self.recently_entered.items()
                if (now_time - ts).total_seconds() < 120
            }

            try:
                positions = await self.client.get_positions()
                symbols_held = {p["symbol"] for p in positions}
                
                for sym in list(self.recently_entered.keys()):
                    if sym in symbols_held:
                        self.recently_entered.pop(sym, None)

                if sig.symbol in symbols_held or sig.symbol in self.recently_entered:
                    logger.info(f"[SKIP] {sig.symbol} — 이미 포지션 보유 중이거나 진입 주문이 전송되었습니다.")
                    return

                effective_count = len(symbols_held) + len(self.recently_entered)
                if effective_count >= self.cfg.MAX_POSITIONS:
                    logger.info(f"[SKIP] 최대 포지션 수 도달: {effective_count}/{self.cfg.MAX_POSITIONS}")
                    return
            except Exception as e:
                logger.error(f"[TRADER ERROR] 포지션 체크 중 예외 발생: {e}")
                self._log_trade(sig, status="FAILED", reason=f"포지션 조회 오류 ({e})")
                return

            side = "buy" if sig.direction == "long" else "sell"
            
            # [Dynamic Compounding Margin]
            if getattr(self.cfg, "USE_AUTO_COMPOUND", False):
                try:
                    balance = await self.client.get_balance()
                    total_bal = balance.get("total", 0.0)
                    if total_bal > 0:
                        margin_usdt = round((total_bal / self.cfg.MAX_POSITIONS) * 0.9, 2)
                        logger.info(f"[COMPOUND] 자동 복리 마진 적용: 총 잔고 ${total_bal:.2f} -> 1회 진입 증거금 ${margin_usdt:.2f} USDT")
                    else:
                        margin_usdt = self.cfg.MARGIN_USDT
                except Exception as e:
                    logger.error(f"[COMPOUND ERROR] 잔고 조회 실패로 고정 마진 사용: {e}")
                    margin_usdt = self.cfg.MARGIN_USDT
            else:
                margin_usdt = self.cfg.MARGIN_USDT

            if margin_usdt < 1.0:
                logger.warning(f"[SKIP] 증거금 설정 오류 (최소 $1): {margin_usdt:.2f} USDT")
                return

            if (getattr(self.cfg, "USE_ATR_SL_TP", False) or getattr(self.cfg, "USE_DYNAMIC_SLTP", False)) and sig.atr > 0 and sig.close > 0:
                atr_pct = sig.atr / sig.close
                dynamic_sl_pct = atr_pct * self.cfg.ATR_SL_MULT
                dynamic_tp_pct = atr_pct * self.cfg.ATR_TP_MULT
                logger.info(f"[DYNAMIC SL/TP] {sig.symbol} ATR={sig.atr:.4f} ({atr_pct*100:.2f}%) -> SL={dynamic_sl_pct*100:.2f}%, TP={dynamic_tp_pct*100:.2f}%")
            else:
                dynamic_sl_pct = self.cfg.STOP_LOSS_PCT
                dynamic_tp_pct = self.cfg.TAKE_PROFIT_PCT

            result = await self.client.place_order(
                symbol=sig.symbol,
                side=side,
                margin_usdt=margin_usdt,
                stop_loss_pct=dynamic_sl_pct,
                take_profit_pct=dynamic_tp_pct
            )

            if result:
                self.recently_entered[sig.symbol] = datetime.now()
                self.orders_today += 1
                stats_store.record_order()
                self._log_trade(sig, status="EXECUTED", result=result)
                logger.info(f"[ORDER] {sig.symbol} {sig.direction.upper()} 실행 완료")
                
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

                # 진입 성공 텔레그램 알림
                send_telegram_alert(
                    f"🟢 *[포지션 진입 완료]*\n"
                    f"종목: {sig.symbol}\n"
                    f"구분: {sig.direction.upper()} 진입\n"
                    f"진입가: {result.get('entry_price', 0)} USDT\n"
                    f"증거금: {margin_usdt:.2f} USDT\n"
                    f"레버리지: {self.cfg.LEVERAGE}x\n"
                    f"수량: {result.get('amount', 0)}\n"
                    f"익절 목표: {result.get('tp_price', 0):.6f}\n"
                    f"손절 설정: {result.get('sl_price', 0):.6f}"
                )
            else:
                self._log_trade(sig, status="FAILED", reason="주문 API 오류")

    async def _risk_check(self, sig: Signal) -> tuple[bool, str]:
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

        if self.daily_pnl_usdt <= -self.cfg.DAILY_LOSS_LIMIT_USDT:
            if not getattr(self, "_daily_loss_alert_sent", False):
                self._daily_loss_alert_sent = True
                send_telegram_alert(
                    f"🚨 *[RISK ALERT]* 일일 손실 한도 초과! 자동매매 신규 진입이 차단됩니다.\n"
                    f"금일 누적 손익: {self.daily_pnl_usdt:.2f} USDT (한도: {self.cfg.DAILY_LOSS_LIMIT_USDT} USDT)"
                )
            return False, f"일일 손실 한도 초과: {self.daily_pnl_usdt:.2f} USDT"

        balance = await self.client.get_balance()
        total = balance.get("total", 0)
        if total < self.cfg.MIN_REQUIRED_BALANCE_USDT:
            return False, f"잔고 부족 (< {self.cfg.MIN_REQUIRED_BALANCE_USDT} USDT)"

        try:
            _stats = stats_store.load_stats()
            seed_money = _stats.get("seed_money", 0)
            if seed_money > 0:
                drawdown_pct = (seed_money - total) / seed_money
                if drawdown_pct >= self.cfg.MAX_DRAWDOWN_PCT:
                    return False, f"최대 낙폭 초과: {drawdown_pct*100:.1f}%"
        except Exception as e:
            logger.warning(f"[RISK] MDD 체크 중 예외: {e}")

        if sig.strength < 100:
            return False, f"신호 강도 부족: {sig.strength}% (4대 조건 모두 충족 필요)"

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
            self._daily_loss_alert_sent = False
            self._today = today
            _s = stats_store.load_stats()
            _s["orders_today"] = 0
            _s["daily_pnl_usdt"] = 0.0
            stats_store.save_stats(_s)

    def _log_trade(self, sig: Signal, status: str, reason: str = "", result: Optional[Dict] = None):
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

    async def get_trade_log(self) -> List[Dict]:
        async with self._lock:
            return list(reversed(self.trade_log))
