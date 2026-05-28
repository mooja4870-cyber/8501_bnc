import asyncio
import json
import logging
import time
from typing import Dict, Optional
import websockets

logger = logging.getLogger(__name__)

class BinanceWebsocketClient:
    """
    바이낸스 Futures 실시간 WebSocket 클라이언트
    - 전종목 실시간 Ticker (!ticker@arr) 구독으로 API Rate Limit 절감 및 지연 시간 최소화
    - 연결 유실 시 자동 재연결 및 상태 체크 지원
    """
    _instance = None
    _lock = asyncio.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.tickers: Dict[str, Dict] = {}
        self.is_connected = False
        self.last_update_time = 0.0
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._connect_loop())
        logger.info("[WS] 웹소켓 클라이언트 시작")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.is_connected = False
        logger.info("[WS] 웹소켓 클라이언트 중지")

    async def _connect_loop(self):
        uri = "wss://fstream.binance.com/ws"
        while self._running:
            try:
                async with websockets.connect(
                    uri, 
                    ping_interval=20, 
                    ping_timeout=10,
                    max_size=2**22 # 대량 데이터 수신 대응 버퍼 확장
                ) as ws:
                    self.is_connected = True
                    logger.info("[WS] 바이낸스 선물 웹소켓 연결 성공")
                    
                    # 전종목 티커 (!ticker@arr) 실시간 스트림 구독
                    sub_msg = {
                        "method": "SUBSCRIBE",
                        "params": ["!ticker@arr"],
                        "id": 1
                    }
                    await ws.send(json.dumps(sub_msg))
                    
                    while self._running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if isinstance(data, list):
                            now_time = time.time()
                            for item in data:
                                symbol_raw = item.get("s", "")
                                if not symbol_raw.endswith("USDT"):
                                    continue
                                
                                # CCXT 심볼 표준 포맷으로 정규화 (예: BTCUSDT -> BTC/USDT:USDT)
                                base = symbol_raw[:-4]
                                symbol = f"{base}/USDT:USDT"
                                
                                last_price = float(item.get("c", 0))
                                quote_volume = float(item.get("q", 0))
                                change_pct = float(item.get("P", 0))
                                bid = float(item.get("b", 0))
                                ask = float(item.get("a", 0))
                                
                                self.tickers[symbol] = {
                                    "symbol": symbol,
                                    "last": last_price,
                                    "bid": bid,
                                    "ask": ask,
                                    "volume": quote_volume,
                                    "change_pct": change_pct,
                                    "ws_timestamp": now_time
                                }
                            self.last_update_time = now_time
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.is_connected = False
                logger.error(f"[WS] 웹소켓 에러 또는 연결 끊김: {e}, 5초 후 재연결 시도")
                await asyncio.sleep(5.0)

    def get_tickers(self) -> Optional[Dict[str, Dict]]:
        """웹소켓이 정상 상태이고 캐시 데이터가 10초 미만으로 신선할 때만 티커 목록 반환"""
        if self.is_connected and self.tickers and (time.time() - self.last_update_time < 10.0):
            return self.tickers
        return None
