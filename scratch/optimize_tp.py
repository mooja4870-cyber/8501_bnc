import os
import sys
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

# 프로젝트 루트 경로 추가
sys.path.append(os.getcwd())

from core.exchange import OKXClient
from core.backtest import BacktestEngine
from core.config import CFG

def run_sl_optimization(symbols=["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "XRP-USDT-SWAP", "DOGE-USDT-SWAP"], days=365):
    print(f"[*] Starting Stop Loss optimization (TP fixed at 1.0%)...")
    
    api_key = os.getenv("OKX_API_KEY", "")
    secret_key = os.getenv("OKX_SECRET_KEY", "")
    passphrase = os.getenv("OKX_PASSPHRASE", "")
    client = OKXClient(api_key, secret_key, passphrase)
    engine = BacktestEngine()
    
    # 익절가는 추천값인 1.0%로 고정
    CFG.TAKE_PROFIT_PCT = 0.01 
    sl_range = np.arange(0.5, 3.1, 0.2)
    total_stats = []

    for symbol in symbols:
        print(f"[-] Fetching {symbol} data...")
        df = client.get_ohlcv(symbol, timeframe='1h', limit=days * 24)
        if df.empty: continue
        
        # 전략 지표 계산
        df = engine.strategy.calculate_indicators(df)
        
        for sl in sl_range:
            CFG.STOP_LOSS_PCT = sl / 100.0
            report = engine.run(df, symbol, period_label=f"SL_{sl:.1f}%")
            
            total_stats.append({
                "Symbol": symbol,
                "SL (%)": round(sl, 1),
                "PnL (%)": report.total_pnl_pct,
                "WinRate": report.win_rate,
                "Trades": report.total_trades,
                "MDD (%)": report.max_drawdown_pct,
                "PF": report.profit_factor
            })

    res_df = pd.DataFrame(total_stats)
    if res_df.empty or res_df["Trades"].sum() == 0:
        print("[!] No trades found even in wide scan. Strategy is extremely tight.")
        return None, None

    # 결과 평균화
    avg_res = res_df.groupby("SL (%)").agg({
        "PnL (%)": "mean",
        "WinRate": "mean",
        "Trades": "sum",
        "MDD (%)": "mean",
        "PF": "mean"
    }).reset_index()
    
    # 점수화 (MDD가 낮고 PnL이 높은 지점 찾기)
    avg_res["Score"] = (avg_res["PnL (%)"] * 0.6) - (avg_res["MDD (%)"] * 0.4) + (avg_res["PF"] * 5)
    best_row = avg_res.loc[avg_res["Score"].idxmax()]
    
    print("\n" + "="*50)
    print(f"[Final Result] Recommended Optimal SL: {best_row['SL (%)']}%")
    print(f"[Final Result] Average PnL: {best_row['PnL (%)']:.2f}%")
    print(f"[Final Result] Average MDD: {best_row['MDD (%)']:.2f}%")
    print("="*50)
    
    res_df.to_csv("scratch/sl_optimization_results.csv", index=False)
    return avg_res, best_row

if __name__ == "__main__":
    res_df, best_row = run_sl_optimization()
