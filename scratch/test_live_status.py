import os
from dotenv import load_dotenv
from core.exchange import BinanceClient

def test_live():
    load_dotenv(override=True)
    api_key = os.getenv("BINANCE_API_KEY")
    secret = os.getenv("BINANCE_SECRET_KEY")
    passphrase = os.getenv("BINANCE_PASSPHRASE") or ""
    
    print("=" * 60)
    print("TESTING LIVE BINANCE CONNECTION...")
    print("=" * 60)
    
    if not api_key or not secret:
        print("Error: API credentials not found in .env")
        return
        
    try:
        client = BinanceClient(api_key, secret, passphrase)
        if client.load_markets():
            print("Successfully loaded exchange markets!")
            
            # Fetch Balance
            bal = client.get_balance()
            print(f"Total Balance: {bal.get('total', 0.0):,.4f} USDT")
            print(f"Free Margin:   {bal.get('free', 0.0):,.4f} USDT")
            print(f"Used Margin:   {bal.get('used', 0.0):,.4f} USDT")
            
            # Fetch Active Positions
            positions = client.get_positions()
            print(f"\nActive Positions Count: {len(positions)}")
            for p in positions:
                print(f"  - Symbol: {p.get('symbol')}, Side: {p.get('side')}, Size: {p.get('amount_usdt')} USDT, UnPnL: {p.get('pnl_usdt')} USDT")
                
            print("\nVerification complete. Exchange connection is healthy!")
        else:
            print("Failed to load exchange markets.")
    except Exception as e:
        print(f"Exception during verification: {e}")

if __name__ == "__main__":
    test_live()
