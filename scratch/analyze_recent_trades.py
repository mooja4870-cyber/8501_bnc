import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(os.getcwd())
from core.history_helper import load_local_trade_history, aggregate_and_pair_trades

def analyze():
    print("=== Analyzing Trade History from 2026-05-26 23:45:00 ===")
    
    # Load all trades
    raw_trades = load_local_trade_history()
    if not raw_trades:
        print("No trade history loaded.")
        return
        
    # Deduplicate order-level duplicates (trader order log vs syncer fill log)
    deduped_trades = []
    by_order = {}
    for t in raw_trades:
        oid = t.get("order_id")
        if oid not in by_order:
            by_order[oid] = []
        by_order[oid].append(t)
        
    for oid, group in by_order.items():
        if len(group) == 1:
            deduped_trades.append(group[0])
        else:
            # Check if there are fills (non-empty trade_id)
            fills = [t for t in group if t.get("trade_id")]
            if fills:
                deduped_trades.extend(fills)
            else:
                deduped_trades.append(group[0])
                
    raw_trades = sorted(deduped_trades, key=lambda x: x['timestamp'])
        
    print(f"Total raw trades loaded: {len(raw_trades)}")
    
    # Filter raw trades from 2026-05-26 23:45:00 onwards
    start_time = pd.to_datetime('2026-05-26 23:45:00')
    recent_raw = [t for t in raw_trades if t['timestamp'] >= start_time]
    print(f"Raw trades since 2026-05-26 23:45:00: {len(recent_raw)}")
    
    if not recent_raw:
        print("No trades found in the specified period.")
        return

    # Pair the trades using the project's logic
    # We pass the full history to make sure pairings that started before 23:45 but ended after are processed,
    # or should we pair first and then filter?
    # Filtering the paired cycles is much better because some exits after 23:45 might correspond to entries before 23:45,
    # and vice versa.
    all_paired = aggregate_and_pair_trades(raw_trades)
    
    # Filter paired cycles where exit_time or entry_time is after 23:45
    # The user asks for performance "since 2026.05.26 23:45". Usually this means cycles that closed after 23:45, 
    # or cycles that started after 23:45. Let's look at both!
    
    # Closed cycles after 23:45
    closed_cycles = [p for p in all_paired if p['exit_time'] is not None and p['exit_time'] >= start_time]
    # Holding cycles
    holding_cycles = [p for p in all_paired if p['exit_time'] is None and p['status'] == "보유 중"]
    
    print(f"Closed cycles (completed trades) since 23:45: {len(closed_cycles)}")
    print(f"Currently holding positions: {len(holding_cycles)}")
    
    if not closed_cycles and not holding_cycles:
        print("No paired cycles found in the specified period.")
        return

    # 1. Closed Trades Analysis
    if closed_cycles:
        df_closed = pd.DataFrame(closed_cycles)
        
        # Calculate PnL
        total_pnl = df_closed['pnl_usdt'].sum()
        wins = df_closed[df_closed['pnl_usdt'] > 0]
        losses = df_closed[df_closed['pnl_usdt'] <= 0]
        
        win_rate = len(wins) / len(df_closed) * 100 if len(df_closed) > 0 else 0.0
        
        avg_win_pnl = wins['pnl_usdt'].mean() if len(wins) > 0 else 0
        avg_loss_pnl = losses['pnl_usdt'].mean() if len(losses) > 0 else 0
        
        avg_win_pct = wins['pnl_pct'].mean() if len(wins) > 0 else 0
        avg_loss_pct = losses['pnl_pct'].mean() if len(losses) > 0 else 0
        
        max_win_pct = df_closed['pnl_pct'].max()
        max_loss_pct = df_closed['pnl_pct'].min()
        
        print("\n=== 1. CLOSED TRADES OVERALL PERFORMANCE ===")
        print(f"• Cumulative PnL       : {total_pnl:+.4f} USDT")
        print(f"• Total Closed Trades  : {len(df_closed)} (Wins: {len(wins)}, Losses: {len(losses)})")
        print(f"• Win Rate             : {win_rate:.2f}%")
        print(f"• Profit Factor        : {abs(wins['pnl_usdt'].sum() / losses['pnl_usdt'].sum()) if losses['pnl_usdt'].sum() != 0 else np.inf:.2f}")
        print(f"• Avg Win Amount       : {avg_win_pnl:.4f} USDT (Avg Win %: {avg_win_pct:.2f}%)")
        print(f"• Avg Loss Amount      : {avg_loss_pnl:.4f} USDT (Avg Loss %: {avg_loss_pct:.2f}%)")
        print(f"• Max Win %            : {max_win_pct:.2f}%")
        print(f"• Max Loss %           : {max_loss_pct:.2f}%")

        # 2. Leverage & Margin Size Analysis
        # Let's match back to raw trades to find the leverage and margin used for these closed trades.
        # Margin per trade is estimated as (entry_price * amount) / leverage.
        # Let's find leverage from raw trades by order_id or symbol.
        # In history_helper, each trade has raw leverage.
        # Let's calculate the margin for each closed cycle.
        margins = []
        leverages = []
        for c in closed_cycles:
            # Find raw entry trade to get leverage
            # Let's search raw_trades
            matching_entries = [t for t in raw_trades if t['symbol'] == c['symbol'] and t['category'] in ('진입', '*진입') and (abs((t['timestamp'] - c['entry_time']).total_seconds()) < 10 if c['entry_time'] else False)]
            if matching_entries:
                lev = matching_entries[0]['leverage']
            else:
                lev = 10 # fallback
            leverages.append(lev)
            if c['entry_price'] is not None:
                margin = (c['entry_price'] * c['amount']) / lev
                margins.append(margin)
        
        print("\n=== 2. LEVERAGE & MARGIN ANALYSIS ===")
        print(f"• Leverage Used        : {set(leverages)}")
        if margins:
            print(f"• Margin per Trade     : Avg {np.mean(margins):.2f} USDT, Min {np.min(margins):.2f} USDT, Max {np.max(margins):.2f} USDT")
            print(f"• Total Position Size  : Avg {np.mean(margins) * np.mean(leverages):.2f} USDT")
        else:
            print("• Margin per Trade     : Unknown")
            
        # 3. Direction Analysis
        long_trades = df_closed[df_closed['direction'].str.contains('LONG')]
        short_trades = df_closed[df_closed['direction'].str.contains('SHORT')]
        print("\n=== 3. DIRECTION PERFORMANCE ===")
        print(f"• LONG Trades  : Count {len(long_trades)}, PnL {long_trades['pnl_usdt'].sum():+.4f} USDT, Win Rate {len(long_trades[long_trades['pnl_usdt'] > 0]) / len(long_trades) * 100 if len(long_trades) > 0 else 0:.2f}%")
        print(f"• SHORT Trades : Count {len(short_trades)}, PnL {short_trades['pnl_usdt'].sum():+.4f} USDT, Win Rate {len(short_trades[short_trades['pnl_usdt'] > 0]) / len(short_trades) * 100 if len(short_trades) > 0 else 0:.2f}%")

        # 4. Ticker performance distribution
        print("\n=== 4. TICKER PERFORMANCE ===")
        ticker_groups = df_closed.groupby('symbol').agg({
            'pnl_usdt': ['sum', 'count'],
            'pnl_pct': 'mean'
        })
        ticker_groups.columns = ['PnL_sum', 'Count', 'Avg_Pct']
        ticker_groups = ticker_groups.sort_values('PnL_sum', ascending=False)
        for sym, row in ticker_groups.iterrows():
            print(f"• {sym:<15} : PnL {row['PnL_sum']:+.4f} USDT | Count {int(row['Count']):<3} | Avg PnL% {row['Avg_Pct']:+.2f}%")
            
    # 5. Concurrent Positions Analysis
    # Let's count concurrent open positions over time.
    # To do this, we collect all events (entry and exit) from recent raw trades, and sort them.
    # For each entry, active count increases by 1. For each exit, it decreases by 1.
    events = []
    for t in recent_raw:
        cat = t['category'].strip()
        sym = t['symbol']
        # Each unique order is an event. Let's group by symbol and category.
        # But wait, to be safe, let's track active symbols over time.
        # Let's build a timeline of active positions.
        # We can look at paired cycles: each cycle spans from entry_time to exit_time.
        # If exit_time is None, it runs until now.
        pass
        
    timeline = []
    for p in all_paired:
        if p['entry_time'] is not None:
            # Only consider cycles that were active during our period
            entry = p['entry_time']
            exit = p['exit_time'] if p['exit_time'] is not None else pd.Timestamp.now()
            
            # Check overlap with period [start_time, now]
            if exit >= start_time:
                timeline.append((entry, 1, p['symbol']))
                timeline.append((exit, -1, p['symbol']))
                
    timeline.sort(key=lambda x: x[0])
    
    current_active = set()
    max_active = 0
    max_active_time = None
    active_counts_at_events = []
    
    for event_time, val, sym in timeline:
        if event_time < start_time:
            # If the entry happened before start_time, it was already active at start_time
            if val == 1:
                current_active.add(sym)
            continue
            
        if val == 1:
            current_active.add(sym)
        else:
            current_active.discard(sym)
            
        active_counts_at_events.append((event_time, len(current_active), list(current_active)))
        if len(current_active) > max_active:
            max_active = len(current_active)
            max_active_time = event_time
            
    print("\n=== 5. CONCURRENT POSITIONS ===")
    print(f"• Max Concurrent Tickers: {max_active} (at {max_active_time})")
    # Average concurrent positions
    if active_counts_at_events:
        counts = [c[1] for c in active_counts_at_events]
        print(f"• Avg Concurrent Tickers: {np.mean(counts):.2f}")
    else:
        print(f"• Active tickers at start: {len(current_active)}")

    # 6. Holding time analysis
    if closed_cycles:
        durations = []
        for c in closed_cycles:
            if c['entry_time'] is not None and c['exit_time'] is not None:
                durations.append((c['exit_time'] - c['entry_time']).total_seconds() / 3600.0)
        if durations:
            print("\n=== 6. HOLDING TIME ANALYSIS ===")
            print(f"• Holding Duration (hrs): Avg {np.mean(durations):.2f} hours, Min {np.min(durations):.2f} hours, Max {np.max(durations):.2f} hours")

if __name__ == "__main__":
    analyze()
