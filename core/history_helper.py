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
    
    # 만약 방향 자체가 long/short으로 명시되어 있다면 직접 반환
    if s in ("long", "l"):
        return "LONG"
    if s in ("short", "s"):
        return "SHORT"
    
    # buy/sell인 경우 유형(진입/청산) 기준으로 판별
    if cat in ("진입", "*진입"):
        return "LONG" if s == "buy" else "SHORT"
    else:  # 청산
        # 롱 포지션 청산은 매도(sell), 숏 포지션 청산은 매수(buy)
        return "LONG" if s == "sell" else "SHORT"

def load_local_trade_history() -> List[Dict]:
    """local trade_history.csv 로드하여 원본 데이터 리스트 반환 (모의 거래 필터링 포함)"""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        df = pd.read_csv(LOG_FILE, encoding="utf-8-sig")
        df.columns = [c.strip() for c in df.columns]
        
        trades = []
        for _, row in df.iterrows():
            order_id = str(row.get("주문ID", "")).replace("ID_", "").strip()
            
            # 모의 거래(MOCK) 데이터 필터링하여 실거래 내역 오염 방지
            if "MOCK" in order_id or order_id == "" or order_id == "nan":
                continue
                
            pnl_val = row.get("수익(USDT)", 0.0)
            pnl = 0.0 if pd.isna(pnl_val) else float(pnl_val)
            
            pnl_pct_val = row.get("수익률(%)", 0.0)
            pnl_pct = 0.0 if pd.isna(pnl_pct_val) else float(pnl_pct_val)
            
            lev_val = row.get("레버리지")
            leverage = CFG.LEVERAGE if pd.isna(lev_val) else int(float(lev_val))
            
            trade_id_val = row.get("체결ID")
            trade_id = "" if pd.isna(trade_id_val) else str(trade_id_val).strip()
            
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
                "trade_id": trade_id,
            })
        return trades
    except Exception as e:
        print(f"[HISTORY_HELPER] 로컬 CSV 로드 실패: {e}")
        return []

