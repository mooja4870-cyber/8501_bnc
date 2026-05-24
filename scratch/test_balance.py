import os
import sys
from dotenv import load_dotenv

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.exchange import BinanceClient

def main():
    load_dotenv(override=True)
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    
    print(f"API Key: {api_key[:10]}...{api_key[-10:] if api_key else ''}")
    print(f"Secret Key: {secret_key[:10]}...{secret_key[-10:] if secret_key else ''}")
    
    try:
        client = BinanceClient(api_key, secret_key)
        client.load_markets()
        balance = client.get_balance()
        print(f"Successfully connected to Binance!")
        print(f"Balance: {balance}")
    except Exception as e:
        print(f"Failed to connect or get balance: {e}")

if __name__ == "__main__":
    main()
