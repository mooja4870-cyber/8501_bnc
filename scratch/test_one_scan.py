
import sys
import os
import time
from dotenv import load_dotenv
import logging

# Ensure the core module can be imported
sys.path.append(os.getcwd())

from core.engine import QuantumEngine
from core.config import CFG

def test_scan_cycle():
    load_dotenv(override=True)
    ak = os.getenv("OKX_API_KEY")
    sk = os.getenv("OKX_SECRET_KEY")
    pw = os.getenv("OKX_PASSPHRASE")
    
    # Configure logging to stdout
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    engine = QuantumEngine()
    success, msg = engine.initialize(ak, sk, pw)
    if not success:
        print(f"Failed to initialize: {msg}")
        return

    print("Starting one-off scan cycle...")
    start_time = time.time()
    
    # Run scanner once
    # We need to access private _run_once for testing
    engine.scanner._run_once()
    
    end_time = time.time()
    print(f"Scan cycle completed in {end_time - start_time:.2f} seconds")
    
    print("\n--- Scanner Logs ---")
    for log in engine.scanner.log_buffer:
        print(log)
        
    print("\n--- Scan Results ---")
    results = engine.scanner.get_results()
    print(f"Total results: {len(results)}")
    for res in results[:5]: # Show first 5
        print(f"{res['symbol']}: {res['signal']} (Strength: {res['strength']}, Reason: {res['reason']})")

if __name__ == "__main__":
    test_scan_cycle()
