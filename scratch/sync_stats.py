import os
import sys
import pandas as pd
from dotenv import load_dotenv

# 프로젝트 루트를 패스에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")

from core.exchange import OKXClient
import core.stats as stats_store

def sync():
    load_dotenv(override=True)
    api_key = os.getenv("OKX_API_KEY")
    secret_key = os.getenv("OKX_SECRET_KEY")
    passphrase = os.getenv("OKX_PASSPHRASE")

    if not all([api_key, secret_key, passphrase]):
        print("Error: API keys not found in .env")
        return

    print("Starting deep sync with OKX...")
    client = OKXClient(api_key, secret_key, passphrase)
    if not client.load_markets():
        print("Error: Market load failed")
        return

    all_trades = []
    last_id = None
    
    # 여러 번 루프를 돌며 과거 데이터를 가져옴 (최대 500건까지)
    for i in range(5):
        try:
            params = {}
            if last_id:
                params['after'] = last_id  # OKX v5 uses 'after' for older records
                
            # ccxt fetch_my_trades
            trades = client.exchange.fetch_my_trades(symbol=None, limit=100, params=params)
            
            if not trades:
                break
                
            # client.get_trade_history 형식으로 변환 (pnl_usdt 등 포함)
            # 여기서는 로직 단순화를 위해 직접 client의 변환 로직을 모방하거나 
            # client.get_trade_history를 수정해서 사용할 수 있지만, 
            # 일단 직접 처리
            for t in trades:
                raw = t.get('info', {})
                side = t.get('side')
                pos_side = raw.get('posSide')
                trade_type = "—"
                if pos_side == "long":
                    trade_type = "진입" if side == "buy" else "청산"
                elif pos_side == "short":
                    trade_type = "진입" if side == "sell" else "청산"
                
                all_trades.append({
                    'id': t['id'],
                    'type': trade_type,
                    'order_id': t.get('order'),
                    'pnl_usdt': float(raw.get('fillPnl', 0)) if trade_type == "청산" else 0.0
                })
            
            last_id = trades[-1]['id']
            print(f"Fetched {len(trades)} trades (Total: {len(all_trades)})")
            
            if len(trades) < 100:
                break
        except Exception as e:
            print(f"Error during fetch loop {i}: {e}")
            break

    if not all_trades:
        print("Warning: No trades found")
        return

    close_results = {}
    for t in all_trades:
        if t['type'] == '청산' and t.get('order_id'):
            oid = t['order_id']
            pnl = t['pnl_usdt']
            close_results[oid] = close_results.get(oid, 0.0) + pnl

    total_wins = sum(1 for pnl in close_results.values() if pnl >= 0)
    total_losses = sum(1 for pnl in close_results.values() if pnl < 0)
    
    data = stats_store.load_stats()
    data["total_wins"] = total_wins
    data["total_losses"] = total_losses
    data["total_trades"] = sum(1 for t in all_trades if t['type'] == '진입')
    
    stats_store.save_stats(data)
    
    print("Deep Sync Complete!")
    print(f"Stats: {total_wins}W / {total_losses}L (Total {len(close_results)} closes)")
    if (total_wins + total_losses) > 0:
        print(f"Win Rate: {(total_wins / (total_wins + total_losses) * 100):.1f}%")

if __name__ == "__main__":
    sync()
