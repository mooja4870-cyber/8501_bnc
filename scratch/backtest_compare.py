import sys
import os
import time
import pandas as pd
import numpy as np
from dotenv import load_dotenv
import logging

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure the core module can be imported
sys.path.append(os.getcwd())

from core.exchange import BinanceClient
from core.config import CFG

# Suppress logging noise
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def calculate_indicators(df):
    if len(df) < 220:  # Need enough data for EMA200
        return pd.DataFrame()

    df = df.copy()
    close = df['close']
    
    # 1. MACD
    ema_fast = close.ewm(span=CFG.MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=CFG.MACD_SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=CFG.MACD_SIGNAL, adjust=False).mean()
    histogram = macd_line - signal_line

    # Histogram Bollinger Bands (히스토그램 BB)
    bb_mid = histogram.rolling(CFG.BB_PERIOD).mean()
    bb_std = histogram.rolling(CFG.BB_PERIOD).std()
    bb_upper = bb_mid + (CFG.BB_STD * bb_std)
    bb_lower = bb_mid - (CFG.BB_STD * bb_std)

    dot_color = pd.Series('red', index=df.index)
    dot_color[histogram > histogram.shift(1)] = 'green'

    df['macd_hist'] = histogram
    df['dot_color'] = dot_color
    df['bb_upper'] = bb_upper
    df['bb_lower'] = bb_lower

    # 2. Price Bollinger Bands (가격 BB)
    price_bb_mid = close.rolling(20).mean()
    price_bb_std = close.rolling(20).std()
    df['price_bb_upper'] = price_bb_mid + (2.0 * price_bb_std)
    df['price_bb_lower'] = price_bb_mid - (2.0 * price_bb_std)

    # 3. SSL Hybrid
    high = df['high']
    low = df['low']
    sma_high = high.rolling(CFG.SSL_PERIOD).mean()
    sma_low = low.rolling(CFG.SSL_PERIOD).mean()

    hlv = pd.Series(0, index=df.index)
    hlv[close > sma_high] = 1
    hlv[close < sma_low] = -1
    hlv = hlv.replace(0, np.nan).ffill().fillna(0)

    ssl_down = pd.Series(np.where(hlv < 0, sma_high, sma_low), index=df.index)
    ssl_up = pd.Series(np.where(hlv < 0, sma_low, sma_high), index=df.index)

    df['ssl_up'] = ssl_up
    df['ssl_down'] = ssl_down
    df['candle_color'] = pd.Series(np.where(close > close.shift(1), 'blue', 'red'), index=df.index)

    # Filter indicators
    df['ema200'] = close.ewm(span=200, adjust=False).mean()
    df['volume_sma20'] = df['volume'].rolling(20).mean()
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    return df.dropna()

def simulate_backtest(df_dict, filter_type=None, window_size=192):
    """
    Simulate trades on a specific window (192 for 48h, 672 for 7d)
    """
    total_trades = 0
    wins = 0
    total_pnl = 0.0
    gross_profit = 0.0
    gross_loss = 0.0
    
    tp_pct = CFG.TAKE_PROFIT_PCT 
    sl_pct = CFG.STOP_LOSS_PCT   
    
    for symbol, df in df_dict.items():
        if df.empty or len(df) < window_size:
            continue
            
        test_df = df.tail(window_size)
        indices = test_df.index
        
        in_pos = False
        pos_side = None
        entry_price = 0.0
        tp_price = 0.0
        sl_price = 0.0
        entry_idx = 0
        
        for i in range(len(test_df)):
            curr_idx = indices[i]
            loc_in_full = df.index.get_loc(curr_idx)
            if loc_in_full < 2:
                continue
                
            curr = df.iloc[loc_in_full]
            prev = df.iloc[loc_in_full - 1]
            
            # Position check
            if in_pos:
                close_trade = False
                pnl = 0.0
                bars_held = i - entry_idx
                
                if pos_side == 'long':
                    if curr['low'] <= sl_price:
                        close_trade = True
                        pnl = -sl_pct
                    elif curr['high'] >= tp_price:
                        close_trade = True
                        pnl = tp_pct
                    elif bars_held >= 16:
                        close_trade = True
                        pnl = (curr['close'] - entry_price) / entry_price
                else: # short
                    if curr['high'] >= sl_price:
                        close_trade = True
                        pnl = -sl_pct
                    elif curr['low'] <= tp_price:
                        close_trade = True
                        pnl = tp_pct
                    elif bars_held >= 16:
                        close_trade = True
                        pnl = (entry_price - curr['close']) / entry_price
                
                if close_trade:
                    total_trades += 1
                    total_pnl += pnl
                    if pnl > 0:
                        wins += 1
                        gross_profit += pnl
                    else:
                        gross_loss += abs(pnl)
                    in_pos = False
                continue
                
            # Entry conditions
            cond_long_1 = curr['close'] > curr['ssl_up']
            cond_long_2 = curr['candle_color'] == 'blue'
            cond_long_3 = curr['macd_hist'] > 0
            cond_long_4 = prev['dot_color'] == 'red' and curr['dot_color'] == 'green'
            
            cond_short_1 = curr['close'] < curr['ssl_down']
            cond_short_2 = curr['candle_color'] == 'red'
            cond_short_3 = curr['macd_hist'] < 0
            cond_short_4 = prev['dot_color'] == 'green' and curr['dot_color'] == 'red'
            
            # Base + RSI Filter
            cond_long_1 = cond_long_1 and (curr['rsi'] < 60)
            cond_short_1 = cond_short_1 and (curr['rsi'] > 40)
            
            # Apply additional filters
            if filter_type == 'rsi_ema':
                # Base + RSI + EMA 200
                cond_long_1 = cond_long_1 and (curr['close'] > curr['ema200'])
                cond_short_1 = cond_short_1 and (curr['close'] < curr['ema200'])
                
            elif filter_type == 'rsi_price_bb':
                # Base + RSI + Price BB (과열 상/하한 차단)
                cond_long_1 = cond_long_1 and (curr['close'] < curr['price_bb_upper'])
                cond_short_1 = cond_short_1 and (curr['close'] > curr['price_bb_lower'])
                
            elif filter_type == 'rsi_hist_bb':
                # Base + RSI + Hist BB (MACD 히스토그램 BB 밴드 이내 유지)
                cond_long_1 = cond_long_1 and (curr['macd_hist'] < curr['bb_upper'])
                cond_short_1 = cond_short_1 and (curr['macd_hist'] > curr['bb_lower'])
                
            # Signal Action
            if cond_long_1 and cond_long_2 and cond_long_3 and cond_long_4:
                in_pos = True
                pos_side = 'long'
                entry_price = curr['close']
                tp_price = entry_price * (1 + tp_pct)
                sl_price = entry_price * (1 - sl_pct)
                entry_idx = i
            elif cond_short_1 and cond_short_2 and cond_short_3 and cond_short_4:
                in_pos = True
                pos_side = 'short'
                entry_price = curr['close']
                tp_price = entry_price * (1 - tp_pct)
                sl_price = entry_price * (1 + sl_pct)
                entry_idx = i

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)
    
    return {
        "trades": total_trades,
        "win_rate": win_rate,
        "net_profit_pct": total_pnl * 100,
        "profit_factor": profit_factor
    }

