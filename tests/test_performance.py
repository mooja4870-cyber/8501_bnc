"""
AI QUANTUM — Lv.5 성능 하네스 & 프로파일링 테스트
전체 종목 스캔 소요 시간, CPU/Memory 프로파일링 검증
"""
import pytest
import sys
import os
import time
import tracemalloc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mock_exchange import MockBinanceClient
from core.scanner import Scanner


def test_performance_and_memory_profiling():
    print("\n" + "=" * 50)
    print("  AI QUANTUM - PERFORMANCE & PROFILE HARNESS  ")
    print("=" * 50)
    
    # 1. tracemalloc 초기화
    tracemalloc.start()
    
    # 2. Mock 인스턴스 준비
    import asyncio
    mock = MockBinanceClient()
    asyncio.run(mock.load_markets())
    scanner = Scanner(mock)
    
    # 3. 메모리 측정 시작 스냅샷
    snapshot1 = tracemalloc.take_snapshot()
    initial_mem, _ = tracemalloc.get_traced_memory()
    print(f"[MEM] 초기 메모리 사용량: {initial_mem / 1024:.2f} KB")
    
    # 4. 스캔 1회 시간 측정
    start_time = time.time()
    asyncio.run(scanner._run_once())
    duration = time.time() - start_time
    
    # 5. 메모리 측정 종료 스냅샷
    snapshot2 = tracemalloc.take_snapshot()
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    symbols_count = len(mock.get_all_usdt_swap_symbols())
    avg_duration_per_pair = duration / symbols_count if symbols_count > 0 else 0
    
    print("-" * 50)
    print(f"[TIME] 총 스캔 대상 종목 수: {symbols_count}개")
    print(f"[TIME] 전체 스캔 소요 시간: {duration:.4f} 초")
    print(f"[TIME] 종목당 평균 스캔 소요 시간: {avg_duration_per_pair:.4f} 초")
    print(f"[MEM] 현재 메모리 사용량: {current_mem / (1024 * 1024):.4f} MB")
    print(f"[MEM] 피크 메모리 사용량: {peak_mem / (1024 * 1024):.4f} MB")
    print("=" * 50)
    
    # 성능 게이트 검증
    # Mock이라 매우 빠르고 가벼워야 함 (전체 시간 < 5.0초, 피크 메모리 < 20MB)
    assert duration < 5.0, f"스캔 시간이 너무 깁니다: {duration:.2f}초"
    assert peak_mem < 20 * 1024 * 1024, f"피크 메모리가 너무 높습니다: {peak_mem / (1024*1024):.2f} MB"
    
    # 상위 메모리 할당 위치 분석 출력
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    print("[MEM_TOP] 상위 메모리 소비 라인:")
    for stat in top_stats[:3]:
        print(f"  {stat}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
