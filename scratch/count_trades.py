import pickle
import pandas as pd
import numpy as np
import os
import sys

sys.path.append(os.getcwd())
from scratch.dl_parameter_optimizer import calculate_indicators_vectorized

# Load data and best parameters
with open("data/candles_cache.pkl", "rb") as f:
    data_dict = pickle.load(f)
with open("scratch/best_params.pkl", "rb") as f:
    best_res = pickle.load(f)
    
p = best_res['params']
print("Parameters:", p)

# Extract params
leverage = int(p['LEVERAGE'])
margin_usdt = float(p['MARGIN_USDT'])
max_positions = int(p['MAX_POSITIONS'])
sl_pct = float(p['STOP_LOSS_PCT'])
tp_pct = float(p['TAKE_PROFIT_PCT'])
ts_activate = float(p['TRAILING_ACTIVATE_PCT'])
ts_callback = float(p['TRAILING_CALLBACK_PCT'])
max_dd_limit = float(p['MAX_DRAWDOWN_PCT'])
allow_long = bool(p['ALLOW_LONG'])
allow_short = bool(p['ALLOW_SHORT'])
timeframe = p['TIMEFRAME']

ema_period = int(p['EMA_PERIOD'])
bb_period = int(p['BB_PERIOD'])
bb_std = float(p['BB_STD'])
rsi_period = int(p['RSI_PERIOD'])
rsi_oversold = float(p['RSI_OVERSOLD'])
rsi_overbought = float(p['RSI_OVERBOUGHT'])

macd_fast, macd_slow, macd_signal = 12, 26, 9
ssl_period = 10
price_bb_period, price_bb_std = 20, 2.0

tf_data = data_dict.get(timeframe, {})

# Process indicators
processed_dfs = {}
for symbol, df in tf_data.items():
    pdf = calculate_indicators_vectorized(
        df, ema_period, bb_period, bb_std, macd_fast, macd_slow, macd_signal, 
        ssl_period, rsi_period, price_bb_period, price_bb_std
    )
    if not pdf.empty:
        latest_ts = pdf.index[-1]
        cutoff_time = latest_ts - pd.Timedelta(days=30)
        pdf_sliced = pdf.loc[pdf.index >= cutoff_time]
        if not pdf_sliced.empty:
            processed_dfs[symbol] = pdf_sliced

all_timestamps = sorted(list(set().union(*(df.index for df in processed_dfs.values()))))

# Align each symbol's DataFrame to all_timestamps and extract as numpy arrays
symbol_data = {}
for symbol, df in processed_dfs.items():
    adf = df.reindex(all_timestamps)
    symbol_data[symbol] = {
        'close': adf['close'].to_numpy(),
        'high': adf['high'].to_numpy(),
        'low': adf['low'].to_numpy(),
        'ssl_up': adf['ssl_up'].to_numpy(),
        'ssl_down': adf['ssl_down'].to_numpy(),
        'candle_color_blue': (adf['candle_color'] == 'blue').to_numpy(),
        'macd_hist': adf['macd_hist'].to_numpy(),
        'dot_color': adf['dot_color'].to_numpy(),
        'rsi': adf['rsi'].to_numpy(),
        'ema_trend': adf['ema_trend'].to_numpy(),
        'has_data': (~adf['close'].isna()).to_numpy()
    }

# Portfolio State
initial_balance = 1000.0
balance = initial_balance
positions = {}

wins = 0
losses = 0
total_long_entries = 0
total_short_entries = 0
max_drawdown = 0.0
peak = initial_balance

# Track per-symbol entry counts
symbol_entries = {}

