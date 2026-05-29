import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from dotenv import load_dotenv
import pandas as pd
from core.exchange import BinanceClient

async def main():
    load_dotenv(override=True)
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    
    client = BinanceClient(api_key, secret_key)
    await client.load_markets()
    
    symbol = "ADA/USDT:USDT"
    
    print("=== Positions ===")
    positions = await client.get_positions()
    ada_pos = [p for p in positions if "ADA" in p["symbol"]]
    for p in ada_pos:
        print(p)
        
    print("\n=== Open Orders ===")
    open_orders = await client.get_open_orders()
    ada_open = [o for o in open_orders if "ADA" in o["symbol"]]
    for o in ada_open:
        print(o)
        
    print("\n=== Exchange Trade History (last 30) ===")
    trades = await client.get_trade_history(symbol, limit=30)
    for t in trades:
        print(f"ID={t['id']}, Time={t['timestamp']}, Cat={t['category']}, Side={t['side']}, Price={t['price']}, Qty={t['amount']}, PnL={t['pnl']}, OrderID={t['order_id']}")

    await client.exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
