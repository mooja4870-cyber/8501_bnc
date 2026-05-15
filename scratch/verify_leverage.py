"""
레버리지 파싱 검증 스크립트
실제 OKX API를 호출하여 알트코인 5종의 레버리지를 테스트
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(override=True)

from core.exchange import OKXClient
from core.config import CFG

client = OKXClient(
    os.getenv("OKX_API_KEY"),
    os.getenv("OKX_SECRET_KEY"),
    os.getenv("OKX_PASSPHRASE"),
)
client.load_markets()

test_symbols = [
    "UMA/USDT:USDT",
    "AAVE/USDT:USDT",
    "AVAX/USDT:USDT",
    "AVNT/USDT:USDT",
    "DOGE/USDT:USDT",
]

print("=" * 70)
print(f"설정 레버리지: {CFG.LEVERAGE}x | 증거금: ${CFG.MARGIN_USDT}")
print("=" * 70)

for sym in test_symbols:
    market = client._markets.get(sym)
    if not market:
        print(f"  {sym}: 마켓 정보 없음")
        continue

    inst_id = market.get("id", sym)
    
    # 1단계: set_leverage 호출 (기존 로직)
    try:
        resp = client.exchange.set_leverage(
            int(CFG.LEVERAGE), sym, params={"mgnMode": "isolated"}
        )
        old_parsed = None
        if isinstance(resp, dict):
            old_parsed = resp.get('lever') or resp.get('data', [{}])[0].get('lever')
        print(f"\n[{sym}]")
        print(f"  set_leverage 응답 파싱: {old_parsed}")
    except Exception as e:
        print(f"\n[{sym}]")
        print(f"  set_leverage 에러: {e}")
        old_parsed = None

    # 2단계: 2차 검증 (신규 로직) - privateGetAccountLeverageInfo
    try:
        acct_resp = client.exchange.privateGetAccountLeverageInfo({
            "instId": inst_id,
            "mgnMode": "isolated",
        })
        acct_data = acct_resp.get("data", [])
        verified = acct_data[0].get("lever") if acct_data else "N/A"
        print(f"  API 2차 검증 (실제): {verified}x")
    except Exception as e:
        print(f"  API 2차 검증 실패: {e}")
        verified = "?"

    # 3단계: 비교
    if old_parsed and verified != "?":
        match = str(old_parsed) == str(verified)
        if match:
            print(f"  ✅ 1차 파싱 = 2차 검증 → 정상")
        else:
            print(f"  ❌ 불일치! 1차={old_parsed}x vs 실제={verified}x → 이전엔 {old_parsed}x로 수량 계산했을 것")
    
    # 수량 계산 비교
    if verified and verified != "?" and verified != "N/A":
        actual_lev = float(verified)
        correct_notional = CFG.MARGIN_USDT * actual_lev
        wrong_notional = CFG.MARGIN_USDT * CFG.LEVERAGE
        print(f"  [수정 후] ${ CFG.MARGIN_USDT} × {actual_lev}x = ${correct_notional:.2f} 노셔널")
        print(f"  [수정 전] ${ CFG.MARGIN_USDT} × {CFG.LEVERAGE}x = ${wrong_notional:.2f} 노셔널 ← 버그")

print("\n" + "=" * 70)
print("검증 완료")
