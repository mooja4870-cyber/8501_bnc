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
    퀀텀 엔진 (Orchestrator) - Singleton
    - UI(app.py)와 비즈니스 로직 사이의 완벽한 분리 제공
    - 모든 하위 모듈의 생명주기(Lifecycle) 관리
    - 전역적으로 단 하나의 인스턴스만 생성 (이중 실행 방지)
    """
    _instance = None
    _singleton_lock = threading.Lock()

    def __new__(cls):
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super(QuantumEngine, cls).__new__(cls)
                cls._instance._initialized_inner = False
            return cls._instance

    def __init__(self):
        # __init__은 매번 호출될 수 있으므로 내부 플래그로 초기화 방지
        if getattr(self, "_initialized_inner", False):
            return
            
        self.client: Optional[OKXClient] = None
        self.scanner: Optional[Scanner] = None
        self.trader: Optional[AutoTrader] = None
        self.cfg = CFG
        self._lock = threading.Lock()
        self._initialized = False
        self._prev_position_symbols: set = set()  # 청산 감지용 스냅샷
        self._prev_initialized: bool = False       # 첫 스캔 시 초기화 여부
        self._recorded_closes: set = set()          # 이미 기록한 청산 ID (중복 방지)
        self._initialized_inner = True

    def initialize(self, api_key: str, secret_key: str, passphrase: str) -> tuple[bool, str]:
        """API 연결 및 모듈 초기화 (기본 스레드 정리 포함)"""
        with self._lock:
            try:
                # 기존 엔진 구성 요소 정리 (중복 스레드 방지)
                if self.scanner:
                    self.scanner.stop()
                if self.trader:
                    self.trader.disable()
                
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
            
    def reboot(self) -> tuple[bool, str]:
        """현재 설정된 API 키로 엔진을 완전히 재시작합니다. (v2.23)"""
        if not self.client:
            return False, "❌ 초기화된 클라이언트가 없습니다."
        
        # 기존 자격 증명 사용
        api_key = self.client.exchange.apiKey
        secret_key = self.client.exchange.secret
        passphrase = self.client.exchange.password
        
        return self.initialize(api_key, secret_key, passphrase)

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
            "used_margin": balance.get("used", 0),
            "free_margin": balance.get("free", 0),
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

            # 첫 스캔: 현재 포지션을 스냅샷으로 저장만 하고 비교하지 않음
            # (앱 시작 시 빈 세트와 비교하면 "모든 포지션이 청산됨"으로 오판)
            if not self._prev_initialized:
                self._prev_position_symbols = current
                self._prev_initialized = True
                logger.info(f"[ENGINE] 포지션 스냅샷 초기화: {current}")
                return

            closed = self._prev_position_symbols - current  # 사라진 심볼 = 청산됨

            if closed:
                closed_records = self.client.get_closed_positions_pnl(limit=40)
                for sym in closed:
                    matched = next(
                        (r for r in closed_records
                         if r["symbol"].replace("-SWAP", "/USDT:USDT") == sym
                         or r["symbol"] == sym.replace("/USDT:USDT", "-USDT-SWAP")),
                        None
                    )
                    if not matched:
                        continue

                    # 중복 방지: 고유 키(심볼 + 청산시간)로 이미 기록했는지 확인
                    close_key = f"{sym}_{matched.get('close_time', '')}"
                    if close_key in self._recorded_closes:
                        logger.info(f"[SKIP] 이미 기록된 청산: {close_key}")
                        continue

                    pnl = matched["pnl_usdt"]
                    stats_store.record_result(pnl)
                    self._recorded_closes.add(close_key)
                    logger.info(
                        f"[CLOSED] {sym} PnL={pnl:+.4f} USDT"
                        f" -> {'WIN' if pnl >= 0 else 'LOSS'} 기록"
                    )

            self._prev_position_symbols = current
            
            # [v1.1.57] 실시간 설정 동기화 실행
            if self.trader:
                self.trader.sync_sl_tp()
        except Exception as e:
            logger.error(f"청산 감지 오류: {e}")
