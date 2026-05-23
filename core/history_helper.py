"""
매매 이력 파싱, 병합 및 진입/청산 페어링 헬퍼 모듈
v3.3.4 — 분 단위 병합 및 1:N 가중평균 FIFO 매칭 적용
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
    1. 동일 분(minute)에 발생한 동일 심볼, 유형, 방향, 레버리지 거래(Split-Fill/분할 체결)들을 하나로 합산.
    2. 청산 주문(Exit) 기준으로 진입 주문(Entry)들과 수량 기반으로 FIFO 매칭 (1:N 및 N:1 가중평균 가격 대응).
    3. 청산 주문의 실제 거래소 PnL 및 PnL%를 그대로 보존하여 매칭 결과를 정밀하게 도출.
    4. 남은 진입 포지션에 대해 active_positions_set과 교차 검증하여 "보유 중" 또는 "청산 완료 (미기록)" 구분.
    """
    if not trades:
        return []

    # 먼저 각 거래에 방향 정보를 추가
    for t in trades:
        t["direction"] = get_position_direction(t["category"], t["side"])

    df_fills = pd.DataFrame(trades)
    
    # 동일 분(minute) 단위로 절사하여 동일 시각 분할 건을 하나로 묶음
    df_fills["minute"] = df_fills["timestamp"].dt.floor("min")
    df_fills["cost"] = df_fills["price"] * df_fills["amount"]
    df_fills["weighted_pnl_pct"] = df_fills["pnl_pct"] * df_fills["amount"]

    # 그룹화 항목: symbol, category, side, leverage, direction, minute
    grouped = df_fills.groupby(["symbol", "category", "side", "leverage", "direction", "minute"], as_index=False).agg({
        "timestamp": "min",
        "amount": "sum",
        "cost": "sum",
        "pnl": "sum",
        "weighted_pnl_pct": "sum"
    })
    
    grouped["price"] = grouped["cost"] / grouped["amount"]
    # pnl_pct는 수량 가중 평균
    grouped["pnl_pct"] = grouped["weighted_pnl_pct"] / grouped["amount"]
    grouped = grouped.drop(columns=["cost", "weighted_pnl_pct"])
    
    # 다시 딕셔너리 리스트로 변환
    orders = grouped.to_dict("records")
    
    # 시간 순 정렬
    orders.sort(key=lambda x: x["timestamp"])

    paired_cycles = []
    
    # (symbol, direction) 별로 그룹핑하여 순차 FIFO 페어링 진행
    group_key = {}
    for o in orders:
        key = (o["symbol"], o["direction"])
        if key not in group_key:
            group_key[key] = []
        group_key[key].append(o)

    for (sym, direction), sym_orders in group_key.items():
        sym_orders.sort(key=lambda x: x["timestamp"])
        
        # 진입 큐 (각 항목은 {"order": order_dict, "remaining_qty": float})
        entry_queue = []

        for o in sym_orders:
            cat = o["category"].strip()
            
            if cat in ("진입", "*진입"):
                entry_queue.append({
                    "order": o,
                    "remaining_qty": o["amount"],
                })
            elif cat in ("청산", "청산(로테이션)"):
                exit_qty = o["amount"]
                matched_entries = []
                total_matched_qty = 0.0
                
                # 진입 큐에서 FIFO 순으로 수량 매칭
                while exit_qty > 1e-10 and entry_queue:
                    entry = entry_queue[0]
                    match_qty = min(entry["remaining_qty"], exit_qty)
                    
                    matched_entries.append({
                        "entry_time": entry["order"]["timestamp"],
                        "entry_price": entry["order"]["price"],
                        "qty": match_qty,
                    })
                    
                    entry["remaining_qty"] -= match_qty
                    exit_qty -= match_qty
                    total_matched_qty += match_qty
                    
                    if entry["remaining_qty"] <= 1e-10:
                        entry_queue.pop(0)
                
                # 매칭된 진입가들의 가중평균 산출
                if matched_entries:
                    total_entry_cost = sum(m["entry_price"] * m["qty"] for m in matched_entries)
                    avg_entry_price = total_entry_cost / total_matched_qty if total_matched_qty > 0 else 0.0
                    entry_time = matched_entries[0]["entry_time"]
                else:
                    avg_entry_price = None
                    entry_time = None
                
                # 매칭 상태 구분
                status = "청산 완료" if exit_qty <= 1e-10 else "청산 완료 (진입유실)"
                
                paired_cycles.append({
                    "entry_time": entry_time,
                    "exit_time": o["timestamp"],
                    "symbol": sym,
                    "direction": f"🟢 LONG" if direction == "LONG" else f"🔴 SHORT",
                    "entry_price": round(avg_entry_price, 8) if avg_entry_price is not None else None,
                    "exit_price": o["price"],
                    "amount": round(o["amount"], 8),
                    "pnl_usdt": round(o["pnl"], 4),
                    "pnl_pct": round(o["pnl_pct"], 2),
                    "status": status
                })
        
        # 스캔 후 남은 진입중인 포지션 표시
        for entry in entry_queue:
            if entry["remaining_qty"] > 1e-10:
                is_actually_holding = True
                if active_positions_set is not None:
                    is_actually_holding = ((sym, direction) in active_positions_set)
                
                status_str = "보유 중" if is_actually_holding else "청산 완료 (미기록)"
                
                paired_cycles.append({
                    "entry_time": entry["order"]["timestamp"],
                    "exit_time": None if is_actually_holding else entry["order"]["timestamp"],
                    "symbol": sym,
                    "direction": f"🟢 LONG" if direction == "LONG" else f"🔴 SHORT",
                    "entry_price": entry["order"]["price"],
                    "exit_price": None if is_actually_holding else entry["order"]["price"],
                    "amount": round(entry["remaining_qty"], 8),
                    "pnl_usdt": None if is_actually_holding else 0.0,
                    "pnl_pct": None if is_actually_holding else 0.0,
                    "status": status_str
                })

    # 전체 사이클을 최신 종료 시각(exit_time이 없으면 entry_time) 기준으로 내림차순 정렬
    def sort_key(x):
        t = x["exit_time"] if x["exit_time"] is not None else x["entry_time"]
        return t if t is not None else pd.Timestamp.min

    paired_cycles.sort(key=sort_key, reverse=True)
    return paired_cycles
