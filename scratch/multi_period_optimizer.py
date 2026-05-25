import os
import sys
import time
import pickle
import random
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.getcwd())
from scratch.dl_parameter_optimizer import calculate_indicators_vectorized, MLP, get_random_parameter, parameter_to_vector, vector_to_parameter

CACHE_FILE = os.path.join("data", "candles_cache.pkl")

# Modified portfolio backtest supporting dynamic duration
def run_portfolio_backtest_dynamic(data_dict, p, duration_td):
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
    if not tf_data:
        return 0.0, 0.0, 0.0, 0, 0, 0  # return metrics + counts
        
    processed_dfs = {}
    for symbol, df in tf_data.items():
        pdf = calculate_indicators_vectorized(
            df, ema_period, bb_period, bb_std, macd_fast, macd_slow, macd_signal, 
            ssl_period, rsi_period, price_bb_period, price_bb_std
        )
        if not pdf.empty:
            latest_ts = pdf.index[-1]
            cutoff_time = latest_ts - duration_td
            pdf_sliced = pdf.loc[pdf.index >= cutoff_time]
            if not pdf_sliced.empty:
                processed_dfs[symbol] = pdf_sliced
            
    if not processed_dfs:
        return 0.0, 0.0, 0.0, 0, 0, 0
        
    all_timestamps = sorted(list(set().union(*(df.index for df in processed_dfs.values()))))
    # For very short timeframes (e.g. 12h), the timestamps count can be small.
    # Relax constraint from 100 to 2.
    if len(all_timestamps) < 2:
        return 0.0, 0.0, 0.0, 0, 0, 0

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
        
    initial_balance = 1000.0
    balance = initial_balance
    positions = {}
    
    peak = initial_balance
    max_drawdown = 0.0
    
    wins = 0
    losses = 0
    total_long_entries = 0
    total_short_entries = 0
    
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
            else:  # short
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
                    if long_trigger:
                        total_long_entries += 1
                    else:
                        total_short_entries += 1
                        
    net_profit = balance - initial_balance
    net_profit_pct = (net_profit / initial_balance) * 100
    
    if len(all_timestamps) > 2:
        duration_days = (all_timestamps[-1] - all_timestamps[0]).total_seconds() / (24 * 3600)
        daily_return = (net_profit_pct / duration_days) if duration_days > 0.05 else net_profit_pct
    else:
        daily_return = 0.0
        
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0
    total_trades = total_long_entries + total_short_entries
    
    return daily_return, max_drawdown * 100, win_rate, total_long_entries, total_short_entries, total_trades

