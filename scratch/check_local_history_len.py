import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.history_helper import load_local_trade_history

trades = load_local_trade_history()
print(f"Loaded {len(trades)} trades from local trade history.")
if trades:
    print("First trade:", trades[0])
    print("Last trade:", trades[-1])
