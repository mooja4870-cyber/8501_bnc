import sys
import os
import time
import pandas as pd
import numpy as np
import asyncio
from dotenv import load_dotenv

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.getcwd())
from core.exchange import BinanceClient
from core.config import CFG

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

def simulate_backtest(df_dict, rsi_overbought, rsi_oversold, window_size=672):
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
        
        for i in range(len(test_df)):
            loc_in_full = df.index.get_loc(indices[i])
            if loc_in_full < 2: continue
                
            curr = df.iloc[loc_in_full]
            prev = df.iloc[loc_in_full - 1]
            
            if in_pos:
                close_trade = False
                pnl = 0.0
                
                if pos_side == 'long':
                    if curr['low'] <= entry_price * (1 - sl_pct):
                        close_trade, pnl = True, -sl_pct
                    elif curr['high'] >= entry_price * (1 + tp_pct):
                        close_trade, pnl = True, tp_pct
                else:
                    if curr['high'] >= entry_price * (1 + sl_pct):
                        close_trade, pnl = True, -sl_pct
                    elif curr['low'] <= entry_price * (1 - tp_pct):
                        close_trade, pnl = True, tp_pct
                
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
                
            cl_1 = curr['close'] > curr['ssl_up']
            cl_2 = curr['candle_color'] == 'blue'
            cl_3 = curr['macd_hist'] > 0
            cl_4 = prev['dot_color'] == 'red' and curr['dot_color'] == 'green'
            
            cs_1 = curr['close'] < curr['ssl_down']
            cs_2 = curr['candle_color'] == 'red'
            cs_3 = curr['macd_hist'] < 0
            cs_4 = prev['dot_color'] == 'green' and curr['dot_color'] == 'red'
            
            cl_1 = cl_1 and (curr['rsi'] < rsi_overbought) and (curr['close'] > curr['ema200'])
            cs_1 = cs_1 and (curr['rsi'] > rsi_oversold) and (curr['close'] < curr['ema200'])
            
            if cl_1 and cl_2 and cl_3 and cl_4:
                in_pos, pos_side, entry_price = True, 'long', curr['close']
            elif cs_1 and cs_2 and cs_3 and cs_4:
                in_pos, pos_side, entry_price = True, 'short', curr['close']

    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)
    
    return {
        "trades": total_trades,
        "win_rate": win_rate,
        "net_profit_pct": total_pnl * 100,
        "profit_factor": profit_factor
    }

async def async_main():
    load_dotenv(override=True)
    ak = os.getenv("BINANCE_API_KEY")
    sk = os.getenv("BINANCE_SECRET_KEY")
    
    client = BinanceClient(ak, sk)
    await client.exchange.load_markets()
    
    tickers = await client.exchange.fetch_tickers()
    symbols = [s for s in tickers.keys() if s.endswith(':USDT')]
    
    top_symbols = sorted(
        symbols,
        key=lambda s: tickers.get(s, {}).get("quoteVolume", 0),
        reverse=True
    )[:40]
    
    df_dict = {}
    print("Fetching data...")
    for idx, sym in enumerate(top_symbols):
        try:
            ohlcv = await client.exchange.fetch_ohlcv(sym, timeframe='15m', limit=900)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            df_ind = calculate_indicators(df)
            if not df_ind.empty:
                df_dict[sym] = df_ind
        except Exception as e:
            pass
            
    await client.close()
    
    print("\n" + "="*60)
    print("RSI 60/40 vs 75/25 백테스트 비교 (최근 7일, TOP 40종목)")
    print("익절: 1.0% / 손절: 1.0% / EMA 200 필터 적용")
    print("="*60)
    
    configs = [
        ("안정형 (RSI 60/40)", 60, 40),
        ("공격형 (RSI 75/25)", 75, 25)
    ]
    
    for name, ob, os_val in configs:
        res = simulate_backtest(df_dict, ob, os_val, window_size=672)
        print(f"\n[{name}]")
        print(f"- 매매 횟수 : {res['trades']} 회")
        print(f"- 승률      : {res['win_rate']:.1f}%")
        print(f"- 누적 수익 : {res['net_profit_pct']:+.2f}%")
        print(f"- 수익 팩터 : {res['profit_factor']:.2f}")
        
    print("\n" + "="*60)

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