def aggregate_and_pair_trades(trades: List[Dict], active_positions_set: Optional[set] = None) -> List[Dict]:
    """
    1. 동일 주문ID(order_id)의 개별 체결(fill)들을 하나의 주문 단위로 합산.
    2. 동일 종목(symbol)에 대해 시간순으로 진입(Entry)과 청산(Exit)을 LONG/SHORT 방향별로 분리하여 짝지어(Pairing) 반환.
    """
    if not trades:
        return []

    # ── 1. 주문 ID 단위로 체결 합산 ──
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
    orders.sort(key=lambda x: x["timestamp"])

    # ── 2. 진입/청산 페어링 (LONG / SHORT 분리 관리, M:N 매칭 지원) ──
    paired_cycles = []
    symbol_groups = {}
    
    for o in orders:
        sym = o["symbol"]
        if sym not in symbol_groups:
            symbol_groups[sym] = []
        symbol_groups[sym].append(o)

    for sym, sym_orders in symbol_groups.items():
        sym_orders.sort(key=lambda x: x["timestamp"])
        
        active_longs = []
        active_shorts = []

        for o in sym_orders:
            cat = o["category"].strip()
            direction = get_position_direction(o["category"], o["side"])
            
            if cat in ("진입", "*진입"):
                # entry 딕셔너리에 amount_remaining 필드를 초깃값 amount로 설정하여 복사본 저장
                entry_copy = dict(o)
                entry_copy["amount_remaining"] = o["amount"]
                if direction == "LONG":
                    active_longs.append(entry_copy)
                else:
                    active_shorts.append(entry_copy)
            elif cat in ("청산", "청산(로테이션)"):
                remaining_exit_amount = o["amount"]
                total_exit_pnl = o["pnl"]
                
                if direction == "LONG":
                    while remaining_exit_amount > 1e-8 and active_longs:
                        entry = active_longs[0]
                        match_amount = min(entry["amount_remaining"], remaining_exit_amount)
                        
                        # 분할 청산에 비례하여 PnL 분할
                        match_pnl = total_exit_pnl * (match_amount / o["amount"])
                        
                        paired_cycles.append({
                            "entry_time": entry["timestamp"],
                            "exit_time": o["timestamp"],
                            "symbol": sym,
                            "direction": "🟢 LONG",
                            "entry_price": entry["price"],
                            "exit_price": o["price"],
                            "amount": match_amount,
                            "pnl_usdt": match_pnl,
                            "pnl_pct": o["pnl_pct"],
                            "status": "청산 완료"
                        })
                        
                        entry["amount_remaining"] -= match_amount
                        remaining_exit_amount -= match_amount
                        
                        if entry["amount_remaining"] <= 1e-8:
                            active_longs.pop(0)
                            
                    if remaining_exit_amount > 1e-8:
                        match_pnl = total_exit_pnl * (remaining_exit_amount / o["amount"])
                        paired_cycles.append({
                            "entry_time": None,
                            "exit_time": o["timestamp"],
                            "symbol": sym,
                            "direction": "🟢 LONG",
                            "entry_price": None,
                            "exit_price": o["price"],
                            "amount": remaining_exit_amount,
                            "pnl_usdt": match_pnl,
                            "pnl_pct": o["pnl_pct"],
                            "status": "청산 완료 (진입유실)"
                        })
                else:  # SHORT
                    while remaining_exit_amount > 1e-8 and active_shorts:
                        entry = active_shorts[0]
                        match_amount = min(entry["amount_remaining"], remaining_exit_amount)
                        
                        match_pnl = total_exit_pnl * (match_amount / o["amount"])
                        
                        paired_cycles.append({
                            "entry_time": entry["timestamp"],
                            "exit_time": o["timestamp"],
                            "symbol": sym,
                            "direction": "🔴 SHORT",
                            "entry_price": entry["price"],
                            "exit_price": o["price"],
                            "amount": match_amount,
                            "pnl_usdt": match_pnl,
                            "pnl_pct": o["pnl_pct"],
                            "status": "청산 완료"
                        })
                        
                        entry["amount_remaining"] -= match_amount
                        remaining_exit_amount -= match_amount
                        
                        if entry["amount_remaining"] <= 1e-8:
                            active_shorts.pop(0)
                            
                    if remaining_exit_amount > 1e-8:
                        match_pnl = total_exit_pnl * (remaining_exit_amount / o["amount"])
                        paired_cycles.append({
                            "entry_time": None,
                            "exit_time": o["timestamp"],
                            "symbol": sym,
                            "direction": "🔴 SHORT",
                            "entry_price": None,
                            "exit_price": o["price"],
                            "amount": remaining_exit_amount,
                            "pnl_usdt": match_pnl,
                            "pnl_pct": o["pnl_pct"],
                            "status": "청산 완료 (진입유실)"
                        })
        
        # 스캔 후 남은 진입중인 포지션 표시
        for entry in active_longs:
            if entry["amount_remaining"] <= 1e-8:
                continue
            is_actually_holding = False
            if active_positions_set is not None:
                is_actually_holding = ((sym, "LONG") in active_positions_set)
            else:
                time_diff = pd.Timestamp.now() - entry["timestamp"]
                if time_diff.total_seconds() < 24 * 3600:
                    is_actually_holding = True
                
            status_str = "보유 중" if is_actually_holding else "청산 완료 (미기록)"
            
            paired_cycles.append({
                "entry_time": entry["timestamp"],
                "exit_time": None if is_actually_holding else entry["timestamp"],
                "symbol": sym,
                "direction": "🟢 LONG",
                "entry_price": entry["price"],
                "exit_price": entry["price"] if not is_actually_holding else None,
                "amount": entry["amount_remaining"],
                "pnl_usdt": 0.0 if not is_actually_holding else None,
                "pnl_pct": 0.0 if not is_actually_holding else None,
                "status": status_str
            })

        for entry in active_shorts:
            if entry["amount_remaining"] <= 1e-8:
                continue
            is_actually_holding = False
            if active_positions_set is not None:
                is_actually_holding = ((sym, "SHORT") in active_positions_set)
            else:
                time_diff = pd.Timestamp.now() - entry["timestamp"]
                if time_diff.total_seconds() < 24 * 3600:
                    is_actually_holding = True
                
            status_str = "보유 중" if is_actually_holding else "청산 완료 (미기록)"
            
            paired_cycles.append({
                "entry_time": entry["timestamp"],
                "exit_time": None if is_actually_holding else entry["timestamp"],
                "symbol": sym,
                "direction": "🔴 SHORT",
                "entry_price": entry["price"],
                "exit_price": entry["price"] if not is_actually_holding else None,
                "amount": entry["amount_remaining"],
                "pnl_usdt": 0.0 if not is_actually_holding else None,
                "pnl_pct": 0.0 if not is_actually_holding else None,
                "status": status_str
            })

    # 전체 사이클을 최신 종료 시각(exit_time이 없으면 entry_time) 기준으로 내림차순 정렬
    def sort_key(x):
        t = x["exit_time"] if x["exit_time"] is not None else x["entry_time"]
        return t if t is not None else pd.Timestamp.min

    paired_cycles.sort(key=sort_key, reverse=True)
    return paired_cycles
