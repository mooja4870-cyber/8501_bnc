import os
import sys
import time
import pickle
import random
import logging
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.getcwd())

from core.exchange import BinanceClient
from core.config import CFG

# Suppress ccxt and connection logs
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join("data", "candles_cache.pkl")
TOP_N_SYMBOLS = 20  # Limit symbols for faster simulation and API safety

# 30 days of data + 300 candles warm-up buffer for indicators
CANDLE_LIMIT_MAP = {
    "15m": 3180,  # 30 days * 96 + 300 buffer
    "30m": 1740,  # 30 days * 48 + 300 buffer
    "1h": 1020,   # 30 days * 24 + 300 buffer
    "4h": 480     # 30 days * 6 + 300 buffer
}

# Parameter ranges
TIMEFRAME_MAP = {0: "15m", 1: "30m", 2: "1h", 3: "4h"}
TIMEFRAME_REV = {"15m": 0, "30m": 1, "1h": 2, "4h": 3}

# Helper: EWM calculator
def get_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

# ── 1. 데이터 수집 및 캐싱 ──────────────────────────
def get_data_client():
    load_dotenv(override=True)
    ak = os.getenv("BINANCE_API_KEY") or os.getenv("OKX_API_KEY")
    sk = os.getenv("BINANCE_SECRET_KEY") or os.getenv("OKX_SECRET_KEY")
    pw = os.getenv("BINANCE_PASSPHRASE") or os.getenv("OKX_PASSPHRASE") or ""
    if not ak or not sk:
        print("[ERR] API keys not found in .env. Cannot download data.")
        return None
    return BinanceClient(ak, sk, pw)

def download_and_cache_data():
    if os.path.exists(CACHE_FILE):
        print(f"[CACHE] Found cached candle data at {CACHE_FILE}. Loading...")
        with open(CACHE_FILE, 'rb') as f:
            return pickle.load(f)
            
    print("[DOWNLOAD] Cache not found. Fetching historical candles from exchange...")
    client = get_data_client()
    if not client or not client.load_markets():
        raise RuntimeError("Exchange client load failed. Make sure .env has valid keys.")
        
    tickers = client.get_tickers()
    symbols = client.get_all_usdt_swap_symbols()
    
    # Sort symbols by volume
    top_symbols = sorted(
        symbols,
        key=lambda s: tickers.get(s, {}).get("volume", 0),
        reverse=True
    )[:TOP_N_SYMBOLS]
    
    data_dict = {}
    timeframes = ["15m", "30m", "1h", "4h"]
    
    for tf in timeframes:
        data_dict[tf] = {}
        limit = CANDLE_LIMIT_MAP[tf]
        print(f"[DOWNLOAD] Fetching {limit} candles for timeframe: {tf} ...")
        for idx, sym in enumerate(top_symbols):
            try:
                df = client.get_ohlcv(sym, timeframe=tf, limit=limit)
                if not df.empty and len(df) >= 250:
                    data_dict[tf][sym] = df
            except Exception as e:
                print(f"[ERR] Failed to download {sym} on {tf}: {e}")
            if (idx + 1) % 5 == 0:
                print(f"  Progress: {idx+1}/{len(top_symbols)} symbols fetched")
            time.sleep(0.1)
            
    # Save cache
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump(data_dict, f)
    print(f"[CACHE] Download complete. Cached data saved to {CACHE_FILE}")
    return data_dict

