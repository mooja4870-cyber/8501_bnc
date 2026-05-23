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

sys.path.append(os.getcwd())

from core.exchange import BinanceClient
from core.config import CFG

logging.basicConfig(level=logging.WARNING)

def calculate_indicators(df):
    if len(df) < 220:
        return pd.DataFrame()

    df = df.copy()
    close = df['close']
    high = df['high']
    low = df['low']

    # 1. MACD + Histogram
    ema_fast = close.ewm(span=CFG.MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=CFG.MACD_SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=CFG.MACD_SIGNAL, adjust=False).mean()
    histogram = macd_line - signal_line

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

    # 2. Price Bollinger Bands
    price_bb_mid = close.rolling(20).mean()
    price_bb_std = close.rolling(20).std()
    df['price_bb_upper'] = price_bb_mid + (2.0 * price_bb_std)
    df['price_bb_lower'] = price_bb_mid - (2.0 * price_bb_std)

    # 3. SSL Hybrid
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

    # 4. EMA 200
    df['ema200'] = close.ewm(span=200, adjust=False).mean()

    # 5. RSI
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # 6. ADX (Average Directional Index, 14-period)
    # True Range
    hl = high - low
    hc = (high - close.shift(1)).abs()
    lc = (low - close.shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)

    # +DM / -DM
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0).where(
        (minus_dm > 0), 0.0)) & (minus_dm > 0), 0.0)

    # Simplified +DM / -DM
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm2 = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm2 = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    period = 14
    # Wilder smoothing
    tr_smooth = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    plus_dm_smooth = plus_dm2.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    minus_dm_smooth = minus_dm2.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    plus_di = 100 * (plus_dm_smooth / tr_smooth)
    minus_di = 100 * (minus_dm_smooth / tr_smooth)
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
    adx = dx.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    df['adx'] = adx

    # 7. ATR
    df['atr'] = tr.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    df['atr_ma20'] = df['atr'].rolling(20).mean()

    return df.dropna()


