import sys
import os
import time
from dotenv import load_dotenv
import logging

# Reconfigure stdout to use UTF-8 to prevent cp949 encoding errors on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure the core module can be imported
sys.path.append(os.getcwd())

from core.engine import QuantumEngine
from core.config import CFG

def check_enterable_tickers():
    load_dotenv(override=True)
    ak = os.getenv("BINANCE_API_KEY") or os.getenv("OKX_API_KEY")
    sk = os.getenv("BINANCE_SECRET_KEY") or os.getenv("OKX_SECRET_KEY")
    pw = os.getenv("BINANCE_PASSPHRASE") or os.getenv("OKX_PASSPHRASE")
    
    # Configure logging to stdout
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(message)s')
    
    engine = QuantumEngine()
    success, msg = engine.initialize(ak, sk, pw)
    if not success:
        print(f"Failed to initialize engine: {msg}")
        return

    print("=" * 60)
    print("현재 시각 기준 실시간 스캔 시작 (1회성)...")
    print(f"설정 타임프레임: {CFG.TIMEFRAME}")
    print(f"스캔 대상 상위 거래대금 개수: {CFG.SCAN_TOP_N}개")
    print("=" * 60)
    
    start_time = time.time()
    # 1회성 스캔 실행을 위해 running 플래그 임시 활성화
    engine.scanner._running = True
    engine.scanner._run_once()
    engine.scanner._running = False
    end_time = time.time()
    
    results = engine.scanner.get_results()
    
    enterable_tickers = [res for res in results if res['signal'] in ('long', 'short')]
    
    print(f"\n[스캔 요약]")
    print(f"- 전체 스캔된 페어 수: {len(results)}개")
    print(f"- 진입 신호 발생 페어 수: {len(enterable_tickers)}개")
    print(f"- 소요 시간: {end_time - start_time:.2f}초\n")
    
    if enterable_tickers:
        print("-" * 60)
        print(f"{'심볼':<20} | {'방향':<8} | {'현재가':<12} | {'강도':<6} | {'판단 근거'}")
        print("-" * 60)
        for res in enterable_tickers:
            direction_str = "🟢 LONG" if res['signal'] == 'long' else "🔴 SHORT"
            print(f"{res['symbol']:<20} | {direction_str:<8} | {res['price']:<12} | {res['strength']}% | {res['reason']}")
        print("-" * 60)
    else:
        print("현재 진입 조건(SSL 추세, 캔들 색상, AKMCD 영선 및 점 전환 등)을 모두 완벽하게 만족하는 진입 가능 종목이 없습니다.")

if __name__ == "__main__":
    check_enterable_tickers()