# Optimize for a single period
def optimize_for_period(data_dict, period_name, duration_td):
    print(f"\n=========================================")
    print(f"  Optimizing for period: {period_name}")
    print(f"=========================================")
    
    # Step 1: Collect training samples (1000 runs)
    print(f"[{period_name}] Phase 1: Sampling 1,000 parameters and running backtests...")
    X_list = []
    y_list = []
    
    start_time = time.time()
    for s in range(1000):
        p = get_random_parameter()
        daily_ret, mdd, winrate, _, _, _ = run_portfolio_backtest_dynamic(data_dict, p, duration_td)
        
        vec = parameter_to_vector(p)
        X_list.append(vec)
        y_list.append([daily_ret, mdd])
        
        if (s + 1) % 250 == 0:
            elapsed = time.time() - start_time
            print(f"  Simulated {s+1}/1000 - Elapsed: {elapsed:.1f}s")
            
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    
    # Normalize
    X_mean = X.mean(axis=0)
    X_std = X.std(axis=0) + 1e-8
    X_norm = (X - X_mean) / X_std
    
    y_mean = y.mean(axis=0)
    y_std = y.std(axis=0) + 1e-8
    y_norm = (y - y_mean) / y_std
    
    # Step 2: Train MLP
    print(f"[{period_name}] Phase 2: Training Neural Network 대리 모델...")
    mlp = MLP(input_dim=19, h1=128, h2=64, output_dim=2)
    mlp.train(X_norm, y_norm, epochs=600, lr=0.003, batch_size=64)
    
    # Evaluate MAE
    predictions = mlp.forward(X_norm) * y_std + y_mean
    mae = np.mean(np.abs(predictions - y), axis=0)
    print(f"  [Model MAE] Daily Return Error: {mae[0]:.4f}%, MDD Error: {mae[1]:.4f}%")
    
    # Step 3: Fast inference on 500,000 combinations
    INFERENCE_SIZE = 500_000
    print(f"[{period_name}] Phase 3: Inferring {INFERENCE_SIZE:,} combinations...")
    inf_X = np.zeros((INFERENCE_SIZE, 19), dtype=np.float32)
    for i in range(INFERENCE_SIZE):
        p = get_random_parameter()
        inf_X[i] = parameter_to_vector(p)
        
    inf_X_norm = (inf_X - X_mean) / X_std
    inf_preds_norm = mlp.forward(inf_X_norm)
    inf_preds = inf_preds_norm * y_std + y_mean
    
    pred_returns = inf_preds[:, 0]
    pred_mdd = inf_preds[:, 1]
    
    # Filter candidates
    satisfied_indices = np.where((pred_returns >= 1.0) & (pred_mdd <= 15.0))[0]
    if len(satisfied_indices) < 20:
        satisfied_indices = np.where((pred_returns >= 0.5) & (pred_mdd <= 20.0))[0]
    if len(satisfied_indices) == 0:
        satisfied_indices = np.argsort(pred_returns)[-100:]
        
    top_indices = satisfied_indices[np.argsort(pred_returns[satisfied_indices])[-50:]]
    
    # Step 4: Verify top candidates in actual backtest
    print(f"[{period_name}] Phase 4: Verifying top candidates...")
    verified_results = []
    
    for idx in top_indices:
        p_vec = inf_X[idx]
        p = vector_to_parameter(p_vec)
        
        daily_ret, mdd, winrate, long_e, short_e, total_e = run_portfolio_backtest_dynamic(data_dict, p, duration_td)
        verified_results.append({
            'params': p,
            'daily_ret': daily_ret,
            'mdd': mdd,
            'winrate': winrate,
            'long_entries': long_e,
            'short_entries': short_e,
            'total_entries': total_e
        })
        
    # Get absolute best candidate
    verified_results = sorted(verified_results, key=lambda x: x['daily_ret'], reverse=True)
    best = verified_results[0]
    print(f"[{period_name}] Optimization Done! Best Return: {best['daily_ret']:.2f}% | MDD: {best['mdd']:.2f}% | Trades: {best['total_entries']}")
    return best

