import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.append(os.getcwd())
from core.exchange import OKXClient
from core.backtest import BacktestEngine
from core.config import CFG

def run_comprehensive_optimization():
    api_key = os.getenv("OKX_API_KEY", "")
    secret_key = os.getenv("OKX_SECRET_KEY", "")
    passphrase = os.getenv("OKX_PASSPHRASE", "")
    client = OKXClient(api_key, secret_key, passphrase)
    engine = BacktestEngine()
    
    categories = {
        "Large-Cap": ["BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP", "XRP-USDT-SWAP", "DOGE-USDT-SWAP"],
        "Mid-Cap": ["ADA-USDT-SWAP", "POL-USDT-SWAP", "DOT-USDT-SWAP", "LINK-USDT-SWAP", "TRX-USDT-SWAP"],
        "Low-Cap": ["PEPE-USDT-SWAP", "SHIB-USDT-SWAP", "BONK-USDT-SWAP", "ORDI-USDT-SWAP", "WIF-USDT-SWAP"]
    }
    
    tp_range = [0.8, 1.0, 1.5, 2.0, 2.5, 3.0]
    sl_range = [0.8, 1.2, 1.5, 2.0, 2.5]
    
    all_results = []
    
    for cat_name, symbols in categories.items():
        print(f"\n[*] Analyzing Category: {cat_name}")
        for symbol in symbols:
            print(f"  [-] Fetching {symbol}...")
            df = client.get_ohlcv(symbol, timeframe='1h', limit=365*24)
            if df.empty: continue
            
            df = engine.strategy.calculate_indicators(df)
            
            for tp in tp_range:
                for sl in sl_range:
                    CFG.TAKE_PROFIT_PCT = tp / 100.0
                    CFG.STOP_LOSS_PCT = sl / 100.0
                    report = engine.run(df, symbol)
                    
                    all_results.append({
                        "Category": cat_name,
                        "Symbol": symbol,
                        "TP (%)": tp,
                        "SL (%)": sl,
                        "PnL (%)": report.total_pnl_pct,
                        "WinRate": report.win_rate,
                        "Trades": report.total_trades,
                        "PF": report.profit_factor
                    })
    
    res_df = pd.DataFrame(all_results)
    res_df.to_csv("scratch/comprehensive_optimization.csv", index=False)
    
    # 카테고리별 최적값 요약
    summary = []
    for cat_name in categories.keys():
        cat_df = res_df[res_df["Category"] == cat_name]
        
        # 현재 설정값 (2.0/1.5) 성과
        current = cat_df[(cat_df["TP (%)"] == 2.0) & (cat_df["SL (%)"] == 1.5)].mean(numeric_only=True)
        
        # 최적 설정값 찾기 (PnL * PF 기준)
        cat_grouped = cat_df.groupby(["TP (%)", "SL (%)"]).mean(numeric_only=True).reset_index()
        cat_grouped["Score"] = cat_grouped["PnL (%)"] * cat_grouped["PF"]
        best = cat_grouped.loc[cat_grouped["Score"].idxmax()]
        
        summary.append({
            "Category": cat_name,
            "Current_PnL": current["PnL (%)"],
            "Current_WinRate": current["WinRate"],
            "Best_TP": best["TP (%)"],
            "Best_SL": best["SL (%)"],
            "Best_PnL": best["PnL (%)"],
            "Best_WinRate": best["WinRate"]
        })
    
    summary_df = pd.DataFrame(summary)
    summary_df.to_csv("scratch/category_summary.csv", index=False)
    print("\n[Analysis Complete] Results saved to scratch/")

if __name__ == "__main__":
    run_comprehensive_optimization()
