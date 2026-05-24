"""
AI QUANTUM — Orchestration Engine (v2)
모든 모듈(Exchange, Scanner, Trader)을 통합 관리하고 조율하는 중앙 컨트롤러
v2: FSM(상태 머신) + Health Check + 자동 복구 추가
"""
import logging
import threading
import time
from enum import Enum, auto
from typing import Optional, List, Dict

from core.exchange import BinanceClient
from core.scanner import Scanner
from core.trader import AutoTrader
from core.config import CFG
import core.stats as stats_store
from datetime import datetime, timezone, timedelta
from core.logger import log_trade as csv_log

logger = logging.getLogger(__name__)


# ── 엔진 상태 머신 (FSM) ─────────────────────────────────

class EngineState(Enum):
    """엔진 상태 정의"""
    IDLE = auto()           # 초기 상태 — 아무것도 연결 안 됨
    CONNECTING = auto()     # API 연결 시도 중
    CONNECTED = auto()      # API 연결 완료, 스캐너 미실행
    SCANNING = auto()       # 스캐너 구동 중 (매매 비활성)
    TRADING = auto()        # 스캐너 + 자동매매 모두 활성
    ERROR = auto()          # 오류 상태 — 복구 대기
    RECOVERING = auto()     # 자동 복구 시도 중


# 유효 상태 전이 맵
_TRANSITIONS = {
    EngineState.IDLE:       {EngineState.CONNECTING},
    EngineState.CONNECTING: {EngineState.CONNECTED, EngineState.ERROR},
    EngineState.CONNECTED:  {EngineState.SCANNING, EngineState.IDLE, EngineState.CONNECTING},
    EngineState.SCANNING:   {EngineState.TRADING, EngineState.CONNECTED, EngineState.ERROR, EngineState.CONNECTING},
    EngineState.TRADING:    {EngineState.SCANNING, EngineState.CONNECTED, EngineState.ERROR, EngineState.CONNECTING},
    EngineState.ERROR:      {EngineState.RECOVERING, EngineState.IDLE, EngineState.CONNECTING},
    EngineState.RECOVERING: {EngineState.CONNECTED, EngineState.ERROR, EngineState.IDLE, EngineState.CONNECTING},
}


