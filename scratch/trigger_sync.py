import asyncio
import os
from dotenv import load_dotenv
from core.engine import QuantumEngine

async def main():
    load_dotenv(override=True)
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    passphrase = os.getenv("BINANCE_PASSPHRASE") or ""
    
    engine = QuantumEngine.get_instance()
    # Wait a bit for loop thread to start
    await asyncio.sleep(0.5)
    
    success, msg = engine.initialize(api_key, secret_key, passphrase)
    print(f"Engine Init: {success}, {msg}")
    if not success:
        return
        
    print("Syncing trades to CSV...")
    sync_count = engine.sync_trades_to_csv()
    print(f"Sync complete. Added {sync_count} new entries.")
    
    # Read the tail of trade_history.csv
    import pandas as pd
    from core.logger import LOG_FILE
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        print("\nLast 5 rows of trade_history.csv:")
        print(df.tail(5).to_string())
        
    # Stop scanner and engine
    engine.stop_scanner()

if __name__ == "__main__":
    asyncio.run(main())
