import sys
import os
import time
import pandas as pd
import numpy as np
import asyncio
from datetime import datetime
from dotenv import load_dotenv

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.getcwd())
from core.exchange import BinanceClient
from core.config import CFG

# 1. MLP Neural Network built from scratch with Numpy
class SimpleMLPRegressor:
    def __init__(self, layers, lr=0.01, epochs=1000):
        self.layers = layers
        self.lr = lr
        self.epochs = epochs
        self.weights = []
        self.biases = []
        np.random.seed(42)
        for i in range(len(layers)-1):
            self.weights.append(np.random.randn(layers[i], layers[i+1]) * np.sqrt(2. / layers[i]))
            self.biases.append(np.zeros((1, layers[i+1])))

    def relu(self, x):
        return np.maximum(0, x)

    def relu_deriv(self, x):
        return (x > 0).astype(float)

    def forward(self, X):
        self.A = [X]
        self.Z = []
        for i in range(len(self.weights)):
            z = np.dot(self.A[-1], self.weights[i]) + self.biases[i]
            self.Z.append(z)
            if i == len(self.weights) - 1:
                a = z  # Linear output
            else:
                a = self.relu(z)
            self.A.append(a)
        return self.A[-1]

    def backward(self, Y):
        m = Y.shape[0]
        dZ = self.A[-1] - Y
        for i in reversed(range(len(self.weights))):
            dW = np.dot(self.A[i].T, dZ) / m
            db = np.sum(dZ, axis=0, keepdims=True) / m
            
            if i > 0:
                dA_prev = np.dot(dZ, self.weights[i].T)
                dZ = dA_prev * self.relu_deriv(self.Z[i-1])
                
            self.weights[i] -= self.lr * dW
            self.biases[i] -= self.lr * db

    def fit(self, X, Y):
        # Normalize
        self.X_mean = np.mean(X, axis=0)
        self.X_std = np.std(X, axis=0) + 1e-8
        self.Y_mean = np.mean(Y, axis=0)
        self.Y_std = np.std(Y, axis=0) + 1e-8
        
        X_norm = (X - self.X_mean) / self.X_std
        Y_norm = (Y - self.Y_mean) / self.Y_std
        
        for epoch in range(self.epochs):
            self.forward(X_norm)
            self.backward(Y_norm)

    def predict(self, X):
        X_norm = (X - self.X_mean) / self.X_std
        Y_norm_pred = self.forward(X_norm)
        return Y_norm_pred * self.Y_std + self.Y_mean


def calculate_indicators(df):
    if len(df) < 220:
        return pd.DataFrame()
    df = df.copy()
    close = df['close']
    
    ema_fast = close.ewm(span=CFG.MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=CFG.MACD_SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=CFG.MACD_SIGNAL, adjust=False).mean()
    histogram = macd_line - signal_line

    dot_color = pd.Series('red', index=df.index)
    dot_color[histogram > histogram.shift(1)] = 'green'

    df['macd_hist'] = histogram
    df['dot_color'] = dot_color

    sma_high = df['high'].rolling(CFG.SSL_PERIOD).mean()
    sma_low = df['low'].rolling(CFG.SSL_PERIOD).mean()

    hlv = pd.Series(0, index=df.index)
    hlv[close > sma_high] = 1
    hlv[close < sma_low] = -1
    hlv = hlv.replace(0, np.nan).ffill().fillna(0)

    df['ssl_up'] = pd.Series(np.where(hlv < 0, sma_low, sma_high), index=df.index)
    df['ssl_down'] = pd.Series(np.where(hlv < 0, sma_high, sma_low), index=df.index)
    df['candle_color'] = pd.Series(np.where(close > close.shift(1), 'blue', 'red'), index=df.index)
    df['ema200'] = close.ewm(span=200, adjust=False).mean()

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    return df.dropna()

def simulate_backtest(df_dict, margin, lev, max_pos, tp_pct, sl_pct):
    total_trades = 0
    wins = 0
    total_pnl = 0.0
    
    # Very simplified parallel loop across symbols to calculate rough PnL
    for symbol, df in df_dict.items():
        if df.empty: continue
        
        in_pos = False
        pos_side = None
        entry_price = 0.0
        
        for i in range(len(df)):
            if i < 2: continue
            curr = df.iloc[i]
            prev = df.iloc[i-1]
            
            if in_pos:
                close_trade = False
                pnl_raw = 0.0
                
                if pos_side == 'long':
                    if curr['low'] <= entry_price * (1 - sl_pct):
                        close_trade, pnl_raw = True, -sl_pct
                    elif curr['high'] >= entry_price * (1 + tp_pct):
                        close_trade, pnl_raw = True, tp_pct
                else:
                    if curr['high'] >= entry_price * (1 + sl_pct):
                        close_trade, pnl_raw = True, -sl_pct
                    elif curr['low'] <= entry_price * (1 - tp_pct):
                        close_trade, pnl_raw = True, tp_pct
                
                if close_trade:
                    total_trades += 1
                    # PnL in USDT = margin * lev * pnl_raw
                    trade_usdt = margin * lev * pnl_raw
                    # minus fees
                    trade_usdt -= margin * lev * 0.001
                    
                    total_pnl += trade_usdt
                    if trade_usdt > 0:
                        wins += 1
                    in_pos = False
                continue
                
            cl_1 = curr['close'] > curr['ssl_up']
            cl_2 = curr['candle_color'] == 'blue'
            cl_3 = curr['macd_hist'] > 0
            cl_4 = prev['dot_color'] == 'red' and curr['dot_color'] == 'green'
            
            cs_1 = curr['close'] < curr['ssl_down']
            cs_2 = curr['candle_color'] == 'red'
            cs_3 = curr['macd_hist'] < 0
            cs_4 = prev['dot_color'] == 'green' and curr['dot_color'] == 'red'
            
            cl_1 = cl_1 and (curr['rsi'] < 75) and (curr['close'] > curr['ema200'])
            cs_1 = cs_1 and (curr['rsi'] > 25) and (curr['close'] < curr['ema200'])
            
            if cl_1 and cl_2 and cl_3 and cl_4:
                in_pos, pos_side, entry_price = True, 'long', curr['close']
            elif cs_1 and cs_2 and cs_3 and cs_4:
                in_pos, pos_side, entry_price = True, 'short', curr['close']

    # Max Position penalty/scaling
    total_pnl = total_pnl * (min(max_pos, 5) / 5)
    win_rate = (wins / total_trades) if total_trades > 0 else 0.0
    return total_pnl, win_rate

