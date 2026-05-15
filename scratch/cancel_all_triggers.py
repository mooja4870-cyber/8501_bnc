"""
Emergency Script: OKX Trigger/Algo Cancel All
----------------------------------------------
OKX Trigger/Algo orders use a separate API endpoint.
This script queries and cancels all pending algo orders.

Usage:
  python scratch/cancel_all_triggers.py
"""
import sys
import os
import io

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

import ccxt
import time


def main():
    api_key = os.getenv("OKX_API_KEY")
    secret = os.getenv("OKX_SECRET_KEY")
    passphrase = os.getenv("OKX_PASSPHRASE")

    if not all([api_key, secret, passphrase]):
        print("[ERROR] .env API keys not configured.")
        return

    exchange = ccxt.okx({
        "apiKey": api_key,
        "secret": secret,
        "password": passphrase,
        "options": {
            "defaultType": "swap",
            "adjustForTimeDifference": True,
        },
        "enableRateLimit": True,
    })

    exchange.load_markets()

    # ===================================================
    # Step 1: Query Algo (Trigger) Orders
    # ===================================================
    print("\n" + "=" * 60)
    print("[SCAN] Querying OKX Algo/Trigger orders...")
    print("=" * 60)

    algo_orders = []
    
    order_types = ["conditional", "trigger", "move_order_stop", "trailing_stop"]
    
    for ord_type in order_types:
        try:
            resp = exchange.privateGetTradeOrdersAlgoPending({
                "ordType": ord_type,
                "instType": "SWAP",
            })
            orders = resp.get("data", [])
            if orders:
                algo_orders.extend(orders)
                print(f"  [{ord_type}] {len(orders)} found")
            else:
                print(f"  [{ord_type}] none")
        except Exception as e:
            print(f"  [{ord_type}] error: {e}")

    if not algo_orders:
        print("\n[OK] No pending Algo/Trigger orders found. System is clean.")
        return

    # ===================================================
    # Step 2: Display Summary
    # ===================================================
    print(f"\n[WARNING] Total {len(algo_orders)} Algo/Trigger orders found!\n")
    
    by_symbol = {}
    for o in algo_orders:
        inst = o.get("instId", "UNKNOWN")
        if inst not in by_symbol:
            by_symbol[inst] = []
        by_symbol[inst].append(o)

    print(f"{'Symbol':<25} {'Type':<20} {'Side':<8} {'Size':<10} {'TriggerPx':<15}")
    print("-" * 80)
    
    for symbol, orders in sorted(by_symbol.items()):
        for o in orders:
            ord_type = o.get("ordType", "?")
            side = o.get("side", "?")
            sz = o.get("sz", "?")
            trigger_px = o.get("triggerPx", o.get("slTriggerPx", o.get("tpTriggerPx", "-")))
            print(f"  {symbol:<23} {ord_type:<20} {side:<8} {sz:<10} {trigger_px:<15}")
        
    print(f"\n{'='*60}")
    print(f"Summary by symbol:")
    for symbol, orders in sorted(by_symbol.items()):
        print(f"  {symbol}: {len(orders)} orders")
    print(f"{'='*60}")

    # ===================================================
    # Step 3: Confirm and Cancel
    # ===================================================
    confirm = input(f"\n[CONFIRM] Cancel all {len(algo_orders)} orders? (yes/no): ").strip().lower()
    
    if confirm != "yes":
        print("Cancelled by user.")
        return

    print(f"\n[CANCEL] Starting cancellation of {len(algo_orders)} orders...\n")
    
    success = 0
    failed = 0
    
    batch_size = 10
    
    for i in range(0, len(algo_orders), batch_size):
        batch = algo_orders[i:i+batch_size]
        cancel_params = []
        
        for o in batch:
            cancel_params.append({
                "algoId": o["algoId"],
                "instId": o["instId"],
            })
        
        try:
            resp = exchange.privatePostTradeCancelAlgos(cancel_params)
            result_data = resp.get("data", [])
            
            for r in result_data:
                if r.get("sCode") == "0":
                    success += 1
                    print(f"  [OK] {r.get('algoId')} cancelled")
                else:
                    failed += 1
                    print(f"  [FAIL] {r.get('algoId')}: {r.get('sMsg', 'unknown')}")
                    
        except Exception as e:
            print(f"  [WARN] Batch cancel failed, trying individual: {e}")
            for o in batch:
                try:
                    exchange.privatePostTradeCancelAlgos([{
                        "algoId": o["algoId"],
                        "instId": o["instId"],
                    }])
                    success += 1
                    print(f"  [OK] {o['algoId']} ({o['instId']}) cancelled")
                except Exception as e2:
                    failed += 1
                    print(f"  [FAIL] {o['algoId']} ({o['instId']}): {e2}")
        
        time.sleep(0.3)
    
    print(f"\n{'='*60}")
    print(f"[RESULT] Success: {success} / Failed: {failed} / Total: {len(algo_orders)}")
    print(f"{'='*60}")
    
    if failed > 0:
        print("\n[WARN] Some cancellations failed. Check OKX web/app manually.")
    else:
        print("\n[DONE] All Trigger orders successfully cancelled!")


if __name__ == "__main__":
    main()