# ── 2. 지표 계산 및 백테스트 시뮬레이터 ─────────────────
def calculate_indicators_vectorized(df, ema_period, bb_period, bb_std, macd_fast, macd_slow, macd_signal, ssl_period, rsi_period, price_bb_period, price_bb_std):
    if len(df) < max(220, ema_period, bb_period, macd_slow, ssl_period, rsi_period, price_bb_period):
        return pd.DataFrame()
        
    df = df.copy()
    close = df['close']
    high = df['high']
    low = df['low']
    
    # 1. MACD & BB on MACD Hist
    ema_f = get_ema(close, macd_fast)
    ema_s = get_ema(close, macd_slow)
    macd_line = ema_f - ema_s
    signal_line = get_ema(macd_line, macd_signal)
    histogram = macd_line - signal_line
    
    bb_mid = histogram.rolling(bb_period).mean()
    bb_std_val = histogram.rolling(bb_period).std()
    bb_upper = bb_mid + (bb_std * bb_std_val)
    bb_lower = bb_mid - (bb_std * bb_std_val)
    
    dot_color = np.where(histogram > histogram.shift(1), 'green', 'red')
    
    df['macd_hist'] = histogram
    df['bb_upper'] = bb_upper
    df['bb_lower'] = bb_lower
    df['dot_color'] = dot_color
    
    # 2. SSL Hybrid
    sma_high = high.rolling(ssl_period).mean()
    sma_low = low.rolling(ssl_period).mean()
    
    hlv = pd.Series(0, index=df.index)
    hlv[close > sma_high] = 1
    hlv[close < sma_low] = -1
    hlv = hlv.replace(0, np.nan).ffill().fillna(0)
    
    ssl_down = np.where(hlv < 0, sma_high, sma_low)
    ssl_up = np.where(hlv < 0, sma_low, sma_high)
    df['ssl_up'] = ssl_up
    df['ssl_down'] = ssl_down
    df['candle_color'] = np.where(close > close.shift(1), 'blue', 'red')
    
    # 3. EMA 200/EMA trend
    df['ema_trend'] = get_ema(close, ema_period)
    
    # 4. RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(rsi_period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
    rs = gain / (loss.replace(0, 1e-6))
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # 5. Price BB
    price_bb_mid = close.rolling(price_bb_period).mean()
    price_bb_std_val = close.rolling(price_bb_period).std()
    df['price_bb_upper'] = price_bb_mid + (price_bb_std * price_bb_std_val)
    df['price_bb_lower'] = price_bb_mid - (price_bb_std * price_bb_std_val)
    
    return df.dropna()

