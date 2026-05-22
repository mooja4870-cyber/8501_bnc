import sys
import os
from dotenv import load_dotenv

# Ensure the core module can be imported
sys.path.append(os.getcwd())

from core.exchange import BinanceClient

load_dotenv(override=True)
ak = os.getenv("BINANCE_API_KEY")
sk = os.getenv("BINANCE_SECRET_KEY")

client = BinanceClient(ak, sk)
success = client.load_markets()
print(f"load_markets success: {success}")
print(f"Total keys in client._markets: {len(client._markets)}")

# Print first 5 markets and their attributes
count = 0
for sym, mkt in client._markets.items():
    print(f"Symbol: {sym}, Quote: {mkt.get('quote')}, Type: {mkt.get('type')}, Active: {mkt.get('active')}")
    count += 1
    if count >= 10:
        break

# Try get_all_usdt_swap_symbols
symbols = client.get_all_usdt_swap_symbols()
print(f"Total USDT swap symbols: {len(symbols)}")
if symbols:
    print(f"First 10 USDT swap symbols: {symbols[:10]}")
