import sys
import os
import time
from dotenv import load_dotenv
import logging
import pandas as pd

# Ensure the core module can be imported
sys.path.append(os.getcwd())

from core.engine import QuantumEngine
from core.config import CFG

def diagnose():
    load_dotenv(override=True)
    ak = os.getenv("BINANCE_API_KEY")
    sk = os.getenv("BINANCE_SECRET_KEY")
    pw = ""
    
    # Configure logging to warnings only
    logging.basicConfig(level=logging.WARNING)
    
    engine = QuantumEngine()
    success, msg = engine.initialize(ak, sk, pw)
    if not success:
        print(f"Failed to initialize: {msg}")
        return

    print("Running deep diagnostics scan on 80 pairs...")
    
    # Start scanner and force running state
    engine.scanner._running = True
    
    import asyncio
    future = asyncio.run_coroutine_threadsafe(engine.scanner._run_once(), engine._loop)
    future.result() # Wait for scan to finish

    results = engine.scanner.scan_results
    print(f"\nScan completed. Total pairs analyzed: {len(results)}")
    
    # Let's do a deep dive into each pair's historical candles to see if there were any squeeze releases recently
    print("\n--- Squeeze Release & Filter Diagnosis (Last 20 bars / 5 hours) ---")
    print(f"{'Symbol':<15} | {'Squeeze Fired':<15} | {'Trend/Mom/Candle':<16} | {'RSI':<6} | {'Status under 60/40':<18} | {'Status under 75/25':<18}")
    print("-" * 100)
    
    found_recent_fired = 0
    
    for res in results[:40]: # Analyze top 40 pairs by volume
        sym = res["symbol"]
        df = engine.scanner._ohlcv_cache.get(sym)
        if df is None or df.empty:
            continue
            
        # Calculate TTM indicators
        df_ind = engine.scanner.strategy.calculate_indicators(df)
        if df_ind.empty or len(df_ind) < 25:
            continue
            
        # Look back last 20 candles
        for lookback in range(1, 21):
            if len(df_ind) < lookback + 1:
                break
            curr = df_ind.iloc[-lookback]
            prev = df_ind.iloc[-(lookback + 1)]
            
            # Squeeze Fired check: ON -> OFF transition
            squeeze_fired = False
            if 'squeeze_on' in curr:
                if prev['squeeze_on'] and not curr['squeeze_on']:
                    squeeze_fired = True
            else:
                if prev['dot_color'] == 'red' and curr['dot_color'] == 'green':
                    squeeze_fired = True
                    
            if squeeze_fired:
                found_recent_fired += 1
                close = curr['close']
                ema200_val = curr.get('ema200', None)
                ssl_up = curr.get('ssl_up', 0.0)
                ssl_down = curr.get('ssl_down', float('inf'))
                
                if ema200_val is None:
                    cond_long_trend = (close > ssl_up)
                    cond_short_trend = (close < ssl_down)
                else:
                    cond_long_trend = (close > ema200_val) and (close > ssl_up)
                    cond_short_trend = (close < ema200_val) and (close < ssl_down)
                    
                macd_hist = curr['macd_hist']
                cond_long_mom = macd_hist > 0
                cond_short_mom = macd_hist < 0
                
                candle_color_val = curr.get('candle_color', '')
                cond_long_candle = (candle_color_val == 'blue')
                cond_short_candle = (candle_color_val == 'red')
                
                rsi_val = curr.get('rsi', 50.0)
                
                direction = "none"
                trend_ok = False
                mom_ok = False
                candle_ok = False
                
                if cond_long_trend and cond_long_mom and cond_long_candle:
                    direction = "long"
                    trend_ok, mom_ok, candle_ok = True, True, True
                elif cond_short_trend and cond_short_mom and cond_short_candle:
                    direction = "short"
                    trend_ok, mom_ok, candle_ok = True, True, True
                else:
                    # Let's find what was missing
                    if direction == "none":
                        if macd_hist > 0:
                            trend_ok = cond_long_trend
                            mom_ok = cond_long_mom
                            candle_ok = cond_long_candle
                        else:
                            trend_ok = cond_short_trend
                            mom_ok = cond_short_mom
                            candle_ok = cond_short_candle
                
                # Check status under 60/40
                status_60_40 = "No Signal"
                if direction == "long":
                    if rsi_val < 60.0:
                        status_60_40 = "Passed & Entered" if lookback <= 5 else "Passed (but >5 bars)"
                    else:
                        status_60_40 = "Blocked by RSI (>60)"
                elif direction == "short":
                    if rsi_val > 40.0:
                        status_60_40 = "Passed & Entered" if lookback <= 5 else "Passed (but >5 bars)"
                    else:
                        status_60_40 = "Blocked by RSI (<40)"
                else:
                    details = []
                    if not trend_ok: details.append("Trend")
                    if not mom_ok: details.append("Mom")
                    if not candle_ok: details.append("Candle")
                    status_60_40 = f"Missed {','.join(details)}"
                    
                # Check status under 75/25
                status_75_25 = "No Signal"
                if direction == "long":
                    if rsi_val < 75.0:
                        status_75_25 = "Passed & Entered" if lookback <= 5 else "Passed (but >5 bars)"
                    else:
                        status_75_25 = "Blocked by RSI (>75)"
                elif direction == "short":
                    if rsi_val > 25.0:
                        status_75_25 = "Passed & Entered" if lookback <= 5 else "Passed (but >5 bars)"
                    else:
                        status_75_25 = "Blocked by RSI (<25)"
                else:
                    details = []
                    if not trend_ok: details.append("Trend")
                    if not mom_ok: details.append("Mom")
                    if not candle_ok: details.append("Candle")
                    status_75_25 = f"Missed {','.join(details)}"
                
                time_ago = f"{lookback} bars ago"
                indicators_str = "OK" if direction != "none" else f"Fail ({'T' if trend_ok else 't'}{'M' if mom_ok else 'm'}{'C' if candle_ok else 'c'})"
                print(f"{sym:<15} | {time_ago:<15} | {indicators_str:<16} | {rsi_val:4.1f}   | {status_60_40:<18} | {status_75_25:<18}")
                break # Only show the most recent squeeze release for each symbol
                
    if found_recent_fired == 0:
        print("\n[INFO] No squeeze releases (Fired) detected in the last 20 candles for any of the analyzed symbols.")
        
    # Print general market state
    print("\n--- Current Market Squeeze State (Right Now) ---")
    squeeze_on_count = 0
    squeeze_off_count = 0
    for res in results:
        sym = res["symbol"]
        df = engine.scanner._ohlcv_cache.get(sym)
        if df is not None and not df.empty:
            df_ind = engine.scanner.strategy.calculate_indicators(df)
            if not df_ind.empty:
                is_squeezed = df_ind.iloc[-1].get('squeeze_on', False)
                if is_squeezed:
                    squeeze_on_count += 1
                else:
                    squeeze_off_count += 1
                    
    print(f"Total Squeezed pairs (Energy Accumulating): {squeeze_on_count} / {len(results)}")
    print(f"Total Released pairs (Trending/No Squeeze): {squeeze_off_count} / {len(results)}")

if __name__ == "__main__":
    diagnose()
