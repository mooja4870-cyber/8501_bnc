"""
OKX 자동매매봇 - AKMCD + SSL 하이브리드 전략
===============================================
대본 기반: 코인슈타인 전략 구현

[ 설치 방법 ]
터미널(명령 프롬프트)에서 아래 명령어 실행:
    pip install python-okx pandas numpy

[ 실행 방법 ]
    python okx_trading_bot.py

[ 주의사항 ]
- 처음에는 반드시 LIVE_TRADING = False 로 테스트하세요
- 실거래 전 반드시 소액으로 먼저 테스트하세요
- 이 봇은 투자 손실에 대한 책임을 지지 않습니다
"""

import time
import pandas as pd
import numpy as np
from okx.MarketData import MarketAPI
from okx.Trade import TradeAPI
from okx.Account import AccountAPI
import datetime

# ============================================================
#  ★ 설정 구역 - 여기만 수정하세요 ★
# ============================================================

# OKX API 키 설정 (OKX 거래소 → API 관리 → 새 API 키 생성)
API_KEY    = "여기에_API_KEY_입력"
SECRET_KEY = "여기에_SECRET_KEY_입력"
PASSPHRASE = "여기에_PASSPHRASE_입력"

# 거래 설정
SYMBOL       = "BTC-USDT-SWAP"   # 거래 종목 (BTC 무기한 선물)
TIMEFRAME    = "15m"              # 봉 단위: 1m / 5m / 15m / 1H / 4H
LEVERAGE     = 5                  # 레버리지 (위험: 높을수록 손실도 큼, 초보는 3~5 권장)
ORDER_SIZE   = 1                  # 주문 계약 수 (1계약 = BTC 0.01개)

# 손익비 설정
STOP_LOSS_RATIO   = 0.01          # 손절: 진입가 대비 1%
TAKE_PROFIT_RATIO = 0.015         # 익절: 진입가 대비 1.5% (1:1.5 손익비)

# AKMCD 설정 (기본값)
AKMCD_FAST   = 12
AKMCD_SLOW   = 26
AKMCD_SIGNAL = 9
AKMCD_BB_LEN = 20                 # 볼린저밴드 기간
AKMCD_BB_MULT= 2.0                # 볼린저밴드 배수

# SSL 하이브리드 설정
SSL_PERIOD   = 10                 # SSL 기간

# 운영 설정
LIVE_TRADING = False              # ★ 실거래: True / 테스트(신호확인만): False
CHECK_INTERVAL = 60               # 몇 초마다 신호 확인 (초 단위)

# ============================================================
#  지표 계산 함수들
# ============================================================

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """EMA(지수이동평균) 계산"""
    return series.ewm(span=period, adjust=False).mean()


def calculate_akmcd(df: pd.DataFrame) -> pd.DataFrame:
    """
    AKMCD 계산
    - 일반 MACD + 볼린저밴드 개념 결합
    - 결과: macd_line, signal_line, histogram, bb_upper, bb_lower, dot_color
    """
    close = df['close']

    # MACD 계산
    ema_fast   = calculate_ema(close, AKMCD_FAST)
    ema_slow   = calculate_ema(close, AKMCD_SLOW)
    macd_line  = ema_fast - ema_slow
    signal_line= calculate_ema(macd_line, AKMCD_SIGNAL)
    histogram  = macd_line - signal_line

    # MACD 히스토그램에 볼린저밴드 적용
    bb_mid   = histogram.rolling(AKMCD_BB_LEN).mean()
    bb_std   = histogram.rolling(AKMCD_BB_LEN).std()
    bb_upper = bb_mid + (AKMCD_BB_MULT * bb_std)
    bb_lower = bb_mid - (AKMCD_BB_MULT * bb_std)

    # 점 색깔 결정 (초록 = 강세, 빨강 = 약세)
    # 히스토그램이 상승 중이면 초록, 하락 중이면 빨강
    dot_color = pd.Series('red', index=df.index)
    dot_color[histogram > histogram.shift(1)] = 'green'

    df = df.copy()
    df['macd']       = macd_line
    df['signal']     = signal_line
    df['histogram']  = histogram
    df['bb_upper']   = bb_upper
    df['bb_lower']   = bb_lower
    df['dot_color']  = dot_color

    return df