def run_portfolio_backtest(data_dict, p):
    """
    Runs portfolio simulation on given parameter dictionary
    """
    # 1. Extract params
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
    
    # Indicators
    ema_period = int(p['EMA_PERIOD'])
    bb_period = int(p['BB_PERIOD'])
    bb_std = float(p['BB_STD'])
    rsi_period = int(p['RSI_PERIOD'])
    rsi_oversold = float(p['RSI_OVERSOLD'])
    rsi_overbought = float(p['RSI_OVERBOUGHT'])
    
    # Defaults not searched deeply but set
    macd_fast, macd_slow, macd_signal = 12, 26, 9
    ssl_period = 10
    price_bb_period, price_bb_std = 20, 2.0
    
    tf_data = data_dict.get(timeframe, {})
    if not tf_data:
        return 0.0, 0.0, 0.0  # Daily Return, MDD, Win rate
        
    # Calculate indicators for each symbol
    processed_dfs = {}
    for symbol, df in tf_data.items():
        pdf = calculate_indicators_vectorized(
            df, ema_period, bb_period, bb_std, macd_fast, macd_slow, macd_signal, 
            ssl_period, rsi_period, price_bb_period, price_bb_std
        )
        if not pdf.empty:
            # We slice the indicators to only simulate the last 30 days.
            # This ensures indicators have the necessary warm-up data but the trading simulation
            # runs strictly on the last 30 days.
            latest_ts = pdf.index[-1]
            cutoff_time = latest_ts - pd.Timedelta(days=30)
            pdf_sliced = pdf.loc[pdf.index >= cutoff_time]
            if not pdf_sliced.empty:
                processed_dfs[symbol] = pdf_sliced
            
    if not processed_dfs:
        return 0.0, 0.0, 0.0
        
    # Get common timeline (aligned index timestamps)
    all_timestamps = sorted(list(set().union(*(df.index for df in processed_dfs.values()))))
    if len(all_timestamps) < 100:
        return 0.0, 0.0, 0.0

    # Build optimized lookups
    # Align each symbol's DataFrame to all_timestamps and extract as numpy arrays
    symbol_data = {}
    for symbol, df in processed_dfs.items():
        adf = df.reindex(all_timestamps)
        # Using .to_numpy() is extremely fast and avoids pandas overhead in the loop
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
    positions = {}  # symbol -> position dict
    
    # Equity curve for MDD tracking
    peak = initial_balance
    max_drawdown = 0.0
    
    wins = 0
    losses = 0
    
    for t_idx, ts in enumerate(all_timestamps):
        # 1. Update active positions (Mark-to-market and SL/TP hits)
        current_equity = balance
        closed_symbols = []
        
        for symbol, pos in list(positions.items()):
            sdata = symbol_data[symbol]
            if not sdata['has_data'][t_idx]:
                continue
            curr_close = sdata['close'][t_idx]
            curr_high = sdata['high'][t_idx]
            curr_low = sdata['low'][t_idx]
            
            # Position unrealized PnL
            entry_price = pos['entry_price']
            side = pos['side']
            pos_margin = pos['margin']
            
            # Calculate price movement PnL
            if side == 'long':
                price_pct = (curr_close - entry_price) / entry_price
                unrealized_pnl = pos_margin * price_pct * leverage
                # High/Low check for Stop Loss & Take Profit
                high_pct = (curr_high - entry_price) / entry_price
                low_pct = (curr_low - entry_price) / entry_price
                
                # Check Trailing Stop activation
                if high_pct >= ts_activate:
                    pos['ts_active'] = True
                    # Update trailing peak
                    new_peak = entry_price * (1 + high_pct)
                    pos['ts_peak'] = max(pos['ts_peak'], new_peak)
                    
                # Exit Checks
                if low_pct <= -sl_pct:
                    # Stop loss
                    realized_pnl = -pos_margin * sl_pct * leverage
                    balance += realized_pnl
                    losses += 1
                    closed_symbols.append(symbol)
                elif pos['ts_active'] and curr_low <= pos['ts_peak'] * (1 - ts_callback):
                    # Trailing stop hit
                    exit_price = pos['ts_peak'] * (1 - ts_callback)
                    real_pct = (exit_price - entry_price) / entry_price
                    realized_pnl = pos_margin * real_pct * leverage
                    balance += realized_pnl
                    if realized_pnl > 0: wins += 1
                    else: losses += 1
                    closed_symbols.append(symbol)
                elif high_pct >= tp_pct:
                    # Take Profit
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
            
        # Drawdown calculation
        if current_equity > peak:
            peak = current_equity
        dd = (peak - current_equity) / peak
        if dd > max_drawdown:
            max_drawdown = dd
            
        # Stop trading if Max Drawdown Limit is hit
        if max_drawdown >= max_dd_limit:
            balance = current_equity
            break
            
        # 2. Check for new entries
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
            
            # Form final triggers
            long_trigger = cond_long_1 and cond_long_2 and cond_long_3 and cond_long_4 and cond_long_rsi and cond_long_ema and allow_long
            short_trigger = cond_short_1 and cond_short_2 and cond_short_3 and cond_short_4 and cond_short_rsi and cond_short_ema and allow_short
            
            if (long_trigger or short_trigger) and len(positions) < max_positions:
                # Deduct margin
                if balance >= margin_usdt:
                    positions[symbol] = {
                        "side": "long" if long_trigger else "short",
                        "entry_price": close_p,
                        "margin": margin_usdt,
                        "ts_active": False,
                        "ts_peak": close_p
                    }
                    
    # Final metrics
    net_profit = balance - initial_balance
    net_profit_pct = (net_profit / initial_balance) * 100
    
    # Calculate daily average return
    if len(all_timestamps) > 2:
        duration_days = (all_timestamps[-1] - all_timestamps[0]).total_seconds() / (24 * 3600)
        daily_return = (net_profit_pct / duration_days) if duration_days > 0.1 else net_profit_pct
    else:
        daily_return = 0.0
        
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0
    
    return daily_return, max_drawdown * 100, win_rate

