import os
import sys
import pandas as pd
from dotenv import load_dotenv

sys.path.append(os.getcwd())
from core.exchange import OKXClient
from core.config import CFG

def verify_sync_status():
    load_dotenv()
    api_key = os.getenv("OKX_API_KEY", "")
    secret_key = os.getenv("OKX_SECRET_KEY", "")
    passphrase = os.getenv("OKX_PASSPHRASE", "")
    client = OKXClient(api_key, secret_key, passphrase)
    
    # 1. 현재 설정값 확인
    current_tp_pct = CFG.TAKE_PROFIT_PCT * 100
    current_sl_pct = CFG.STOP_LOSS_PCT * 100
    
    print("="*60)
    print(f"[Config Check] TP: {current_tp_pct:.2f}% | SL: {current_sl_pct:.2f}%")
    print("="*60)

    # 2. 보유 포지션 조회
    positions = client.get_positions()
    if not positions:
        print("[!] 현재 보유 중인 포지션이 없습니다.")
        return

    # 3. 미체결 주문(SL/TP) 조회
    open_orders = client.get_open_orders()
    
    report_data = []
    
    for p in positions:
        symbol = p["symbol"]
        entry_price = p["entry_price"]
        side = p["side"]
        
        # 해당 심볼의 SL/TP 주문 찾기
        sl_order = next((o for o in open_orders if o["symbol"] == symbol and o["type"] == "stop" and (("sell" in o["side"] and side == "long") or ("buy" in o["side"] and side == "short")) and (abs(float(o["price"]) - entry_price*(1-CFG.STOP_LOSS_PCT)) < entry_price*0.01 or abs(float(o["price"]) - entry_price*(1+CFG.STOP_LOSS_PCT)) < entry_price*0.01)), None)
        tp_order = next((o for o in open_orders if o["symbol"] == symbol and o["type"] == "stop" and (("sell" in o["side"] and side == "long") or ("buy" in o["side"] and side == "short")) and (abs(float(o["price"]) - entry_price*(1+CFG.TAKE_PROFIT_PCT)) < entry_price*0.01 or abs(float(o["price"]) - entry_price*(1-CFG.TAKE_PROFIT_PCT)) < entry_price*0.01)), None)
        
        # 실제 적용된 % 계산
        actual_sl_pct = 0.0
        actual_tp_pct = 0.0
        
        if sl_order:
            actual_sl_pct = abs((float(sl_order["price"]) - entry_price) / entry_price) * 100
        if tp_order:
            actual_tp_pct = abs((float(tp_order["price"]) - entry_price) / entry_price) * 100

        report_data.append({
            "Symbol": symbol,
            "Side": side,
            "Entry": entry_price,
            "Set_SL(%)": current_sl_pct,
            "Real_SL(%)": round(actual_sl_pct, 2),
            "Set_TP(%)": current_tp_pct,
            "Real_TP(%)": round(actual_tp_pct, 2),
            "Sync": "OK" if abs(actual_sl_pct - current_sl_pct) < 0.1 and abs(actual_tp_pct - current_tp_pct) < 0.1 else "Updating"
        })

    report_df = pd.DataFrame(report_data)
    print(report_df.to_string(index=False))
    print("="*60)
    
    if any(d["Sync"] == "Updating" for d in report_data):
        print("[Note] Syncing can take up to 30 seconds. Please check again soon.")
    else:
        print("All positions are perfectly synced with the new configuration.")

if __name__ == "__main__":
    verify_sync_status()
