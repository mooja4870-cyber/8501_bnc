import os
import sys
from dotenv import load_dotenv

# 프로젝트 경로 추가
sys.path.append(os.path.abspath('.'))

from core.exchange import OKXClient
from core.engine import QuantumEngine
import time

def check_scanner():
    load_dotenv()
    engine = QuantumEngine()
    ak = os.getenv("OKX_API_KEY")
    sk = os.getenv("OKX_SECRET_KEY")
    pw = os.getenv("OKX_PASSPHRASE")
    
    if not (ak and sk and pw):
        print("API keys not found in .env")
        return

    success, msg = engine.initialize(ak, sk, pw)
    print(f"Engine init: {success}, {msg}")
    
    if success:
        print("Starting scanner for a few seconds...")
        engine.start_scanner()
        time.sleep(10) # 10초 정도 대기하며 결과 확인
        
        results = engine.get_scan_results()
        print(f"Scan results count: {len(results)}")
        for r in results[:5]:
            print(f" - {r['symbol']}: {r['signal']} (Strength: {r['strength']}%)")
            
        logs = engine.get_system_logs(10)
        print("\nRecent Logs:")
        for l in logs:
            print(l)
        
        engine.stop_scanner()

if __name__ == "__main__":
    check_scanner()
