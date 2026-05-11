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

def analyze_margin():
    try:
        print(f"--- [Margin Deep Analysis] ---")
        
        # 1. Detailed Balance
        bal = exchange.fetch_balance({"type": "swap"})
        usdt = bal.get("USDT", {})
        print(f"Equity (Total): {usdt.get('total', 0)}")
        print(f"Free Margin (Available): {usdt.get('free', 0)}")
        print(f"Used Margin (Locked): {usdt.get('used', 0)}")
        
        # OKX specific info
        info = usdt.get('info', {})
        print(f"OKX Raw Used Margin (imr): {info.get('imr', 0)}") # Initial Margin Requirement
        print(f"OKX Raw Maint Margin (mmr): {info.get('mmr', 0)}") # Maintenance Margin Requirement
        print(f"OKX Order Margin (ordFrozen): {info.get('ordFrozen', 0)}") # Frozen by orders

        # 2. Open Positions
        positions = exchange.fetch_positions()
        active = [p for p in positions if float(p.get('contracts', 0) or 0) > 0]
        print(f"\n--- Active Positions ({len(active)}) ---")
        for p in active:
            print(f"[{p['symbol']}] {p['side'].upper()} | Margin: {p.get('initialMargin', 0)} | Maint: {p.get('maintMargin', 0)}")

        # 3. Open Orders (The potential culprit)
        print("\n--- Open Orders (Potential Margin Locks) ---")
        orders = exchange.fetch_open_orders()
        for o in orders:
            # Check if it's reduce-only
            params = o.get('info', {})
            reduce_only = params.get('reduceOnly', 'false')
            print(f"[{o['symbol']}] {o['type'].upper()} {o['side'].upper()} | Price: {o['price']} | Amount: {o['amount']} | ReduceOnly: {reduce_only}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_margin()
