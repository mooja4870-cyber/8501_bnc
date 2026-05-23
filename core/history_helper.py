"""
매매 이력 파싱, 병합 및 진입/청산 페어링 헬퍼 모듈
"""
import os
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from core.logger import LOG_FILE
from core.config import CFG

def get_position_direction(category: str, side: str) -> str:
    """유형(진입/청산)과 방향(buy/sell/long/short) 조합으로 포지션 방향 판별"""
    cat = category.strip()
    s = side.strip().lower()
    if s in ("long", "l"):
        return "LONG"
    if s in ("short", "s"):
        return "SHORT"
    
    if cat in ("진입", "*진입"):
        return "LONG" if s == "buy" else "SHORT"
    else:  # 청산
        return "LONG" if s == "sell" else "SHORT"

def load_local_trade_history() -> List[Dict]:
    """local trade_history.csv 로드하여 원본 데이터 리스트 반환"""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        df = pd.read_csv(LOG_FILE, encoding="utf-8-sig")
        df.columns = [c.strip() for c in df.columns]
        
        trades = []
        for _, row in df.iterrows():
            order_id = str(row.get("주문ID", "")).replace("ID_", "").strip()
            
            pnl_val = row.get("수익(USDT)", 0.0)
            pnl = 0.0 if pd.isna(pnl_val) else float(pnl_val)
            
            pnl_pct_val = row.get("수익률(%)", 0.0)
            pnl_pct = 0.0 if pd.isna(pnl_pct_val) else float(pnl_pct_val)
            
            lev_val = row.get("레버리지")
            leverage = CFG.LEVERAGE if pd.isna(lev_val) else int(float(lev_val))
            
            trades.append({
                "timestamp": pd.to_datetime(row["시간"]),
                "symbol": row["심볼"],
                "category": row["유형"],
                "side": row["방향"],
                "price": float(row["가격"]),
                "amount": float(row["수량"]),
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "leverage": leverage,
                "order_id": order_id,
            })
        return trades
    except Exception as e:
        print(f"[HISTORY_HELPER] 로컬 CSV 로드 실패: {e}")
        return []

def aggregate_and_pair_trades(trades: List[Dict], active_positions_set: Optional[set] = None) -> List[Dict]:
    """
    1. 동일 주문ID(order_id)의 개별 체결(fill)들을 하나의 주문 단위로 합산(weighted average price 등).
    2. 동일 종목(symbol)에 대해 시간순으로 진입(Entry)과 청산(Exit)을 짝지어(Pairing) 반환.
    """
    if not trades:
        return []

    # ── 1. 주문 ID 단위로 체결 합산 ──
    # order_id가 없거나 빈 경우 고유 식별자 임시 부여
    for idx, t in enumerate(trades):
        if not t["order_id"] or t["order_id"] == "nan" or t["order_id"] == "":
            t["order_id"] = f"TEMP_{t['timestamp'].strftime('%Y%m%d%H%M%S')}_{idx}"

    df_fills = pd.DataFrame(trades)
    df_fills["cost"] = df_fills["price"] * df_fills["amount"]
    df_fills["weighted_pnl_pct"] = df_fills["pnl_pct"] * df_fills["amount"]

    # 그룹화 항목: order_id, symbol, category, side, leverage
    grouped = df_fills.groupby(["order_id", "symbol", "category", "side", "leverage"], as_index=False).agg({
        "timestamp": "min",  # 가장 빠른 체결 시각
        "amount": "sum",
        "cost": "sum",
        "pnl": "sum",
        "weighted_pnl_pct": "sum"
    })
    
    grouped["price"] = grouped["cost"] / grouped["amount"]
    grouped["pnl_pct"] = grouped["weighted_pnl_pct"] / grouped["amount"]
    grouped = grouped.drop(columns=["weighted_pnl_pct"])
    
    # 다시 딕셔너리 리스트로 변환
    orders = grouped.to_dict("records")
    
    # 시간 순 정렬
    orders.sort(key=lambda x: x["timestamp"])

    # ── 2. 진입/청산 페어링 ──
    paired_cycles = []
    symbol_groups = {}
    
    for o in orders:
        sym = o["symbol"]
        if sym not in symbol_groups:
            symbol_groups[sym] = []
        symbol_groups[sym].append(o)

    for sym, sym_orders in symbol_groups.items():
        # 각 심볼별 시간 순 처리
        sym_orders.sort(key=lambda x: x["timestamp"])
        active_entries = []

        for o in sym_orders:
            cat = o["category"].strip()
            direction = get_position_direction(o["category"], o["side"])
            
            if cat in ("진입", "*진입"):
                active_entries.append(o)
            elif cat in ("청산", "청산(로테이션)"):
                if active_entries:
                    entry = active_entries.pop(0)  # FIFO 페어링
                    paired_cycles.append({
                        "entry_time": entry["timestamp"],
                        "exit_time": o["timestamp"],
                        "symbol": sym,
                        "direction": "🟢 LONG" if direction == "LONG" else "🔴 SHORT",
                        "entry_price": entry["price"],
                        "exit_price": o["price"],
                        "amount": o["amount"],  # 청산 수량 기준
                        "pnl_usdt": o["pnl"],
                        "pnl_pct": o["pnl_pct"],
                        "status": "청산 완료"
                    })
                else:
                    # 진입 기록이 잘렸거나 없는 경우 (청산 단독 표시)
                    paired_cycles.append({
                        "entry_time": None,
                        "exit_time": o["timestamp"],
                        "symbol": sym,
                        "direction": "🟢 LONG" if direction == "LONG" else "🔴 SHORT",
                        "entry_price": None,
                        "exit_price": o["price"],
                        "amount": o["amount"],
                        "pnl_usdt": o["pnl"],
                        "pnl_pct": o["pnl_pct"],
                        "status": "청산 완료 (진입유실)"
                    })
        
        # 스캔 후 남은 진입중인 포지션 표시
        for entry in active_entries:
            entry_dir = get_position_direction(entry["category"], entry["side"])
            
            # 실시간 실제 보유 중인지 크로스 체크
            is_actually_holding = True
            if active_positions_set is not None:
                is_actually_holding = ((sym, entry_dir) in active_positions_set)
                
            status_str = "보유 중" if is_actually_holding else "청산 완료 (미기록)"
            
            paired_cycles.append({
                "entry_time": entry["timestamp"],
                "exit_time": None if is_actually_holding else entry["timestamp"],
                "symbol": sym,
                "direction": "🟢 LONG" if entry_dir == "LONG" else "🔴 SHORT",
                "entry_price": entry["price"],
                "exit_price": entry["price"] if not is_actually_holding else None,
                "amount": entry["amount"],
                "pnl_usdt": 0.0 if not is_actually_holding else None,
                "pnl_pct": 0.0 if not is_actually_holding else None,
                "status": status_str
            })

    # 전체 사이클을 최신 종료 시각(exit_time이 없으면 entry_time) 기준으로 내림차순 정렬
    def sort_key(x):
        t = x["exit_time"] if x["exit_time"] is not None else x["entry_time"]
        return t

    paired_cycles.sort(key=sort_key, reverse=True)
    return paired_cycles
