import ccxt
import os
from dotenv import load_dotenv
import json

def analyze_positions():
    load_dotenv()
    api_key = os.getenv("OKX_API_KEY")
    secret_key = os.getenv("OKX_SECRET_KEY")
    passphrase = os.getenv("OKX_PASSPHRASE")

    exchange = ccxt.okx({
        "apiKey": api_key,
        "secret": secret_key,
        "password": passphrase,
        "options": {"defaultType": "swap"}
    })

    print("--- Fetching Positions ---")
    positions = exchange.fetch_positions()
    
    for p in positions:
        if float(p.get('contracts', 0) or 0) > 0:
            print(f"\nSymbol: {p.get('symbol')}")
            print(f"Contracts: {p.get('contracts')}")
            print(f"Amount: {p.get('amount')}")
            print(f"Notional (unified): {p.get('notional')}")
            print(f"Mark Price: {p.get('markPrice')}")
            
            raw_info = p.get('info', {})
            print(f"NotionalUsd (raw): {raw_info.get('notionalUsd')}")
            print(f"Pos (raw): {raw_info.get('pos')}")
            
            # Check market info
            market = exchange.market(p['symbol'])
            print(f"Contract Size (market): {market.get('contractSize')}")

if __name__ == "__main__":
    analyze_positions()