# ── 3. 딥러닝 신경망 (NumPy MLP) 구현 및 학습 ──────────────────
class MLP:
    """
    NumPy-only 3-layer Neural Network (MLP)
    Architecture: Input (19) -> Hidden1 (128) -> ReLU -> Hidden2 (64) -> ReLU -> Output (2)
    Outputs: [Daily Return %, Max Drawdown %]
    """
    def __init__(self, input_dim=19, h1=128, h2=64, output_dim=2):
        # He initialization for ReLU
        self.W1 = np.random.randn(input_dim, h1) * np.sqrt(2.0 / input_dim)
        self.b1 = np.zeros((1, h1))
        self.W2 = np.random.randn(h1, h2) * np.sqrt(2.0 / h1)
        self.b2 = np.zeros((1, h2))
        self.W3 = np.random.randn(h2, output_dim) * np.sqrt(2.0 / h2)
        self.b3 = np.zeros((1, output_dim))
        
    def forward(self, X):
        self.z1 = np.dot(X, self.W1) + self.b1
        self.a1 = np.maximum(0, self.z1)  # ReLU
        self.z2 = np.dot(self.a1, self.W2) + self.b2
        self.a2 = np.maximum(0, self.z2)  # ReLU
        self.z3 = np.dot(self.a2, self.W3) + self.b3
        return self.z3  # Linear output
        
    def train(self, X, y, epochs=600, lr=0.005, batch_size=64):
        num_samples = X.shape[0]
        
        # Momentum parameters
        vW1, vb1 = 0, 0
        vW2, vb2 = 0, 0
        vW3, vb3 = 0, 0
        beta = 0.9
        
        for epoch in range(epochs):
            # Shuffle
            indices = np.arange(num_samples)
            np.random.shuffle(indices)
            X_shuffled = X[indices]
            y_shuffled = y[indices]
            
            epoch_loss = 0.0
            num_batches = int(np.ceil(num_samples / batch_size))
            
            for b in range(num_batches):
                start = b * batch_size
                end = min(start + batch_size, num_samples)
                xb = X_shuffled[start:end]
                yb = y_shuffled[start:end]
                
                # Forward
                out = self.forward(xb)
                
                # MSE Loss
                loss = np.mean((out - yb) ** 2)
                epoch_loss += loss * (end - start)
                
                # Backward pass
                dout = 2 * (out - yb) / xb.shape[0]
                
                dW3 = np.dot(self.a2.T, dout)
                db3 = np.sum(dout, axis=0, keepdims=True)
                
                da2 = np.dot(dout, self.W3.T)
                dz2 = da2 * (self.z2 > 0)  # ReLU grad
                dW2 = np.dot(self.a1.T, dz2)
                db2 = np.sum(dz2, axis=0, keepdims=True)
                
                da1 = np.dot(dz2, self.W2.T)
                dz1 = da1 * (self.z1 > 0)  # ReLU grad
                dW1 = np.dot(xb.T, dz1)
                db1 = np.sum(dz1, axis=0, keepdims=True)
                
                # Update with momentum
                vW3 = beta * vW3 + (1 - beta) * dW3
                vb3 = beta * vb3 + (1 - beta) * db3
                vW2 = beta * vW2 + (1 - beta) * dW2
                vb2 = beta * vb2 + (1 - beta) * db2
                vW1 = beta * vW1 + (1 - beta) * dW1
                vb1 = beta * vb1 + (1 - beta) * db1
                
                self.W3 -= lr * vW3
                self.b3 -= lr * vb3
                self.W2 -= lr * vW2
                self.b2 -= lr * vb2
                self.W1 -= lr * vW1
                self.b1 -= lr * vb1
                
            if (epoch + 1) % 100 == 0:
                print(f"  Epoch {epoch+1}/{epochs} - Train MSE Loss: {epoch_loss / num_samples:.6f}")

