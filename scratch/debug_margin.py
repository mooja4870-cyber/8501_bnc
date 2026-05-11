import os
import sys
from dotenv import load_dotenv

# 프로젝트 경로 추가
sys.path.append(os.path.abspath('.'))

from core.exchange import OKXClient

def debug_balance_and_orders():
    load_dotenv()
    ak = os.getenv("OKX_API_KEY")
    sk = os.getenv("OKX_SECRET_KEY")
    pw = os.getenv("OKX_PASSPHRASE")
    
    client = OKXClient(ak, sk, pw)
    client.load_markets()
    
    print("--- Detailed Balance Info ---")
    try:
        # fetch_balance의 raw data 확인
        bal = client.exchange.fetch_balance({"type": "swap"})
        usdt = bal.get("info", {}).get("data", [{}])[0].get("details", [{}])[0]
        # OKX v5 details 구조는 다를 수 있음. ccxt의 usdt dict 확인
        usdt_ccxt = bal.get("USDT", {})
        print(f"CCXT USDT: {usdt_ccxt}")
        
        # OKX v5 전용 balance 조회 (계좌 상세)
        raw_bal = client.exchange.privateGetAccountBalance()
        details = raw_bal.get('data', [{}])[0].get('details', [])
        for d in details:
            if d.get('ccy') == 'USDT':
                print(f"OKX Raw USDT Detail: {d}")
                # eq: Equity, availEq: Available Equity, frozenBal: Frozen Balance, ordFrozen: Order Frozen
                print(f"  - Equity (eq): {d.get('eq')}")
                print(f"  - Available Eq (availEq): {d.get('availEq')}")
                print(f"  - Frozen (frozenBal): {d.get('frozenBal')}")
                print(f"  - Order Frozen (ordFrozen): {d.get('ordFrozen')}")
    except Exception as e:
        print(f"Balance check error: {e}")

    print("\n--- Open Orders (Conditional/Trigger) ---")
    try:
        # OKX v5 trigger orders
        triggers = client.exchange.privateGetTradeOrdersAlgoPending({'ordType': 'conditional'})
        data = triggers.get('data', [])
        print(f"Pending Algo Orders: {len(data)}")
        for o in data:
            print(f"  - {o.get('instId')} {o.get('side')} {o.get('ordType')} Sz:{o.get('sz')} TrgPrice:{o.get('slTriggerPx') or o.get('tpTriggerPx')}")
    except Exception as e:
        print(f"Algo orders check error: {e}")

    print("\n--- Active Positions ---")
    pos = client.get_positions()
    for p in pos:
        print(f"  - {p['symbol']} {p['side']} Size:{p['size']} Margin:{p['margin']}")

if __name__ == "__main__":
    debug_balance_and_orders()
