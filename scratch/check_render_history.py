import asyncio
import os
from dotenv import load_dotenv
from core.exchange import BinanceClient

async def main():
    load_dotenv(override=True)
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    passphrase = os.getenv("BINANCE_PASSPHRASE") or ""
    
    client = BinanceClient(api_key, secret_key, passphrase)
    await client.load_markets()
    
    print("=== RENDER TRADE HISTORY ===")
    trades_render = await client.get_trade_history(symbol="RENDER/USDT:USDT", limit=10)
    for t in trades_render:
        print(f"ID: {t['id']}, Time: {t['timestamp']}, Symbol: {t['symbol']}, Cat: {t['category']}, Side: {t['side']}, Price: {t['price']}, Amt: {t['amount']}, PnL: {t['pnl']}, OrderID: {t['order_id']}")
        
    print("\n=== ICP TRADE HISTORY ===")
    trades_icp = await client.get_trade_history(symbol="ICP/USDT:USDT", limit=10)
    for t in trades_icp:
        print(f"ID: {t['id']}, Time: {t['timestamp']}, Symbol: {t['symbol']}, Cat: {t['category']}, Side: {t['side']}, Price: {t['price']}, Amt: {t['amount']}, PnL: {t['pnl']}, OrderID: {t['order_id']}")
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