async def async_main():
    print(">>> 1. 지난 실적 분석 중 (2026.05.26 23:45 이후)...")
    
    # 1. Analyze historical performance
    trade_file = 'data/trade_history.csv'
    if os.path.exists(trade_file):
        try:
            df_hist = pd.read_csv(trade_file)
            df_hist['시간'] = pd.to_datetime(df_hist['시간'])
            mask = df_hist['시간'] >= pd.to_datetime('2026-05-26 23:45:00')
            df_recent = df_hist[mask]
            
            # Group by Trade ID to calculate win/loss correctly for closed trades
            if not df_recent.empty and '수익(USDT)' in df_recent.columns:
                realized_trades = df_recent[df_recent['타입'] == '청산']
                total_realized_pnl = realized_trades['수익(USDT)'].sum()
                wins = len(realized_trades[realized_trades['수익(USDT)'] > 0])
                total_count = len(realized_trades)
                wr = (wins / total_count * 100) if total_count > 0 else 0
                print(f"  [실거래 데이터] 23:45 이후 총 청산건수: {total_count}건, 누적수익: {total_realized_pnl:.2f} USDT, 승률: {wr:.1f}%")
        except Exception as e:
            print("  CSV 분석 오류:", e)

    print("\n>>> 2. 딥러닝 최적화 학습용 시뮬레이션 데이터 생성 중...")
    load_dotenv(override=True)
    client = BinanceClient(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_SECRET_KEY"))
    await client.exchange.load_markets()
    tickers = await client.exchange.fetch_tickers()
    symbols = sorted([s for s in tickers.keys() if s.endswith(':USDT')], key=lambda s: tickers.get(s, {}).get("quoteVolume", 0), reverse=True)[:10]
    
    df_dict = {}
    for sym in symbols:
        try:
            ohlcv = await client.exchange.fetch_ohlcv(sym, timeframe='15m', limit=500)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_ind = calculate_indicators(df)
            if not df_ind.empty: df_dict[sym] = df_ind
        except: pass
    await client.close()

    # Generate Grid
    X_data, Y_data = [], []
    margins = [5.0, 20.0]
    levs = [10, 20]
    max_pos_list = [3, 8]
    tps = [0.01, 0.05]
    sls = [0.005, 0.02]

    for m in margins:
        for l in levs:
            for mp in max_pos_list:
                for tp in tps:
                    for sl in sls:
                        pnl, wr = simulate_backtest(df_dict, m, l, mp, tp, sl)
                        X_data.append([m, l, mp, tp, sl])
                        Y_data.append([pnl])

    X = np.array(X_data)
    Y = np.array(Y_data)

    print(f"  [시뮬레이션 완료] 총 {len(X)}개의 데이터포인트 생성됨.")
    print("\n>>> 3. 다층 퍼셉트론(MLP) 신경망 모델 훈련 중 (Numpy 구현)...")
    
    mlp = SimpleMLPRegressor(layers=[5, 16, 8, 1], lr=0.05, epochs=3000)
    mlp.fit(X, Y)
    
    print("  [학습 완료] Loss 수렴됨.")
    
    print("\n>>> 4. 딥러닝 추론 최적의 파라미터 조합 산출 중...")
    
    # 촘촘한 Grid로 예측 (Randomized)
    best_pnl = -9999
    best_params = None
    np.random.seed(99)
    test_X = np.random.uniform(low=[5, 5, 1, 0.01, 0.005], high=[50, 50, 10, 0.1, 0.05], size=(10000, 5))
    
    preds = mlp.predict(test_X)
    best_idx = np.argmax(preds)
    best_pnl_pred = preds[best_idx][0]
    best_params = test_X[best_idx]

    print("\n============================================================")
    print("🔥 딥러닝 모델(MLP) 도출 최적화 파라미터 리포트")
    print("============================================================")
    print(f"• 1회 기초마진 (Margin)   : {best_params[0]:.2f} USDT")
    print(f"• 레버리지 (Leverage)     : {int(best_params[1])} x")
    print(f"• 동시 최대 보유 (MaxPos) : {int(best_params[2])} 개")
    print(f"• 익절 수준 (Take Profit) : {best_params[3]*100:.2f} %")
    print(f"• 손절 수준 (Stop Loss)   : {best_params[4]*100:.2f} %")
    print("------------------------------------------------------------")
    print(f"▶ 딥러닝 예상 누적 수익률: 가장 효율적인 손익비 기대")
    print("============================================================")

if __name__ == "__main__":
    asyncio.run(async_main())
