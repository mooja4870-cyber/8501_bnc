import pandas as pd
import json
import core.history_helper as hh

stats = json.load(open('data/stats.json', 'r'))
perf_start = pd.to_datetime(stats.get('perf_start_time', '2026-05-15'))

raw_trades = hh.load_local_trade_history()
paired = hh.aggregate_and_pair_trades(raw_trades)

chart_data = []
for p in paired:
    if str(p.get("status", "")).startswith("청산 완료"):
        exit_t = p.get("exit_time")
        if exit_t:
            exit_t_naive = pd.to_datetime(exit_t).replace(tzinfo=None)
            if exit_t_naive >= perf_start:
                chart_data.append({
                    "time": exit_t_naive,
                    "pnl_usdt": float(p.get("pnl_usdt", 0.0))
                })

df = pd.DataFrame(chart_data)
df.sort_values("time", inplace=True)
df.set_index("time", inplace=True)
df_resampled = df.resample("15min").sum()
df_resampled["cumulative_pnl"] = df_resampled["pnl_usdt"].cumsum()
df_resampled["roi_pct"] = (df_resampled["cumulative_pnl"] / stats.get('seed_money')) * 100

print(df_resampled.head(50))
