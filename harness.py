"""
AI QUANTUM — Test Harness
실제 UI(Streamlit) 없이 엔진의 핵심 로직을 독립적으로 검증하는 하네스
"""
import time
import os
from dotenv import load_dotenv
from core.engine import QuantumEngine

def run_harness():
    print("[HARNESS] Starting engine test...")
    load_dotenv(override=True)
    
    api_key = os.getenv("OKX_API_KEY")
    secret_key = os.getenv("OKX_SECRET_KEY")
    passphrase = os.getenv("OKX_PASSPHRASE")
    
    if not all([api_key, secret_key, passphrase]):
        print("[ERR] API keys not found in .env.")
        return

    # 1. 엔진 초기화 테스트
    engine = QuantumEngine()
    success, msg = engine.initialize(api_key, secret_key, passphrase)
    print(f"[INIT] {msg}")
    
    if not success:
        return

    # 2. 데이터 조회 테스트
    print("\n[DATA] Dashboard status:")
    data = engine.get_dashboard_data()
    print(f" - Total Balance: ${data.get('total_balance', 0):,.2f} USDT")
    print(f" - Positions: {len(data.get('positions', []))}")

    # 3. 스캐너 구동 테스트
    print("\n[SCAN] Simulating scanner run...")
    engine.start_scanner()
    time.sleep(3) # 스캔 진행 시간 대기
    
    results = engine.get_scan_results()
    print(f" - Scan Results: {len(results)} items analyzed")
    if results:
        print(f" - First item: {results[0]['symbol']} (Signal: {results[0]['signal']})")

    # 4. 종료
    engine.stop_scanner()
    print("\n[HARNESS] All engine tests completed!")

if __name__ == "__main__":
    run_harness()
