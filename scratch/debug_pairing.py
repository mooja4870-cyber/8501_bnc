import sys
import os
import pandas as pd

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.getcwd())
from core.history_helper import load_local_trade_history, get_position_direction

def debug_pairing(symbol):
    trades = load_local_trade_history()
    sym_trades = [t for t in trades if t['symbol'] == symbol]
    
    # Let's run the first part of aggregate_and_pair_trades
    for idx, t in enumerate(sym_trades):
        if not t["order_id"] or t["order_id"] == "nan" or t["order_id"] == "":
            t["order_id"] = f"TEMP_{t['timestamp'].strftime('%Y%m%d%H%M%S')}_{idx}"

    df_fills = pd.DataFrame(sym_trades)
    df_fills["cost"] = df_fills["price"] * df_fills["amount"]
    df_fills["weighted_pnl_pct"] = df_fills["pnl_pct"] * df_fills["amount"]
    df_fills["direction"] = df_fills.apply(lambda row: get_position_direction(row["category"], row["side"]), axis=1)

    grouped = df_fills.groupby(["order_id", "symbol", "category", "direction", "leverage"], as_index=False).agg({
        "side": "first",
        "timestamp": "min",
        "amount": "sum",
        "cost": "sum",
        "pnl": "sum",
        "weighted_pnl_pct": "sum"
    })
    grouped["price"] = grouped["cost"] / grouped["amount"]
    grouped["pnl_pct"] = grouped["weighted_pnl_pct"] / grouped["amount"]
    grouped = grouped.drop(columns=["weighted_pnl_pct"])
    
    orders = grouped.to_dict("records")
    orders.sort(key=lambda x: x["timestamp"])
    
    print(f"=== Orders for {symbol} ===")
    for o in orders:
        print(f"{o['timestamp']} | {o['category']:<5} | {o['direction']:<5} | Amt: {o['amount']:<6.1f} | Price: {o['price']:<8.5f} | PnL: {o['pnl']:<+6.2f} | ID: {o['order_id']}")

    print("\n=== Simulating Pairing Steps ===")
    active_longs = []
    active_shorts = []
    paired_cycles = []
    
    for o in orders:
        cat = o["category"].strip()
        direction = o["direction"]
        
        if cat in ("진입", "*진입"):
            entry_copy = dict(o)
            entry_copy["amount_remaining"] = o["amount"]
            if direction == "LONG":
                active_longs.append(entry_copy)
                print(f"[ENTRY LONG] Added {o['amount']} at {o['timestamp']}")
            else:
                active_shorts.append(entry_copy)
                print(f"[ENTRY SHORT] Added {o['amount']} at {o['timestamp']}")
        elif cat in ("청산", "청산(로테이션)"):
            remaining_exit_amount = o["amount"]
            total_exit_pnl = o["pnl"]
            
            print(f"[EXIT {direction}] Trying to close {o['amount']} at {o['timestamp']}. Active entries count: LONG={len(active_longs)}, SHORT={len(active_shorts)}")
            
            if direction == "LONG":
                while remaining_exit_amount > 1e-8 and active_longs:
                    entry = active_longs[0]
                    match_amount = min(entry["amount_remaining"], remaining_exit_amount)
                    print(f"  Matching LONG: entry_amount_rem={entry['amount_remaining']:.1f}, exit_amount_rem={remaining_exit_amount:.1f} -> match={match_amount:.1f}")
                    entry["amount_remaining"] -= match_amount
                    remaining_exit_amount -= match_amount
                    if entry["amount_remaining"] <= 1e-8:
                        active_longs.pop(0)
                        print("  LONG entry fully closed.")
                if remaining_exit_amount > 1e-8:
                    print(f"  Warning: unmatched LONG exit amount: {remaining_exit_amount:.1f}")
            else: # SHORT
                while remaining_exit_amount > 1e-8 and active_shorts:
                    entry = active_shorts[0]
                    match_amount = min(entry["amount_remaining"], remaining_exit_amount)
                    print(f"  Matching SHORT: entry_amount_rem={entry['amount_remaining']:.1f}, exit_amount_rem={remaining_exit_amount:.1f} -> match={match_amount:.1f}")
                    entry["amount_remaining"] -= match_amount
                    remaining_exit_amount -= match_amount
                    if entry["amount_remaining"] <= 1e-8:
                        active_shorts.pop(0)
                        print("  SHORT entry fully closed.")
                if remaining_exit_amount > 1e-8:
                    print(f"  Warning: unmatched SHORT exit amount: {remaining_exit_amount:.1f}")

    print("\n=== Remaining Active Positions ===")
    print(f"Active Longs remaining: {len(active_longs)}")
    for l in active_longs:
        print(f"  LONG: timestamp={l['timestamp']}, amount_rem={l['amount_remaining']:.1f}")
    print(f"Active Shorts remaining: {len(active_shorts)}")
    for s in active_shorts:
        print(f"  SHORT: timestamp={s['timestamp']}, amount_rem={s['amount_remaining']:.1f}")

if __name__ == '__main__':
    debug_pairing('BSB/USDT:USDT')
