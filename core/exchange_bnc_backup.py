"""
Binance Exchange 연동 모듈 (비동기 엔터프라이즈 버전)
ccxt.async_support 라이브러리 기반 Binance USD-M Futures API 래퍼
"""
import ccxt.async_support as ccxt_async
import ccxt
import pandas as pd
import asyncio
import logging
from typing import Optional, Dict, List, Tuple
from core.config import CFG

logger = logging.getLogger(__name__)

class BinanceClient:
    """Binance USD-M Futures API 클라이언트 (비동기)"""

    def __init__(self, api_key: str, secret_key: str, passphrase: Optional[str] = None):
        self.exchange = ccxt_async.binanceusdm({
            "apiKey": api_key,
            "secret": secret_key,
            "options": {
                "adjustForTimeDifference": True,
                "recvWindow": 60000,
            },
            "enableRateLimit": True,
            "rateLimit": 200,
        })
        self._markets: Dict = {}
        self._symbol_map: Dict[str, str] = {}
        self._close_locks: Dict[str, asyncio.Lock] = {}

    async def close(self):
        """비동기 세션 종료"""
        if self.exchange:
            await self.exchange.close()

    async def _execute_with_retry(self, func, *args, max_retries=3, initial_delay=1.0, **kwargs):
        """지수 백오프 기반 비동기 재시도 (서킷 브레이커 대체용 기본 뼈대)"""
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                import inspect
                result = func(*args, **kwargs)
                if inspect.iscoroutine(result):
                    return await result
                return result
            except (ccxt.RateLimitExceeded, ccxt.DDoSProtection) as e:
                logger.warning(f"[API RateLimit] {func.__name__} API 제한 감지. {attempt + 1}/{max_retries}. {delay}초 대기... 오류: {e}")
                await asyncio.sleep(delay)
                delay *= 2.0
            except (ccxt.NetworkError, ccxt.RequestTimeout) as e:
                logger.warning(f"[API NetworkError] {func.__name__} 네트워크 오류 감지. {attempt + 1}/{max_retries}. {delay}초 대기... 오류: {e}")
                await asyncio.sleep(delay)
                delay *= 1.5
            except ccxt.ExchangeError as e:
                err_msg = str(e)
                if "-1021" in err_msg or "Timestamp for this request" in err_msg:
                    logger.warning(f"[Time Sync Error] {func.__name__} 시간 비동기화 감지 (-1021). {attempt + 1}/{max_retries}. 1초 대기...")
                    try:
                        await self.exchange.load_time_difference()
                    except Exception as te:
                        logger.error(f"시간 차이 재계산 실패: {te}")
                    await asyncio.sleep(1.0)
                    continue
                raise e
        result = func(*args, **kwargs)
        import inspect
        if inspect.iscoroutine(result):
            return await result
        return result

    async def load_markets(self) -> bool:
        try:
            self._markets = await self._execute_with_retry(self.exchange.load_markets)
            self._symbol_map = {}
            for official_sym in self._markets.keys():
                self._symbol_map[official_sym.upper()] = official_sym
                if ":" in official_sym:
                    self._symbol_map[official_sym.split(":")[0].upper()] = official_sym
                no_slash = official_sym.replace("/", "")
                if ":" in no_slash:
                    no_slash_no_colon = no_slash.split(":")[0]
                    self._symbol_map[no_slash_no_colon.upper()] = official_sym
                else:
                    self._symbol_map[no_slash.upper()] = official_sym
            logger.info(f"마켓 로드 완료: {len(self._markets)}개 종목")
            return True
        except Exception as e:
            logger.error(f"마켓 로드 실패: {e}")
            return False

    async def get_balance(self) -> Dict:
        try:
            bal = await self._execute_with_retry(self.exchange.fetch_balance)
            usdt = bal.get("USDT", {})
            return {
                "total": round(usdt.get("total", 0) or 0, 4),
                "free": round(usdt.get("free", 0) or 0, 4),
                "used": round(usdt.get("used", 0) or 0, 4),
                "pnl": round(usdt.get("info", {}).get("crossUnPnl", 0) or 0, 4)
            }
        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
            raise e

    async def get_positions(self) -> List[Dict]:
        try:
            positions = await self._execute_with_retry(self.exchange.fetch_positions)
            active = []
            for p in positions:
                contracts = abs(float(p.get("contracts") or p.get("amount") or p.get("size") or 0))
                if contracts > 0:
                    entry = p.get("entryPrice") or 0
                    current = p.get("markPrice") or p.get("lastPrice") or 0
                    side = p.get("side")
                    if not side:
                        raw_amt = p.get("contracts") or p.get("amount") or 0
                        side = "long" if float(raw_amt) > 0 else "short"
                    
                    lev = float(p.get("leverage") or CFG.LEVERAGE)
                    if entry and current:
                        raw = (float(current) - float(entry)) / float(entry)
                        pct = raw * lev if side == "long" else -raw * lev
                    else:
                        pct = 0.0
                    market = self._markets.get(p.get("symbol", ""), {})
                    contract_size = market.get("contractSize", 1.0) or 1.0
                    coins = float(contracts) * contract_size
                    entry_val = float(entry) * coins
                    
                    active.append({
                        "symbol": p.get("symbol", ""),
                        "side": side,
                        "size": float(contracts),
                        "coins": coins,
                        "entry_price": float(entry),
                        "mark_price": float(current),
                        "pnl_pct": round(pct * 100, 2),
                        "pnl_usdt": round(float(p.get("unrealizedPnl", 0) or 0), 4),
                        "leverage": p.get("leverage") or CFG.LEVERAGE,
                        "margin": round(float(p.get("initialMargin", 0) or 0), 4),
                        "timestamp": p.get("timestamp"),
                        "amount_usdt": round(entry_val, 2),
                    })
            return active
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            raise e

    async def get_open_orders(self) -> List[Dict]:
        try:
            orders = await self._execute_with_retry(self.exchange.fetch_open_orders)
            return [
                {
                    "id": o["id"],
                    "symbol": o["symbol"],
                    "side": o["side"],
                    "type": o["type"],
                    "price": o.get("price"),
                    "amount": o.get("amount"),
                    "status": o.get("status"),
                    "timestamp": o.get("timestamp"),
                }
                for o in orders
            ]
        except Exception as e:
            logger.error(f"미체결 주문 조회 실패: {e}")
            return []

    async def get_trade_history(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict]:
        if symbol is None:
            return []
        try:
            trades = await self._execute_with_retry(self.exchange.fetch_my_trades, symbol=symbol, limit=limit)
            result = []
            for t in trades:
                info = t.get("info", {})
                side = t.get("side", "").lower()
                pnl = float(info.get("realizedPnl", info.get("realizedProfit", 0)) or 0)
                reduce_only_raw = info.get("reduceOnly", False)
                reduce_only = str(reduce_only_raw).lower() == "true" if isinstance(reduce_only_raw, str) else bool(reduce_only_raw)
                category = "청산" if reduce_only or pnl != 0 else "진입"
                cost = float(t.get("cost", 0) or 0)
                pnl_pct = 0.0
                if category == "청산" and pnl != 0 and cost > 0:
                    margin_est = cost / CFG.LEVERAGE
                    if margin_est > 0:
                        pnl_pct = (pnl / margin_est) * 100
                result.append({
                    "id": t.get("id"),
                    "timestamp": pd.to_datetime(t["timestamp"], unit="ms") + pd.Timedelta(hours=9),
                    "symbol": t["symbol"],
                    "category": category,
                    "side": side,
                    "price": round(t.get("price", 0), 6),
                    "amount": t.get("amount", 0),
                    "cost": round(cost, 4),
                    "pnl": round(pnl, 4),
                    "pnl_pct": round(pnl_pct, 2),
                    "fee": round((t.get("fee") or {}).get("cost", 0), 6),
                    "order_id": t.get("order"),
                    "trade_id": t.get("id"),
                    "reduce_only": reduce_only,
                    "position_side": info.get("positionSide", ""),
                })
            return result
        except Exception as e:
            logger.error(f"거래 이력 조회 실패: {e}")
            return []

    async def get_closed_positions_pnl(self, limit=20) -> List[Dict]:
        try:
            raw = await self._execute_with_retry(
                self.exchange.fapiPrivateGetIncome,
                {
                    'incomeType': 'REALIZED_PNL',
                    'limit': limit
                }
            )
            return [
                {
                    'symbol': self.exchange.safe_symbol(r.get('symbol', '')), 
                    'pnl_usdt': float(r.get('income', 0) or 0)
                }
                for r in raw if r.get('incomeType') == 'REALIZED_PNL'
            ]
        except Exception as e:
            logger.error(f'closed pnl error: {e}')
            return []

    async def get_ohlcv(self, symbol: str, timeframe: Optional[str] = None, limit: int = 300) -> pd.DataFrame:
        if timeframe is None:
            timeframe = CFG.TIMEFRAME
        try:
            if limit <= 300:
                raw = await self._execute_with_retry(self.exchange.fetch_ohlcv, symbol, timeframe=timeframe, limit=limit)
            else:
                tf_ms = self.exchange.parse_timeframe(timeframe) * 1000
                since = self.exchange.milliseconds() - (limit * tf_ms)
                raw = []
                while len(raw) < limit:
                    fetch_limit = min(300, limit - len(raw))
                    chunk = await self._execute_with_retry(self.exchange.fetch_ohlcv, symbol, timeframe=timeframe, since=since, limit=fetch_limit)
                    if not chunk:
                        break
                    raw.extend(chunk)
                    since = chunk[-1][0] + tf_ms
                    await asyncio.sleep(0.1)
            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("timestamp").sort_index()
            return df.astype(float)
        except Exception as e:
            logger.error(f"OHLCV 조회 실패 ({symbol}): {e}")
            return pd.DataFrame()

    async def get_tickers(self) -> Dict[str, Dict]:
        try:
            raw_tickers = await self._execute_with_retry(self.exchange.fetch_tickers)
            tickers = {}
            for sym, t in raw_tickers.items():
                last_price = t.get("last", 0) or 0
                usdt_vol = t.get("quoteVolume")
                if not usdt_vol:
                    base_vol = t.get("baseVolume", 0) or 0
                    usdt_vol = base_vol * last_price if base_vol and last_price else 0
                
                official_sym = self._symbol_map.get(sym.upper(), sym)
                tickers[official_sym] = {
                    "symbol": official_sym,
                    "last": last_price,
                    "bid": t.get("bid", 0) or 0,
                    "ask": t.get("ask", 0) or 0,
                    "volume": usdt_vol,
                    "change_pct": round(t.get("percentage", 0) or 0, 2),
                }
            return tickers
        except Exception as e:
            logger.error(f"Tickers 일괄 조회 실패: {e}")
            return {}

    async def get_ticker(self, symbol: str) -> Dict:
        try:
            t = await self._execute_with_retry(self.exchange.fetch_ticker, symbol)
            last_price = t.get("last", 0)
            usdt_vol = t.get("quoteVolume")
            if not usdt_vol:
                base_vol = t.get("baseVolume", 0)
                usdt_vol = base_vol * last_price if base_vol and last_price else 0

            return {
                "symbol": symbol,
                "last": last_price,
                "bid": t.get("bid", 0),
                "ask": t.get("ask", 0),
                "volume": usdt_vol,
                "change_pct": round(t.get("percentage", 0) or 0, 2),
            }
        except Exception as e:
            logger.error(f"Ticker 조회 실패 ({symbol}): {e}")
            return {}

    def get_all_usdt_swap_symbols(self) -> List[str]:
        symbols = []
        for sym, mkt in self._markets.items():
            if mkt.get("quote") == "USDT" and mkt.get("type") == "swap" and mkt.get("active", False):
                symbols.append(sym)
        return sorted(symbols)

    async def set_margin_mode(self, symbol: str, margin_mode: str = "isolated") -> bool:
        try:
            await self._execute_with_retry(self.exchange.set_margin_mode, margin_mode.upper(), symbol)
            logger.info(f"마진 모드 설정 완료: {symbol} {margin_mode}")
            return True
        except Exception as e:
            logger.debug(f"마진 모드 설정 무시/실패 ({symbol}): {e}")
            return False

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        try:
            await self._execute_with_retry(self.exchange.set_leverage, leverage, symbol)
            logger.info(f"레버리지 설정 완료: {symbol} {leverage}x")
            return True
        except Exception as e:
            logger.error(f"레버리지 설정 실패 ({symbol}): {e}")
            return False

    def get_market_max_leverage(self, symbol: str) -> int:
        try:
            market = self._markets.get(symbol, {})
            limits = market.get("limits", {})
            leverage = limits.get("leverage", {})
            max_lvl = leverage.get("max")
            if max_lvl is not None:
                return int(max_lvl)
            if "BTC" in symbol or "ETH" in symbol:
                return 100
            return 20
        except Exception:
            return 20

    async def cancel_all_orders(self, symbol: str) -> bool:
        try:
            await self._execute_with_retry(self.exchange.cancel_all_orders, symbol)
            logger.info(f"모든 주문 취소 완료: {symbol}")
            return True
        except Exception as e:
            logger.error(f"주문 취소 실패 ({symbol}): {e}")
            return False

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            await self._execute_with_retry(self.exchange.cancel_order, id=order_id, symbol=symbol)
            logger.info(f"주문 개별 취소 완료: {symbol} (ID: {order_id})")
            return True
        except Exception as e:
            logger.error(f"주문 개별 취소 실패 ({symbol} ID: {order_id}): {e}")
            return False

    async def place_order(self, symbol: str, side: str, margin_usdt: float, stop_loss_pct: float = CFG.STOP_LOSS_PCT, take_profit_pct: float = CFG.TAKE_PROFIT_PCT) -> Optional[Dict]:
        try:
            policy_max = self.get_market_max_leverage(symbol)
            applied_leverage = min(CFG.LEVERAGE, policy_max)
            await self.set_margin_mode(symbol, CFG.MARGIN_MODE)
            lev_ok = await self.set_leverage(symbol, applied_leverage)
            if not lev_ok:
                return None

            ticker = await self.get_ticker(symbol)
            price = ticker.get("last", 0)
            if not price:
                raise ValueError("현재가 조회 실패")

            market = self._markets.get(symbol, {})
            contract_size = market.get("contractSize", 1.0) or 1.0
            notional = margin_usdt * applied_leverage
            amount = notional / (price * contract_size)
            amount = self.exchange.amount_to_precision(symbol, amount)

            if CFG.USE_LIMIT_ORDER:
                # 적극적 지정가 (Aggressive Limit Order Offset):
                # 롱 진입(Buy) 시 매도 호가(ask)보다 N틱 높은 가격에 매수 지정가 설정
                # 숏 진입(Sell) 시 매수 호가(bid)보다 N틱 낮은 가격에 매도 지정가 설정
                tick_size = 0.00001
                if market:
                    precision_price = market.get("precision", {}).get("price")
                    if isinstance(precision_price, float):
                        tick_size = precision_price
                    elif isinstance(precision_price, int):
                        tick_size = 10 ** -precision_price
                    else:
                        tick_size = market.get("limits", {}).get("price", {}).get("min") or 0.00001
                
                offset_value = tick_size * CFG.LIMIT_TICK_OFFSET
                if side == "buy":
                    base_price = ticker.get("ask") or ticker.get("last") or price
                    order_price = base_price + offset_value
                else:
                    base_price = ticker.get("bid") or ticker.get("last") or price
                    order_price = base_price - offset_value

                order_price = float(self.exchange.price_to_precision(symbol, order_price))
                order = await self._execute_with_retry(
                    self.exchange.create_order,
                    symbol=symbol,
                    type="limit",
                    side=side,
                    amount=float(amount),
                    price=order_price
                )
            else:
                order = await self._execute_with_retry(
                    self.exchange.create_order,
                    symbol=symbol,
                    type="market",
                    side=side,
                    amount=float(amount)
                )
            # [필수 수정 3] 부분 체결 대응 주문 상태 동기화 및 잔여 주문 즉시 취소
            # 1초간 대기하며 거래소 체결 상태 갱신 시도 (최대 2회)
            for _ in range(2):
                if order.get("status") in ("closed", "canceled") or (order.get("filled") is not None and float(order.get("filled", 0)) > 0):
                    break
                await asyncio.sleep(0.5)
                try:
                    order = await self._execute_with_retry(self.exchange.fetch_order, id=order.get("id"), symbol=symbol)
                except Exception as fe:
                    logger.warning(f"진입 주문 상태 재조회 실패: {fe}")

            filled_amount = float(order.get("filled", 0)) if order.get("filled") is not None else 0.0
            order_status = order.get("status", "open")
            
            # 부분 체결 발생 시 잔여 주문 취소 및 체결 수량 확정
            if order_status == "open":
                if filled_amount > 0:
                    logger.info(f"[PARTIAL FILL] {symbol} 주문 {order.get('id')} 부분 체결 감지 ({filled_amount} / {amount}). 잔여 미체결분 즉시 취소.")
                    try:
                        await self._execute_with_retry(self.exchange.cancel_order, id=order.get("id"), symbol=symbol)
                    except Exception as ce:
                        logger.warning(f"부분 체결 후 잔여 주문 취소 실패: {ce}")
                else:
                    # 완전히 미체결 상태라면 보호 주문의 안전을 위해 원래 요청 수량(amount)을 사용 (이후 3분 대기 후 취소됨)
                    filled_amount = float(amount)
            elif filled_amount <= 0:
                # 주문 완료 혹은 취소 상태이나 filled 수량이 0인 경우 폴백
                filled_amount = float(amount)
                
            entry_price = float(order.get("average") or order.get("price") or price)
            sl_amount = filled_amount

            if side == "buy":
                sl_price = entry_price * (1 - stop_loss_pct)
                tp_price = entry_price * (1 + take_profit_pct)
                close_side = "sell"
                pos_side = "long"
            else:
                sl_price = entry_price * (1 + stop_loss_pct)
                tp_price = entry_price * (1 - take_profit_pct)
                close_side = "buy"
                pos_side = "short"

            sl_price = float(self.exchange.price_to_precision(symbol, sl_price))
            tp_price = float(self.exchange.price_to_precision(symbol, tp_price))

            # [v2.5.1] SL/TP OCO 주문 생성 실패 시 최대 3회 재시도 및 최종 실패 시 Emergency Rollback (긴급 청산)
            sl_ok = False
            for attempt in range(1, 4):
                try:
                    await self._execute_with_retry(self.exchange.create_order, symbol=symbol, type="STOP_MARKET", side=close_side, amount=float(sl_amount), params={"stopPrice": sl_price, "reduceOnly": True})
                    sl_ok = True
                    break
                except Exception as sle:
                    logger.warning(f"Stop Loss 설정 시도 {attempt}회 실패 ({symbol}): {sle}")
                    if attempt < 3:
                        await asyncio.sleep(0.5)

            tp_ok = False
            if sl_ok:
                for attempt in range(1, 4):
                    try:
                        if CFG.TRAILING_ACTIVATE_PCT > 0 and CFG.TRAILING_CALLBACK_PCT > 0:
                            # [필수 수정 2] Binance 네이티브 트레일링 스탑 적용
                            callback_rate = float(CFG.TRAILING_CALLBACK_PCT * 100) # 백분율 환산 (0.43% -> 0.43)
                            callback_rate = min(max(callback_rate, 0.1), 5.0) # 바이낸스 허용치 클램핑 (0.1% ~ 5.0%)
                            
                            params = {
                                "activationPrice": tp_price,
                                "callbackRate": callback_rate,
                                "reduceOnly": True
                            }
                            await self._execute_with_retry(
                                self.exchange.create_order,
                                symbol=symbol,
                                type="TRAILING_STOP_MARKET",
                                side=close_side,
                                amount=float(sl_amount),
                                params=params
                            )
                            logger.info(f"[TRAILING STOP ORDER] {symbol} 트레일링 스탑 설정 완료 (발동가: {tp_price}, 콜백: {callback_rate}%)")
                        else:
                            # 기존 고정 익절 주문
                            await self._execute_with_retry(self.exchange.create_order, symbol=symbol, type="TAKE_PROFIT_MARKET", side=close_side, amount=float(sl_amount), params={"stopPrice": tp_price, "reduceOnly": True})
                        tp_ok = True
                        break
                    except Exception as tpe:
                        logger.warning(f"Take Profit/Trailing Stop 설정 시도 {attempt}회 실패 ({symbol}): {tpe}")
                        if attempt < 3:
                            await asyncio.sleep(0.5)

            if not sl_ok or not tp_ok:
                logger.critical(f"[EMERGENCY] {symbol} 진입 주문은 체결되었으나 SL/TP 설정에 실패하여 긴급 청산(Rollback)을 시작합니다. (SL: {sl_ok}, TP: {tp_ok})")
                try:
                    # OCO 주문 중 하나만 성공했을 수 있으므로 전부 정리
                    await self.cancel_all_orders(symbol)
                    # 현재 진입한 포지션을 시장가로 즉시 청산
                    await self._execute_with_retry(self.exchange.create_order, symbol=symbol, type="market", side=close_side, amount=float(sl_amount), params={"reduceOnly": True})
                    logger.critical(f"[EMERGENCY] {symbol} 긴급 청산(Rollback) 성공 완료")
                except Exception as rollback_err:
                    logger.critical(f"[EMERGENCY FAIL] {symbol} 긴급 청산(Rollback) 마저 실패!!! 즉각적인 수동 개입 필요: {rollback_err}")
                return None

            result = {
                "order_id": order.get("id"),
                "symbol": symbol,
                "side": pos_side,
                "entry_price": entry_price,
                "amount": float(sl_amount),
                "sl_price": sl_price,
                "tp_price": tp_price,
                "usdt_margin": margin_usdt,
            }
            return result
        except Exception as e:
            logger.error(f"주문 실패 ({symbol} {side}): {e}")
            return None

    async def close_position(self, symbol: str, side: str) -> bool:
        if symbol not in self._close_locks:
            self._close_locks[symbol] = asyncio.Lock()

        async with self._close_locks[symbol]:
            logger.info(f"[CLOSE START] {symbol} 포지션 청산 프로세스 시작 (방향: {side})")
            for attempt in range(1, 4):
                try:
                    # 1. 청산 전 기존 TP/SL 등 미체결 주문 우선 정리
                    await self.cancel_all_orders(symbol)
                    
                    # 2. 실시간 포지션 수량 재조회
                    positions = await self.get_positions()
                    target = next((p for p in positions if p["symbol"] == symbol), None)
                    if not target:
                        logger.info(f"[CLOSE] {symbol} 포지션이 이미 존재하지 않습니다.")
                        # 한 번 더 주문 정리 (안전장치)
                        await self.cancel_all_orders(symbol)
                        return True

                    # [v2.6.1] UI 및 호출 인자로 전달된 side에 상관없이 거래소 포지션 실제 방향을 기준으로 close_side 결정
                    actual_side = target["side"].lower()
                    close_side = "sell" if actual_side == "long" else "buy"
                    
                    # [v2.6.1] 파이썬 실수 표현 오차(0.07 -> 0.069999999999)로 인한 수량 절사 오류 방지차 8자리 반올림 적용
                    raw_size = round(target["size"], 8)
                    amount = float(self.exchange.amount_to_precision(symbol, raw_size))
                    if amount <= 0:
                        logger.info(f"[CLOSE] {symbol} 정밀도 변환 후 청산할 수량이 0 이하입니다.")
                        await self.cancel_all_orders(symbol)
                        return True

                    # 3. 시장가 청산 주문 요청
                    logger.info(f"[CLOSE ORDER] {symbol} 시장가 주문 전송: {close_side} {amount} (시도 {attempt}회)")
                    await self._execute_with_retry(
                        self.exchange.create_order,
                        symbol=symbol,
                        type="market",
                        side=close_side,
                        amount=amount,
                        params={"reduceOnly": True}
                    )

                    # 4. 검증 루프: 포지션 수량이 0이 되는지 실시간 확인 (최대 5초간 폴링)
                    verified = False
                    for poll in range(10):
                        await asyncio.sleep(0.5)
                        try:
                            positions_check = await self.get_positions()
                            target_check = next((p for p in positions_check if p["symbol"] == symbol), None)
                            
                            # 포지션이 없거나 수량이 거의 0인 경우 검증 완료
                            if not target_check or abs(target_check["size"]) <= 1e-8:
                                verified = True
                                logger.info(f"[CLOSE VERIFIED] {symbol} 포지션 청산 최종 완료 확인 ({poll * 0.5 + 0.5}초 소요)")
                                break
                            else:
                                logger.warning(f"[CLOSE POLL] {symbol} 청산 대기 중... 잔량 존재: {target_check['size']}")
                        except Exception as pe:
                            logger.warning(f"[CLOSE POLL ERROR] 포지션 상태 확인 중 오류 발생 (폴링 #{poll}): {pe}")

                    if verified:
                        # 5. 청산 후 남은 TP/SL 등 Orphan Order 최종 정리
                        await self.cancel_all_orders(symbol)
                        logger.info(f"[CLOSE SUCCESS] {symbol} 포지션 청산 및 익손절 주문 정리 성공")
                        return True
                    else:
                        logger.warning(f"[CLOSE TIMEOUT] {symbol} 주문 전송 후 수량 0 검증 실패 (시도 {attempt}회). 재시도합니다.")
                except Exception as e:
                    logger.warning(f"청산 시도 {attempt}회 실패 ({symbol}): {e}")
                    if attempt < 3:
                        await asyncio.sleep(1.0)
            
            logger.critical(f"[EMERGENCY FAIL] {symbol} 포지션 청산 최종 실패!!! 즉각적인 수동 개입 필요")
            return False

    async def close_all_positions(self) -> int:
        try:
            positions = await self.get_positions()
        except Exception as e:
            logger.error(f"일괄 청산 중 포지션 조회 실패: {e}")
            return 0
            
        if not positions:
            return 0
            
        # [v2.6.1] Streamlit UI 지연 및 타임아웃 방지를 위해 병렬 청산 실행 (asyncio.gather)
        tasks = [self.close_position(p["symbol"], p["side"]) for p in positions]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = 0
        for p, r in zip(positions, results):
            if isinstance(r, Exception):
                logger.error(f"일괄 청산 중 {p['symbol']} 청산 예외 발생: {r}")
            elif r is True:
                success_count += 1
                
        return success_count