def calculate_ssl(df: pd.DataFrame) -> pd.DataFrame:
    """
    SSL 하이브리드 계산
    - 고가/저가 SMA 기반으로 추세 방향 결정
    - 결과: ssl_up(파란선), ssl_down(빨간선), ssl_trend('up'/'down')
    """
    high  = df['high']
    low   = df['low']
    close = df['close']

    sma_high = high.rolling(SSL_PERIOD).mean()
    sma_low  = low.rolling(SSL_PERIOD).mean()

    # 추세 방향 결정
    hlv = pd.Series(0, index=df.index)
    hlv[close > sma_high] =  1
    hlv[close < sma_low]  = -1
    hlv = hlv.replace(0, np.nan).ffill().fillna(0)

    ssl_down = pd.Series(np.where(hlv < 0, sma_high, sma_low), index=df.index)
    ssl_up   = pd.Series(np.where(hlv < 0, sma_low, sma_high), index=df.index)

    # 추세: 캔들이 ssl_up 위면 'up', ssl_down 아래면 'down'
    ssl_trend = pd.Series('neutral', index=df.index)
    ssl_trend[close > ssl_up]   = 'up'
    ssl_trend[close < ssl_down] = 'down'

    # 캔들 색상 (파란=상승, 빨강=하락)
    candle_color = pd.Series('red', index=df.index)
    candle_color[close > close.shift(1)] = 'blue'

    df = df.copy()
    df['ssl_up']       = ssl_up
    df['ssl_down']     = ssl_down
    df['ssl_trend']    = ssl_trend
    df['candle_color'] = candle_color

    return df


def check_signal(df: pd.DataFrame) -> str:
    """
    매매 신호 확인
    
    롱 조건:
      1. 캔들이 SSL 파란선(ssl_up) 위
      2. 캔들 색상 파란색
      3. AKMCD histogram이 영선(0) 위
      4. 이전 봉: 빨간점 → 현재 봉: 초록점 (색깔 전환)

    숏 조건:
      1. 캔들이 SSL 빨간선(ssl_down) 아래
      2. 캔들 색상 빨간색
      3. AKMCD histogram이 영선(0) 아래
      4. 이전 봉: 초록점 → 현재 봉: 빨간점 (색깔 전환)

    반환값: 'long' / 'short' / 'none'
    """
    # 마지막 2개 봉 사용 (인덱스: -2=이전봉, -1=현재봉)
    curr = df.iloc[-1]
    prev = df.iloc[-2]

    close = curr['close']

    # ── 롱 조건 체크 ──
    cond_long_1 = close > curr['ssl_up']                     # SSL 파란선 위
    cond_long_2 = curr['candle_color'] == 'blue'             # 캔들 파란색
    cond_long_3 = curr['histogram'] > 0                      # AKMCD 영선 위
    cond_long_4 = (prev['dot_color'] == 'red' and            # 이전: 빨강
                   curr['dot_color'] == 'green')             # 현재: 초록 (전환!)

    if cond_long_1 and cond_long_2 and cond_long_3 and cond_long_4:
        return 'long'

    # ── 숏 조건 체크 ──
    cond_short_1 = close < curr['ssl_down']                  # SSL 빨간선 아래
    cond_short_2 = curr['candle_color'] == 'red'             # 캔들 빨간색
    cond_short_3 = curr['histogram'] < 0                     # AKMCD 영선 아래
    cond_short_4 = (prev['dot_color'] == 'green' and         # 이전: 초록
                    curr['dot_color'] == 'red')              # 현재: 빨강 (전환!)

    if cond_short_1 and cond_short_2 and cond_short_3 and cond_short_4:
        return 'short'

    return 'none'


# ============================================================
#  OKX API 연결 및 데이터 함수
# ============================================================

def get_okx_clients(live: bool):
    """OKX API 클라이언트 생성"""
    flag = "0" if live else "1"   # "0"=실거래, "1"=모의거래
    market_api  = MarketAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, flag)
    trade_api   = TradeAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, flag)
    account_api = AccountAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, flag)
    return market_api, trade_api, account_api


