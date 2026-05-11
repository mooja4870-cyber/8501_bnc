import ccxt
import pandas as pd
from datetime import datetime, timedelta
import warnings
import sys

# Force UTF-8 output
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

warnings.filterwarnings("ignore")

# API Keys
api_key = 'fd67e23d-8857-4ef4-9761-39b0b0cd13bd'
secret_key = '57172B2A5F19E6FBF808161AE40BFB00'
passphrase = 'COco@@5454'

exchange = ccxt.okx({
    'apiKey': api_key,
    'secret': secret_key,
    'password': passphrase,
    'options': {'defaultType': 'swap'},
    'enableRateLimit': True,
})

def get_report():
    try:
        now_kst = datetime.utcnow() + timedelta(hours=9)
        today_str = now_kst.strftime('%Y-%m-%d')

        print(f"\n[AI QUANTUM] 2026-05-11 Trade Report\n")

        # 1. Recent trades
        trades = exchange.fetch_my_trades(limit=50)
        today_trades = []
        for t in trades:
            ts_kst = pd.to_datetime(t['timestamp'], unit='ms') + pd.Timedelta(hours=9)
            if ts_kst.strftime('%Y-%m-%d') == today_str:
                today_trades.append({
                    'time': ts_kst.strftime('%H:%M:%S'),
                    'symbol': t['symbol'],
                    'side': t['side'],
                    'price': t['price'],
                    'amount': t['amount'],
                    'cost': t.get('cost', 0) or 0
                })

        print("Today's Fills (Entry/Exit):")
        if today_trades:
            today_trades.sort(key=lambda x: x['time'])
            for tr in today_trades:
                side_label = "LONG" if tr['side'] == 'buy' else "SHORT"
                print(f"   - [{tr['time']}] {tr['symbol']:<15} | {side_label:<8} | Price: {tr['price']:>10.4f} | Cost: {tr['cost']:>7.2f} USDT")
        else:
            print("   - No fills found for today.")

        # 2. Open positions
        print("\nActive Positions:")
        positions = exchange.fetch_positions()
        active = [p for p in positions if float(p.get('contracts', 0) or 0) > 0]
        if active:
            for p in active:
                pnl_pct = float(p.get('unrealizedPnlPcnt', 0) or 0) * 100
                side_label = "LONG" if p['side'] == 'long' else "SHORT"
                print(f"   - {p['symbol']:<15} | {side_label:<8} | Entry: {p['entryPrice']:>10.4f} | PnL: {pnl_pct:>+6.2f}%")
        else:
            print("   - No active positions.")

    except Exception as e:
        print(f"Error fetching data: {e}")

if __name__ == "__main__":
    get_report()