def main():
    load_dotenv(override=True)
    ak = os.getenv("BINANCE_API_KEY")
    sk = os.getenv("BINANCE_SECRET_KEY")
    
    client = BinanceClient(ak, sk)
    if not client.load_markets():
        print("Failed to load markets")
        return
        
    print("Loading exchange tickers...")
    tickers = client.get_tickers()
    symbols = client.get_all_usdt_swap_symbols()
    
    top_symbols = sorted(
        symbols,
        key=lambda s: tickers.get(s, {}).get("volume", 0),
        reverse=True
    )[:CFG.SCAN_TOP_N]
    
    print(f"Fetching 15m candles (900 bars) for top {len(top_symbols)} symbols...")
    df_dict = {}
    
    start_time = time.time()
    for idx, sym in enumerate(top_symbols):
        df = client.get_ohlcv(sym, timeframe="15m", limit=900)
        if not df.empty and len(df) >= 700:
            df_indicators = calculate_indicators(df)
            if not df_indicators.empty:
                df_dict[sym] = df_indicators
        if (idx + 1) % 10 == 0:
            print(f"Progress: {idx+1}/{len(top_symbols)} symbols fetched")
            
    print(f"Data loading complete in {time.time() - start_time:.2f} seconds.")
    print(f"Loaded data for {len(df_dict)} valid symbols.")
    
    print("\n" + "="*80)
    print("최근 48시간 vs 7일간 정밀 비교 시뮬레이션 결과")
    print("익절: 1.5% / 손절: 1.0% / 레버리지: 5배 / 1회 진입: 5 USDT / 시드: 30 USDT")
    print("="*80)
    
    strategies = {
        "Base + RSI + EMA 200 (변합 5)": "rsi_ema",
        "Base + RSI + Price BB (가격 밴드 차단)": "rsi_price_bb",
        "Base + RSI + Hist BB (히스토그램 밴드 차단)": "rsi_hist_bb"
    }
    
    print("\n[ 최근 48시간 (192봉) 결과 ]")
    print(f"{'전략명':<38} | {'총 거래수':<8} | {'승률':<8} | {'누적수익률':<10} | {'수익 팩터'}")
    print("-"*80)
    for name, f_type in strategies.items():
        res = simulate_backtest(df_dict, filter_type=f_type, window_size=192)
        print(f"{name:<38} | {res['trades']:<8d} | {res['win_rate']:<7.1f}% | {res['net_profit_pct']:+8.2f}% | {res['profit_factor']:.2f}")
        
    print("\n[ 최근 7일간 (672봉) 결과 ]")
    print(f"{'전략명':<38} | {'총 거래수':<8} | {'승률':<8} | {'누적수익률':<10} | {'수익 팩터'}")
    print("-"*80)
    for name, f_type in strategies.items():
        res = simulate_backtest(df_dict, filter_type=f_type, window_size=672)
        print(f"{name:<38} | {res['trades']:<8d} | {res['win_rate']:<7.1f}% | {res['net_profit_pct']:+8.2f}% | {res['profit_factor']:.2f}")
        
    print("="*80)

if __name__ == "__main__":
    main()