# ── 4. 검색 공간 탐색 ───────────────────────────────
def get_random_parameter():
    long_side = random.choice([True, False])
    # Short side should be True if Long is False to make sure we trade, or both True
    short_side = True if not long_side else random.choice([True, False])
    
    return {
        'LEVERAGE': random.choice([2, 5, 10, 15, 20]),
        'MARGIN_USDT': round(random.uniform(2.0, 20.0), 1),
        'MAX_POSITIONS': random.randint(2, 6),
        'STOP_LOSS_PCT': round(random.uniform(0.005, 0.04), 4),
        'TAKE_PROFIT_PCT': round(random.uniform(0.01, 0.08), 4),
        'TRAILING_ACTIVATE_PCT': round(random.uniform(0.008, 0.06), 4),
        'TRAILING_CALLBACK_PCT': round(random.uniform(0.001, 0.015), 4),
        'MAX_DRAWDOWN_PCT': round(random.uniform(0.08, 0.30), 3),
        'ALLOW_LONG': long_side,
        'ALLOW_SHORT': short_side,
        'TIMEFRAME': random.choice(["15m", "30m", "1h", "4h"]),
        # Scan parameters
        'SCAN_INTERVAL_SEC': random.choice([10, 20, 30, 60]),
        'MIN_VOLUME_USDT': random.choice([500_000, 1_000_000, 2_000_000, 5_000_000, 10_000_000]),
        # Indicator params
        'EMA_PERIOD': random.randint(80, 250),
        'BB_PERIOD': random.randint(14, 40),
        'BB_STD': round(random.uniform(1.2, 2.5), 2),
        'RSI_PERIOD': random.randint(8, 20),
        'RSI_OVERSOLD': round(random.uniform(25.0, 45.0), 1),
        'RSI_OVERBOUGHT': round(random.uniform(55.0, 75.0), 1),
    }

def parameter_to_vector(p):
    # Vector of size 19
    return np.array([
        float(p['LEVERAGE']),
        float(p['MARGIN_USDT']),
        float(p['MAX_POSITIONS']),
        float(p['STOP_LOSS_PCT']),
        float(p['TAKE_PROFIT_PCT']),
        float(p['TRAILING_ACTIVATE_PCT']),
        float(p['TRAILING_CALLBACK_PCT']),
        float(p['MAX_DRAWDOWN_PCT']),
        1.0 if p['ALLOW_LONG'] else 0.0,
        1.0 if p['ALLOW_SHORT'] else 0.0,
        float(TIMEFRAME_REV[p['TIMEFRAME']]),
        float(p['SCAN_INTERVAL_SEC']),
        float(p['MIN_VOLUME_USDT']) / 1_000_000.0, # scale volume to avoid large numbers
        float(p['EMA_PERIOD']),
        float(p['BB_PERIOD']),
        float(p['BB_STD']),
        float(p['RSI_PERIOD']),
        float(p['RSI_OVERSOLD']),
        float(p['RSI_OVERBOUGHT'])
    ], dtype=np.float32)

def vector_to_parameter(v):
    return {
        'LEVERAGE': int(round(v[0])),
        'MARGIN_USDT': round(float(v[1]), 1),
        'MAX_POSITIONS': int(round(v[2])),
        'STOP_LOSS_PCT': round(float(v[3]), 4),
        'TAKE_PROFIT_PCT': round(float(v[4]), 4),
        'TRAILING_ACTIVATE_PCT': round(float(v[5]), 4),
        'TRAILING_CALLBACK_PCT': round(float(v[6]), 4),
        'MAX_DRAWDOWN_PCT': round(float(v[7]), 3),
        'ALLOW_LONG': bool(v[8] > 0.5),
        'ALLOW_SHORT': bool(v[9] > 0.5),
        'TIMEFRAME': TIMEFRAME_MAP[int(round(np.clip(v[10], 0, 3)))],
        'SCAN_INTERVAL_SEC': int(round(v[11])),
        'MIN_VOLUME_USDT': int(round(v[12] * 1_000_000.0)),
        'EMA_PERIOD': int(round(v[13])),
        'BB_PERIOD': int(round(v[14])),
        'BB_STD': round(float(v[15]), 2),
        'RSI_PERIOD': int(round(v[16])),
        'RSI_OVERSOLD': round(float(v[17]), 1),
        'RSI_OVERBOUGHT': round(float(v[18]), 1),
    }

