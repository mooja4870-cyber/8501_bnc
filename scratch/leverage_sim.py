import os
import pandas as pd
import numpy as np

CSV_PATH = r"d:\AI\project\1127_okx\data\trade_history.csv"

def run_sim():
    if not os.path.exists(CSV_PATH):
        print("CSV file not found")
        return
    
    # Detect encoding
    with open(CSV_PATH, "rb") as f:
        raw_data = f.read(1000)
    
    encodings_to_try = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "cp1252", "latin1"]
    detected_encoding = None
    for enc in encodings_to_try:
        try:
            decoded = raw_data.decode(enc)
            first_line = decoded.splitlines()[0]
            print(f"Decoded with {enc}: {first_line}")
            if "시간" in first_line or "시간" in decoded or "심볼" in decoded:
                detected_encoding = enc
                break
        except Exception:
            continue
            
    if not detected_encoding:
        print("Could not reliably detect encoding containing '시간'. Defaulting to latin1.")
        detected_encoding = "latin1"
        
    print(f"Using detected encoding: {detected_encoding}")
    df = pd.read_csv(CSV_PATH, encoding=detected_encoding)
    print("CSV Columns:", df.columns.tolist())
    print("CSV Shape:", df.shape)
    
    # Pair entries and exits
    entries = {}
    trades = []
    
    for _, row in df.iterrows():
        try:
            t_time = pd.to_datetime(row.iloc[0])
            symbol = str(row.iloc[1])
            category = str(row.iloc[2])
            side = str(row.iloc[3])
            price = float(row.iloc[4])
            amount = float(row.iloc[5])
            pnl = float(row.iloc[6])
            order_id = str(row.iloc[9])
        except Exception as e:
            continue
            
    # Pair entries and exits using FIFO matching by symbol
    from collections import defaultdict
    entries = defaultdict(list)
    trades = []
    
    for _, row in df.iterrows():
        try:
            t_time = pd.to_datetime(row.iloc[0])
            symbol = str(row.iloc[1])
            category = str(row.iloc[2])
            side = str(row.iloc[3])
            price = float(row.iloc[4])
            amount = float(row.iloc[5])
            pnl = float(row.iloc[6])
            order_id = str(row.iloc[9])
        except Exception as e:
            continue
            
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
                entry = symbol_entries.pop(0)  # FIFO
                entry["exit_time"] = t_time
                entry["exit_price"] = price
                entry["pnl"] = pnl
                trades.append(entry)
                
    print(f"Loaded {len(trades)} complete trades.")
    
    # Sim configs: (Leverage, SL_pct, TP_pct)
    # Compare matching margin risk (L * SL_pct is roughly similar)
    configs = [
        {"name": "A (Current: 10x leverage, SL 0.8%, TP 1.2%)", "lev": 10, "sl": 0.8, "tp": 1.2},
        {"name": "B (20x leverage, SL 0.4%, TP 0.6%)", "lev": 20, "sl": 0.4, "tp": 0.6},
        {"name": "C (30x leverage, SL 0.25%, TP 0.4%)", "lev": 30, "sl": 0.25, "tp": 0.4},
        {"name": "D (High-Risk: 20x leverage, SL 0.8%, TP 1.2%)", "lev": 20, "sl": 0.8, "tp": 1.2},
    ]
    
    margin = 5.0  # USDT per trade
    fee_rate = 0.0005  # OKX Taker Fee (0.05%)
    
    for c in configs:
        lev = c["lev"]
        sl = c["sl"] / 100.0
        tp = c["tp"] / 100.0
        
        total_pnl = 0.0
        wins = 0
        losses = 0
        total_fees = 0.0
        
        for t in trades:
            # Estimate price path or use actual pnl as proxy for simpler visualization
            # Let's calculate based on actual entry/exit price changes
            entry_p = t["entry_price"]
            exit_p = t["exit_price"]
            side = t["side"]
            
            # Max price change during trade (since we don't have high/low here, we use entry/exit price)
            # This is a simplified simulation based on entry/exit prices
            price_change_pct = (exit_p - entry_p) / entry_p if side == "long" else (entry_p - exit_p) / entry_p
            
            # Position size (Notional)
            notional = margin * lev
            roundtrip_fee = notional * fee_rate * 2
            total_fees += roundtrip_fee
            
            # Sim execution
            if price_change_pct <= -sl:
                # Stopped out
                trade_pnl = -notional * sl - roundtrip_fee
                losses += 1
            elif price_change_pct >= tp:
                # Took profit
                trade_pnl = notional * tp - roundtrip_fee
                wins += 1
            else:
                # Normal close
                trade_pnl = notional * price_change_pct - roundtrip_fee
                if trade_pnl > 0:
                    wins += 1
                else:
                    losses += 1
            
            total_pnl += trade_pnl
            
        total_trades = wins + losses
        winrate = (wins / total_trades * 100) if total_trades > 0 else 0.0
        
        print(f"\nConfiguration: {c['name']}")
        print(f"  - Net PnL (after fees): {total_pnl:+.4f} USDT")
        print(f"  - Win Rate: {winrate:.1f}% (Wins: {wins}, Losses: {losses})")
        print(f"  - Total Fees Paid: {total_fees:.4f} USDT")
        print(f"  - Net Reward/Risk Ratio (TP-Fee)/(SL+Fee): {(tp - fee_rate*2)/(sl + fee_rate*2):.3f}")

if __name__ == "__main__":
    run_sim()
