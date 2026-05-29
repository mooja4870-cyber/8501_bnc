import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.history_helper import load_local_trade_history, aggregate_and_pair_trades

trades = load_local_trade_history()
ada_trades = [t for t in trades if t["symbol"] == "ADA/USDT:USDT"]
print(f"=== Raw ADA trades in CSV ({len(ada_trades)}) ===")
for t in sorted(ada_trades, key=lambda x: x["timestamp"]):
    print(f"Time={t['timestamp']}, Cat={repr(t['category'])}, Side={t['side']}, Price={t['price']}, Qty={t['amount']}, PnL={t['pnl']}, OrderID={t['order_id']}, TradeID={t['trade_id']}")

print("\n=== Paired ADA cycles ===")
paired = aggregate_and_pair_trades(trades)
ada_paired = [p for p in paired if p["symbol"] == "ADA/USDT:USDT"]
for p in ada_paired[:15]:
    print(p)
