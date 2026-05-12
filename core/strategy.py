"""
Triple-Indicator 매매 전략
EMA200 (추세 필터) + BB Reversion (과매도 포착) + MACD Signal (진입 확인)
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
import ta
from core.config import CFG
import logging

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    symbol: str
    direction: str          # "long" | "short" | "none"
    strength: int           # 0~100 (신호 강도)
    ema_ok: bool
    bb_ok: bool
    macd_ok: bool
    close: float
    ema200: float
    bb_upper: float
    bb_lower: float
    macd_hist: float
    regime: str             # "Trend" | "Range" | "Neutral"
    reason: str


class StrategyEngine:
    """
    Triple-Indicator 전략 엔진

    진입 조건 (Long):
        1. 종가 > EMA200 (상승 추세)
        2. 종가가 BB 하단 터치 후 회귀 (과매도 반등)
        3. MACD 히스토그램 음 → 양 전환 (모멘텀 확인)

    진입 조건 (Short):
        1. 종가 < EMA200 (하락 추세)
        2. 종가가 BB 상단 터치 후 회귀
        3. MACD 히스토그램 양 → 음 전환
    """

    def __init__(self):
        self.cfg = CFG

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """기술 지표 계산"""
        if len(df) < max(self.cfg.EMA_PERIOD, self.cfg.BB_PERIOD, self.cfg.MACD_SLOW) + 10:
            return pd.DataFrame()

        df = df.copy()

        # EMA 200
        df["ema200"] = ta.trend.ema_indicator(df["close"], window=self.cfg.EMA_PERIOD)

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(
            df["close"], window=self.cfg.BB_PERIOD, window_dev=self.cfg.BB_STD
        )
        df["bb_upper"] = bb.bollinger_hband()
        df["bb_mid"] = bb.bollinger_mavg()
        df["bb_lower"] = bb.bollinger_lband()
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

        # MACD
        macd = ta.trend.MACD(
            df["close"],
            window_fast=self.cfg.MACD_FAST,
            window_slow=self.cfg.MACD_SLOW,
            window_sign=self.cfg.MACD_SIGNAL,
        )
        df["macd"] = macd.macd()
        df["macd_signal"] = macd.macd_signal()
        df["macd_hist"] = macd.macd_diff()

        # ADX (추세 강도) - 결측치 방지 처리
        adx_series = ta.trend.adx(df["high"], df["low"], df["close"], window=14)
        df["adx"] = adx_series.fillna(0)
        
        # EMA 20, 50 (추세 정배열 확인용) - 결측치 방지
        df["ema20"] = ta.trend.ema_indicator(df["close"], window=20).fillna(df["close"])
        df["ema50"] = ta.trend.ema_indicator(df["close"], window=50).fillna(df["close"])

        # RSI (보조)
        df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi().fillna(50)

        return df.dropna()

    def get_market_regime(self, df: pd.DataFrame) -> str:
        """현재 시장이 추세장인지 횡보장인지 판별 (v2.1.0 구조적 개선)"""
        if df.empty or len(df) < 5: return "Neutral"
        
        cur = df.iloc[-1]
        adx = float(cur.get("adx", 0))
        ema20 = float(cur.get("ema20", cur["close"]))
        ema50 = float(cur.get("ema50", cur["close"]))
        close = float(cur["close"])
        
        # 민감도에 따른 임계값 설정
        sensitivity = self.cfg.REGIME_SENSITIVITY
        if sensitivity == "Aggressive":
            trend_adx = 15   # 매우 낮춤
            range_adx = 30   # 매우 높임
            ema_gap_pct = 0.020
        elif sensitivity == "Conservative":
            trend_adx = 30
            range_adx = 15
            ema_gap_pct = 0.005
        else: # Neutral (Default)
            trend_adx = 22
            range_adx = 22
            ema_gap_pct = 0.010
            
        # 1. 횡보장 판별 (ADX가 낮거나 이평선이 밀집된 경우) - 횡보를 먼저 잡음
        is_ranging = (adx < range_adx) or (abs(ema20 - ema50) / ema20 < ema_gap_pct)
        
        # 2. 추세장 판별 (ADX가 충분히 높고 가격이 이평선 위에 있는 경우)
        is_trending_long = (adx >= range_adx) and (close > ema20)
        is_trending_short = (adx >= range_adx) and (close < ema20)
        
        if is_trending_long or is_trending_short:
            return "Trend"
        elif is_ranging:
            return "Range"
            
        return "Neutral"

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal:
        """최신 캔들 기준 매매 신호 생성"""
        df = self.calculate_indicators(df)

        empty_signal = Signal(
            symbol=symbol, direction="none", strength=0,
            ema_ok=False, bb_ok=False, macd_ok=False,
            close=0, ema200=0, bb_upper=0, bb_lower=0,
            macd_hist=0, regime="Neutral", reason="데이터 부족"
        )

        if df.empty or len(df) < 3:
            return empty_signal

        cur = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]
        
        regime = self.get_market_regime(df)

        close = cur["close"]
        ema200 = cur["ema200"]
        bb_upper = cur["bb_upper"]
        bb_lower = cur["bb_lower"]
        macd_hist = cur["macd_hist"]
        prev_hist = prev["macd_hist"]
        rsi = cur["rsi"]

        # ── LONG 조건 평가 ──────────────────────────────
        long_ema = close > ema200
        long_bb = (prev["close"] <= prev["bb_lower"] or prev2["close"] <= prev2["bb_lower"]) \
                  and close > bb_lower
        long_macd = prev_hist < 0 and macd_hist > prev_hist  # 음 → 상승 전환
        long_rsi = rsi < 60  # 과매수 아님

        # ── SHORT 조건 평가 ─────────────────────────────
        short_ema = close < ema200
        short_bb = (prev["close"] >= prev["bb_upper"] or prev2["close"] >= prev2["bb_upper"]) \
                   and close < bb_upper
        short_macd = prev_hist > 0 and macd_hist < prev_hist  # 양 → 하락 전환
        short_rsi = rsi > 40  # 과매도 아님

        # ── 신호 강도 계산 ──────────────────────────────
        def compute_strength(ema_ok, bb_ok, macd_ok, hist_mag) -> int:
            score = 0
            if ema_ok:
                score += 35
            if bb_ok:
                score += 35
            if macd_ok:
                score += 20
            # MACD 히스토그램 절대값이 클수록 가중
            score += min(10, int(abs(hist_mag) / close * 10_000))
            return min(100, score)

        if long_ema and long_bb and long_macd and long_rsi and self.cfg.ALLOW_LONG:
            strength = compute_strength(long_ema, long_bb, long_macd, macd_hist)
            return Signal(
                symbol=symbol, direction="long", strength=strength,
                ema_ok=long_ema, bb_ok=long_bb, macd_ok=long_macd,
                close=close, ema200=ema200,
                bb_upper=bb_upper, bb_lower=bb_lower,
                macd_hist=macd_hist, regime=regime,
                reason=f"EMA200 위 + BB하단 반등 + MACD강세 ({regime}, 강도 {strength}%)"
            )

        if short_ema and short_bb and short_macd and short_rsi and self.cfg.ALLOW_SHORT:
            strength = compute_strength(short_ema, short_bb, short_macd, macd_hist)
            return Signal(
                symbol=symbol, direction="short", strength=strength,
                ema_ok=short_ema, bb_ok=short_bb, macd_ok=short_macd,
                close=close, ema200=ema200,
                bb_upper=bb_upper, bb_lower=bb_lower,
                macd_hist=macd_hist, regime=regime,
                reason=f"EMA200 아래 + BB상단 반전 + MACD약세 ({regime}, 강도 {strength}%)"
            )

        # 부분 신호 강도 계산 (스캐너 표시용)
        if long_ema:
            s = compute_strength(long_ema, long_bb, long_macd, macd_hist)
            return Signal(
                symbol=symbol, direction="none", strength=s,
                ema_ok=long_ema, bb_ok=long_bb, macd_ok=long_macd,
                close=close, ema200=ema200,
                bb_upper=bb_upper, bb_lower=bb_lower,
                macd_hist=macd_hist, regime=regime, reason="조건 미충족"
            )

        return Signal(
            symbol=symbol, direction="none", strength=10,
            ema_ok=long_ema, bb_ok=False, macd_ok=False,
            close=close, ema200=ema200,
            bb_upper=bb_upper, bb_lower=bb_lower,
            macd_hist=macd_hist, reason="EMA200 이하 — 추세 없음"
        )
