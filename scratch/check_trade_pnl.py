import os
import sys
from dotenv import load_dotenv

# 프로젝트 경로 추가
sys.path.append(os.path.abspath('.'))

from core.exchange import OKXClient

def check_trade_pnl():
    load_dotenv()
    ak = os.getenv("OKX_API_KEY")
    sk = os.getenv("OKX_SECRET_KEY")
    pw = os.getenv("OKX_PASSPHRASE")
    
    client = OKXClient(ak, sk, pw)
    client.load_markets()
    
    print("--- Fetching Recent Trades ---")
    try:
        trades = client.exchange.fetch_my_trades(limit=10)
        for t in trades:
            raw = t.get("info", {})
            side = t.get("side")
            pos_side = raw.get("posSide")
            realized_pnl = raw.get("realizedPnl")
            fee = raw.get("fee")
            print(f"Symbol: {t['symbol']} | Side: {side} | PosSide: {pos_side}")
            print(f"  Realized PnL: {realized_pnl}")
            print(f"  Fee: {fee}")
            print(f"  Raw Info Keys: {list(raw.keys())}")
            print("-" * 30)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_trade_pnl()