def get_candles(market_api, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
    """캔들(OHLCV) 데이터 가져오기"""
    result = market_api.get_candlesticks(instId=symbol, bar=timeframe, limit=str(limit))

    if result['code'] != '0':
        raise Exception(f"캔들 데이터 오류: {result['msg']}")

    # OKX 응답 형식: [timestamp, open, high, low, close, vol, ...]
    data = result['data']
    df = pd.DataFrame(data, columns=['timestamp','open','high','low','close','vol','volCcy','volCcyQuote','confirm'])
    df = df[['timestamp','open','high','low','close','vol']].copy()

    # 숫자 변환
    for col in ['open','high','low','close','vol']:
        df[col] = pd.to_numeric(df[col])

    # 시간 변환 및 정렬 (오래된 것 → 최신 순)
    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(np.int64), unit='ms')
    df = df.sort_values('timestamp').reset_index(drop=True)

    return df


def place_order(trade_api, side: str, entry_price: float) -> dict:
    """
    주문 실행
    side: 'long' 또는 'short'
    """
    # 롱/숏에 따른 파라미터
    if side == 'long':
        pos_side = 'long'
        order_side = 'buy'
        sl_price = round(entry_price * (1 - STOP_LOSS_RATIO), 2)
        tp_price = round(entry_price * (1 + TAKE_PROFIT_RATIO), 2)
    else:
        pos_side = 'short'
        order_side = 'sell'
        sl_price = round(entry_price * (1 + STOP_LOSS_RATIO), 2)
        tp_price = round(entry_price * (1 - TAKE_PROFIT_RATIO), 2)

    print(f"  진입가: {entry_price}")
    print(f"  손절가: {sl_price}  ({STOP_LOSS_RATIO*100}%)")
    print(f"  익절가: {tp_price}  ({TAKE_PROFIT_RATIO*100}%)")

    if not LIVE_TRADING:
        print("  [테스트 모드] 실제 주문은 실행되지 않습니다.")
        return {"test": True}

    # 실거래 주문
    result = trade_api.place_order(
        instId   = SYMBOL,
        tdMode   = "cross",           # 교차 마진
        side     = order_side,
        posSide  = pos_side,
        ordType  = "market",          # 시장가 주문
        sz       = str(ORDER_SIZE),
        slTriggerPx  = str(sl_price),
        slOrdPx      = "-1",          # 시장가 손절
        tpTriggerPx  = str(tp_price),
        tpOrdPx      = "-1",          # 시장가 익절
    )
    return result


# ============================================================
#  메인 실행 루프
# ============================================================

def main():
    print("=" * 55)
    print("  OKX 자동매매봇 시작")
    print(f"  종목: {SYMBOL}  |  타임프레임: {TIMEFRAME}")
    print(f"  레버리지: {LEVERAGE}x  |  모드: {'실거래' if LIVE_TRADING else '테스트(신호확인)'}")
    print("=" * 55)

    # API 클라이언트 초기화
    try:
        market_api, trade_api, account_api = get_okx_clients(LIVE_TRADING)
        print("✅ OKX API 연결 성공\n")
    except Exception as e:
        print(f"❌ API 연결 실패: {e}")
        print("API 키를 확인하세요.")
        return

    consecutive_errors = 0

    while True:
        try:
            now = datetime.datetime.now().strftime("%H:%M:%S")

            # 1. 캔들 데이터 수집
            df = get_candles(market_api, SYMBOL, TIMEFRAME, limit=100)

            # 2. 지표 계산
            df = calculate_akmcd(df)
            df = calculate_ssl(df)

            # 3. 신호 확인
            signal = check_signal(df)

            curr = df.iloc[-1]
            print(f"[{now}] 현재가: {curr['close']:.2f} | "
                  f"AKMCD hist: {curr['histogram']:.4f} | "
                  f"SSL추세: {curr['ssl_trend']} | "
                  f"신호: {signal.upper()}")

            # 4. 신호 발생 시 주문
            if signal in ('long', 'short'):
                direction = "🟢 롱" if signal == 'long' else "🔴 숏"
                print(f"\n{'='*40}")
                print(f"  {direction} 진입 신호 발생!")
                place_order(trade_api, signal, curr['close'])
                print(f"{'='*40}\n")

            consecutive_errors = 0

        except KeyboardInterrupt:
            print("\n봇을 종료합니다.")
            break

        except Exception as e:
            consecutive_errors += 1
            print(f"⚠️  오류 발생 ({consecutive_errors}회): {e}")
            if consecutive_errors >= 5:
                print("연속 5회 오류. 봇을 종료합니다.")
                break

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