class QuantumEngine:
    """
    퀀텀 엔진 (Orchestrator v2)
    - UI(app.py)와 비즈니스 로직 사이의 완벽한 분리 제공
    - 모든 하위 모듈의 생명주기(Lifecycle) 관리
    - FSM 기반 명시적 상태 관리
    - 모듈별 Health 모니터링
    """
    _instance = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        """전역 단일 엔진(Singleton) 반환"""
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
        self._lock = threading.Lock()
        self._initialized = False
        self._prev_position_symbols: set = set()  # 청산 감지용 스냅샷

        # FSM 상태
        self._state = EngineState.IDLE
        self._state_lock = threading.Lock()
        self._error_msg = ""
        self._recovery_attempts = 0
        self._max_recovery_attempts = 3

        # API 연결 정보 (복구용 보관)
        self._api_key = ""
        self._secret_key = ""
        self._passphrase = ""

    # ── FSM 상태 관리 ─────────────────────────────────────

    @property
    def state(self) -> EngineState:
        return self._state

    def _transition(self, new_state: EngineState, reason: str = ""):
        """상태 전이 — 유효하지 않은 전이 시 경고 로깅"""
        with self._state_lock:
            allowed = _TRANSITIONS.get(self._state, set())
            if new_state not in allowed:
                logger.warning(
                    f"[FSM] 유효하지 않은 전이: {self._state.name} → {new_state.name} "
                    f"(허용: {[s.name for s in allowed]})"
                )
                return False
            old = self._state
            self._state = new_state
            logger.info(f"[FSM] {old.name} → {new_state.name} | {reason}")
            return True

    # ── 초기화 ────────────────────────────────────────────

    def initialize(self, api_key: str, secret_key: str, passphrase: str) -> tuple[bool, str]:
        """API 연결 및 모듈 초기화"""
        # 만약 이미 초기화되어 있고 API Key가 동일하며 에러 상태가 아닌 경우, 재연결 건너뜀
        if self._initialized and self._state != EngineState.ERROR and self._api_key == api_key and self._secret_key == secret_key and self._passphrase == passphrase:
            logger.info("[ENGINE] 이미 동일한 API 키로 정상 작동 중이므로 초기화를 건너뜁니다.")
            return True, "✅ 엔진이 이미 활성화되어 있습니다."

        self._transition(EngineState.CONNECTING, "API 연결 시도")

        # 복구용 보관
        self._api_key = api_key
        self._secret_key = secret_key
        self._passphrase = passphrase

        with self._lock:
            try:
                self.client = BinanceClient(api_key, secret_key, passphrase)
                if self.client.load_markets():
                    self.scanner = Scanner(self.client)
                    self.trader = AutoTrader(self.client)

                    # 스캐너와 트레이더 연결 (콜백)
                    self.scanner.on_signal = self.trader.on_signal
                    # 스캔 완료 시 청산 감지 콜백 등록
                    self.scanner.on_scan_complete = self._check_closed_positions

                    self._initialized = True
                    self._recovery_attempts = 0
                    self._transition(EngineState.CONNECTED, "마켓 로드 성공")
                    return True, "✅ 엔진 초기화 및 마켓 로드 성공"

                self._error_msg = "마켓 정보 로드 실패"
                self._transition(EngineState.ERROR, self._error_msg)
                return False, f"❌ {self._error_msg}"
            except Exception as e:
                self._error_msg = str(e)
                logger.error(f"엔진 초기화 실패: {e}")
                self._transition(EngineState.ERROR, f"초기화 예외: {e}")
                return False, f"❌ 엔진 초기화 오류: {e}"

    @property
    def is_ready(self) -> bool:
        return self._initialized and self.client is not None

    # ── 모듈 제어 ──────────────────────────────────────

    def start_scanner(self):
        if self.scanner and not self.scanner.is_running:
            self.scanner.start()
            self._transition(EngineState.SCANNING, "스캐너 시작")

    def stop_scanner(self):
        if self.scanner:
            self.scanner.stop()
            if self._state == EngineState.TRADING:
                self.disable_trading()
            if self.is_ready:
                self._transition(EngineState.CONNECTED, "스캐너 중지")

    def enable_trading(self):
        if self.trader:
            self.trader.enable()
            if self._state == EngineState.SCANNING:
                self._transition(EngineState.TRADING, "자동매매 활성화")

    def disable_trading(self):
        if self.trader:
            self.trader.disable()
            if self._state == EngineState.TRADING:
                self._transition(EngineState.SCANNING, "자동매매 비활성화")

    # ── Health Check ──────────────────────────────────

    def get_health(self) -> Dict:
        """모듈별 상태 점검 결과 반환"""
        return {
            "engine_state": self._state.name,
            "api_connected": self.is_ready,
            "scanner_running": self.scanner.is_running if self.scanner else False,
            "trading_enabled": self.trader.enabled if self.trader else False,
            "recovery_attempts": self._recovery_attempts,
            "last_error": self._error_msg,
            "scan_count": self.scanner.scan_count if self.scanner else 0,
        }

    # ── 자동 복구 ─────────────────────────────────────

    def attempt_recovery(self) -> tuple[bool, str]:
        """ERROR 상태에서 자동 복구 시도 (지수 백오프)"""
        if self._state != EngineState.ERROR:
            return False, "ERROR 상태가 아님"

        if self._recovery_attempts >= self._max_recovery_attempts:
            return False, f"최대 복구 횟수 초과 ({self._max_recovery_attempts}회)"

        self._transition(EngineState.RECOVERING, f"복구 시도 #{self._recovery_attempts + 1}")
        self._recovery_attempts += 1

        # 지수 백오프 대기
        wait = min(2 ** self._recovery_attempts, 30)
        logger.info(f"[RECOVERY] {wait}초 대기 후 재연결...")
        time.sleep(wait)

        if self._api_key:
            success, msg = self.initialize(
                self._api_key, self._secret_key, self._passphrase
            )
            if success:
                return True, f"✅ 복구 성공 (시도 #{self._recovery_attempts})"

        self._transition(EngineState.ERROR, "복구 실패")
        return False, f"❌ 복구 실패 (시도 #{self._recovery_attempts})"

    # ── 데이터 게이트웨이 (UI용) ────────────────────────

    def get_dashboard_data(self) -> Dict:
        """대시보드에 필요한 핵심 상태 통합 반환"""
        if not self.is_ready:
            return {}

        try:
            balance = self.client.get_balance()
            positions = self.client.get_positions()
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

    def get_scan_results(self) -> List[Dict]:
        return self.scanner.get_results() if self.scanner else []

    def get_system_logs(self, limit: int = 50) -> List[str]:
        """스캐너와 트레이더 로그 통합"""
        logs = []
        if self.scanner:
            logs.extend(self.scanner.get_logs(limit))
        return sorted(logs, reverse=True)[:limit]

    def get_trade_history(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """거래소 체결 내역 조회"""
        return self.client.get_trade_history(symbol, limit) if self.client else []

    # ── 청산 감지 & 승패 기록 ──────────────────────────

    def _check_closed_positions(self):
        """스캔 완료 시마다 호출 — 청산된 포지션 감지 및 타임아웃 체크"""
        if not self.is_ready:
            return
        try:
            raw_positions = self.client.get_positions()
            current = {p["symbol"] for p in raw_positions}
            closed = self._prev_position_symbols - current  # 사라진 심볼 = 청산됨

            if closed:
                closed_records = self.client.get_closed_positions_pnl(limit=10)
                for sym in closed:
                    pnl = 0.0
                    try:
                        recent_trades = self.client.get_trade_history(symbol=sym, limit=5)
                        exit_trade = next((t for t in recent_trades if t.get("category") == "청산"), None)
                        if exit_trade:
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
                            })
                    except Exception as e:
                        logger.error(f"청산 CSV 기록 실패: {e}")

                    stats_store.record_result(pnl)
                    if self.trader:
                        self.trader.daily_pnl_usdt = round(self.trader.daily_pnl_usdt + pnl, 4)
                        self.trader.trigger_symbol_cooldown(sym, 60)
                    logger.info(
                        f"[CLOSED] {sym} PnL={pnl:+.4f} USDT"
                        f" -> {'WIN' if pnl >= 0 else 'LOSS'} 기록"
                    )

                # [Auto-Tuning] 자동 피팅 최적화 실행
                if self.cfg.AUTO_TUNE_SL_TP:
                    try:
                        logger.info("[AUTO-TUNE] 청산 감지됨. 실시간 손익비 최적 피팅 기동...")
                        self.sync_trades_to_csv()
                        opt_res = self.run_optimization()
                        if opt_res.get("status") == "success" and opt_res.get("analyzed_count", 0) >= 5:
                            opt_sl = opt_res["optimal_sl"] / 100.0
                            opt_tp = opt_res["optimal_tp"] / 100.0
                            
                            if opt_sl != self.cfg.STOP_LOSS_PCT or opt_tp != self.cfg.TAKE_PROFIT_PCT:
                                old_sl = self.cfg.STOP_LOSS_PCT * 100
                                old_tp = self.cfg.TAKE_PROFIT_PCT * 100
                                self.cfg.STOP_LOSS_PCT = opt_sl
                                self.cfg.TAKE_PROFIT_PCT = opt_tp
                                
                                from core.logger import log_autotune as autotune_log
                                autotune_log({
                                    "old_tp": old_tp,
                                    "old_sl": old_sl,
                                    "new_tp": opt_res['optimal_tp'],
                                    "new_sl": opt_res['optimal_sl'],
                                    "winrate": opt_res['optimal_winrate'],
                                    "pnl": opt_res['optimal_pnl'],
                                    "count": opt_res['analyzed_count']
                                })
                                
                                msg = f"[AUTO-TUNE SUCCESS] 실시간 최적화 반영: 익절 {old_tp:.1f}% → {opt_res['optimal_tp']:.1f}%, 손절 {old_sl:.1f}% → {opt_res['optimal_sl']:.1f}% (예상승률 {opt_res['optimal_winrate']:.1f}%)"
                                logger.warning(msg)
                    except Exception as e:
                        logger.error(f"[AUTO-TUNE ERROR] {e}")

            # [v1.2.90] 강제 청산 타임아웃 체크 (Holding Time Timeout)
            if self.cfg.MAX_HOLDING_HOURS > 0:
                import time as time_mod
                now_ms = time_mod.time() * 1000
                timeout_ms = self.cfg.MAX_HOLDING_HOURS * 3600 * 1000

                for p in raw_positions:
                    entry_ts = p.get("timestamp")
                    if entry_ts and (now_ms - entry_ts) > timeout_ms:
                        sym = p["symbol"]
                        side = p["side"]
                        logger.warning(f"[TIMEOUT] {sym} {side} - {self.cfg.MAX_HOLDING_HOURS}시간 초과 강제청산 실행")
                        self.client.close_position(sym, side)
                        if self.trader:
                            self.trader.trigger_symbol_cooldown(sym, 60)

            self._prev_position_symbols = current
            
            # [Rotation] 정체 포지션 로테이션 체크 실행
            try:
                self._run_position_rotation_check(raw_positions)
            except Exception as e:
                logger.error(f"정체 포지션 로테이션 오류: {e}")

        except Exception as e:
            logger.error(f"청산 감지 오류: {e}")

    def _run_position_rotation_check(self, raw_positions: List[Dict]):
        """정체 포지션 감지 및 신규 스캐너 종목 교체 청산 제어"""
        if not self.cfg.ROTATION_ENABLED:
            return

        # 1. 대기 중인 신규 고강도 신호 수 확인 (강도 60% 이상이고 방향이 있는 것)
        scan_signals = [s for s in self.get_scan_results() if s.get("signal") in ("long", "short") and s.get("strength", 0) >= 60]
        
        # 교체 진입 대기 신호 개수 미달 시 패스
        if len(scan_signals) < self.cfg.ROTATION_MIN_SIGNALS:
            return

        import time as time_mod
        now_ms = time_mod.time() * 1000
        stale_limit_ms = self.cfg.ROTATION_STALE_HOURS * 3600 * 1000

        for p in raw_positions:
            entry_ts = p.get("timestamp")
            if not entry_ts:
                continue

            # 지정된 시간 초과 보유한 포지션만 대상
            if (now_ms - entry_ts) > stale_limit_ms:
                if self._is_flow_bad(p):
                    sym = p["symbol"]
                    side = p["side"]
                    pnl = float(p.get("pnl_usdt", 0.0))
                    pnl_pct = float(p.get("pnl_pct", 0.0))
                    
                    logger.warning(
                        f"[ROTATION] {sym} {side} 정체 포지션 감지 "
                        f"(보유시간 {((now_ms - entry_ts)/3600000):.2f}시간, PnL {pnl:+.4f} USDT, {pnl_pct:+.2f}%). "
                        f"스캐너 대기 신호 {len(scan_signals)}개 존재. 즉시 시장가 청산 실행."
                    )
                    
                    # 시장가 즉시 청산
                    close_res = self.client.close_position(sym, side)
                    if close_res:
                        if self.trader:
                            self.trader.trigger_symbol_cooldown(sym, 60)
                        # 로컬 CSV 영구 기록
                        try:
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
                            })
                        except Exception as e:
                            logger.error(f"로테이션 청산 CSV 기록 실패: {e}")
                        
                        # 일별 승률 통계 반영
                        stats_store.record_result(pnl)
                        if self.trader:
                            self.trader.daily_pnl_usdt = round(self.trader.daily_pnl_usdt + pnl, 4)

    def _is_flow_bad(self, p: Dict) -> bool:
        """포지션의 가격 흐름이 나쁜지 판단"""
        symbol = p["symbol"]
        side = p["side"]
        entry_price = float(p.get("entry_price") or 0.0)
        current_price = float(p.get("mark_price") or p.get("current_price") or 0.0)
        
        if entry_price <= 0 or current_price <= 0:
            return False

        check_type = self.cfg.ROTATION_FLOW_CHECK

        # [제1안] 모멘텀 이탈 (EMA 돌파)
        if check_type == "momentum":
            try:
                import pandas as pd
                df = self.client.get_ohlcv(symbol, timeframe="15m", limit=50)
                if not df.empty and len(df) >= 20:
                    # 20 EMA 계산
                    ema = df["close"].ewm(span=20, adjust=False).mean().iloc[-1]
                    if "long" in side.lower() or "buy" in side.lower():
                        # Long 포지션인데 현재 가격이 EMA보다 아래에 있으면 흐름이 나쁨
                        return current_price < ema
                    else:
                        # Short 포지션인데 현재 가격이 EMA보다 위에 있으면 흐름이 나쁨
                        return current_price > ema
            except Exception as e:
                logger.error(f"[ROTATION] {symbol} EMA 계산 실패: {e}")
                return False

        # [제2안] 절대 가격 정체 (횡보)
        elif check_type == "flat":
            try:
                entry_ts = p.get("timestamp")
                if entry_ts:
                    import time as time_mod
                    now_ms = time_mod.time() * 1000
                    duration_min = int((now_ms - entry_ts) / 60000)
                    limit = min(max(duration_min, 10), 200)
                    df = self.client.get_ohlcv(symbol, timeframe="1m", limit=limit)
                    if not df.empty:
                        highs = df["high"].max()
                        lows = df["low"].min()
                        amplitude = (highs - lows) / entry_price
                        # 0.25% 미만인 경우 정체로 판단
                        return amplitude < 0.0025
            except Exception as e:
                logger.error(f"[ROTATION] {symbol} 횡보 여부 계산 실패: {e}")
                return False

        # [제3안] 기간 대비 수익률 부진 (시간 감쇠)
        elif check_type == "time":
            pnl_pct = float(p.get("pnl_pct") or 0.0)
            # 수수료/마이너스에 머물러 있거나 1.0% 미만의 매우 소폭인 상태
            return -2.0 <= pnl_pct <= 1.0

        return False

    def run_optimization(self) -> Dict:
        """MAE/MFE 손익 최적화 시뮬레이션 실행"""
        if not self.client:
            return {"status": "error", "message": "거래소가 연결되어 있지 않습니다."}
        from core.optimizer import TradeOptimizer
        opt = TradeOptimizer(self.client)
        return opt.run_optimization()

    def sync_trades_to_csv(self):
        """거래소의 최근 거래 기록을 로컬 CSV로 안전하게 추가 동기화 (기록 누락 복구용, 중복 및 덮어쓰기 방지)"""
        if not self.client:
            return
        try:
            # 1) 동기화 대상 심볼 추출
            target_symbols = set()
            
            # 현재 포지션 심볼들 추가
            try:
                positions = self.client.get_positions()
                for p in positions:
                    target_symbols.add(p["symbol"])
            except Exception as pe:
                logger.error(f"동기화 대상 포지션 조회 실패: {pe}")
            
            # 로컬 매매 이력에 있는 최근 거래들의 심볼들 추가
            local_trades = []
            try:
                from core.history_helper import load_local_trade_history
                local_trades = load_local_trade_history()
                # 최근 20개 거래의 심볼들을 대상에 추가하여 최근 체결의 동기화 보장
                for lt in local_trades[-20:]:
                    target_symbols.add(lt["symbol"])
            except Exception as le:
                logger.error(f"동기화 대상 로컬 이력 로드 실패: {le}")

            # 2) 각 심볼별로 최근 체결 내역 통합 수집
            trades = []
            for sym in target_symbols:
                try:
                    sym_trades = self.client.get_trade_history(symbol=sym, limit=20)
                    if sym_trades:
                        trades.extend(sym_trades)
                    time.sleep(0.1)  # API Rate Limit 방지용 미세 대기
                except Exception as se:
                    logger.error(f"{sym} 거래소 체결 이력 조회 실패: {se}")

            if not trades:
                return
            
            # 3) 기존 로컬 이력에 기록된 order_id 목록 추출 (중복 저장 가드)
            existing_ids = set()
            try:
                for lt in local_trades:
                    oid = lt.get("order_id")
                    if oid:
                        existing_ids.add(str(oid).strip())
            except Exception:
                pass

            # 시간 오름차순으로 정렬해서 순차 기록
            trades = sorted(trades, key=lambda x: x["timestamp"])
            
            new_count = 0
            for t in trades:
                t_order_id = str(t.get("order_id", "")).strip()
                if t_order_id and t_order_id in existing_ids:
                    continue  # 이미 기록된 거래 건너뜀
                
                csv_log({
                    "timestamp": t["timestamp"],
                    "symbol": t["symbol"],
                    "type": "진입" if t["category"] == "*진입" or t["category"] == "진입" else "청산",
                    "side": t["side"],
                    "price": t["price"],
                    "amount": t["amount"],
                    "pnl_usdt": t["pnl"],
                    "pnl_pct": t["pnl_pct"],
                    "leverage": self.cfg.LEVERAGE,
                    "order_id": t_order_id,
                })
                existing_ids.add(t_order_id)
                new_count += 1
                
            if new_count > 0:
                logger.info(f"로컬 CSV에 {new_count}개의 새로운 거래 내역을 추가 동기화했습니다.")
        except Exception as e:
            logger.error(f"거래 내역 CSV 동기화 실패: {e}")
