from core.exchange import OKXClient
import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv()
client = OKXClient(os.getenv('OKX_API_KEY'), os.getenv('OKX_SECRET_KEY'), os.getenv('OKX_PASSPHRASE'))
client.load_markets()
history = client.get_trade_history(limit=50)
df = pd.DataFrame(history)
df.to_csv('scratch/trade_history_check.csv')
print(df[['symbol', 'type', 'pnl_usdt', 'timestamp']].tail(10))
