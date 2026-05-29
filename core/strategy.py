"""
TTM Squeeze + 200 EMA Trend Filter 하이브리드 매매 전략
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
    ema_ok: bool            # 장기 추세 필터 충족 여부 (UI 호환용)
    bb_ok: bool             # 모멘텀 조건 충족 여부 (UI 호환용)
    macd_ok: bool           # 스퀴즈 돌파(Fired) 여부 (UI 호환용)
    close: float
    ema200: float           # 200 EMA 값 (UI 호환용)
    bb_upper: float         # Bollinger Band 상단
    bb_lower: float         # Bollinger Band 하단
    macd_hist: float        # TTM 모멘텀 값
    reason: str
    rsi: float = 50.0       # RSI 값 (기본값 50.0)
    rsi_ok: bool = True     # RSI 필터 충족 여부 (기본값 True)
    ema200_ok: bool = True  # EMA 200 필터 충족 여부 (기본값 True)
    atr: float = 0.0        # 매매 신호 시점의 ATR 값 (기본값 0.0)



class StrategyEngine:
    """
    TTM Squeeze + 200 EMA Trend Filter 전략 엔진
    
    진입 전략:
      1. 볼린저 밴드(20, 2.0)가 켈트너 채널(20, 1.5) 안으로 들어가면 스퀴즈 ON (에너지 응축)
      2. 스퀴즈 상태에서 볼린저 밴드가 켈트너 채널 밖으로 빠져나오면 스퀴즈 OFF (돌파 발생)
      3. 돌파 시점에 TTM Momentum (Linear Regression of Diff)의 방향에 따라 진입:
         - Momentum > 0: 롱 진입 (Close > 200 EMA 조건 필수)
         - Momentum < 0: 숏 진입 (Close < 200 EMA 조건 필수)
    """

    def __init__(self):
        self.cfg = CFG

    def calculate_linreg(self, series: pd.Series, period: int) -> pd.Series:
        """선형 회귀선 최신값 계산 (Pine Script linreg와 동일)"""
        x = np.arange(period)
        x_mean = x.mean()
        x_dev = x - x_mean
        x_var = (x_dev ** 2).sum()

        def get_linreg_val(y):
            if len(y) < period:
                return 0.0
            y_mean = y.mean()
            slope = np.dot(x_dev, y) / x_var
            intercept = y_mean - slope * x_mean
            return slope * (period - 1) + intercept

        return series.rolling(window=period).apply(get_linreg_val, raw=True)

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """TTM Squeeze + 200 EMA 지표 계산"""
        required_len = max(self.cfg.BB_PERIOD, self.cfg.EMA_PERIOD, self.cfg.TTM_MOM_PERIOD) + 10
        if len(df) < required_len:
            return pd.DataFrame()

        df = df.copy()
        close = df['close']
        high = df['high']
        low = df['low']

        # 1. Bollinger Bands (20, 2.0)
        bb_mid = close.rolling(self.cfg.BB_PERIOD).mean()
        bb_std = close.rolling(self.cfg.BB_PERIOD).std()
        bb_upper = bb_mid + (self.cfg.BB_STD * bb_std)
        bb_lower = bb_mid - (self.cfg.BB_STD * bb_std)

        # 2. Keltner Channels (20, 1.5) using True Range (ATR)
        kc_basis = close.ewm(span=self.cfg.BB_PERIOD, adjust=False).mean()
        
        # True Range
        tr_hl = high - low
        tr_hc = (high - close.shift(1)).abs()
        tr_lc = (low - close.shift(1)).abs()
        tr = pd.concat([tr_hl, tr_hc, tr_lc], axis=1).max(axis=1)
        atr = tr.ewm(span=self.cfg.BB_PERIOD, adjust=False).mean()

        kc_upper = kc_basis + (self.cfg.TTM_KC_MULT * atr)
        kc_lower = kc_basis - (self.cfg.TTM_KC_MULT * atr)

        # Squeeze State: BB inside KC
        squeeze_on = (bb_upper < kc_upper) & (bb_lower > kc_lower)

        # 3. TTM Momentum (20)
        highest_high = high.rolling(self.cfg.TTM_MOM_PERIOD).max()
        lowest_low = low.rolling(self.cfg.TTM_MOM_PERIOD).min()
        average_price = (highest_high + lowest_low) / 2
        ema_close = close.ewm(span=self.cfg.TTM_MOM_PERIOD, adjust=False).mean()
        diff = close - (average_price + ema_close) / 2
        macd_hist = self.calculate_linreg(diff, self.cfg.TTM_MOM_PERIOD)

        # 4. 컬럼 매핑 (UI 및 테스트 호환용)
        df['ssl_up'] = kc_upper
        df['ssl_down'] = kc_lower
        df['bb_upper'] = bb_upper
        df['bb_lower'] = bb_lower
        df['macd_hist'] = macd_hist
        df['squeeze_on'] = squeeze_on
        df['atr'] = atr

        # dot_color: 스퀴즈 상태 표시 (ON: red, OFF: green)
        dot_color = pd.Series('green', index=df.index)
        dot_color[squeeze_on] = 'red'
        df['dot_color'] = dot_color

        # candle_color: 모멘텀 방향 (양수: blue, 음수: red)
        candle_color = pd.Series('red', index=df.index)
        candle_color[macd_hist > 0] = 'blue'
        df['candle_color'] = candle_color

        # 5. EMA 200 (장기 추세 필터)
        df['ema200'] = close.ewm(span=self.cfg.EMA_PERIOD, adjust=False).mean()

        # 6. RSI (14)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.cfg.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.cfg.RSI_PERIOD).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        df['rsi'] = df['rsi'].fillna(50.0)

        # 7. 거래량(Volume) MA 필터
        if 'volume' in df.columns:
            vol_period = getattr(self.cfg, 'VOL_MA_PERIOD', 20)
            df['vol_ma'] = df['volume'].rolling(vol_period).mean()
        else:
            df['vol_ma'] = 0.0

        return df.dropna()

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        """최신 캔들 기준 TTM Squeeze + 200 EMA 매매 신호 생성"""
        # [즉시 조치 1] 완성 캔들 데이터 기반 신호 체계로 고정하기 위해 미완성 실시간 캔들 제거
        if not df.empty:
            df = df.iloc[:-1]
        df = self.calculate_indicators(df)

        empty_signal = Signal(
            symbol=symbol, direction="none", strength=0,
            ema_ok=False, bb_ok=False, macd_ok=False,
            close=0, ema200=0, bb_upper=0, bb_lower=0,
            macd_hist=0, reason="데이터 부족", rsi=50.0, rsi_ok=False, atr=0.0
        )

        if df.empty or len(df) < 5:
            return empty_signal

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        close = curr['close']
        macd_hist = curr['macd_hist']
        rsi_val = curr.get('rsi', 50.0)
        atr_val = curr.get('atr', 0.0)
        vol_val = curr.get('volume', 0.0)
        vol_ma_val = curr.get('vol_ma', 0.0)

        # Fallback for mock/test data
        ema200_val = curr.get('ema200', None)
        ssl_up = curr.get('ssl_up', 0.0)
        ssl_down = curr.get('ssl_down', float('inf'))

        if ema200_val is None:
            # Mock/테스트 데이터 폴백: ssl_up(KC 상단)을 EMA 대리값으로 사용
            cond_long_trend = (close > ssl_up)
            cond_short_trend = (close < ssl_down)
            ema200_val = ssl_up
        else:
            # [수정 1] ssl_up(KC 상단) 이중 필터 제거 → EMA200 단일 추세 필터
            # 스퀴즈 해제 직후 price는 KC 경계 근처에 있어 ssl_up 조건이 진입 차단 유발
            cond_long_trend = (close > ema200_val)
            cond_short_trend = (close < ema200_val)

        # 1. 스퀴즈 상태 및 돌파(Fired) 여부 판정
        squeeze_fired = False
        lookback = getattr(self.cfg, 'SQUEEZE_LOOKBACK', 5)
        
        # squeeze_on 컬럼 여부에 따라 판정 분기 (테스트 데이터 호환성 보장)
        if 'squeeze_on' in curr:
            # [기존] ON -> OFF 전환 순간 포착 (최근 lookback 봉 내)
            for i in range(1, lookback + 1):
                if len(df) >= i + 1:
                    if df.iloc[-(i+1)]['squeeze_on'] and not df.iloc[-i]['squeeze_on']:
                        squeeze_fired = True
                        break

            # [방안 B] 현재 squeeze_on=False(해제 상태) + 확장 윈도우(lookback×3) 내 ON 이력 존재 → fired 인정
            # 스퀴즈 전환점을 놓쳤어도 에너지 응축 후 해제 중이라면 진입 허용
            if not squeeze_fired and not bool(curr['squeeze_on']):
                # [v4.0.2] lookback*3(24봉) → lookback+4(12봉): 수십 봉 전 이력으로 인한 과신호 방지
                extended_window = min(lookback + 4, len(df) - 1)
                had_squeeze = df.iloc[-extended_window:]['squeeze_on'].any()
                if had_squeeze:
                    squeeze_fired = True
        else:
            # 테스트 Mock 데이터 지원용 폴백 (dot_color 기반)
            for i in range(1, lookback + 1):
                if len(df) >= i + 1:
                    p_dot = df.iloc[-(i+1)]['dot_color']
                    c_dot = df.iloc[-i]['dot_color']
                    if p_dot == 'red' and c_dot == 'green':
                        squeeze_fired = True
                        break
                    if p_dot == 'green' and c_dot == 'red':
                        squeeze_fired = True
                        break

        # 2. 모멘텀 필터
        cond_long_mom = macd_hist > 0
        cond_short_mom = macd_hist < 0
        # [수정 2] candle_color 조건 제거 — candle_color=='blue' ≡ macd_hist>0 으로 완전 중복
        # 강도 재배분: 35(추세)+35(fired)+30(모멘텀) = 100

        # 3. RSI 필터
        # [수정 3] squeeze_fired 시 RSI 필터 면제: 돌파 직후 강한 양봉은 RSI 과열이 자연스러움
        if squeeze_fired:
            cond_long_rsi = True
            cond_short_rsi = True
        else:
            cond_long_rsi = (rsi_val < self.cfg.RSI_OVERBOUGHT) if self.cfg.USE_RSI_FILTER else True
            cond_short_rsi = (rsi_val > self.cfg.RSI_OVERSOLD) if self.cfg.USE_RSI_FILTER else True

        # 4. 거래량 급증 필터
        use_vol_filter = getattr(self.cfg, 'USE_VOL_FILTER', False)
        vol_mult = getattr(self.cfg, 'VOL_SURGE_MULT', 1.5)
        cond_vol_surge = (vol_val > (vol_ma_val * vol_mult)) if (use_vol_filter and vol_ma_val > 0) else True

        # 5. UI 및 컬럼 표시용 상태 매핑 (명시적 bool 변환으로 numpy type 방지)
        ema_ok = bool(cond_long_trend if cond_long_mom else (cond_short_trend if cond_short_mom else False))
        macd_ok = bool(squeeze_fired)
        bb_ok = bool(cond_long_mom if cond_long_trend else (cond_short_mom if cond_short_trend else False))

        # 신호 강도 계산 (candle 중복 제거 후 재배분: 35+35+30=100)
        def compute_strength(trend, fired, mom) -> int:
            score = 0
            if trend: score += 35
            if fired: score += 35
            if mom: score += 30
            return score

        # ── 롱 진입 판단 ──
        if cond_long_trend and squeeze_fired and cond_long_mom and self.cfg.ALLOW_LONG:
            if not cond_long_rsi:
                return Signal(
                    symbol=symbol, direction="none", strength=80,
                    ema_ok=ema_ok, bb_ok=bb_ok, macd_ok=macd_ok,
                    close=close, ema200=ema200_val,
                    bb_upper=curr.get('bb_upper', 0.0), bb_lower=curr.get('bb_lower', 0.0),
                    macd_hist=macd_hist, rsi=rsi_val, rsi_ok=False,
                    ema200_ok=bool(cond_long_trend), atr=atr_val,
                    reason=f"롱 조건 충족했으나 RSI 과열({rsi_val:.1f} >= {self.cfg.RSI_OVERBOUGHT})로 진입 차단"
                )
            if not cond_vol_surge:
                return Signal(
                    symbol=symbol, direction="none", strength=80,
                    ema_ok=ema_ok, bb_ok=bb_ok, macd_ok=macd_ok,
                    close=close, ema200=ema200_val,
                    bb_upper=curr.get('bb_upper', 0.0), bb_lower=curr.get('bb_lower', 0.0),
                    macd_hist=macd_hist, rsi=rsi_val, rsi_ok=True,
                    ema200_ok=bool(cond_long_trend), atr=atr_val,
                    reason=f"롱 조건 충족했으나 거래량 부족(현재 {vol_val:.1f} <= 기준 {vol_ma_val * vol_mult:.1f})으로 차단"
                )
            strength = compute_strength(cond_long_trend, squeeze_fired, cond_long_mom)
            return Signal(
                symbol=symbol, direction="long", strength=strength,
                ema_ok=ema_ok, bb_ok=bb_ok, macd_ok=macd_ok,
                close=close, ema200=ema200_val,
                bb_upper=curr.get('bb_upper', 0.0), bb_lower=curr.get('bb_lower', 0.0),
                macd_hist=macd_hist, rsi=rsi_val, rsi_ok=True,
                ema200_ok=bool(cond_long_trend), atr=atr_val,
                reason=f"TTM 스퀴즈 롱 돌파 포착 (강도 {strength}%, RSI {rsi_val:.1f})"
            )

        # ── 숏 진입 판단 ──
        if cond_short_trend and squeeze_fired and cond_short_mom and self.cfg.ALLOW_SHORT:
            if not cond_short_rsi:
                return Signal(
                    symbol=symbol, direction="none", strength=80,
                    ema_ok=ema_ok, bb_ok=bb_ok, macd_ok=macd_ok,
                    close=close, ema200=ema200_val,
                    bb_upper=curr.get('bb_upper', 0.0), bb_lower=curr.get('bb_lower', 0.0),
                    macd_hist=macd_hist, rsi=rsi_val, rsi_ok=False,
                    ema200_ok=bool(cond_short_trend), atr=atr_val,
                    reason=f"숏 조건 충족했으나 RSI 과매도({rsi_val:.1f} <= {self.cfg.RSI_OVERSOLD})로 진입 차단"
                )
            if not cond_vol_surge:
                return Signal(
                    symbol=symbol, direction="none", strength=80,
                    ema_ok=ema_ok, bb_ok=bb_ok, macd_ok=macd_ok,
                    close=close, ema200=ema200_val,
                    bb_upper=curr.get('bb_upper', 0.0), bb_lower=curr.get('bb_lower', 0.0),
                    macd_hist=macd_hist, rsi=rsi_val, rsi_ok=True,
                    ema200_ok=bool(cond_short_trend), atr=atr_val,
                    reason=f"숏 조건 충족했으나 거래량 부족(현재 {vol_val:.1f} <= 기준 {vol_ma_val * vol_mult:.1f})으로 차단"
                )
            strength = compute_strength(cond_short_trend, squeeze_fired, cond_short_mom)
            return Signal(
                symbol=symbol, direction="short", strength=strength,
                ema_ok=ema_ok, bb_ok=bb_ok, macd_ok=macd_ok,
                close=close, ema200=ema200_val,
                bb_upper=curr.get('bb_upper', 0.0), bb_lower=curr.get('bb_lower', 0.0),
                macd_hist=macd_hist, rsi=rsi_val, rsi_ok=True,
                ema200_ok=bool(cond_short_trend), atr=atr_val,
                reason=f"TTM 스퀴즈 숏 돌파 포착 (강도 {strength}%, RSI {rsi_val:.1f})"
            )

        # ── 부분 신호 및 대기 ──
        if cond_long_trend:
            s = compute_strength(cond_long_trend, squeeze_fired, cond_long_mom)
            return Signal(
                symbol=symbol, direction="none", strength=s,
                ema_ok=ema_ok, bb_ok=bb_ok, macd_ok=macd_ok,
                close=close, ema200=ema200_val,
                bb_upper=curr.get('bb_upper', 0.0), bb_lower=curr.get('bb_lower', 0.0),
                macd_hist=macd_hist, rsi=rsi_val, rsi_ok=cond_long_rsi,
                ema200_ok=bool(cond_long_trend), atr=atr_val,
                reason="조건 일부 미충족 (스퀴즈 대기 또는 모멘텀/캔들색상 미확보)"
            )

        if cond_short_trend:
            s = compute_strength(cond_short_trend, squeeze_fired, cond_short_mom)
            return Signal(
                symbol=symbol, direction="none", strength=s,
                ema_ok=ema_ok, bb_ok=bb_ok, macd_ok=macd_ok,
                close=close, ema200=ema200_val,
                bb_upper=curr.get('bb_upper', 0.0), bb_lower=curr.get('bb_lower', 0.0),
                macd_hist=macd_hist, rsi=rsi_val, rsi_ok=cond_short_rsi,
                ema200_ok=bool(cond_short_trend), atr=atr_val,
                reason="조건 일부 미충족 (스퀴즈 대기 또는 모멘텀/캔들색상 미확보)"
            )

        return Signal(
            symbol=symbol, direction="none", strength=10,
            ema_ok=False, bb_ok=False, macd_ok=False,
            close=close, ema200=ema200_val,
            bb_upper=curr.get('bb_upper', 0.0), bb_lower=curr.get('bb_lower', 0.0),
            macd_hist=macd_hist, rsi=rsi_val, rsi_ok=True,
            ema200_ok=False, atr=atr_val,
            reason="추세 판독 불가 — 신호 없음"
        )
