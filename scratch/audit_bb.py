import os
import sys
import pandas as pd
from dotenv import load_dotenv

# 프로젝트 경로 추가
sys.path.append(os.path.abspath('.'))

from core.exchange import OKXClient
from core.strategy import StrategyEngine
from core.config import CFG

def analyze_bb_conditions(symbol="BTC/USDT:USDT"):
    load_dotenv()
    client = OKXClient()
    ak = os.getenv("OKX_API_KEY")
    sk = os.getenv("OKX_SECRET_KEY")
    pw = os.getenv("OKX_PASSPHRASE")
    
    if not (ak and sk and pw):
        print("API keys not found")
        return

    client.initialize(ak, sk, pw)
    print(f"Analyzing {symbol}...")
    
    df = client.get_ohlcv(symbol, timeframe="1h", limit=100)
    if df.empty:
        print("No data")
        return
    
    engine = StrategyEngine()
    df_with_ind = engine.calculate_indicators(df)
    
    # 최근 20개 캔들에 대해 BB 조건 체크
    print("\n[BB Condition Audit - Last 20 Candles]")
    print(f"{'Time':<20} | {'Close':<10} | {'BB_Lower':<10} | {'Touch?':<7} | {'Recover?':<8} | {'Result'}")
    print("-" * 80)
    
    for i in range(len(df_with_ind) - 20, len(df_with_ind)):
        cur = df_with_ind.iloc[i]
        prev = df_with_ind.iloc[i-1]
        prev2 = df_with_ind.iloc[i-2]
        
        # 현재 로직: Close 기준
        touched = (prev["close"] <= prev["bb_lower"] or prev2["close"] <= prev2["bb_lower"])
        recovered = cur["close"] > cur["bb_lower"]
        bb_ok = touched and recovered
        
        # 대안 로직: Low 기준
        low_touched = (prev["low"] <= prev["bb_lower"] or prev2["low"] <= prev2["bb_lower"])
        
        ts = cur.name.strftime("%Y-%m-%d %H:%M")
        print(f"{ts:<20} | {cur['close']:<10.2f} | {cur['bb_lower']:<10.2f} | {str(touched):<7} | {str(recovered):<8} | {'✅ OK' if bb_ok else '❌ NO'} (Low_Touch: {low_touched})")

if __name__ == "__main__":
    analyze_bb_conditions()
