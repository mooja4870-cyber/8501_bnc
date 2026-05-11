"""
OKX Exchange 연동 모듈
ccxt 라이브러리 기반 OKX API v5 래퍼
"""
import ccxt
import pandas as pd
import time
import logging
from typing import Optional, Dict, List, Tuple
from core.config import CFG

logger = logging.getLogger(__name__)


class OKXClient:
    """OKX API v5 클라이언트 — 실거래 전용"""

    def __init__(self, api_key: str, secret_key: str, passphrase: str):
        self.exchange = ccxt.okx({
            "apiKey": api_key,
            "secret": secret_key,
            "password": passphrase,        # OKX는 passphrase 필수
            "options": {
                "defaultType": "swap",     # 선물(영구 계약)
                "adjustForTimeDifference": True,
            },
            "enableRateLimit": True,       # Rate-limit 자동 준수
            "rateLimit": 200,              # ms 단위
        })
        self._markets: Dict = {}

    # ── 초기화 ─────────────────────────────────────────

    def load_markets(self) -> bool:
        """마켓 정보 로드 (앱 시작 시 1회 호출)"""
        try:
            self._markets = self.exchange.load_markets()
            logger.info(f"마켓 로드 완료: {len(self._markets)}개 종목")
            return True
        except Exception as e:
            logger.error(f"마켓 로드 실패: {e}")
            return False

    # ── 계좌 조회 ──────────────────────────────────────

    def get_balance(self) -> Dict:
        """계좌 잔고 조회 (USDT 기준)"""
        try:
            bal = self.exchange.fetch_balance({"type": "swap"})
            usdt = bal.get("USDT", {})
            return {
                "total": round(usdt.get("total", 0), 4),
                "free": round(usdt.get("free", 0), 4),
                "used": round(usdt.get("used", 0), 4),
            }
        except Exception as e:
            logger.error(f"잔고 조회 실패: {e}")
            return {"total": 0, "free": 0, "used": 0}

    def get_positions(self) -> List[Dict]:
        """현재 보유 포지션 목록 조회"""
        try:
            positions = self.exchange.fetch_positions()
            active = []
            for p in positions:
                contracts = p.get("contracts", 0) or 0
                if float(contracts) > 0:
                    entry = p.get("entryPrice") or 0
                    current = p.get("markPrice") or p.get("lastPrice") or 0
                    side = p.get("side", "long")
                    pct = 0.0
                    if entry and current:
                        raw = (float(current) - float(entry)) / float(entry)
                        pct = raw * CFG.LEVERAGE if side == "long" else -raw * CFG.LEVERAGE
                    active.append({
                        "symbol": p.get("symbol", ""),
                        "side": side,
                        "size": float(contracts),
                        "entry_price": float(entry),
                        "mark_price": float(current),
                        "pnl_pct": round(pct * 100, 2),
                        "pnl_usdt": round(p.get("unrealizedPnl", 0) or 0, 4),
                        "leverage": p.get("leverage", CFG.LEVERAGE),
                        "margin": round(p.get("initialMargin", 0) or 0, 4),
                    })
            return active
        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []

    def get_open_orders(self) -> List[Dict]:
        """미체결 주문 조회"""
        try:
            orders = self.exchange.fetch_open_orders()
            return [
                {
                    "id": o["id"],
                    "symbol": o["symbol"],
                    "side": o["side"],
                    "type": o["type"],
                    "price": o.get("price"),
                    "amount": o.get("amount"),
                    "status": o.get("status"),
                }
                for o in orders
            ]
        except Exception as e:
            logger.error(f"미체결 주문 조회 실패: {e}")
            return []

    def get_trade_history(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """체결 이력 조회 (진입/청산 구분 및 레버리지 포함)"""
        try:
            trades = self.exchange.fetch_my_trades(symbol=symbol, limit=limit)
            result = []
            for t in trades:
                raw = t.get("info", {})
                side = t.get("side")      # buy / sell
                pos_side = raw.get("posSide")  # long / short
                
                # 진입/청산 구분 로직
                trade_type = "—"
                pnl_usdt = 0.0
                pnl_pct = 0.0
                
                if pos_side == "long":
                    trade_type = "진입" if side == "buy" else "청산"
                elif pos_side == "short":
                    trade_type = "진입" if side == "sell" else "청산"
                
                # 청산 시 손익 데이터 추출 (OKX v5: fillPnl)
                if trade_type == "청산":
                    pnl_usdt = float(raw.get("fillPnl", 0))
                    # 수익률 추정 (비용 대비 손익 * 레버리지 개념)
                    # 실제 정확한 수익률은 (청산가-진입가)/진입가 * 레버리지이나, 
                    # 단일 fill 데이터에서는 fillPnl을 금액(cost)으로 나누어 추산 가능
                    cost = float(t.get("cost", 0))
                    if cost > 0:
                        lever = float(raw.get("lever", CFG.LEVERAGE))
                        pnl_pct = (pnl_usdt / cost) * 100 * lever

                result.append({
                    "timestamp": pd.to_datetime(t["timestamp"], unit="ms") + pd.Timedelta(hours=9),
                    "symbol": t["symbol"],
                    "type": trade_type,
                    "side": side,
                    "price": round(t.get("price", 0), 6),
                    "amount": t.get("amount", 0),
                    "cost": round(float(t.get("cost", 0)), 2),
                    "leverage": f"{raw.get('lever', CFG.LEVERAGE)}x",
                    "pnl_usdt": round(pnl_usdt, 4),
                    "pnl_pct": round(pnl_pct, 2),
                    "fee": round((t.get("fee") or {}).get("cost", 0), 6),
                    "order_id": t.get("order"),
                })
            return result
        except Exception as e:
            logger.error(f"거래 이력 조회 실패: {e}")
            return []


    def get_closed_positions_pnl(self, limit=20):
        try:
            raw = self.exchange.privateGetAccountPositionsHistory({'limit': str(limit)})
            return [
                {'symbol': r.get('instId',''), 'pnl_usdt': float(r.get('realizedPnl', 0) or 0)}
                for r in raw.get('data', [])
            ]
        except Exception as e:
            logger.error(f'closed pnl error: {e}')
            return []
    # ── 시장 데이터 ────────────────────────────────────

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = CFG.TIMEFRAME,
        limit: int = 300,
    ) -> pd.DataFrame:
        """OHLCV 캔들 데이터 조회"""
        try:
            if limit <= 300:
                raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            else:
                tf_ms = self.exchange.parse_timeframe(timeframe) * 1000
                since = self.exchange.milliseconds() - (limit * tf_ms)
                raw = []
                while len(raw) < limit:
                    fetch_limit = min(300, limit - len(raw))
                    chunk = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=fetch_limit)
                    if not chunk:
                        break
                    raw.extend(chunk)
                    since = chunk[-1][0] + tf_ms
                    import time
                    time.sleep(0.1)
            df = pd.DataFrame(
                raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("timestamp").sort_index()
            return df.astype(float)
        except Exception as e:
            logger.error(f"OHLCV 조회 실패 ({symbol}): {e}")
            return pd.DataFrame()

    def get_ticker(self, symbol: str) -> Dict:
        """현재가 조회"""
        try:
            t = self.exchange.fetch_ticker(symbol)
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
        """USDT 선물 전종목 심볼 목록 반환 (거래대금 필터 적용)"""
        symbols = []
        for sym, mkt in self._markets.items():
            if (
                mkt.get("quote") == "USDT"
                and mkt.get("type") == "swap"
                and mkt.get("active", False)
            ):
                symbols.append(sym)
        return sorted(symbols)

    # ── 주문 실행 ──────────────────────────────────────

    def set_leverage(self, symbol: str, leverage: int = CFG.LEVERAGE) -> bool:
        """레버리지 설정"""
        try:
            self.exchange.set_leverage(leverage, symbol, params={"mgnMode": "isolated"})
            logger.info(f"레버리지 설정: {symbol} {leverage}x")
            return True
        except Exception as e:
            logger.error(f"레버리지 설정 실패 ({symbol}): {e}")
            return False

    def place_order(
        self,
        symbol: str,
        side: str,          # "buy" | "sell"
        margin_usdt: float,
        stop_loss_pct: float = CFG.STOP_LOSS_PCT,
        take_profit_pct: float = CFG.TAKE_PROFIT_PCT,
    ) -> Optional[Dict]:
        """
        시장가 주문 + 즉시 SL/TP 설정
        side: "buy" = 롱 진입, "sell" = 숏 진입
        """
        try:
            # 1) 레버리지 설정 및 실제 적용값 확인
            self.set_leverage(symbol, CFG.LEVERAGE)
            
            # 실제 적용된 레버리지 조회 (OKX 제한 사항 반영)
            actual_leverage = CFG.LEVERAGE
            try:
                lev_info = self.exchange.privateGetAccountLeverageInfo({
                    'instId': symbol.replace('/', '-').replace(':USDT', ''),
                    'mgnMode': 'isolated'
                })
                actual_leverage = float(lev_info.get('data', [{}])[0].get('lever', CFG.LEVERAGE))
                logger.info(f"실제 적용 레버리지 ({symbol}): {actual_leverage}x")
            except Exception as e:
                logger.warning(f"실제 레버리지 조회 실패, 설정값 사용: {e}")

            # 2) 현재가로 수량 계산
            ticker = self.get_ticker(symbol)
            price = ticker.get("last", 0)
            if not price:
                raise ValueError("현재가 조회 실패")

            market = self._markets.get(symbol, {})
            contract_size = market.get("contractSize", 1)
            target_margin = margin_usdt
            target_notional = target_margin * actual_leverage
            amount = target_notional / (price * contract_size)

            # ccxt precision 적용
            amount = self.exchange.amount_to_precision(symbol, amount)
            amount_float = float(amount)
            if amount_float <= 0:
                raise ValueError(f"주문 수량 계산 실패: {symbol} amount={amount}")

            estimated_notional = amount_float * price * contract_size
            estimated_margin = estimated_notional / actual_leverage
            max_margin = target_margin + max(0.01, target_margin * 0.01)
            if estimated_margin > max_margin:
                raise ValueError(
                    f"예상 증거금 초과: {estimated_margin:.4f} USDT "
                    f"> 설정 {target_margin:.4f} USDT"
                )

            # 3) 시장가 진입
            order = self.exchange.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=amount_float,
                params={"tdMode": "isolated", "posSide": "long" if side == "buy" else "short"},
            )
            entry_price = float(order.get("average") or price)

            # 4) Stop-Loss 주문 즉시 전송
            sl_price = (
                entry_price * (1 - stop_loss_pct)
                if side == "buy"
                else entry_price * (1 + stop_loss_pct)
            )
            tp_price = (
                entry_price * (1 + take_profit_pct)
                if side == "buy"
                else entry_price * (1 - take_profit_pct)
            )
            sl_price = float(self.exchange.price_to_precision(symbol, sl_price))
            tp_price = float(self.exchange.price_to_precision(symbol, tp_price))

            # SL 주문
            self.exchange.create_order(
                symbol=symbol,
                type="stop",
                side="sell" if side == "buy" else "buy",
                amount=amount_float,
                price=sl_price,
                params={
                    "stopPrice": sl_price,
                    "tdMode": "isolated",
                    "posSide": "long" if side == "buy" else "short",
                    "reduceOnly": True,
                },
            )

            # TP 주문
            self.exchange.create_order(
                symbol=symbol,
                type="stop",
                side="sell" if side == "buy" else "buy",
                amount=amount_float,
                price=tp_price,
                params={
                    "stopPrice": tp_price,
                    "tdMode": "isolated",
                    "posSide": "long" if side == "buy" else "short",
                    "reduceOnly": True,
                },
            )

            result = {
                "order_id": order.get("id"),
                "symbol": symbol,
                "side": "long" if side == "buy" else "short",
                "entry_price": entry_price,
                "amount": amount_float,
                "sl_price": sl_price,
                "tp_price": tp_price,
                "usdt_margin": target_margin,
                "estimated_margin_usdt": round(estimated_margin, 6),
                "target_notional_usdt": target_notional,
                "estimated_notional_usdt": round(estimated_notional, 6),
            }
            logger.info(f"주문 완료: {result}")
            return result

        except Exception as e:
            logger.error(f"주문 실패 ({symbol} {side}): {e}")
            return None

    def close_position(self, symbol: str, side: str) -> bool:
        """포지션 전체 청산 (시장가)"""
        try:
            pos_side = "long" if side == "long" else "short"
            close_side = "sell" if side == "long" else "buy"
            positions = self.get_positions()
            target = next((p for p in positions if p["symbol"] == symbol), None)
            if not target:
                return False

            self.exchange.create_order(
                symbol=symbol,
                type="market",
                side=close_side,
                amount=target["size"],
                params={"tdMode": "isolated", "posSide": pos_side, "reduceOnly": True},
            )
            logger.info(f"포지션 청산 완료: {symbol} {side}")
            return True
        except Exception as e:
            logger.error(f"청산 실패 ({symbol}): {e}")
            return False

    def close_all_positions(self) -> int:
        """모든 활성 포지션 일괄 청산 (시장가)"""
        positions = self.get_positions()
        success_count = 0
        for p in positions:
            if self.close_position(p["symbol"], p["side"]):
                success_count += 1
        return success_count
