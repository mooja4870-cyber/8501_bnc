import sys
import os
# 프로젝트 루트를 경로에 추가
sys.path.append(os.getcwd())

from core.engine import QuantumEngine

def test_singleton():
    print("--- Singleton Verification Test ---")
    
    # 첫 번째 인스턴스 생성
    engine1 = QuantumEngine()
    print(f"Engine 1 ID: {id(engine1)}")
    
    # 두 번째 인스턴스 생성
    engine2 = QuantumEngine()
    print(f"Engine 2 ID: {id(engine2)}")
    
    # 두 객체가 동일한지 비교
    is_same = (engine1 is engine2)
    print(f"Are they the same instance? {is_same}")
    
    if is_same:
        print("\n✅ 증빙 완료: 두 객체의 메모리 주소가 동일합니다. 전역적으로 단 하나의 엔진만 존재합니다.")
    else:
        print("\n❌ 증빙 실패: 두 객체가 서로 다릅니다.")

if __name__ == "__main__":
    test_singleton()
