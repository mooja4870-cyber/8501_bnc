import asyncio
import logging
import pandas as pd
import ccxt.pro as ccxtpro
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class WebSocketClient:
    """
    CCXT Pro 기반 실시간 웹소켓 클라이언트
    실시간 캔들 데이터를 스트리밍 수신하여 Scanner의 캐시 메모리에 직접 주입합니다.
    """
    def __init__(self, scanner):
        self.scanner = scanner
        self.client = scanner.client
        self.cfg = scanner.cfg
        
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._ws_exchange: Optional[ccxtpro.Exchange] = None
        
    def start(self, symbols: List[str]):
        if self._running:
            return
            
        # MockClient 감지 시 웹소켓 구독 우회
        if not hasattr(self.client, "exchange"):
            logger.warning("[WS] MockClient 감지됨. 웹소켓 구독을 실행하지 않고 건너뜁니다.")
            return
            
        self._running = True
        
        # OKX 및 Binance 공용 CCXT Pro 거래소 생성
        exchange_class = getattr(ccxtpro, self.client.exchange.id)
        self._ws_exchange = exchange_class({
            "apiKey": self.client.exchange.apiKey,
            "secret": self.client.exchange.secret,
            "password": getattr(self.client.exchange, "password", ""),
            "options": self.client.exchange.options,
        })
        
        # 각 심볼별로 비동기 감시 태스크 할당
        for symbol in symbols:
            task = asyncio.create_task(self._watch_symbol_loop(symbol))
            self._tasks.append(task)
        logger.info(f"[WS] {len(symbols)}개 종목에 대한 실시간 캔들 웹소켓 구독을 성공적으로 구동했습니다.")
        
    async def stop(self):
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._ws_exchange:
            await self._ws_exchange.close()
        self._tasks.clear()
        logger.info("[WS] 실시간 웹소켓 클라이언트 감시 종료")
        
    async def _watch_symbol_loop(self, symbol: str):
        timeframe = self.cfg.TIMEFRAME
        while self._running:
            try:
                # CCXT Pro watch_ohlcv 비동기 대기
                ohlcv = await self._ws_exchange.watch_ohlcv(symbol, timeframe)
                if ohlcv:
                    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                    df = df.set_index("timestamp").sort_index()
                    df = df.astype(float)
                    
                    async with self.scanner._lock:
                        # 스캐너 내부 캐시 병합 업데이트
                        cached = self.scanner._ohlcv_cache.get(symbol)
                        if cached is not None and not cached.empty:
                            merged = pd.concat([cached, df])
                            merged = merged[~merged.index.duplicated(keep='last')]
                            merged = merged.sort_index().tail(300)
                            self.scanner._ohlcv_cache[symbol] = merged
                            self.scanner._ohlcv_cache_ts[symbol] = int(merged.index[-1].timestamp() * 1000)
                        else:
                            self.scanner._ohlcv_cache[symbol] = df
                            self.scanner._ohlcv_cache_ts[symbol] = int(df.index[-1].timestamp() * 1000)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[WS ERROR] {symbol} 웹소켓 지연/단절 발생 ({e}), 5초 후 재시도...")
                await asyncio.sleep(5)
