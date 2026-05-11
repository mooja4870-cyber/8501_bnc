import os
import sys
from dotenv import load_dotenv

# 프로젝트 경로 추가
sys.path.append(os.path.abspath('.'))

from core.exchange import OKXClient
from core.config import CFG

def check_symbol_leverage():
    load_dotenv()
    ak = os.getenv("OKX_API_KEY")
    sk = os.getenv("OKX_SECRET_KEY")
    pw = os.getenv("OKX_PASSPHRASE")
    
    client = OKXClient(ak, sk, pw)
    client.load_markets()
    
    symbols = ["BTC/USDT:USDT", "ORCL/USDT:USDT", "COIN/USDT:USDT"]
    
    for symbol in symbols:
        print(f"\n--- Analysis: {symbol} ---")
        market = client._markets.get(symbol, {})
        # OKX v5 leverage info from markets might be limited, let's fetch it
        try:
            # 현재 설정된 레버리지 조회
            lev_info = client.exchange.privateGetAccountLeverageInfo({
                'instId': symbol.replace('/', '-').replace(':USDT', ''),
                'mgnMode': 'isolated'
            })
            data = lev_info.get('data', [{}])[0]
            print(f"  Current Leverage on OKX: {data.get('lever')}")
            print(f"  Max Leverage allowed: {data.get('maxLever')}")
            
            # 우리 설정값
            print(f"  Our Config Leverage: {CFG.LEVERAGE}")
            
            # 가상 주문 계산
            price = client.get_ticker(symbol).get('last', 100)
            target_margin = CFG.MARGIN_USDT
            target_notional = target_margin * CFG.LEVERAGE
            amount = target_notional / price
            
            actual_lev = float(data.get('lever', 1))
            required_margin_at_actual = target_notional / actual_lev
            
            print(f"  Target Margin: ${target_margin}")
            print(f"  Target Notional: ${target_notional}")
            print(f"  Required Margin at {actual_lev}x: ${required_margin_at_actual:.2f}")
            
            if actual_lev < CFG.LEVERAGE:
                print(f"  >> ISSUE: Leverage is capped at {actual_lev}x. Your ${target_margin} risk became ${required_margin_at_actual:.2f} real margin!")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    check_symbol_leverage()
