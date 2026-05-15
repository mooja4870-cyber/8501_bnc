import os
import sys
import pandas as pd
from datetime import datetime

sys.path.append(os.getcwd())
from core.exchange import OKXClient
from core.config import CFG
from dotenv import load_dotenv

def analyze_actual_trade_counts():
    load_dotenv()
    api_key = os.getenv("OKX_API_KEY", "")
    secret_key = os.getenv("OKX_SECRET_KEY", "")
    passphrase = os.getenv("OKX_PASSPHRASE", "")
    client = OKXClient(api_key, secret_key, passphrase)
    
    print("[*] Fetching actual trade history from OKX...")
    trades = client.get_trade_history(limit=100) # 최근 100건 분석 (OKX v5 제한 준수)
    
    if not trades:
        print("[!] No trade history found.")
        return

    # 청산 건수만 필터링
    closed_trades = [t for t in trades if t["type"] == "청산"]
    
    # 카테고리 정의 (심볼 기반)
    categories = {
        "Large-Cap": ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "DOT", "LINK", "TRX", "AVAX", "BCH"],
        "Mid-Cap": ["MATIC", "POL", "ETC", "NEAR", "FIL", "APT", "ARB", "OP", "STX", "SUI", "LTC", "ICP"],
        "Low-Cap": ["PEPE", "SHIB", "BONK", "ORDI", "WIF", "MEME", "FLOKI", "1000SHIB", "1000PEPE", "BOME"]
    }
    
    stats = {"Large-Cap": 0, "Mid-Cap": 0, "Low-Cap": 0, "Unknown": 0}
    symbol_counts = {}
    
    for t in closed_trades:
        symbol = t["symbol"].split("-")[0]
        symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
        
        found = False
        for cat, list_ in categories.items():
            if symbol in list_:
                stats[cat] += 1
                found = True
                break
        if not found:
            # 리스트에 없으면 거래대금이나 성격상 임시 분류 (여기선 Unknown)
            stats["Unknown"] += 1

    print("\n" + "="*50)
    print("[Actual Trade Statistics - Last 100 entries]")
    print(f"Total Closed Trades: {len(closed_trades)}")
    print("-" * 30)
    for cat, count in stats.items():
        print(f"{cat}: {count} 건")
    print("="*50)
    
    # 상세 종목별 건수
    print("\n[상세 종목별 청산 횟수]")
    sorted_symbols = sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)
    for sym, cnt in sorted_symbols:
        print(f"{sym}: {cnt}회")

if __name__ == "__main__":
    analyze_actual_trade_counts()
