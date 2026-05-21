import sys
import os
# 프로젝트 루트를 경로에 추가
sys.path.append(os.getcwd())

from core.engine import QuantumEngine

def test_singleton():
    print("--- Singleton Verification Test ---")
    
    # get_instance() 호출
    engine1 = QuantumEngine.get_instance()
    print(f"Engine 1 ID: {id(engine1)}")
    
    # 두 번째 get_instance() 호출
    engine2 = QuantumEngine.get_instance()
    print(f"Engine 2 ID: {id(engine2)}")
    
    # 두 객체가 동일한지 비교
    is_same = (engine1 is engine2)
    print(f"Are they the same instance? {is_same}")
    
    if is_same:
        print("[SUCCESS] Both variables point to the exact same memory address. Singleton verified.")
    else:
        print("[FAILED] Variables point to different memory addresses.")

if __name__ == "__main__":
    test_singleton()
