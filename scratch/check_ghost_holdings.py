import sys
import os
import pandas as pd

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.getcwd())
from core.history_helper import load_local_trade_history, aggregate_and_pair_trades

def check_holding():
    raw_trades = load_local_trade_history()
    all_paired = aggregate_and_pair_trades(raw_trades)
    
    holding = [p for p in all_paired if p['exit_time'] is None and p['status'] == "보유 중"]
    print(f"Ghost holding positions count: {len(holding)}")
    for h in holding:
        print(f"• {h['symbol']}: direction={h['direction']}, entry_time={h['entry_time']}, amount={h['amount']}, entry_price={h['entry_price']}")

if __name__ == '__main__':
    check_holding()