def main():
    print("=" * 80)
    print("  MULTI-PERIOD DEEP LEARNING OPTIMIZATION ENGINE")
    print("=" * 80)
    
    # Load cache data
    if not os.path.exists(CACHE_FILE):
        print(f"[ERR] Cache file not found at {CACHE_FILE}. Please run standard optimizer once to fetch data.")
        return
        
    with open(CACHE_FILE, 'rb') as f:
        data_dict = pickle.load(f)
        
    periods = {
        "30일 (30d)": pd.Timedelta(days=30),
        "15일 (15d)": pd.Timedelta(days=15),
        "7일 (7d)": pd.Timedelta(days=7),
        "48시간 (48h)": pd.Timedelta(hours=48),
        "24시간 (24h)": pd.Timedelta(hours=24),
        "12시간 (12h)": pd.Timedelta(hours=12)
    }
    
    results = {}
    
    for p_name, duration_td in periods.items():
        results[p_name] = optimize_for_period(data_dict, p_name, duration_td)
        
    # Print comparison table in Excel-like format
    print("\n\n" + "=" * 100)
    print("                                   FINAL COMPARISON REPORT")
    print("=" * 100)
    
    # Build markdown table
    header = "| 구분 / 기간 | 30일 (30d) | 15일 (15d) | 7일 (7d) | 48시간 (48h) | 24시간 (24h) | 12시간 (12h) |"
    divider = "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |"
    
    rows = []
    
    # 1. Performance Metrics
    metrics_keys = [
        ('일평균 수익률 (Daily Return)', lambda r: f"{r['daily_ret']:.2f}%"),
        ('최대 낙폭 (Max Drawdown)', lambda r: f"{r['mdd']:.2f}%"),
        ('승률 (Win Rate)', lambda r: f"{r['winrate']:.1f}%"),
        ('총 롱(Long) 진입', lambda r: f"{r['long_entries']}회"),
        ('총 숏(Short) 진입', lambda r: f"{r['short_entries']}회"),
        ('총 진입(거래) 횟수', lambda r: f"{r['total_entries']}회")
    ]
    
    for label, formatter in metrics_keys:
        row_str = f"| **{label}**"
        for p_name in periods.keys():
            row_str += f" | **{formatter(results[p_name])}**"
        row_str += " |"
        rows.append(row_str)
        
    rows.append("| **[19개 파라미터 값]** | | | | | | |")
    
    # 2. 19 parameters
    param_keys = [
        ('LEVERAGE', '레버리지 (LEVERAGE)', lambda v: f"{v}x"),
        ('MARGIN_USDT', '마진 (MARGIN_USDT)', lambda v: f"{v} USDT"),
        ('MAX_POSITIONS', '최대 포지션 (MAX_POSITIONS)', lambda v: f"{v}"),
        ('STOP_LOSS_PCT', '손절 비율 (STOP_LOSS_PCT)', lambda v: f"{v*100:.2f}%"),
        ('TAKE_PROFIT_PCT', '익절 비율 (TAKE_PROFIT_PCT)', lambda v: f"{v*100:.2f}%"),
        ('TRAILING_ACTIVATE_PCT', '트레일링 활성화 (TRAILING_ACTIVATE)', lambda v: f"{v*100:.2f}%"),
        ('TRAILING_CALLBACK_PCT', '트레일링 콜백 (TRAILING_CALLBACK)', lambda v: f"{v*100:.2f}%"),
        ('MAX_DRAWDOWN_PCT', '최대 DD 제한 (MAX_DRAWDOWN)', lambda v: f"{v*100:.1f}%"),
        ('ALLOW_LONG', '롱 진입 허용 (ALLOW_LONG)', lambda v: f"{v}"),
        ('ALLOW_SHORT', '숏 진입 허용 (ALLOW_SHORT)', lambda v: f"{v}"),
        ('TIMEFRAME', '봉 주기 (TIMEFRAME)', lambda v: f"{v}"),
        ('SCAN_INTERVAL_SEC', '스캔 주기 (SCAN_INTERVAL_SEC)', lambda v: f"{v}초"),
        ('MIN_VOLUME_USDT', '최소 거래량 (MIN_VOLUME)', lambda v: f"{v:,} USDT"),
        ('EMA_PERIOD', 'EMA 기간 (EMA_PERIOD)', lambda v: f"{v}"),
        ('BB_PERIOD', 'BB 기간 (BB_PERIOD)', lambda v: f"{v}"),
        ('BB_STD', 'BB 표준편차 (BB_STD)', lambda v: f"{v:.2f}"),
        ('RSI_PERIOD', 'RSI 기간 (RSI_PERIOD)', lambda v: f"{v}"),
        ('RSI_OVERSOLD', 'RSI 과매도 (RSI_OVERSOLD)', lambda v: f"{v:.1f}"),
        ('RSI_OVERBOUGHT', 'RSI 과매수 (RSI_OVERBOUGHT)', lambda v: f"{v:.1f}")
    ]
    
    for key, label, formatter in param_keys:
        row_str = f"| {label}"
        for p_name in periods.keys():
            val = results[p_name]['params'][key]
            row_str += f" | {formatter(val)}"
        row_str += " |"
        rows.append(row_str)
        
    # Print Table
    print(header)
    print(divider)
    for r in rows:
        print(r)
        
    # Save results to pickle for backup
    with open("scratch/multi_period_results.pkl", "wb") as f:
        pickle.dump(results, f)
        
if __name__ == "__main__":
    main()
