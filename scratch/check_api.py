import os
import sys
from dotenv import load_dotenv
import ccxt

# Add workspace root to python path
sys.path.append(os.getcwd())

load_dotenv(override=True)

def check_connection():
    api_key = os.getenv("BINANCE_API_KEY") or os.getenv("OKX_API_KEY", "")
    secret_key = os.getenv("BINANCE_SECRET_KEY") or os.getenv("OKX_SECRET_KEY", "")
    
    print("--- Binance USD-M Futures Connection Test ---")
    print(f"API Key: {api_key[:8]}... if api_key else 'None'")
    print(f"Secret Key: {secret_key[:8]}... if secret_key else 'None'")
    
    if not api_key or not secret_key:
        print("Error: API keys are missing from .env file.")
        return

    exchange = ccxt.binanceusdm({
        "apiKey": api_key,
        "secret": secret_key,
        "options": {
            "adjustForTimeDifference": True,
        },
        "enableRateLimit": True,
    })
    
    try:
        print("Attempting load_markets()...")
        markets = exchange.load_markets()
        print(f"✅ Success! Loaded {len(markets)} markets.")
        
        print("Attempting fetch_balance()...")
        bal = exchange.fetch_balance()
        usdt = bal.get("USDT", {})
        print(f"✅ Success! USDT Balance: Total={usdt.get('total')}, Free={usdt.get('free')}")
        
    except ccxt.RateLimitExceeded as e:
        print(f"[RateLimitExceeded] {e}")
    except ccxt.AuthenticationError as e:
        print(f"[AuthenticationError] {e}")
    except ccxt.ExchangeError as e:
        print(f"[ExchangeError] {e}")
    except Exception as e:
        err_msg = str(e)
        if "banned until" in err_msg:
            # Extract ban time
            try:
                import re
                import datetime
                match = re.search(r"banned until (\d+)", err_msg)
                if match:
                    ban_ts = int(match.group(1))
                    ban_time = datetime.datetime.fromtimestamp(ban_ts / 1000.0)
                    print(f"[IP BAN ACTIVE] Banned until: {ban_time} KST")
            except Exception:
                pass
        print(f"[Error] {type(e).__name__} - {e}")

if __name__ == "__main__":
    check_connection()
