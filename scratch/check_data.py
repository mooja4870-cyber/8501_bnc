import pandas as pd
import json

try:
    with open('data/stats.json', 'r') as f:
        stats = json.load(f)
    print(f"perf_start_time: {stats.get('perf_start_time')}")
    print(f"seed_money: {stats.get('seed_money')}")
except Exception as e:
    print('No stats.json:', e)

try:
    df = pd.read_csv('data/trade_history.csv')
    df['Time'] = pd.to_datetime(df['Time']).dt.tz_localize(None)
    perf_start = pd.to_datetime(stats.get('perf_start_time', '2026-05-15'))
    df = df[df['Time'] >= perf_start]
    df['PnL_USDT'] = pd.to_numeric(df['PnL_USDT'], errors='coerce').fillna(0.0)
    print(df[['Time', 'Symbol', 'PnL_USDT', 'Status']].to_string())
    print("Total PNL USDT:", df['PnL_USDT'].sum())
except Exception as e:
    print('Error:', e)