for t_idx, ts in enumerate(all_timestamps):
    current_equity = balance
    closed_symbols = []
    
    for symbol, pos in list(positions.items()):
        sdata = symbol_data[symbol]
        if not sdata['has_data'][t_idx]:
            continue
        curr_close = sdata['close'][t_idx]
        curr_high = sdata['high'][t_idx]
        curr_low = sdata['low'][t_idx]
        
        entry_price = pos['entry_price']
        side = pos['side']
        pos_margin = pos['margin']
        
        if side == 'long':
            price_pct = (curr_close - entry_price) / entry_price
            unrealized_pnl = pos_margin * price_pct * leverage
            high_pct = (curr_high - entry_price) / entry_price
            low_pct = (curr_low - entry_price) / entry_price
            
            if high_pct >= ts_activate:
                pos['ts_active'] = True
                new_peak = entry_price * (1 + high_pct)
                pos['ts_peak'] = max(pos['ts_peak'], new_peak)
                
            if low_pct <= -sl_pct:
                realized_pnl = -pos_margin * sl_pct * leverage
                balance += realized_pnl
                losses += 1
                closed_symbols.append(symbol)
            elif pos['ts_active'] and curr_low <= pos['ts_peak'] * (1 - ts_callback):
                exit_price = pos['ts_peak'] * (1 - ts_callback)
                real_pct = (exit_price - entry_price) / entry_price
                realized_pnl = pos_margin * real_pct * leverage
                balance += realized_pnl
                if realized_pnl > 0: wins += 1
                else: losses += 1
                closed_symbols.append(symbol)
            elif high_pct >= tp_pct:
                realized_pnl = pos_margin * tp_pct * leverage
                balance += realized_pnl
                wins += 1
                closed_symbols.append(symbol)
        else: # short
            price_pct = (entry_price - curr_close) / entry_price
            unrealized_pnl = pos_margin * price_pct * leverage
            high_pct = (entry_price - curr_low) / entry_price
            low_pct = (entry_price - curr_high) / entry_price
            
            if high_pct >= ts_activate:
                pos['ts_active'] = True
                new_peak = entry_price * (1 - high_pct)
                pos['ts_peak'] = min(pos['ts_peak'], new_peak)
                
            if low_pct <= -sl_pct:
                realized_pnl = -pos_margin * sl_pct * leverage
                balance += realized_pnl
                losses += 1
                closed_symbols.append(symbol)
            elif pos['ts_active'] and curr_high >= pos['ts_peak'] * (1 + ts_callback):
                exit_price = pos['ts_peak'] * (1 + ts_callback)
                real_pct = (entry_price - exit_price) / entry_price
                realized_pnl = pos_margin * real_pct * leverage
                balance += realized_pnl
                if realized_pnl > 0: wins += 1
                else: losses += 1
                closed_symbols.append(symbol)
            elif high_pct >= tp_pct:
                realized_pnl = pos_margin * tp_pct * leverage
                balance += realized_pnl
                wins += 1
                closed_symbols.append(symbol)
                
        if symbol not in closed_symbols:
            current_equity += unrealized_pnl
            
    for sym in closed_symbols:
        del positions[sym]
        
    if current_equity > peak:
        peak = current_equity
    dd = (peak - current_equity) / peak
    if dd > max_drawdown:
        max_drawdown = dd
        
    if max_drawdown >= max_dd_limit:
        balance = current_equity
        break
        
    if len(positions) >= max_positions:
        continue
        
    for symbol, sdata in symbol_data.items():
        if symbol in positions:
            continue
        if not sdata['has_data'][t_idx]:
            continue
        if t_idx < 1:
            continue
            
        close_p = sdata['close'][t_idx]
        
        # Entry Conditions
        cond_long_1 = close_p > sdata['ssl_up'][t_idx]
        cond_long_2 = sdata['candle_color_blue'][t_idx]
        cond_long_3 = sdata['macd_hist'][t_idx] > 0
        cond_long_4 = sdata['dot_color'][t_idx - 1] == 'red' and sdata['dot_color'][t_idx] == 'green'
        cond_long_rsi = sdata['rsi'][t_idx] < rsi_overbought
        cond_long_ema = close_p > sdata['ema_trend'][t_idx]
        
        cond_short_1 = close_p < sdata['ssl_down'][t_idx]
        cond_short_2 = not sdata['candle_color_blue'][t_idx]
        cond_short_3 = sdata['macd_hist'][t_idx] < 0
        cond_short_4 = sdata['dot_color'][t_idx - 1] == 'green' and sdata['dot_color'][t_idx] == 'red'
        cond_short_rsi = sdata['rsi'][t_idx] > rsi_oversold
        cond_short_ema = close_p < sdata['ema_trend'][t_idx]
        
        long_trigger = cond_long_1 and cond_long_2 and cond_long_3 and cond_long_4 and cond_long_rsi and cond_long_ema and allow_long
        short_trigger = cond_short_1 and cond_short_2 and cond_short_3 and cond_short_4 and cond_short_rsi and cond_short_ema and allow_short
        
        if (long_trigger or short_trigger) and len(positions) < max_positions:
            if balance >= margin_usdt:
                positions[symbol] = {
                    "side": "long" if long_trigger else "short",
                    "entry_price": close_p,
                    "margin": margin_usdt,
                    "ts_active": False,
                    "ts_peak": close_p
                }
                symbol_entries[symbol] = symbol_entries.get(symbol, 0) + 1
                if long_trigger:
                    total_long_entries += 1
                else:
                    total_short_entries += 1

print("\n--- RESULTS ---")
print(f"Total Long Entries: {total_long_entries}")
print(f"Total Short Entries: {total_short_entries}")
print(f"Total Trades: {total_long_entries + total_short_entries}")
print(f"Wins: {wins}, Losses: {losses}")
print("Entries per symbol:")
for sym, count in sorted(symbol_entries.items(), key=lambda x: x[1], reverse=True):
    print(f"  {sym}: {count}")
