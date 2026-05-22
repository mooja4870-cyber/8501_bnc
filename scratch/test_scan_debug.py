import sys
import os
from dotenv import load_dotenv

# Ensure the core module can be imported
sys.path.append(os.getcwd())

from core.exchange import BinanceClient
from core.config import CFG

load_dotenv(override=True)
ak = os.getenv("BINANCE_API_KEY")
sk = os.getenv("BINANCE_SECRET_KEY")

client = BinanceClient(ak, sk)
client.load_markets()

symbols = client.get_all_usdt_swap_symbols()
tickers = client.get_tickers()

print(f"Total USDT swap symbols: {len(symbols)}")
print(f"Total tickers: {len(tickers)}")

# Check key intersection
ticker_keys = set(tickers.keys())
symbol_set = set(symbols)

intersection = ticker_keys.intersection(symbol_set)
print(f"Intersection count: {len(intersection)}")

if len(intersection) == 0:
    print("No matching keys!")
    print(f"Sample symbol keys: {list(symbol_set)[:5]}")
    print(f"Sample ticker keys: {list(ticker_keys)[:5]}")
else:
    # Print volume stats
    matched = list(intersection)[:5]
    for s in matched:
        print(f"Symbol: {s}, Ticker Vol: {tickers[s].get('volume')}")

# Let's debug scanner._run_once logic manually
if CFG.SCAN_TOP_N > 0:
    sorted_syms = sorted(
        symbols,
        key=lambda s: tickers.get(s, {}).get("volume", 0),
        reverse=True
    )
    print(f"Sorted symbols count: {len(sorted_syms)}")
    print(f"Top 5 sorted: {[(s, tickers.get(s, {}).get('volume', 0)) for s in sorted_syms[:5]]}")
    
    # Check scanner filtration
    results = []
    for sym in sorted_syms[:CFG.SCAN_TOP_N]:
        ticker = tickers.get(sym)
        if not ticker:
            continue
        vol = ticker.get("volume", 0)
        if vol < CFG.MIN_VOLUME_USDT:
            print(f"Filtered {sym} due to MIN_VOLUME: {vol} < {CFG.MIN_VOLUME_USDT}")
            continue
        bid = ticker.get("bid", 0)
        ask = ticker.get("ask", 0)
        if bid and ask and ask > 0:
            spread_pct = (ask - bid) / ask * 100
            if spread_pct > CFG.MAX_SPREAD_PCT:
                print(f"Filtered {sym} due to SPREAD: {spread_pct} > {CFG.MAX_SPREAD_PCT}")
                continue
        results.append(sym)
    print(f"After filtration count: {len(results)}")
