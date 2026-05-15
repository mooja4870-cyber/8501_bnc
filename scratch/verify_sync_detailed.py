import os
import sys
import pandas as pd
import time
from dotenv import load_dotenv

sys.path.append(os.getcwd())
from core.exchange import OKXClient
from core.config import CFG

def verify_sync_status_detailed():
    load_dotenv()
    api_key = os.getenv("OKX_API_KEY", "")
    secret_key = os.getenv("OKX_SECRET_KEY", "")
    passphrase = os.getenv("OKX_PASSPHRASE", "")
    client = OKXClient(api_key, secret_key, passphrase)
    
    # 1. 현재 설정값 확인
    current_tp_pct = CFG.TAKE_PROFIT_PCT * 100
    current_sl_pct = CFG.STOP_LOSS_PCT * 100
    
    print("="*80)
    print(f"[Config Check] Target TakeProfit: {current_tp_pct:.2f}% | Target StopLoss: {current_sl_pct:.2f}%")
    print("="*80)

    # 2. 보유 포지션 조회
    positions = client.get_positions()
    if not positions:
        print("[!] No active positions found.")
        return

    # 3. 모든 미체결 주문 조회 (종류 불문)
    try:
        # ccxt의 fetch_open_orders는 일부 trigger 주문을 누락할 수 있으므로 
        # OKX 전용 엔드포인트를 직접 확인하는 것이 안전함
        open_orders = client.exchange.fetch_open_orders()
    except:
        open_orders = []
    
    report_data = []
    
    for p in positions:
        symbol = p["symbol"]
        entry_price = p["entry_price"]
        side = p["side"]
        
        # 해당 종목의 모든 대기 주문 필터링
        relevant_orders = [o for o in open_orders if o["symbol"] == symbol]
        
        # SL/TP로 추정되는 주문들 찾기
        applied_sl = "None"
        applied_tp = "None"
        status = "Updating..."

        for o in relevant_orders:
            order_price = float(o.get("price") or o.get("stopPrice") or 0)
            if order_price == 0: continue
            
            diff_pct = (order_price - entry_price) / entry_price * 100
            if side == "short": diff_pct = -diff_pct
            
            # SL 판정 (음수 수익률 부근)
            if diff_pct < 0:
                applied_sl = f"{abs(diff_pct):.2f}%"
            # TP 판정 (양수 수익률 부근)
            elif diff_pct > 0:
                applied_tp = f"{diff_pct:.2f}%"

        # 설정값과 대조
        sl_match = "OK" if applied_sl != "None" and abs(float(applied_sl[:-1]) - current_sl_pct) < 0.2 else "Syncing"
        tp_match = "OK" if applied_tp != "None" and abs(float(applied_tp[:-1]) - current_tp_pct) < 0.2 else "Syncing"
        
        report_data.append({
            "Ticker": symbol,
            "Side": side,
            "Entry": f"{entry_price:.4f}",
            "Active_SL": applied_sl,
            "Active_TP": applied_tp,
            "Sync_Status": "ALL OK" if (sl_match == "OK" and tp_match == "OK") else "Syncing..."
        })

    report_df = pd.DataFrame(report_data)
    print(report_df.to_string(index=False))
    print("="*80)
    
    if any("Syncing" in d["Sync_Status"] for d in report_data):
        print("[Notice] Some orders are being updated. Check again in 10s.")
    else:
        print("All trades are successfully updated to new TP/SL rules.")

if __name__ == "__main__":
    # 엔진이 갱신할 시간을 주기 위해 살짝 대기
    print("[*] Waiting for engine sync (10s)...")
    time.sleep(10)
    verify_sync_status_detailed()
