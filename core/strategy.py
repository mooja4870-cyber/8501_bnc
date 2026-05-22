"""
AKMCD + SSL 하이브리드 매매 전략
===============================
대본 기반: 코인슈타인 전략 구현 (OKX -> Binance)
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
from core.config import CFG
import logging

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    symbol: str
    direction: str          # "long" | "short" | "none"
    strength: int           # 0~100 (신호 강도)
    ema_ok: bool            # SSL 추세 조건 충족 여부 (ema_ok로 필드명 유지)
    bb_ok: bool             # AKMCD 점 색상 전환 조건 충족 여부 (bb_ok로 필드명 유지)
    macd_ok: bool           # AKMCD 영선 돌파 조건 충족 여부 (macd_ok로 필드명 유지)
    close: float
    ema200: float           # SSL 추세선 값 (UI 호환용)
    bb_upper: float         # AKMCD 볼린저 밴드 상단
    bb_lower: float         # AKMCD 볼린저 밴드 하단
    macd_hist: float        # AKMCD 히스토그램 값
    reason: str
    rsi: float = 50.0       # RSI 값 (기본값 50.0)
    rsi_ok: bool = True     # RSI 필터 충족 여부 (기본값 True)
    ema200_ok: bool = True  # EMA 200 필터 충족 여부 (기본값 True)



class StrategyEngine:
    """
    AKMCD + SSL 하이브리드 전략 엔진
    
    롱 조건:
      1. 캔들이 SSL 파란선(ssl_up) 위 (ema_ok)
      2. 캔들 색상 파란색 (close > close.shift(1))
      3. AKMCD histogram이 영선(0) 위 (macd_ok)
      4. 이전 봉: 빨간점 → 현재 봉: 초록점 (색깔 전환) (bb_ok)

    숏 조건:
      1. 캔들이 SSL 빨간선(ssl_down) 아래 (ema_ok)
      2. 캔들 색상 빨간색 (close <= close.shift(1))
      3. AKMCD histogram이 영선(0) 아래 (macd_ok)
      4. 이전 봉: 초록점 → 현재 봉: 빨간점 (색깔 전환) (bb_ok)
    """

    def __init__(self):
        self.cfg = CFG

    def calculate_ema(self, series: pd.Series, period: int) -> pd.Series:
        """EMA(지수이동평균) 계산"""
        return series.ewm(span=period, adjust=False).mean()

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술 지표 계산"""
        required_len = max(self.cfg.BB_PERIOD, self.cfg.MACD_SLOW, self.cfg.SSL_PERIOD) + 10
        if len(df) < required_len:
            return pd.DataFrame()

        df = df.copy()

        # 1. AKMCD 계산
        close = df['close']
        ema_fast = self.calculate_ema(close, self.cfg.MACD_FAST)
        ema_slow = self.calculate_ema(close, self.cfg.MACD_SLOW)
        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema(macd_line, self.cfg.MACD_SIGNAL)
        histogram = macd_line - signal_line

        # 히스토그램 볼린저 밴드
        bb_mid = histogram.rolling(self.cfg.BB_PERIOD).mean()
        bb_std = histogram.rolling(self.cfg.BB_PERIOD).std()
        bb_upper = bb_mid + (self.cfg.BB_STD * bb_std)
        bb_lower = bb_mid - (self.cfg.BB_STD * bb_std)

        # 점 색깔 결정 (상승: green, 하락: red)
        dot_color = pd.Series('red', index=df.index)
        dot_color[histogram > histogram.shift(1)] = 'green'

        df['macd'] = macd_line
        df['signal'] = signal_line
        df['macd_hist'] = histogram
        df['bb_upper'] = bb_upper
        df['bb_lower'] = bb_lower
        df['dot_color'] = dot_color

        # 2. SSL 하이브리드 계산
        high = df['high']
        low = df['low']
        sma_high = high.rolling(self.cfg.SSL_PERIOD).mean()
        sma_low = low.rolling(self.cfg.SSL_PERIOD).mean()

        hlv = pd.Series(0, index=df.index)
        hlv[close > sma_high] = 1
        hlv[close < sma_low] = -1
        hlv = hlv.replace(0, np.nan).ffill().fillna(0)

        ssl_down = pd.Series(np.where(hlv < 0, sma_high, sma_low), index=df.index)
        ssl_up = pd.Series(np.where(hlv < 0, sma_low, sma_high), index=df.index)

        ssl_trend = pd.Series('neutral', index=df.index)
        ssl_trend[close > ssl_up] = 'up'
        ssl_trend[close < ssl_down] = 'down'

        candle_color = pd.Series('red', index=df.index)
        candle_color[close > close.shift(1)] = 'blue'

        df['ssl_up'] = ssl_up
        df['ssl_down'] = ssl_down
        df['ssl_trend'] = ssl_trend
        df['candle_color'] = candle_color

        # 3. EMA 200
        df['ema200'] = close.ewm(span=200, adjust=False).mean()

        # 4. RSI 계산
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.cfg.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.cfg.RSI_PERIOD).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50.0)

        # 5. ADX (평균 방향성 지수) — 시장 체계 자동 판별용
        adx_period = self.cfg.ADX_PERIOD
        tr_hl = high - low
        tr_hc = (high - close.shift(1)).abs()
        tr_lc = (low - close.shift(1)).abs()
        tr = pd.concat([tr_hl, tr_hc, tr_lc], axis=1).max(axis=1)

        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

        alpha = 1.0 / adx_period
        tr_smooth = tr.ewm(alpha=alpha, min_periods=adx_period, adjust=False).mean()
        plus_dm_s = plus_dm.ewm(alpha=alpha, min_periods=adx_period, adjust=False).mean()
        minus_dm_s = minus_dm.ewm(alpha=alpha, min_periods=adx_period, adjust=False).mean()

        plus_di = 100 * (plus_dm_s / tr_smooth.replace(0, float('nan')))
        minus_di = 100 * (minus_dm_s / tr_smooth.replace(0, float('nan')))
        di_sum = (plus_di + minus_di).replace(0, float('nan'))
        dx = 100 * ((plus_di - minus_di).abs() / di_sum)
        df['adx'] = dx.ewm(alpha=alpha, min_periods=adx_period, adjust=False).mean().fillna(0.0)

        # 6. Price Bollinger Bands (횡보장 모드용)
        price_bb_mid = close.rolling(self.cfg.PRICE_BB_PERIOD).mean()
        price_bb_std = close.rolling(self.cfg.PRICE_BB_PERIOD).std()
        df['price_bb_upper'] = price_bb_mid + (self.cfg.PRICE_BB_STD * price_bb_std)
        df['price_bb_lower'] = price_bb_mid - (self.cfg.PRICE_BB_STD * price_bb_std)

        return df.dropna()

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        """최신 캔들 기준 매매 신호 생성"""
        df = self.calculate_indicators(df)

        empty_signal = Signal(
            symbol=symbol, direction="none", strength=0,
            ema_ok=False, bb_ok=False, macd_ok=False,
            close=0, ema200=0, bb_upper=0, bb_lower=0,
            macd_hist=0, reason="데이터 부족", rsi=50.0, rsi_ok=False
        )

        if df.empty or len(df) < 3:
            return empty_signal

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        close = curr['close']
        ssl_up = curr['ssl_up']
        ssl_down = curr['ssl_down']
        macd_hist = curr['macd_hist']

        # ── 롱 조건 체크 ──
        cond_long_1 = close > ssl_up                     # SSL 파란선 위
        cond_long_2 = curr['candle_color'] == 'blue'     # 캔들 파란색
        cond_long_3 = macd_hist > 0                      # AKMCD 영선 위
        cond_long_4 = (prev['dot_color'] == 'red' and    # 이전: 빨강 -> 현재: 초록
                       curr['dot_color'] == 'green')
        cond_long_rsi = (curr['rsi'] < self.cfg.RSI_OVERBOUGHT) if self.cfg.USE_RSI_FILTER else True

        # ── 숏 조건 체크 ──
        cond_short_1 = close < ssl_down                  # SSL 빨간선 아래
        cond_short_2 = curr['candle_color'] == 'red'     # 캔들 빨간색
        cond_short_3 = macd_hist < 0                     # AKMCD 영선 아래
        cond_short_4 = (prev['dot_color'] == 'green' and  # 이전: 초록 -> 현재: 빨강
                        curr['dot_color'] == 'red')
        cond_short_rsi = (curr['rsi'] > self.cfg.RSI_OVERSOLD) if self.cfg.USE_RSI_FILTER else True

        # 신호 강도 계산 (4가지 조건 각각 점수 배분)
        # SSL 추세 일치(35점), 영선 돌파(25점), 캔들 색상 일치(20점), 점 색상 전환 완료(20점)
        def compute_strength(c1, c2, c3, c4) -> int:
            score = 0
            if c1: score += 35
            if c2: score += 20
            if c3: score += 25
            if c4: score += 20
            return score

        # ── 추세 필터 모드 판정 ────────────────────────────────
        # ADX 자동 스위칭이 ON이면: ADX값으로 다동적 필터 선택
        # ADX 자동 스위칭이 OFF이면: USE_EMA200_FILTER 기본값(기본 ON)으로 EMA200 필터 적용
        adx_val = curr.get('adx', 0) if hasattr(curr, 'get') else curr['adx'] if 'adx' in curr.index else 0
        ema200_val = curr.get('ema200', None) if hasattr(curr, 'get') else curr['ema200'] if 'ema200' in curr.index else None
        is_trending = True  # 기본: 추세장 모드 (EMA200)
        mode_label = ""

        if self.cfg.ADX_AUTO_SWITCH:
            if adx_val >= self.cfg.ADX_THRESHOLD:
                is_trending = True
                mode_label = f"토네장(ADX {adx_val:.1f}≥25)"
            else:
                is_trending = False
                mode_label = f"횡보장(ADX {adx_val:.1f}<25)"
        elif self.cfg.USE_EMA200_FILTER:
            is_trending = True  # EMA200 필터 강제 적용
            mode_label = "EMA200"

        # EMA200 필터 vs Price BB 필터
        if is_trending and self.cfg.USE_EMA200_FILTER and ema200_val is not None:
            # 추세장 모드: EMA 200 위에서만 롱, 아래에서만 숏
            cond_long_ema200 = close > ema200_val
            cond_short_ema200 = close < ema200_val
        else:
            cond_long_ema200 = True
            cond_short_ema200 = True


        if not is_trending and self.cfg.ADX_AUTO_SWITCH:
            # 횡보장 모드: Price BB 상단 바로 아래에서만 롱, 하단 바로 위에서만 숏 (가격 과열 차단)
            pbb_upper = curr.get('price_bb_upper', float('inf')) if hasattr(curr, 'get') else curr['price_bb_upper'] if 'price_bb_upper' in curr.index else float('inf')
            pbb_lower = curr.get('price_bb_lower', 0) if hasattr(curr, 'get') else curr['price_bb_lower'] if 'price_bb_lower' in curr.index else 0
            cond_long_bb_range = close < pbb_upper
            cond_short_bb_range = close > pbb_lower
        else:
            cond_long_bb_range = True
            cond_short_bb_range = True        # EMA200 필터 조건 충족 여부 (체커용)
        if ema200_val is None:
            ema200_ok = True
        elif close > ssl_up:
            ema200_ok = close > ema200_val
        elif close < ssl_down:
            ema200_ok = close < ema200_val
        else:
            ema200_ok = False


        # ── 롱 신호 ───────────────────────────────────────────────
        if cond_long_1 and cond_long_2 and cond_long_3 and cond_long_4 and cond_long_ema200 and cond_long_bb_range and self.cfg.ALLOW_LONG:
            if not cond_long_rsi:
                return Signal(
                    symbol=symbol, direction="none", strength=80,
                    ema_ok=cond_long_1, bb_ok=cond_long_4, macd_ok=cond_long_3,
                    close=close, ema200=ema200_val if ema200_val is not None else ssl_up,
                    bb_upper=curr['bb_upper'], bb_lower=curr['bb_lower'],
                    macd_hist=macd_hist, rsi=curr['rsi'], rsi_ok=False,
                    ema200_ok=ema200_ok,
                    reason=f"롱 조건 충족했으나 RSI 과열({curr['rsi']:.1f} >= {self.cfg.RSI_OVERBOUGHT})로 진입 차단"
                )
            strength = compute_strength(cond_long_1, cond_long_2, cond_long_3, cond_long_4)
            return Signal(
                symbol=symbol, direction="long", strength=strength,
                ema_ok=cond_long_1, bb_ok=cond_long_4, macd_ok=cond_long_3,
                close=close, ema200=ema200_val if ema200_val is not None else ssl_up,
                bb_upper=curr['bb_upper'], bb_lower=curr['bb_lower'],
                macd_hist=macd_hist, rsi=curr['rsi'], rsi_ok=True,
                ema200_ok=ema200_ok,
                reason=f"SSL 롱 추세 + AKMCD 초록점 전환 [{mode_label}] (강도 {strength}%, RSI {curr['rsi']:.1f})"
            )

        # ── 숏 신호 ───────────────────────────────────────────────
        if cond_short_1 and cond_short_2 and cond_short_3 and cond_short_4 and cond_short_ema200 and cond_short_bb_range and self.cfg.ALLOW_SHORT:
            if not cond_short_rsi:
                return Signal(
                    symbol=symbol, direction="none", strength=80,
                    ema_ok=cond_short_1, bb_ok=cond_short_4, macd_ok=cond_short_3,
                    close=close, ema200=ema200_val if ema200_val is not None else ssl_down,
                    bb_upper=curr['bb_upper'], bb_lower=curr['bb_lower'],
                    macd_hist=macd_hist, rsi=curr['rsi'], rsi_ok=False,
                    ema200_ok=ema200_ok,
                    reason=f"숏 조건 충족했으나 RSI 과매도({curr['rsi']:.1f} <= {self.cfg.RSI_OVERSOLD})로 진입 차단"
                )
            strength = compute_strength(cond_short_1, cond_short_2, cond_short_3, cond_short_4)
            return Signal(
                symbol=symbol, direction="short", strength=strength,
                ema_ok=cond_short_1, bb_ok=cond_short_4, macd_ok=cond_short_3,
                close=close, ema200=ema200_val if ema200_val is not None else ssl_down,
                bb_upper=curr['bb_upper'], bb_lower=curr['bb_lower'],
                macd_hist=macd_hist, rsi=curr['rsi'], rsi_ok=True,
                ema200_ok=ema200_ok,
                reason=f"SSL 숏 추세 + AKMCD 빨간점 전환 [{mode_label}] (강도 {strength}%, RSI {curr['rsi']:.1f})"
            )




        # 부분 신호 강도 계산 (스캐너 표시용)
        # 롱 방향 추세인 경우
        if close > ssl_up:
            s = compute_strength(cond_long_1, cond_long_2, cond_long_3, cond_long_4)
            return Signal(
                symbol=symbol, direction="none", strength=s,
                ema_ok=cond_long_1, bb_ok=cond_long_4, macd_ok=cond_long_3,
                close=close, ema200=ssl_up,
                bb_upper=curr['bb_upper'], bb_lower=curr['bb_lower'],
                macd_hist=macd_hist, rsi=curr['rsi'], rsi_ok=cond_long_rsi,
                ema200_ok=ema200_ok,
                reason="조건 일부 미충족 (LONG 추세)"
            )

        # 숏 방향 추세인 경우
        if close < ssl_down:
            s = compute_strength(cond_short_1, cond_short_2, cond_short_3, cond_short_4)
            return Signal(
                symbol=symbol, direction="none", strength=s,
                ema_ok=cond_short_1, bb_ok=cond_short_4, macd_ok=cond_short_3,
                close=close, ema200=ssl_down,
                bb_upper=curr['bb_upper'], bb_lower=curr['bb_lower'],
                macd_hist=macd_hist, rsi=curr['rsi'], rsi_ok=cond_short_rsi,
                ema200_ok=ema200_ok,
                reason="조건 일부 미충족 (SHORT 추세)"
            )

        return Signal(
            symbol=symbol, direction="none", strength=10,
            ema_ok=False, bb_ok=False, macd_ok=False,
            close=close, ema200=ssl_up,
            bb_upper=curr['bb_upper'], bb_lower=curr['bb_lower'],
            macd_hist=macd_hist, rsi=curr['rsi'], rsi_ok=True,
            ema200_ok=ema200_ok,
            reason="SSL 중립 추세 — 신호 없음"
        )

