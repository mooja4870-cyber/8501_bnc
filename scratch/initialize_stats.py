import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import QuantumEngine
import core.stats as stats_store

def main():
    load_dotenv(override=True)
    engine = QuantumEngine()
    
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    passphrase = os.getenv("BINANCE_PASSPHRASE", "")
    
    if not api_key or not secret_key:
        print("Error: BINANCE_API_KEY or BINANCE_SECRET_KEY not found in .env")
        sys.exit(1)
        
    print("Connecting to Binance Exchange...")
    success, msg = engine.initialize(api_key, secret_key, passphrase)
    if not success:
        print(f"Failed to connect: {msg}")
        sys.exit(1)
        
    print("Connected successfully. Fetching dashboard data...")
    dash = engine.get_dashboard_data()
    total_balance = dash.get("total_balance", 0.0)
    print(f"Current Total Balance: {total_balance} USDT")
    
    if total_balance <= 0:
        print("Warning: Total balance is 0 or negative. Using default 30.0 USDT")
        total_balance = 30.0
        
    print("Resetting stats with current total balance and current KST time...")
    stats_store.reset_stats(total_balance)
    
    # Reload stats to confirm
    new_stats = stats_store.load_stats()
    print("New Stats.json Content:")
    import json
    print(json.dumps(new_stats, indent=2, ensure_ascii=False))
    print("Stats initialized successfully!")

if __name__ == "__main__":
    main()
