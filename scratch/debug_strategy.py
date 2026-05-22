import sys, os
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.strategy import StrategyEngine
from core.config import CFG

engine = StrategyEngine()

timestamps = pd.date_range(end=pd.Timestamp.now(), periods=5, freq="15min")
df_base = pd.DataFrame({
    "open": [100.0] * 5,
    "high": [101.0] * 5,
    "low": [99.0] * 5,
    "close": [100.0] * 5,
    "volume": [10000.0] * 5,
}, index=timestamps)

# 1. 롱 진입 100% 만족하는 지표 결과 Mocking
def mock_calc_long(df_input):
    res = df_input.copy()
    res['ssl_up'] = 90.0
    res['ssl_down'] = 85.0
    res['macd_hist'] = 1.5
    res['dot_color'] = ['red', 'red', 'red', 'red', 'green']
    res['candle_color'] = ['blue', 'blue', 'blue', 'blue', 'blue']
    res['bb_upper'] = 2.0
    res['bb_lower'] = -2.0
    res['rsi'] = 50.0 # 정상
    return res

# 2. 롱 진입 100% 만족 + RSI 과열 Mocking
def mock_calc_long_rsi_blocked(df_input):
    res = mock_calc_long(df_input)
    res.loc[res.index[-1], 'rsi'] = 65.0 # 과열
    return res

# 3. 숏 진입 100% 만족하는 지표 결과 Mocking
def mock_calc_short(df_input):
    res = df_input.copy()
    res['ssl_up'] = 115.0
    res['ssl_down'] = 110.0
    res['macd_hist'] = -1.5
    res['dot_color'] = ['green', 'green', 'green', 'green', 'red']
    res['candle_color'] = ['red', 'red', 'red', 'red', 'red']
    res['bb_upper'] = 2.0
    res['bb_lower'] = -2.0
    res['rsi'] = 50.0 # 정상
    return res

# 4. 숏 진입 100% 만족 + RSI 과매도 Mocking
def mock_calc_short_rsi_blocked(df_input):
    res = mock_calc_short(df_input)
    res.loc[res.index[-1], 'rsi'] = 35.0 # 과매도
    return res

print("--- Mock Strategy Verification ---")

# Case 1
engine.calculate_indicators = mock_calc_long
sig_long_ok = engine.generate_signal(df_base, "BTC/USDT:USDT")
print(f"Case 1 (Long, RSI 50.0) -> Direction: {sig_long_ok.direction}, rsi_ok: {sig_long_ok.rsi_ok}, strength: {sig_long_ok.strength}")
assert sig_long_ok.direction == "long"
assert sig_long_ok.rsi_ok is True
assert sig_long_ok.strength == 100

# Case 2
engine.calculate_indicators = mock_calc_long_rsi_blocked
sig_long_blocked = engine.generate_signal(df_base, "BTC/USDT:USDT")
print(f"Case 2 (Long, RSI 65.0) -> Direction: {sig_long_blocked.direction}, rsi_ok: {sig_long_blocked.rsi_ok}, strength: {sig_long_blocked.strength}")
print(f"Reason: {sig_long_blocked.reason}")
assert sig_long_blocked.direction == "none"
assert sig_long_blocked.rsi_ok is False
assert "RSI 과열" in sig_long_blocked.reason
assert sig_long_blocked.strength == 80

# Case 3
engine.calculate_indicators = mock_calc_short
sig_short_ok = engine.generate_signal(df_base, "BTC/USDT:USDT")
print(f"Case 3 (Short, RSI 50.0) -> Direction: {sig_short_ok.direction}, rsi_ok: {sig_short_ok.rsi_ok}, strength: {sig_short_ok.strength}")
assert sig_short_ok.direction == "short"
assert sig_short_ok.rsi_ok is True
assert sig_short_ok.strength == 100

# Case 4
engine.calculate_indicators = mock_calc_short_rsi_blocked
sig_short_blocked = engine.generate_signal(df_base, "BTC/USDT:USDT")
print(f"Case 4 (Short, RSI 35.0) -> Direction: {sig_short_blocked.direction}, rsi_ok: {sig_short_blocked.rsi_ok}, strength: {sig_short_blocked.strength}")
print(f"Reason: {sig_short_blocked.reason}")
assert sig_short_blocked.direction == "none"
assert sig_short_blocked.rsi_ok is False
assert "RSI 과매도" in sig_short_blocked.reason
assert sig_short_blocked.strength == 80

print("\nAll Mock Assertions Passed!")