# ── 5. 실행 및 메인 제어 ─────────────────────────────
def main():
    print("=" * 80)
    print("  AI QUANTUM - Deep Learning Parameter Optimizer (v1.0)")
    print("=" * 80)
    
    # Step 1: 데이터 로드
    data_dict = download_and_cache_data()
    
    # Step 2: 무작위 샘플링 및 백테스트 데이터 수집
    NUM_SAMPLES = 1000
    print(f"\n[PHASE 1] Sampling {NUM_SAMPLES} parameter sets and running backtests...")
    
    X_list = []
    y_list = []
    
    start_time = time.time()
    for s in range(NUM_SAMPLES):
        p = get_random_parameter()
        daily_ret, mdd, winrate = run_portfolio_backtest(data_dict, p)
        
        vec = parameter_to_vector(p)
        X_list.append(vec)
        y_list.append([daily_ret, mdd])
        
        if (s + 1) % 100 == 0:
            elapsed = time.time() - start_time
            est_total = (elapsed / (s + 1)) * NUM_SAMPLES
            print(f"  Simulated {s+1}/{NUM_SAMPLES} - Elapsed: {elapsed:.1f}s | Est Total: {est_total:.1f}s")
            
    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    
    # Data Normalization
    X_mean = X.mean(axis=0)
    X_std = X.std(axis=0) + 1e-8
    X_norm = (X - X_mean) / X_std
    
    y_mean = y.mean(axis=0)
    y_std = y.std(axis=0) + 1e-8
    y_norm = (y - y_mean) / y_std
    
    # Step 3: Deep Neural Network (MLP) 학습
    print("\n[PHASE 2] Training NumPy Deep Neural Network (MLP)...")
    mlp = MLP(input_dim=19, h1=128, h2=64, output_dim=2)
    mlp.train(X_norm, y_norm, epochs=600, lr=0.003, batch_size=64)
    
    # Evaluate model training accuracy
    predictions = mlp.forward(X_norm) * y_std + y_mean
    mae = np.mean(np.abs(predictions - y), axis=0)
    print(f"  Neural Network Evaluation Accuracy (MAE):")
    print(f"    - Daily Return Predict Error: {mae[0]:.4f}%")
    print(f"    - MDD Predict Error: {mae[1]:.4f}%")
    
    # Step 4: 1,000,000개 무작위 조합 생성 및 모델 고속 추론
    INFERENCE_SIZE = 1_000_000
    print(f"\n[PHASE 3] Generating {INFERENCE_SIZE:,} random combinations and running Neural Network inference...")
    
    # Fast vectorized candidates generation
    inf_X = np.zeros((INFERENCE_SIZE, 19), dtype=np.float32)
    for i in range(INFERENCE_SIZE):
        p = get_random_parameter()
        inf_X[i] = parameter_to_vector(p)
        
    # Scale input
    inf_X_norm = (inf_X - X_mean) / X_std
    
    # Model inference
    inf_preds_norm = mlp.forward(inf_X_norm)
    inf_preds = inf_preds_norm * y_std + y_mean  # de-normalize
    
    pred_returns = inf_preds[:, 0]
    pred_mdd = inf_preds[:, 1]
    
    # Filter candidates: Target Daily Return >= 1.0% and MDD <= 15%
    # If no combinations satisfy >= 1.0%, we will take the ones with max returns
    satisfied_indices = np.where((pred_returns >= 1.0) & (pred_mdd <= 15.0))[0]
    
    if len(satisfied_indices) < 20:
        print("  Notice: Few combinations satisfy both Daily Return >= 1.0% and MDD <= 15.0%. Softening filters...")
        satisfied_indices = np.where((pred_returns >= 0.5) & (pred_mdd <= 20.0))[0]
        
    if len(satisfied_indices) == 0:
        # Fallback to absolute best return
        satisfied_indices = np.argsort(pred_returns)[-100:]
        
    print(f"  Neural network found {len(satisfied_indices):,} promising candidate sets.")
    
    # Take top 50 by predicted return, and sort them
    top_indices = satisfied_indices[np.argsort(pred_returns[satisfied_indices])[-50:]]
    
    # Step 5: 실제 백테스트 시뮬레이션 검증
    print("\n[PHASE 4] Verifying top 20 candidate sets through actual vectorized backtests...")
    verified_results = []
    
    for idx in top_indices:
        p_vec = inf_X[idx]
        p = vector_to_parameter(p_vec)
        
        # Run real backtest
        daily_ret, mdd, winrate = run_portfolio_backtest(data_dict, p)
        pred_ret = pred_returns[idx]
        pred_m = pred_mdd[idx]
        
        verified_results.append({
            'params': p,
            'daily_ret': daily_ret,
            'mdd': mdd,
            'winrate': winrate,
            'pred_ret': pred_ret,
            'pred_mdd': pred_m
        })
        
    # Sort verified results by daily return
    verified_results = sorted(verified_results, key=lambda x: x['daily_ret'], reverse=True)
    
    print("\n" + "="*80)
    print("  TOP 5 VERIFIED PARAMETER SETS (OPTIMIZED BY DEEP LEARNING)")
    print("="*80)
    
    for rank, res in enumerate(verified_results[:5]):
        p = res['params']
        print(f"\n[RANK {rank + 1}] Verified Daily Return: {res['daily_ret']:.2f}% | MDD: {res['mdd']:.2f}% | Win Rate: {res['winrate']:.1f}%")
        print(f"  - (Neural Net Predicted: Daily Return {res['pred_ret']:.2f}% | MDD {res['pred_mdd']:.2f}%)")
        print(f"  - Parameters:")
        print(f"    * Leverage: {p['LEVERAGE']}x | Margin: {p['MARGIN_USDT']} USDT | Max Positions: {p['MAX_POSITIONS']} | Timeframe: {p['TIMEFRAME']}")
        print(f"    * Stop-Loss: {p['STOP_LOSS_PCT']*100:.2f}% | Take-Profit: {p['TAKE_PROFIT_PCT']*100:.2f}%")
        print(f"    * Trailing Stop: Activate {p['TRAILING_ACTIVATE_PCT']*100:.2f}% | Callback {p['TRAILING_CALLBACK_PCT']*100:.2f}%")
        print(f"    * Indicators: EMA {p['EMA_PERIOD']} | BB {p['BB_PERIOD']} (std {p['BB_STD']}) | RSI {p['RSI_PERIOD']} (OB {p['RSI_OVERBOUGHT']} / OS {p['RSI_OVERSOLD']})")
        print(f"    * Filter Rules: Max MDD Limit {p['MAX_DRAWDOWN_PCT']*100:.1f}% | Allow Long {p['ALLOW_LONG']} | Allow Short {p['ALLOW_SHORT']}")
        print(f"    * Volume Gate: > {p['MIN_VOLUME_USDT']:,} USDT")
        
    # Save the absolute best parameters to settings/config file or report
    best_res = verified_results[0]
    best_p = best_res['params']
    
    # Save best parameters to scratch for walkthrough report usage
    with open("scratch/best_params.pkl", "wb") as f:
        pickle.dump(best_res, f)
        
    print("\n" + "="*80)
    print("Optimization Complete! The best verified parameter set is saved.")
    print("="*80)

if __name__ == "__main__":
    main()
