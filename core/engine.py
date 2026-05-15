"""
AI QUANTUM — Orchestration Engine
모든 모듈(Exchange, Scanner, Trader)을 통합 관리하고 조율하는 중앙 컨트롤러
"""
import logging
import threading
from typing import Optional, List, Dict

from core.exchange import OKXClient
from core.scanner import Scanner
from core.trader import AutoTrader
from core.config import CFG
import core.stats as stats_store

logger = logging.getLogger(__name__)

class QuantumEngine:
    """
    퀀텀 엔진 (Orchestrator)
    - UI(app.py)와 비즈니스 로직 사이의 완벽한 분리 제공
    - 모든 하위 모듈의 생명주기(Lifecycle) 관리
    """
    def __init__(self):
        self.client: Optional[OKXClient] = None
        self.scanner: Optional[Scanner] = None
        self.trader: Optional[AutoTrader] = None
        self.cfg = CFG
        self._lock = threading.Lock()
        self._initialized = False
        self._prev_position_symbols: set = set()  # 청산 감지용 스냅샷

    def initialize(self, api_key: str, secret_key: str, passphrase: str) -> tuple[bool, str]:
        """API 연결 및 모듈 초기화"""
        with self._lock:
            try:
                self.client = OKXClient(api_key, secret_key, passphrase)
                if self.client.load_markets():
                    self.scanner = Scanner(self.client)
                    self.trader = AutoTrader(self.client)
                    
                    # 스캐너와 트레이더 연결 (콜백)
                    self.scanner.on_signal = self.trader.on_signal
                    # 스캔 완료 시 청산 감지 콜백 등록
                    self.scanner.on_scan_complete = self._check_closed_positions
                    
                    self._initialized = True
                    return True, "✅ 엔진 초기화 및 마켓 로드 성공"
                return False, "❌ 마켓 정보 로드 실패"
            except Exception as e:
                logger.error(f"엔진 초기화 실패: {e}")
                return False, f"❌ 엔진 초기화 오류: {e}"

    @property
    def is_ready(self) -> bool:
        return self._initialized and self.client is not None

    # ── 모듈 제어 ──────────────────────────────────────

    def start_scanner(self):
        if self.scanner and not self.scanner.is_running:
            self.scanner.start()

    def stop_scanner(self):
        if self.scanner:
            self.scanner.stop()

    def enable_trading(self):
        if self.trader:
            self.trader.enable()

    def disable_trading(self):
        if self.trader:
            self.trader.disable()

    # ── 데이터 게이트웨이 (UI용) ────────────────────────

    def get_dashboard_data(self) -> Dict:
        """대시보드에 필요한 핵심 상태 통합 반환"""
        if not self.is_ready:
            return {}
            
        balance = self.client.get_balance()
        positions = self.client.get_positions()
        
        return {
            "total_balance": balance.get("total", 0),
            "free_margin": balance.get("free", 0),
            "used_margin": balance.get("used", 0),
            "realized_pnl": balance.get("pnl", 0),
            "positions": positions,
            "is_scanning": self.scanner.is_running if self.scanner else False,
            "is_trading": self.trader.enabled if self.trader else False,
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
        """스캔 완료 시마다 호출 — 청산된 포지션 감지 후 승/패 기록"""
        if not self.is_ready:
            return
        try:
            current = {p["symbol"] for p in self.client.get_positions()}
            closed = self._prev_position_symbols - current  # 사라진 심볼 = 청산됨

            if closed:
                closed_records = self.client.get_closed_positions_pnl(limit=10)
                for sym in closed:
                    matched = next(
                        (r for r in closed_records
                         if r["symbol"].replace("-SWAP", "/USDT:USDT") == sym
                         or r["symbol"] == sym.replace("/USDT:USDT", "-USDT-SWAP")),
                        None
                    )
                    pnl = matched["pnl_usdt"] if matched else 0.0
                    stats_store.record_result(pnl)
                    logger.info(
                        f"[CLOSED] {sym} PnL={pnl:+.4f} USDT"
                        f" -> {'WIN' if pnl >= 0 else 'LOSS'} 기록"
                    )

            self._prev_position_symbols = current
        except Exception as e:
            logger.error(f"청산 감지 오류: {e}")
