
import sys
import os
from dotenv import load_dotenv

# Ensure the core module can be imported
sys.path.append(os.getcwd())

from core.engine import QuantumEngine
from core.config import CFG

def run_diagnosis():
    load_dotenv(override=True)
    ak = os.getenv("OKX_API_KEY")
    sk = os.getenv("OKX_SECRET_KEY")
    pw = os.getenv("OKX_PASSPHRASE")
    
    print(f"API Key present: {bool(ak)}")
    print(f"Secret Key present: {bool(sk)}")
    print(f"Passphrase present: {bool(pw)}")
    
    engine = QuantumEngine()
    success, msg = engine.initialize(ak, sk, pw)
    print(f"Initialization: {success}")
    
    if success:
        report = engine.perform_self_diagnosis()
        print("\n--- Self Diagnosis Report ---")
        print(f"Status: {report['status']}")
        for detail in report['details']:
            print(detail)
            
        print("\n--- Scanner Check ---")
        symbols = engine.client.get_all_usdt_swap_symbols()
        print("Total USDT Swap Symbols: " + str(len(symbols)))
        
        all_tickers = engine.client.get_all_tickers()
        print("Total Tickers fetched: " + str(len(all_tickers)))
        
        if len(symbols) > 0 and len(all_tickers) > 0:
            sample_sym = symbols[0]
            print(f"Sample symbol: {sample_sym}")
            print(f"Ticker for sample: {all_tickers.get(sample_sym)}")
            
            # Check volume filter
            count_above_vol = 0
            for sym in symbols:
                ticker = all_tickers.get(sym)
                if ticker and ticker.get("volume", 0) >= CFG.MIN_VOLUME_USDT:
                    count_above_vol += 1
            print(f"Symbols above volume threshold ({CFG.MIN_VOLUME_USDT}): {count_above_vol}")

if __name__ == "__main__":
    run_diagnosis()
