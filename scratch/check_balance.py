import os
from dotenv import load_dotenv
from core.exchange import OKXClient

load_dotenv(override=True)

api_key = os.getenv("OKX_API_KEY")
secret = os.getenv("OKX_SECRET_KEY")
password = os.getenv("OKX_PASSPHRASE")

client = OKXClient(api_key, secret, password)
if client.load_markets():
    bal = client.get_balance()
    print("Balance Info:", bal)
else:
    print("Failed to load markets")