def simulate_backtest(df_dict, filter_type=None, window_size=192):
    """
    filter_type:
      None          — Base + RSI only (현재 전략)
      'rsi_ema'     — Base + RSI + EMA 200
      'rsi_pbb'     — Base + RSI + Price BB
      'adx_auto'    — ADX 자동 판별: ADX≥25 → RSI+EMA200, ADX<25 → RSI+PBB
      'atr_auto'    — ATR 변동성 자동 판별: ATR>ATR_MA → RSI+EMA200, ATR≤ATR_MA → RSI+PBB
    """
    total_trades = 0
    wins = 0
    total_pnl = 0.0
    gross_profit = 0.0
    gross_loss = 0.0
    trending_entries = 0
    ranging_entries = 0

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

            if in_pos:
                close_trade = False
                pnl = 0.0
                bars_held = i - entry_idx

                if pos_side == 'long':
                    if curr['low'] <= sl_price:
                        close_trade = True; pnl = -sl_pct
                    elif curr['high'] >= tp_price:
                        close_trade = True; pnl = tp_pct
                    elif bars_held >= 16:
                        close_trade = True; pnl = (curr['close'] - entry_price) / entry_price
                else:
                    if curr['high'] >= sl_price:
                        close_trade = True; pnl = -sl_pct
                    elif curr['low'] <= tp_price:
                        close_trade = True; pnl = tp_pct
                    elif bars_held >= 16:
                        close_trade = True; pnl = (entry_price - curr['close']) / entry_price

                if close_trade:
                    total_trades += 1
                    total_pnl += pnl
                    if pnl > 0:
                        wins += 1; gross_profit += pnl
                    else:
                        gross_loss += abs(pnl)
                    in_pos = False
                continue

            # Base entry conditions
            cond_long_1 = curr['close'] > curr['ssl_up']
            cond_long_2 = curr['candle_color'] == 'blue'
            cond_long_3 = curr['macd_hist'] > 0
            cond_long_4 = prev['dot_color'] == 'red' and curr['dot_color'] == 'green'

            cond_short_1 = curr['close'] < curr['ssl_down']
            cond_short_2 = curr['candle_color'] == 'red'
            cond_short_3 = curr['macd_hist'] < 0
            cond_short_4 = prev['dot_color'] == 'green' and curr['dot_color'] == 'red'

            # RSI filter (항상 공통 적용)
            cond_long_1 = cond_long_1 and (curr['rsi'] < 60)
            cond_short_1 = cond_short_1 and (curr['rsi'] > 40)

            if filter_type == 'rsi_ema':
                cond_long_1 = cond_long_1 and (curr['close'] > curr['ema200'])
                cond_short_1 = cond_short_1 and (curr['close'] < curr['ema200'])

            elif filter_type == 'rsi_pbb':
                cond_long_1 = cond_long_1 and (curr['close'] < curr['price_bb_upper'])
                cond_short_1 = cond_short_1 and (curr['close'] > curr['price_bb_lower'])

            elif filter_type == 'adx_auto':
                # ADX 자동 판별: 25 이상이면 추세장(EMA200), 미만이면 횡보장(PBB)
                adx_val = curr['adx']
                if adx_val >= 25:
                    # 추세장 → EMA 200 필터
                    cond_long_1 = cond_long_1 and (curr['close'] > curr['ema200'])
                    cond_short_1 = cond_short_1 and (curr['close'] < curr['ema200'])
                    if cond_long_1 or cond_short_1:
                        trending_entries += 1
                else:
                    # 횡보장 → Price BB 필터
                    cond_long_1 = cond_long_1 and (curr['close'] < curr['price_bb_upper'])
                    cond_short_1 = cond_short_1 and (curr['close'] > curr['price_bb_lower'])
                    if cond_long_1 or cond_short_1:
                        ranging_entries += 1

            elif filter_type == 'atr_auto':
                # ATR 변동성 자동 판별
                atr_val = curr['atr']
                atr_ma = curr['atr_ma20']
                if atr_val > atr_ma:
                    # 변동성 확대 → 추세장 모드 (EMA 200)
                    cond_long_1 = cond_long_1 and (curr['close'] > curr['ema200'])
                    cond_short_1 = cond_short_1 and (curr['close'] < curr['ema200'])
                    if cond_long_1 or cond_short_1:
                        trending_entries += 1
                else:
                    # 변동성 수축 → 횡보장 모드 (Price BB)
                    cond_long_1 = cond_long_1 and (curr['close'] < curr['price_bb_upper'])
                    cond_short_1 = cond_short_1 and (curr['close'] > curr['price_bb_lower'])
                    if cond_long_1 or cond_short_1:
                        ranging_entries += 1

            if cond_long_1 and cond_long_2 and cond_long_3 and cond_long_4:
                in_pos = True; pos_side = 'long'
                entry_price = curr['close']
                tp_price = entry_price * (1 + tp_pct)
                sl_price = entry_price * (1 - sl_pct)
                entry_idx = i
            elif cond_short_1 and cond_short_2 and cond_short_3 and cond_short_4:
                in_pos = True; pos_side = 'short'
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
        "profit_factor": profit_factor,
        "trending_entries": trending_entries,
        "ranging_entries": ranging_entries,
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

    strategies = [
        ("현재 전략 (RSI 단독 필터)",              None),
        ("RSI + EMA 200 (추세장 최적)",             "rsi_ema"),
        ("RSI + Price BB (횡보장 최적)",             "rsi_pbb"),
        ("★ ADX 자동 판별 스위칭 (ADX≥25→EMA, <25→BB)",  "adx_auto"),
        ("★ ATR 변동성 자동 스위칭 (ATR>MA→EMA, ≤MA→BB)", "atr_auto"),
    ]

    for window_size, label in [(192, "최근 48시간 (192봉)"), (672, "최근 7일간 (672봉)")]:
        print(f"\n{'='*90}")
        print(f"[ {label} 시뮬레이션 결과 ]  익절 1.5% / 손절 1.0% / 레버리지 5배 / 진입 5 USDT / 시드 30 USDT")
        print(f"{'='*90}")
        print(f"{'전략명':<48} | {'총 거래수':<7} | {'승률':>7} | {'누적수익률':>9} | {'수익팩터':>8} | {'추세/횡보 배분'}")
        print("-"*90)
        for name, f_type in strategies:
            res = simulate_backtest(df_dict, filter_type=f_type, window_size=window_size)
            mode_info = ""
            if res['trending_entries'] > 0 or res['ranging_entries'] > 0:
                total_mode = res['trending_entries'] + res['ranging_entries']
                t_pct = res['trending_entries'] / total_mode * 100 if total_mode > 0 else 0
                r_pct = res['ranging_entries'] / total_mode * 100 if total_mode > 0 else 0
                mode_info = f"추세 {t_pct:.0f}% / 횡보 {r_pct:.0f}%"
            else:
                mode_info = "-"
            marker = "🏆 " if res['net_profit_pct'] > 0 else "   "
            print(f"{marker}{name:<46} | {res['trades']:<7d} | {res['win_rate']:>6.1f}% | {res['net_profit_pct']:>+8.2f}% | {res['profit_factor']:>8.2f} | {mode_info}")
        print(f"{'='*90}")

if __name__ == "__main__":
    main()
