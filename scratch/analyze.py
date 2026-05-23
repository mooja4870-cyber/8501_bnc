import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.history_helper import load_local_trade_history, aggregate_and_pair_trades
from collections import Counter

raw = load_local_trade_history()
print(f"Raw trades: {len(raw)}")

# Check side values
sides = Counter(t['side'] for t in raw)
print(f"Sides: {dict(sides)}")
cats = Counter(t['category'] for t in raw)
print(f"Categories: {dict(cats)}")

# Run pairing WITHOUT active positions (simulating offline)
paired = aggregate_and_pair_trades(raw)
print(f"Paired cycles: {len(paired)}")

statuses = Counter(p['status'] for p in paired)
for status, cnt in statuses.items():
    print(f"  Status '{status}': {cnt}")

# Analyze problems
holding_count = sum(1 for p in paired if p['status'] == '\xeb\xb3\xb4\xec\x9c\xa0 \xec\xa4\x91' or 'holding' in str(p['status']).lower() or p['status'] == '\ubcf4\uc720 \uc911')
print(f"\nHolding (no exit): {holding_count}")

# Count entries with side='long' or 'short' (not buy/sell)
raw_long_short = [t for t in raw if t['side'].lower() in ('long', 'short')]
print(f"\nRaw trades with side=long/short (instead of buy/sell): {len(raw_long_short)}")
for t in raw_long_short[:5]:
    print(f"  {t['timestamp']} {t['symbol']} cat={t['category']} side={t['side']} price={t['price']}")

# Show direction detection issues
print("\n=== Direction detection test ===")
from core.history_helper import get_position_direction
test_cases = [
    ("entry", "buy"), ("entry", "sell"),
    ("exit", "buy"), ("exit", "sell"),
    ("entry", "long"), ("entry", "short"),
]
for cat, side in test_cases:
    cat_kr = "\uc9c4\uc785" if "entry" in cat else "\uccad\uc0b0"
    d = get_position_direction(cat_kr, side)
    print(f"  cat={cat_kr} side={side} -> direction={d}")

# Show problematic cycles
print("\n=== Sample paired cycles ===")
for i, p in enumerate(paired[:20]):
    entry_t = str(p.get('entry_time', '-'))[:19]
    exit_t = str(p.get('exit_time', '-'))[:19]
    ep = p.get('entry_price')
    xp = p.get('exit_price')
    ep_str = f"{ep:.6f}" if ep else "-"
    xp_str = f"{xp:.6f}" if xp else "-"
    d = p.get('direction', '?').replace('\U0001f7e2', 'G').replace('\U0001f534', 'R')
    print(f"  [{i}] {p['symbol'][:15]:<15} {d:<10} entry={entry_t} exit={exit_t} ep={ep_str} xp={xp_str} pnl={p.get('pnl_usdt')} status={p['status']}")

# Check for mismatched pairing - same order getting paired as entry AND exit
print("\n=== Checking entry-exit mismatch ===")
entry_no_exit = sum(1 for p in paired if p.get('exit_time') is None)
exit_no_entry = sum(1 for p in paired if p.get('entry_time') is None)
print(f"  Entry without exit: {entry_no_exit}")
print(f"  Exit without entry: {exit_no_entry}")

# Check symbol-level entry/exit balance
print("\n=== Per-symbol entry/exit imbalance ===")
sym_entries = Counter()
sym_exits = Counter()
for t in raw:
    cat = t['category'].strip()
    if cat in ('\uc9c4\uc785', '*\uc9c4\uc785'):
        sym_entries[t['symbol']] += 1
    elif '\uccad\uc0b0' in cat:
        sym_exits[t['symbol']] += 1

all_syms = sorted(set(list(sym_entries.keys()) + list(sym_exits.keys())))
for sym in all_syms[:15]:
    e = sym_entries.get(sym, 0)
    x = sym_exits.get(sym, 0)
    diff = e - x
    if abs(diff) > 2:
        print(f"  {sym}: entries={e} exits={x} diff={diff}")
