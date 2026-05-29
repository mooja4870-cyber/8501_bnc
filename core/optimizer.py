"""
AI QUANTUM — MAE/MFE SL/TP Optimizer
매매 이력(CSV)을 읽고, 진입~청산 기간의 1m OHLCV 데이터를 거래소에서 조회하여
최대 수익(MFE) 및 최대 낙폭(MAE)을 계산하고 최적의 손절/익절 비율을 추천합니다.
"""
import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple, Optional
from core.config import CFG

logger = logging.getLogger(__name__)

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "trade_history.csv")

class TradeOptimizer:
    def __init__(self, client):
        self.client = client

    def load_trades_from_csv(self) -> List[Dict]:
        """CSV에서 진입/청산 쌍 매칭하여 거래 목록 생성"""
        if not os.path.exists(CSV_PATH):
            return []
        
        try:
            df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
            if df.empty:
                return []
            
            # 컬럼 한글 지원
            # "시간", "심볼", "유형", "방향", "가격", "수량", "수익(USDT)", "수익률(%)", "레버리지", "주문ID"
            from collections import defaultdict
            entries = defaultdict(list)
            trades = []
            
            for _, row in df.iterrows():
                try:
                    t_time = pd.to_datetime(row["시간"])
                    symbol = str(row["심볼"])
                    category = str(row["유형"]) # 진입 / 청산
                    side = str(row["방향"]) # buy(long) / sell(short)
                    price = float(row["가격"])
                    amount = float(row["수량"])
                    pnl = float(row["수익(USDT)"])
                    order_id = str(row["주문ID"])
                except Exception:
                    continue
                
                # 진입 기록 임시 매칭
                if "진입" in category:
                    entries[symbol].append({
                        "entry_time": t_time,
                        "symbol": symbol,
                        "side": "long" if "buy" in side.lower() or "long" in side.lower() else "short",
                        "entry_price": price,
                        "amount": amount,
                        "order_id": order_id
                    })
                elif "청산" in category:
                    symbol_entries = entries[symbol]
                    if symbol_entries:
                        entry = symbol_entries.pop(0)  # FIFO 매칭
                        entry["exit_time"] = t_time
                        entry["exit_price"] = price
                        entry["pnl"] = pnl
                        trades.append(entry)
            
            return trades
        except Exception as e:
            logger.error(f"CSV 로딩 실패: {e}")
            return []

    def calculate_mae_mfe(self, trade: Dict) -> Optional[Dict]:
        """하나의 거래에 대해 진입~청산 사이의 고가/저가를 추적하여 MAE/MFE 계산"""
        if not self.client:
            return None
        
        symbol = trade["symbol"]
        entry_time = trade["entry_time"]
        exit_time = trade["exit_time"]
        entry_price = trade["entry_price"]
        side = trade["side"]
        
        # KST -> UTC 변환 (OKX API는 ms timestamp 사용)
        entry_ms = int((entry_time - pd.Timedelta(hours=9)).timestamp() * 1000)
        
        try:
            # 1m 캔들 조회하여 상세 경로 분석
            limit = 300
            ohlcv = self.client.exchange.fetch_ohlcv(symbol, timeframe="1m", since=entry_ms, limit=limit)
            if not ohlcv:
                return None
            
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["time"] = pd.to_datetime(df["timestamp"], unit="ms") + pd.Timedelta(hours=9)
            
            # 진입~청산 시간 사이만 필터링
            df = df[(df["time"] >= entry_time) & (df["time"] <= exit_time)]
            if df.empty:
                return None
            
            highest = df["high"].max()
            lowest = df["low"].min()
            
            if side == "long":
                mfe_pct = (highest - entry_price) / entry_price * 100
                mae_pct = (entry_price - lowest) / entry_price * 100
            else:
                mfe_pct = (entry_price - lowest) / entry_price * 100
                mae_pct = (highest - entry_price) / entry_price * 100
                
            trade["mae"] = max(0.0, mae_pct)
            trade["mfe"] = max(0.0, mfe_pct)
            return trade
        except Exception as e:
            logger.debug(f"{symbol} MAE/MFE 계산 오류: {e}")
            return None

    def run_optimization(self) -> Dict:
        """모든 거래 분석 및 최적의 손익 비율 탐색"""
        trades = self.load_trades_from_csv()
        if not trades:
            return {"status": "error", "message": "분석할 매매 기록(진입/청산 쌍)이 없습니다."}
            
        analyzed = []
        for t in trades:
            res = self.calculate_mae_mfe(t)
            if res:
                analyzed.append(res)
                
        if not analyzed:
            return {"status": "error", "message": "Binance API에서 진입 시점의 캔들 데이터를 가져오지 못했습니다. (API 제한 또는 과거 거래)"}
            
        # 가상 시뮬레이션 (익절 0.5%~3.0%, 손절 0.3%~2.0%)
        best_tp = 1.2
        best_sl = 0.8
        max_pnl = -99999.0
        best_winrate = 0.0
        
        sim_results = []
        
        # 10배 레버리지 기준 시뮬레이션
        leverage = CFG.LEVERAGE
        margin = CFG.MARGIN_USDT
        
        for sl in np.arange(0.3, 2.1, 0.1):
            for tp in np.arange(0.5, 3.1, 0.1):
                total_sim_pnl = 0.0
                wins = 0
                losses = 0
                
                for t in analyzed:
                    mae = t["mae"]
                    mfe = t["mfe"]
                    
                    # MAE가 SL에 먼저 도달했는지 확인 (단순 보수적 가정: MAE가 SL보다 크면 손절 처리)
                    if mae >= sl:
                        # 손절
                        total_sim_pnl -= margin * (sl / 100) * leverage
                        losses += 1
                    elif mfe >= tp:
                        # 익절
                        total_sim_pnl += margin * (tp / 100) * leverage
                        wins += 1
                    else:
                        # 보유 후 기존 만기/청산가 체결
                        total_sim_pnl += t["pnl"]
                        if t["pnl"] > 0:
                            wins += 1
                        else:
                            losses += 1
                            
                total_trades = wins + losses
                winrate = (wins / total_trades * 100) if total_trades > 0 else 0.0
                
                sim_results.append({
                    "sl": sl,
                    "tp": tp,
                    "pnl": total_sim_pnl,
                    "winrate": winrate
                })
                
                if total_sim_pnl > max_pnl:
                    max_pnl = total_sim_pnl
                    best_tp = tp
                    best_sl = sl
                    best_winrate = winrate
                    
        return {
            "status": "success",
            "analyzed_count": len(analyzed),
            "current_sl": CFG.STOP_LOSS_PCT * 100,
            "current_tp": CFG.TAKE_PROFIT_PCT * 100,
            "optimal_sl": round(best_sl, 2),
            "optimal_tp": round(best_tp, 2),
            "optimal_winrate": round(best_winrate, 1),
            "optimal_pnl": round(max_pnl, 2),
            "trades": analyzed,
            "sim_results": sim_results
        }
