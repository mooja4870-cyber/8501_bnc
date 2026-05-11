import ccxt
import pandas as pd
from datetime import datetime, timedelta
import warnings
import sys

# Force UTF-8 output
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

warnings.filterwarnings("ignore")

# API Keys
api_key = 'fd67e23d-8857-4ef4-9761-39b0b0cd13bd'
secret_key = '57172B2A5F19E6FBF808161AE40BFB00'
passphrase = 'COco@@5454'

exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': secret_key,
    'password': passphrase,
    'options': {'defaultType': 'swap'},
    'enableRateLimit': True,
})

def check_status():
    try:
        print(f"--- [Status Check] ---")
        
        # 1. Balance check
        bal = exchange.fetch_balance({"type": "swap"})
        usdt = bal.get("USDT", {})
        total = usdt.get("total", 0)
        free = usdt.get("free", 0)
        print(f"Total Balance: {total:.4f} USDT")
        print(f"Free Margin: {free:.4f} USDT")

        # 2. Positions check
        positions = exchange.fetch_positions()
        active = [p for p in positions if float(p.get('contracts', 0) or 0) > 0]
        print(f"Active Positions ({len(active)}): {[p['symbol'] for p in active]}")

        # 3. AUCTION check
        sym = "AUCTION/USDT:USDT"
        ticker = exchange.fetch_ticker(sym)
        last = ticker.get('last', 0)
        vol = ticker.get('quoteVolume', 0)
        print(f"AUCTION Current Price: {last}")
        print(f"AUCTION 24h Volume: {vol:,.0f} USDT")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_status()
