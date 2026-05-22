import pandas as pd
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.history_helper import load_local_trade_history, aggregate_and_pair_trades

def test():
    trades = load_local_trade_history()
    print(f"Total raw trades loaded: {len(trades)}")
    
    doge_raw = [t for t in trades if "DOGE" in t["symbol"]]
    print(f"DOGE raw trades: {len(doge_raw)}")
    for t in doge_raw[:10]:
        print(f"Time: {t['timestamp']}, Cat: {t['category']}, Side: {t['side']}, Price: {t['price']}, Qty: {t['amount']}, PnL: {t['pnl']}, OrderID: {t['order_id']}")

if __name__ == "__main__":
    test()
