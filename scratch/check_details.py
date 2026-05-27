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
    
    balance = await client.get_balance()
    print("=== BALANCE INFO ===")
    print(f"Total: {balance['total']}")
    print(f"Free: {balance['free']}")
    print(f"Used: {balance['used']}")
    print(f"PnL: {balance['pnl']}")
    
    positions = await client.get_positions()
    print("\n=== POSITIONS INFO ===")
    for p in positions:
        print(f"Symbol: {p['symbol']}, Side: {p['side']}, Size: {p['size']}, Entry: {p['entry_price']}, Mark: {p['mark_price']}, PnL: {p['pnl_usdt']} ({p['pnl_pct']}%), Margin: {p['margin']}, Leverage: {p['leverage']}x, Amt USDT: {p['amount_usdt']}")
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
