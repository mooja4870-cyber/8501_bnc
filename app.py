"""
AI QUANTUM — OKX Auto-Trading Dashboard (v1.2.07)
Streamlit 기반 전문가용 실시간 대시보드
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, timezone
import time
import os
from dotenv import load_dotenv, set_key

# ── 서버 강제 종료 로직 (v1.2.07) ──────────────────
if "kill_server_final" in st.session_state:
    os._exit(0)

from core.exchange import OKXClient
from core.scanner import Scanner
from core.trader import AutoTrader
from core.engine import QuantumEngine
from core.backtest import BacktestEngine
from core.config import CFG, TradingConfig
import core.stats as stats_store
from core.utils import ServerLock

# ── 페이지 설정 (MUST BE FIRST) ──────────────────────
st.set_page_config(
    page_title="AI QUANTUM · OKX Trader",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 중복 실행 방지 (Windows Mutex) ───────────────────
@st.cache_resource
def acquire_server_lock():
    return ServerLock.acquire()

if not acquire_server_lock():
    st.error("⚠️ **이미 다른 터미널에서 서버가 실행 중입니다.**")
    st.info("이중 실행 시 주문이 중복으로 발생할 수 있어 실행을 원천 차단합니다. 기존 터미널을 종료하거나 확인해 주세요.")
    st.stop()

# ── 환경 설정 로드 ─────────────────────────────────
load_dotenv(override=True)
CFG.refresh()

@st.cache_data
def get_system_start_date():
    """Git 로그에서 최초 커밋 날짜를 추출함"""
    try:
        import subprocess
        cmd = ["git", "log", "--reverse", "--format=%ai"]
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8')
        first_line = result.split('\n')[0].strip()
        if first_line:
            return pd.to_datetime(first_line)
    except Exception:
        pass
    # 기본값: 2026-05-10 (v1.1.75 기준 시점)
    return pd.to_datetime("2026-05-10 15:48:45 +0900")

# ── 다크 테마 CSS ─────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Noto+Sans+KR:wght@400;500;700&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        background-color: #0a0a0a !important;
        color: #e8e8e8 !important;
        font-family: 'Noto Sans KR', sans-serif;
    }
    [data-testid="stHeader"] { background: transparent !important; }
    [data-testid="stSidebar"] { background: #111111 !important; border-right: 1px solid rgba(255,255,255,0.07) !important; }

    /* 메트릭 카드 */
    [data-testid="metric-container"] {
        background: #111111 !important;
        border: 1px solid rgba(255,255,255,0.07) !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
    }
    [data-testid="stMetricValue"] {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 1.5rem !important;
        color: #e8e8e8 !important;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.65rem !important;
        letter-spacing: 0.08em !important;
        color: #666 !important;
        text-transform: uppercase !important;
    }
    [data-testid="stMetricDelta"] { font-family: 'IBM Plex Mono', monospace !important; }

    /* 버튼 */
    .stButton > button {
        background: #e0e0e0 !important;
        color: #0a0a0a !important;
        border: none !important;
        border-radius: 6px !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-weight: 600 !important;
        letter-spacing: 0.05em !important;
    }
    .stButton > button:hover { opacity: 0.85 !important; }
    .refresh-btn button {
        background: rgba(9, 18, 28, 0.9) !important;
        color: #5de1ff !important;
        border: 1px solid rgba(93, 225, 255, 0.6) !important;
        border-radius: 12px !important;
        box-shadow: inset 0 0 0 1px rgba(93, 225, 255, 0.15), 0 0 10px rgba(93, 225, 255, 0.15) !important;
        letter-spacing: 0.08em !important;
    }
    .refresh-btn button:hover {
        opacity: 1 !important;
        box-shadow: inset 0 0 0 1px rgba(93, 225, 255, 0.35), 0 0 16px rgba(93, 225, 255, 0.35) !important;
    }

    /* 구분선 */
    hr { border-color: rgba(255,255,255,0.07) !important; }

    /* 탭 */
    .stTabs [data-baseweb="tab-list"] { background: #111111; border-radius: 8px; padding: 4px; }
    .stTabs [data-baseweb="tab"] { color: #888 !important; font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem; letter-spacing: 0.05em; }
    .stTabs [aria-selected="true"] { background: #e0e0e0 !important; color: #0a0a0a !important; border-radius: 6px !important; }

    /* 인풋 */
    .stTextInput input, .stSelectbox select, .stNumberInput input {
        background: #1a1a1a !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        color: #e8e8e8 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        border-radius: 6px !important;
    }

    /* 데이터프레임 */
    [data-testid="stDataFrame"] { background: #111111 !important; }
    .dataframe { background: #111111 !important; color: #e8e8e8 !important; }

    /* 로고 헤더 */
    .quantum-logo {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 1.1rem;
        font-weight: 600;
        color: #c8f53b;
        letter-spacing: 0.1em;
    }
    .quantum-logo span { color: #555; font-weight: 400; }

    /* 상태 배지 */
    .badge-live {
        display: inline-flex; align-items: center; gap: 10px;
        background: rgba(17, 24, 39, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 20px;
        padding: 8px 16px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.72rem;
        font-weight: 700;
        color: #7ef45a;
        letter-spacing: 0.08em;
        box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.12);
    }
    .badge-live .dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: #7ef45a;
        box-shadow: 0 0 8px rgba(126, 244, 90, 0.8);
        animation: green-pulse 1.2s infinite ease-in-out;
    }
    .badge-stopped {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(239,68,68,0.1);
        border: 1px solid rgba(239,68,68,0.3);
        border-radius: 20px;
        padding: 3px 12px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        color: #ef4444;
    }
    .log-box {
        background: #0a0a0a;
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 6px;
        padding: 10px 14px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.7rem;
        color: #666;
        height: 220px;
        overflow-y: auto;
        line-height: 1.8;
        white-space: pre-wrap;
    }
    .neon { color: #c8f53b !important; }
    .green { color: #22c55e !important; }
    .red { color: #ef4444 !important; }
    /* 청산 버튼 특화 스타일 (77% 축소) */
    .small-btn button {
        font-size: 0.26rem !important;
        height: 15px !important;
        min-height: 15px !important;
        width: 35% !important;
        padding: 0 !important;
        margin: 0 auto !important;
        display: block !important;
        transform: scale(0.77) !important;
        transform-origin: center !important;
    }
    /* 분홍색 깜빡임 애니메이션 */
    @keyframes pink-fade {
        0% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(0.98); }
        100% { opacity: 1; transform: scale(1); }
    }
    .badge-pink-blink {
        display: inline-flex; align-items: center; gap: 8px;
        background: rgba(255, 20, 147, 0.15);
        border: 1px solid rgba(255, 20, 147, 0.5);
        border-radius: 6px;
        padding: 6px 16px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem;
        font-weight: 600;
        color: #ff69b4;
        animation: pink-fade 1.5s infinite ease-in-out;
        box-shadow: 0 0 10px rgba(255, 20, 147, 0.2);
    }
    .badge-green-blink {
        display: inline-flex; align-items: center; gap: 8px;
        background: rgba(200, 245, 59, 0.15);
        border: 1px solid rgba(200, 245, 59, 0.5);
        border-radius: 6px;
        padding: 6px 16px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem;
        font-weight: 600;
        color: #c8f53b;
        animation: pink-fade 1.5s infinite ease-in-out;
        box-shadow: 0 0 10px rgba(200, 245, 59, 0.2);
    }
    .badge-red-blink {
        display: inline-flex; align-items: center; gap: 8px;
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.5);
        border-radius: 6px;
        padding: 6px 16px;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem;
        font-weight: 600;
        color: #ef4444;
        animation: pink-fade 1.5s infinite ease-in-out;
        box-shadow: 0 0 10px rgba(239, 68, 68, 0.2);
    }
    /* 서버 중지 버튼 커스텀 (v1.2.07 Ultimate) */
    .btn-stop-wrapper {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 100% !important;
        padding-top: 8px !important;
    }
    /* 특정 키를 가진 스트림릿 버튼 강제 스타일링 */
    div[data-testid="stButton"] button:has(div p:contains("서버중지")),
    div[data-testid="stButton"] button:has(span:contains("서버중지")) {
        background-color: #ef4444 !important;
        color: white !important;
        border-radius: 50px !important;
        border: 1px solid rgba(255,255,255,0.4) !important;
        font-size: 0.72rem !important;
        font-weight: 800 !important;
        height: 28px !important;
        padding: 0 15px !important;
        box-shadow: 0 2px 4px rgba(239, 68, 68, 0.3) !important;
        transition: all 0.2s ease !important;
    }
    /* 위 셀렉터가 안먹을 경우를 대비한 범용 셀렉터 */
    .btn-stop-wrapper button {
        background-color: #ef4444 !important;
        color: white !important;
        border-radius: 50px !important;
        border: 1px solid rgba(255,255,255,0.4) !important;
    }
    .btn-stop-wrapper button p {
        color: white !important;
        font-weight: 800 !important;
    }
    .btn-stop-wrapper button:hover {
        background-color: #dc2626 !important;
        box-shadow: 0 4px 10px rgba(239, 68, 68, 0.5) !important;
        transform: translateY(-1px) !important;
    }
    @keyframes green-pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    .log-latest {
        color: #c8f53b !important;
        font-weight: 700 !important;
        animation: green-pulse 1.2s infinite ease-in-out;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 첨부 디자인 오버라이드 (stitch_trading_bot_ui_design.zip) ──
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --cyber-bg: #0a0c10;
        --cyber-surface: #161b22;
        --cyber-text: #e2e2e8;
        --cyber-dim: #8f9bb3;
        --cyber-green: #e0e0e0;
        --cyber-cyan: #00e5ff;
        --cyber-red: #ff3b30;
    }

    html, body, [data-testid="stAppViewContainer"] {
        background: var(--cyber-bg) !important;
        color: var(--cyber-text) !important;
        font-family: 'Inter', 'Noto Sans KR', sans-serif !important;
    }
    [data-testid="stSidebar"] {
        background: rgba(22, 27, 34, 0.82) !important;
        border-right: 1px solid rgba(132, 150, 126, 0.2) !important;
        backdrop-filter: blur(12px) !important;
    }

    [data-testid="metric-container"] {
        background: rgba(22, 27, 34, 0.78) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 12px !important;
        backdrop-filter: blur(12px) !important;
        box-shadow: inset 0 0 0 1px rgba(255,255,255,0.03);
    }
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'JetBrains Mono', monospace !important;
        color: #7f8aa3 !important;
    }

    .stButton > button {
        background: #e0e0e0 !important;
        color: #0c110d !important;
        border: 1px solid rgba(0,255,65,0.32) !important;
        border-radius: 8px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
        box-shadow: 0 0 10px rgba(255,255,255,0.1) !important;
    }
    .stButton > button:hover {
        opacity: 1 !important;
        box-shadow: 0 0 16px rgba(255,255,255,0.2) !important;
    }
    .refresh-btn button {
        background: rgba(9, 18, 28, 0.9) !important;
        color: var(--cyber-cyan) !important;
        border: 1px solid rgba(0,229,255,0.62) !important;
        border-radius: 12px !important;
        box-shadow: inset 0 0 0 1px rgba(0,229,255,0.18), 0 0 11px rgba(0,229,255,0.2) !important;
        letter-spacing: 0.08em !important;
    }
    .refresh-btn button:hover {
        box-shadow: inset 0 0 0 1px rgba(0,229,255,0.42), 0 0 18px rgba(0,229,255,0.34) !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        background: rgba(22, 27, 34, 0.82);
        border: 1px solid rgba(132, 150, 126, 0.2);
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        color: #94a3b8 !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    .stTabs [aria-selected="true"] {
        background: #e0e0e0 !important;
        color: #0a0c10 !important;
    }

    .quantum-logo {
        font-family: 'Space Grotesk', sans-serif !important;
        line-height: 0.95 !important;
        font-weight: 700 !important;
    }
    .quantum-logo-title {
        display: inline-block !important;
        font-size: 0.8rem !important;
        color: transparent !important;
        background: linear-gradient(
            to right,
            #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3, #ff0000
        ) !important;
        background-size: 200% auto !important;
        -webkit-background-clip: text !important;
        background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        animation: rainbow 6s linear infinite !important;
        letter-spacing: -0.5px !important;
    }
    .quantum-version {
        display: inline-block !important;
        font-size: 0.75rem !important;
        color: var(--cyber-green) !important;
        letter-spacing: 0.08em !important;
    }
    @keyframes rainbow {
        0% { background-position: 0% 50%; }
        100% { background-position: 200% 50%; }
    }

    .badge-live {
        background: rgba(18, 26, 34, 0.82) !important;
        border: 1px solid rgba(126, 244, 90, 0.26) !important;
        border-radius: 999px !important;
        color: #7ef45a !important;
        box-shadow: inset 0 0 0 1px rgba(126, 244, 90, 0.08), 0 0 10px rgba(126, 244, 90, 0.1) !important;
    }
    .badge-live .dot {
        box-shadow: 0 0 9px rgba(126, 244, 90, 0.85) !important;
    }

    .log-box {
        background: rgba(10, 12, 16, 0.86) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 10px !important;
        font-family: 'JetBrains Mono', monospace !important;
        color: #7f8aa3 !important;
    }
    .log-latest {
        color: #7ef45a !important;
    }
    .tabline-time {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.9em !important;
        color: #ffffff !important;
        letter-spacing: 0.02em !important;
        margin: 8px 0 0 !important;
        text-align: right !important;
        white-space: nowrap !important;
        position: relative !important;
        z-index: 30 !important;
    }
    .tabline-status {
        display: flex !important;
        justify-content: flex-end !important;
        margin-top: 0 !important;
        position: relative !important;
        z-index: 30 !important;
    }
    .tabline-status .badge-live,
    .tabline-status .badge-stopped {
        margin-bottom: 0 !important;
        white-space: nowrap !important;
    }
    .tabline-refresh {
        position: relative !important;
        z-index: 30 !important;
        display: block !important;
    }
    .tabline-refresh-link {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        height: 30px !important;
        min-height: 30px !important;
        padding: 0 16px !important;
        border-radius: 8px !important;
        background: #e0e0e0 !important;
        border: 1px solid rgba(0,255,65,0.32) !important;
        color: #0c110d !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.75rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.08em !important;
        text-decoration: none !important;
        box-shadow: 0 0 10px rgba(255,255,255,0.1) !important;
        position: relative !important;
        z-index: 31 !important;
        transform: translateY(-1px) !important;
        white-space: nowrap !important;
        box-sizing: border-box !important;
    }
    .tabline-refresh-link:hover {
        color: #0c110d !important;
        text-decoration: none !important;
        box-shadow: 0 0 16px rgba(0,255,65,0.35) !important;
    }
    .tabline-refresh button {
        height: 30px !important;
        min-height: 30px !important;
        margin-top: 0 !important;
        padding: 0 16px !important;
        position: relative !important;
        z-index: 31 !important;
        transform: translateY(-1px) !important;
        white-space: nowrap !important;
    }
    .stTabs {
        margin-top: -42px !important;
        position: relative !important;
        z-index: 1 !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        padding-right: 600px !important;
        min-height: 42px !important;
        align-items: center !important;
        position: relative !important;
        z-index: 1 !important;
    }
    @media (max-width: 1200px) {
        .stTabs {
            margin-top: 8px !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            padding-right: 4px !important;
        }
        .tabline-time {
            text-align: left !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── 세션 상태 초기화 ──────────────────────────────────

DEFAULT_PRESET_NAME = "기본 (Stable)"
STRATEGY_PRESETS = {
    "기본 (Stable)": {
        "ema": 200, "bb_p": 20, "bb_s": 2.0, "macd_f": 12, "macd_sl": 26, "macd_si": 9
    },
    "1차 공격적 (Trend)": {
        "ema": 100, "bb_p": 20, "bb_s": 1.8, "macd_f": 10, "macd_sl": 22, "macd_si": 7
    },
    "2차 공격적 (Scalping)": {
        "ema": 50, "bb_p": 14, "bb_s": 1.5, "macd_f": 8, "macd_sl": 18, "macd_si": 5
    },
}
DEFAULT_BACKTEST_SYMBOL = "BTC/USDT:USDT"
DEFAULT_BACKTEST_PERIOD = "1년"
BACKTEST_PERIOD_DAYS = {"1년": 365, "2년": 730, "3년": 1095}


def apply_strategy_preset(preset_name=DEFAULT_PRESET_NAME):
    p = STRATEGY_PRESETS[preset_name]
    st.session_state.active_preset = preset_name
    CFG.EMA_PERIOD = p["ema"]
    CFG.BB_PERIOD = p["bb_p"]
    CFG.BB_STD = p["bb_s"]
    CFG.MACD_FAST = p["macd_f"]
    CFG.MACD_SLOW = p["macd_sl"]
    CFG.MACD_SIGNAL = p["macd_si"]


def activate_okx_auto_flow(engine: QuantumEngine):
    apply_strategy_preset(DEFAULT_PRESET_NAME)
    st.session_state.auto_trading = True
    st.session_state.auto_backtest_pending = True

    if engine.is_ready:
        engine.enable_trading()
        engine.start_scanner()


@st.cache_resource
def get_engine():
    return QuantumEngine()

def init_session():
    defaults = {
        "engine": get_engine(),
        "api_connected": False,
        "auto_trading": False,
        "allow_long": True,
        "allow_short": True,
        "active_preset": DEFAULT_PRESET_NAME,
        "auto_backtest_pending": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # .env 값이 있으면 UI 입력창 세션 상태 강제 초기화
    for state_key, env_key in [("api_key_input", "OKX_API_KEY"), 
                               ("secret_input", "OKX_SECRET_KEY"), 
                               ("pass_input", "OKX_PASSPHRASE")]:
        env_val = os.getenv(env_key, "")
        if env_val and (state_key not in st.session_state or not st.session_state[state_key]):
            st.session_state[state_key] = env_val

def connect_api(api_key, secret_key, passphrase, activate_automation=False):
    if not api_key or not secret_key or not passphrase:
        return False, "❌ API 키를 모두 입력해주세요."
    
    engine: QuantumEngine = st.session_state.engine
    success, msg = engine.initialize(api_key, secret_key, passphrase)
    
    if success:
        st.session_state.api_connected = True
        if activate_automation:
            activate_okx_auto_flow(engine)
        return True, msg
    return False, msg

init_session()
engine = st.session_state.engine

# 엔진 상태와 세션 상태 동기화
if engine.is_ready:
    st.session_state.api_connected = True
    if engine.scanner and engine.scanner.is_running:
        st.session_state.auto_trading = True

if not st.session_state.api_connected:
    ak = os.getenv("OKX_API_KEY", "")
    sk = os.getenv("OKX_SECRET_KEY", "")
    pw = os.getenv("OKX_PASSPHRASE", "")
    if ak and sk and pw:
        connect_api(ak, sk, pw)

# ── 백테스트 자동 실행 로직 (글로벌) ───────────────────
if st.session_state.get("auto_backtest_pending", False):
    st.session_state.auto_backtest_pending = False
    with st.spinner("🚀 [자동화] 기본 종목 백테스트 실행 중..."):
        bt_symbol = DEFAULT_BACKTEST_SYMBOL
        period_days = BACKTEST_PERIOD_DAYS[DEFAULT_BACKTEST_PERIOD]
        limit = period_days * 24
        
        df_bt = engine.client.get_ohlcv(bt_symbol, timeframe="1h", limit=min(limit, 1500))
        bt_engine = BacktestEngine()
        st.session_state.last_bt_report = bt_engine.run(df_bt, bt_symbol, DEFAULT_BACKTEST_PERIOD)
        st.toast(f"✅ {bt_symbol} 백테스트 완료")


# ── Plotly 공통 레이아웃 ──────────────────────────────

PLOT_LAYOUT = dict(
    plot_bgcolor="#111111",
    paper_bgcolor="#0a0a0a",
    font=dict(family="IBM Plex Mono", color="#888", size=11),
    xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", zeroline=False),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.04)", zeroline=False),
    margin=dict(l=10, r=10, t=30, b=10),
)


# ══════════════════════════════════════════════════════
# 사이드바 — API 설정
# ══════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(
        '<div class="quantum-logo"><span class="quantum-logo-title">MACD-BB-EMA</span><br><span class="quantum-version">v1.2.07</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown(
        '<p style="font-family:IBM Plex Mono;font-size:0.65rem;color:#555;letter-spacing:0.08em;">API 연결 설정</p>',
        unsafe_allow_html=True,
    )

    api_key = st.text_input(
        "API Key", value=os.getenv("OKX_API_KEY", ""), type="password", key="api_key_input"
    )
    secret_key = st.text_input(
        "Secret Key", value=os.getenv("OKX_SECRET_KEY", ""), type="password", key="secret_input"
    )
    passphrase = st.text_input(
        "Passphrase", value=os.getenv("OKX_PASSPHRASE", ""), type="password", key="pass_input"
    )

    if st.button("🔗  OKX 연결", use_container_width=True):
        with st.spinner("연결 중..."):
            ak = api_key if api_key else os.getenv("OKX_API_KEY", "")
            sk = secret_key if secret_key else os.getenv("OKX_SECRET_KEY", "")
            pw = passphrase if passphrase else os.getenv("OKX_PASSPHRASE", "")
            success, msg = connect_api(ak, sk, pw, activate_automation=True)
            if success:
                st.success(msg)
            else:
                st.error(msg)

    longs = True
    shorts = True

    engine: QuantumEngine = st.session_state.engine

    if st.session_state.auto_trading and engine.is_ready:
        engine.enable_trading()
        if not (engine.scanner and engine.scanner.is_running):
            engine.start_scanner()

    if engine.is_ready and engine.trader:
        engine.trader.allow_long = True
        engine.trader.allow_short = True

    st.markdown("---")
    st.markdown(
        """
        <div style="font-family:'IBM Plex Mono';font-size:0.8rem;color:#666;line-height:1.6;">
        <b style="color:#888;">서버 켜기 (실행)</b><br>
        <code style="font-size:0.8rem; color:#aaa;">streamlit run app.py</code><br><br>
        <b style="color:#888;">서버작동 확인</b><br>
        <code style="font-size:0.8rem; color:#aaa;">tasklist | findstr python</code><br>
        <span style="color:#444;">(python.exe가 보이면 OK!)</span><br><br>
        <b style="color:#888;">포트연결 확인</b><br>
        <code style="font-size:0.8rem; color:#aaa;">netstat -ano | findstr :8502</code>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════
# 메인 헤더
# ══════════════════════════════════════════════════════

now_kst = datetime.now(timezone.utc) + timedelta(hours=9)
tabline_spacer, tabline_time, tabline_stop, tabline_status, tabline_refresh = st.columns([3.8, 1.8, 1.3, 1.35, 1.45])

with tabline_time:
    st.markdown(
        f'<p class="tabline-time">{now_kst.strftime("%Y-%m-%d %H:%M:%S")} KST</p>',
        unsafe_allow_html=True,
    )

with tabline_stop:
    st.markdown('<div class="btn-stop-wrapper">', unsafe_allow_html=True)
    if st.button("서버중지", key="kill_server_final"):
        import os
        os._exit(0)
    st.markdown('</div>', unsafe_allow_html=True)

with tabline_status:
    # 엔진의 실제 실행 상태를 기준으로 표시
    is_live = False
    if engine.is_ready and engine.scanner and engine.scanner.is_running:
        is_live = True
    
    if is_live:
        status_html = '<div class="badge-live"><span class="dot"></span><span>LIVE CONNECTION</span></div>'
    else:
        status_html = '<div class="badge-stopped">● STOPPED</div>'
    st.markdown(f'<div class="tabline-status">{status_html}</div>', unsafe_allow_html=True)

with tabline_refresh:
    st.markdown(
        f'<div class="tabline-refresh"><a class="tabline-refresh-link" href="?refresh={int(time.time())}" target="_self">⟳ REFRESH</a></div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════
# 탭 구성
# ══════════════════════════════════════════════════════

tabs = st.tabs([
    "📊  대시보드",
    "🔍  스캐너",
    "📈  백테스트",
    "📋  매매 이력",
    "🎯  포지션 진입",
    "⚙️  설정",
])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 1: 대시보드
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[0]:
    engine: QuantumEngine = st.session_state.engine

    if not st.session_state.api_connected or not engine.is_ready:
        st.info("사이드바에서 OKX API를 연결하세요.")
    else:
        # ── 데이터 통합 조회 ──────────────────────────
        dash = engine.get_dashboard_data()
        positions = dash.get("positions", [])

        # ── 상단 지표 (투명성 강화 버전) ──────────────────────
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric("💰 총 잔고", f"${dash.get('total_balance', 0.0):,.2f}")
        with m2:
            # 🔒 사용 중 증거금 상세 팝오버
            with st.popover("🔒 사용 중 증거금"):
                st.markdown("##### 🛡️ 증거금 상세 내역")
                used_total = dash.get('used_margin', 0.0)
                st.write(f"**합계:** `${used_total:,.2f} USDT`")
                
                # 1. 포지션 증거금
                if positions:
                    st.markdown("**📂 포지션 유지 증거금**")
                    pos_df = pd.DataFrame([
                        {"종목": p['symbol'], "방향": p['side'].upper(), "사용 증거금": f"${p['margin']:.2f}"}
                        for p in positions
                    ])
                    st.table(pos_df)
                
                # 2. 미체결 주문 (예약 증거금)
                open_orders = engine.client.get_open_orders()
                if open_orders:
                    st.markdown("**⏳ 미체결 주문 (예약 중)**")
                    order_df = pd.DataFrame([
                        {"종목": o['symbol'], "구분": o['side'].upper(), "수량": o['amount']}
                        for o in open_orders
                    ])
                    st.table(order_df)
                
                if not positions and not open_orders:
                    st.info("현재 사용 중인 증거금이 없습니다.")
            
            st.markdown(f'<p style="font-size:1.5rem; font-weight:bold; margin-top:-15px;">${dash.get("used_margin", 0.0):,.2f}</p>', unsafe_allow_html=True)
            
        with m3:
            st.metric("🔓 가용 증거금", f"${dash.get('free_margin', 0.0):,.2f}")
        with m4:
            total_upnl = sum(p.get("pnl_usdt", 0.0) for p in positions)
            st.metric("미실현 손익", f"${total_upnl:+.2f}")
        with m5:
            dpnl = engine.trader.daily_pnl_usdt if engine.trader else 0.0
            st.metric("금일 실현 손익", f"${dpnl:+.2f}")

        st.markdown("---")

        # ── 포지션 / 로그 ──────────────────────────
        col_pos, col_log = st.columns([1.2, 1])

        with col_pos:
            col_title, col_bulk = st.columns([1, 1])
            with col_title:
                st.markdown(
                    '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">ACTIVE POSITIONS</p>',
                    unsafe_allow_html=True,
                )
            with col_bulk:
                if positions:
                    st.markdown('<div class="small-btn">', unsafe_allow_html=True)
                    if st.button("🔴 모든 종목 일괄청산", use_container_width=False, key="bulk_close"):
                        count = engine.client.close_all_positions()
                        if count > 0:
                            st.toast(f"✅ {count}개 포지션 일괄 청산 완료")
                            time.sleep(1)
                            st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

            if not positions:
                st.markdown(
                    '<p style="color:#444;font-family:\'IBM Plex Mono\',monospace;font-size:0.8rem;">포지션 없음</p>',
                    unsafe_allow_html=True,
                )
            else:
                for p in positions:
                    pnl_val = p.get("pnl_usdt", 0.0)
                    pnl_color = "#22c55e" if pnl_val >= 0 else "#ef4444"
                    side_badge = (
                        "🟢 LONG" if p["side"] == "long" else "🔴 SHORT"
                    )
                    pc1, pc2 = st.columns([3.5, 1])
                    with pc1:
                        st.markdown(
                            f"""
                            <div style="background:#161616;border:1px solid rgba(255,255,255,0.07);
                                        border-radius:8px;padding:12px 14px;margin-bottom:8px;">
                              <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                                <span style="font-family:'IBM Plex Mono';font-size:0.85rem;font-weight:600;">{p['symbol']}</span>
                                <span style="font-family:'IBM Plex Mono';font-size:0.85rem;font-weight:600;color:{pnl_color};">
                                  {p.get('pnl_usdt', 0.0):+.4f} USDT ({p.get('pnl_pct', 0.0):+.1f}%)
                                </span>
                              </div>
                              <div style="font-family:'IBM Plex Mono';font-size:0.7rem;color:#555;display:flex;gap:16px;">
                                <span>{side_badge}</span>
                                <span>진입가 ${p['entry_price']:,.4f}</span>
                                <span>현재가 ${p['mark_price']:,.4f}</span>
                                <span>{p['leverage']}x LEV</span>
                              </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    with pc2:
                        st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)
                        st.markdown('<div class="small-btn">', unsafe_allow_html=True)
                        if st.button("즉시청산", key=f"close_{p['symbol']}", use_container_width=False):
                            if engine.client.close_position(p["symbol"], p["side"]):
                                # 수동 청산 결과도 누적 통계에 즉시 반영
                                pnl = p.get("pnl_usdt", 0.0)
                                stats_store.record_result(pnl)
                                st.toast(f"✅ {p['symbol']} 청산 완료 (PnL: {pnl:+.4f})")
                                time.sleep(1)
                                st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)

        with col_log:
            st.markdown(
                '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">SYSTEM LOG</p>',
                unsafe_allow_html=True,
            )
            engine: QuantumEngine = st.session_state.engine
            logs = engine.scanner.get_logs(30) if engine.scanner else ["[SYS] 엔진 미연결"]
            
            if logs:
                # 최신 로그(마지막 요소)에 특수 스타일 적용
                latest_line = f'<span class="log-latest">{logs[-1]}</span>'
                other_lines = "\n".join(reversed(logs[:-1])) if len(logs) > 1 else ""
                log_html = f"{latest_line}\n{other_lines}" if other_lines else latest_line
            else:
                log_html = "로그 없음"

            st.markdown(
                f'<div class="log-box">{log_html}</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # ── 하단 리스크 및 통계 ───────────────────────
        # ── 거래소 이력 기반 실시간 집계 (stats.json 의존 제거) ──
        all_trades = engine.get_trade_history(limit=100)
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        _kst = _tz(_td(hours=9))
        _today_str = _dt.now(_kst).strftime("%Y-%m-%d")
        
        # 금일 거래만 필터
        today_trades = [
            t for t in all_trades
            if str(t['timestamp'])[:10] == _today_str
        ]
        
        # 금일 진입 주문 (고유 order_id 기준)
        entry_ids = set()
        for t in today_trades:
            if t['type'] == '진입' and t.get('order_id'):
                entry_ids.add(t['order_id'])
        orders_today = len(entry_ids)
        
        # 금일 청산 건 기준 승/패 (고유 order_id 기준)
        close_results = {}
        for t in today_trades:
            if t['type'] == '청산' and t.get('order_id'):
                oid = t['order_id']
                if oid not in close_results:
                    close_results[oid] = t.get('pnl_usdt', 0.0)
                else:
                    close_results[oid] += t.get('pnl_usdt', 0.0)
        
        total_wins = sum(1 for pnl in close_results.values() if pnl >= 0)
        total_losses = sum(1 for pnl in close_results.values() if pnl < 0)
        total_trades = total_wins + total_losses
        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
        win_label = f"{win_rate:.1f}%" if total_trades > 0 else "-"
        win_delta = f"{total_wins}W / {total_losses}L" if total_trades > 0 else "N/A"

        # ── 수익률 계산 (실시간 잔고 반영) ──
        live_bal = engine.client.get_balance()
        total_equity = live_bal.get("total", 0.0)
        initial_cap = CFG.INITIAL_CAPITAL
        accu_profit_pct = ((total_equity - initial_cap) / initial_cap) * 100 if initial_cap > 0 else 0.0
        
        # 24시간 수익률 계산
        now = pd.Timestamp.now()
        pnl_24h_usdt = sum(t.get('pnl_usdt', 0.0) for t in all_trades if 'timestamp' in t and (now - t['timestamp']).total_seconds() < 86400)
        equity_24h_ago = total_equity - pnl_24h_usdt
        pnl_24h_pct = (pnl_24h_usdt / equity_24h_ago) * 100 if equity_24h_ago > 0 else 0.0

        # 일 평균 수익률 계산
        start_date = get_system_start_date()
        # 타임존 통일 (UTC 기준 계산)
        now_utc = pd.Timestamp.now(tz=start_date.tz)
        days_elapsed = (now_utc - start_date).days + 1
        daily_avg_pct = accu_profit_pct / days_elapsed if days_elapsed > 0 else accu_profit_pct

        # ── 5컬럼 레이아웃 ──
        total_win_rate = stats_store.get_win_rate()
        _st = stats_store.load_stats()
        total_wins = _st.get("total_wins", 0)
        total_losses = _st.get("total_losses", 0)
        win_summary = f"{total_wins}W / {total_losses}L"

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("누적 수익률", f"{accu_profit_pct:+.2f}%", f"{pnl_24h_pct:+.2f}% (24h)")
        with c2:
            st.markdown(f"""
                <div style="line-height: 1.2;">
                    <p style="font-size: 0.85rem; color: #888; margin-bottom: 4px;">일 평균 수익률</p>
                    <p style="font-size: 1.6rem; font-weight: 500; color: #fff; margin-bottom: 2px;">{daily_avg_pct:+.2f}%</p>
                    <p style="font-size: 14px; color: #22c55e;">{start_date.strftime('%m/%d/%Y')}~</p>
                </div>
            """, unsafe_allow_html=True)
        with c3:
            st.metric("누적 승률", f"{total_win_rate:.1f}%", win_summary)
        with c4:
            st.metric("MDD 한도", f"-{CFG.MAX_DRAWDOWN_PCT*100:.0f}%", "Max Risk")
        with c5:
            st.metric("금일 주문", f"{orders_today}건", "Today")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 2: 스캐너
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[1]:
    engine: QuantumEngine = st.session_state.engine

    if not st.session_state.api_connected or not engine.is_ready:
        st.info("사이드바에서 OKX API를 연결하세요.")
    else:
        sc1, sc2, sc3 = st.columns([2, 1, 1])

        with sc1:
            if st.button("▶  스캔 시작", use_container_width=True):
                engine.start_scanner()
        
        with sc2:
            if st.button("⏹  스캔 중지", use_container_width=True):
                engine.stop_scanner()

        with sc3:
            last = engine.scanner.last_scan_time if engine.scanner else None
            if last:
                st.markdown(
                    f'<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;">마지막 스캔: {last.strftime("%H:%M:%S")}</p>',
                    unsafe_allow_html=True,
                )

        # 상태 표시 배지 (상황별 색상 연동)
        if engine.scanner and engine.scanner.is_running:
            preset = st.session_state.active_preset
            badge_class = "badge-green-blink"
            if "1차" in preset:
                badge_class = "badge-pink-blink"
            elif "2차" in preset:
                badge_class = "badge-red-blink"
                
            st.markdown(
                f'<div style="text-align:center; margin-bottom: 20px;">'
                f'<div class="{badge_class}">📡 {preset} 스캐너 가동 중</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        results = engine.get_scan_results()

        if results:
            df_scan = pd.DataFrame(results)

            # 신호 필터
            signal_filter = st.selectbox(
                "신호 필터",
                ["전체", "LONG 신호", "SHORT 신호", "신호 없음"],
                label_visibility="collapsed",
            )
            if signal_filter == "LONG 신호":
                df_scan = df_scan[df_scan["signal"] == "long"]
            elif signal_filter == "SHORT 신호":
                df_scan = df_scan[df_scan["signal"] == "short"]
            elif signal_filter == "신호 없음":
                df_scan = df_scan[df_scan["signal"] == "none"]

            # 표시용 포맷
            display = df_scan[["symbol","price","change_pct","volume_m","signal","strength","ema_ok","macd_ok","bb_ok"]].copy()
            display.columns = ["종목","현재가","등락(%)","거래대금(M)","신호","강도(%)","EMA200","MACD","BB"]
            display["신호"] = display["신호"].map({"long":"🟢 LONG","short":"🔴 SHORT","none":"— "})
            display["EMA200"] = display["EMA200"].map({True:"✅",False:"❌"})
            display["MACD"] = display["MACD"].map({True:"✅",False:"❌"})
            display["BB"] = display["BB"].map({True:"✅",False:"❌"})

            st.dataframe(
                display,
                use_container_width=True,
                height=500,
                hide_index=True,
            )
        else:
            st.markdown(
                '<p style="color:#555;font-family:\'IBM Plex Mono\',monospace;">스캔 결과 없음 — 스캔 시작 버튼을 누르세요.</p>',
                unsafe_allow_html=True,
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 3: 백테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[2]:
    engine: QuantumEngine = st.session_state.engine

    if not st.session_state.api_connected or not engine.is_ready:
        st.info("사이드바에서 OKX API를 연결하세요.")
    else:
        bt1, bt2, bt3 = st.columns([2, 1, 1])

        with bt1:
            bt_symbol = st.selectbox(
                "종목 선택",
                ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", "XRP/USDT:USDT", "DOGE/USDT:USDT"],
            )
        with bt2:
            bt_period = st.selectbox("기간", ["1년", "2년", "3년"])
        with bt3:
            run_bt = st.button("📊  백테스트 실행", use_container_width=True)

        auto_run_bt = False # 글로벌에서 이미 처리됨
        
        report = st.session_state.get("last_bt_report")
        
        if run_bt:
            period_days = BACKTEST_PERIOD_DAYS[bt_period]
            limit = period_days * 24  # 1h 캔들 수

            with st.spinner(f"{bt_symbol} {bt_period} 백테스트 실행 중..."):
                df_bt = engine.client.get_ohlcv(bt_symbol, timeframe="1h", limit=min(limit, 1500))
                bt_engine = BacktestEngine()
                report = bt_engine.run(df_bt, bt_symbol, bt_period)
                st.session_state.last_bt_report = report

        if report:
            if report.total_trades == 0:
                st.warning("백테스트 결과가 없습니다. 데이터를 확인하세요.")
            else:
                # 상단 성과 지표
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("누적 수익률", f"{report.total_pnl_pct:+.1f}%")
                c2.metric("승률", f"{report.win_rate:.1f}%")
                c3.metric("Profit Factor", f"{report.profit_factor:.2f}")
                c4.metric("최대 낙폭", f"{report.max_drawdown_pct:.1f}%")
                c5.metric("총 거래수", f"{report.total_trades}회")

                st.markdown("---")

                col_eq, col_monthly = st.columns(2)

                with col_eq:
                    st.markdown(
                        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">EQUITY CURVE</p>',
                        unsafe_allow_html=True,
                    )
                    fig_eq = go.Figure()
                    fig_eq.add_trace(go.Scatter(
                        y=report.equity_curve,
                        mode="lines",
                        line=dict(color="#c8f53b", width=1.5),
                        fill="tozeroy",
                        fillcolor="rgba(200,245,59,0.06)",
                        name="잔고",
                    ))
                    fig_eq.update_layout(**PLOT_LAYOUT, height=250, showlegend=False)
                    st.plotly_chart(fig_eq, use_container_width=True)

                with col_monthly:
                    st.markdown(
                        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">MONTHLY RETURNS (%)</p>',
                        unsafe_allow_html=True,
                    )
                    if report.monthly_returns:
                        months = list(report.monthly_returns.keys())
                        rets = list(report.monthly_returns.values())
                        colors = ["#22c55e" if r >= 0 else "#ef4444" for r in rets]
                        fig_m = go.Figure(go.Bar(
                            x=months, y=rets,
                            marker_color=colors,
                            text=[f"{r:.1f}%" for r in rets],
                            textposition="outside",
                            textfont=dict(size=9, family="IBM Plex Mono"),
                        ))
                        fig_m.update_layout(**PLOT_LAYOUT, height=250, showlegend=False)
                        st.plotly_chart(fig_m, use_container_width=True)

                # 거래 목록
                st.markdown("---")
                st.markdown(
                    '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">TRADE LIST</p>',
                    unsafe_allow_html=True,
                )
                if report.trades:
                    df_trades = pd.DataFrame([
                        {
                            "진입시각": t.entry_time.strftime("%Y-%m-%d %H:%M"),
                            "청산시각": t.exit_time.strftime("%Y-%m-%d %H:%M"),
                            "방향": "🟢 LONG" if t.direction == "long" else "🔴 SHORT",
                            "진입가": f"${t.entry_price:,.4f}",
                            "청산가": f"${t.exit_price:,.4f}",
                            "수익률(%)": f"{t.pnl_pct:+.2f}%",
                            "손익(USDT)": f"${t.pnl_usdt:+.4f}",
                            "청산사유": t.exit_reason.upper(),
                        }
                        for t in reversed(report.trades[-100:])
                    ])
                    st.dataframe(df_trades, use_container_width=True, hide_index=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 4: 매매 이력
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[3]:
    engine: QuantumEngine = st.session_state.engine

    if not st.session_state.api_connected or not engine.is_ready:
        st.info("사이드바에서 OKX API를 연결하세요.")
    else:
        h1, h2 = st.columns([2, 1])
        with h1:
            hist_symbol = st.selectbox("종목 필터", ["전체"] + [
                "BTC/USDT:USDT","ETH/USDT:USDT","SOL/USDT:USDT"
            ], key="hist_sym")
        with h2:
            if st.button("🔄  이력 새로고침", use_container_width=True):
                st.rerun()

        sym_filter = None if hist_symbol == "전체" else hist_symbol
        history = engine.get_trade_history(symbol=sym_filter, limit=100)

        if history:
            df_hist = pd.DataFrame(history[::-1])
            df_hist["timestamp"] = df_hist["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
            # 컬럼 순서 및 이름 정의
            expected_cols = ["timestamp", "symbol", "type", "side", "amount", "cost", "leverage", "price", "pnl_usdt", "pnl_pct", "fee"]
            df_hist = df_hist.reindex(columns=expected_cols)
            df_hist.columns = ["시각", "종목", "구분", "방향", "수량", "거래금액", "레버리지", "체결가", "손익(USDT)", "수익률(%)", "수수료"]
            
            # 포맷팅 및 스타일링
            df_hist["방향"] = df_hist["방향"].map({"buy":"🟢 BUY","sell":"🔴 SELL"}).fillna(df_hist["방향"])
            df_hist["구분"] = df_hist["구분"].apply(lambda x: f"🟡 {x}" if x == "청산" else x)
            
            # 손익 포맷팅
            df_hist["손익(USDT)"] = df_hist["손익(USDT)"].apply(lambda x: f"📈 +{x:,.4f}" if x > 0 else (f"📉 {x:,.4f}" if x < 0 else "—"))
            df_hist["수익률(%)"] = df_hist["수익률(%)"].apply(lambda x: f"+{x:.2f}%" if x > 0 else (f"{x:.2f}%" if x < 0 else "—"))

            st.dataframe(df_hist, use_container_width=True, hide_index=True, height=500)
        else:
            # 자동매매 엔진 로그 표시
            if engine.trader:
                logs = engine.trader.get_trade_log()
                if logs:
                    df_engine = pd.DataFrame(logs)
                    df_engine["timestamp"] = df_engine["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
                    st.dataframe(df_engine, use_container_width=True, hide_index=True)
                else:
                    st.markdown(
                        '<p style="color:#555;font-family:\'IBM Plex Mono\',monospace;">거래 이력 없음</p>',
                        unsafe_allow_html=True,
                    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 5: 포지션 진입
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[4]:
    st.markdown(
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">ENTRY CONDITIONS</p>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🟢 LONG 포지션 진입 조건**")
        st.markdown("- **추세:** 현재가가 EMA 보다 높음")
        st.markdown("- **반등:** 최근 2캔들 내 볼린저 밴드 하단 터치 후 상승 돌파")
        st.markdown("- **모멘텀:** MACD 히스토그램이 상승 반전 (음수에서 양의 방향)")
        st.markdown("- **필터:** RSI < 60 (과매수 아님)")

    with c2:
        st.markdown("**🔴 SHORT 포지션 진입 조건**")
        st.markdown("- **추세:** 현재가가 EMA 보다 낮음")
        st.markdown("- **반등:** 최근 2캔들 내 볼린저 밴드 상단 터치 후 하락 돌파")
        st.markdown("- **모멘텀:** MACD 히스토그램이 하락 반전 (양수에서 음의 방향)")
        st.markdown("- **필터:** RSI > 40 (과매도 아님)")

    st.markdown("---")
    st.markdown(
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">INDICATOR PARAMETERS & PRESETS</p>',
        unsafe_allow_html=True,
    )

    preset_name = st.selectbox("전략 프리셋 선택", list(STRATEGY_PRESETS.keys()), index=0)
    
    if st.button("🪄 프리셋 적용"):
        apply_strategy_preset(preset_name)
        st.toast(f"✅ {preset_name} 파라미터 적용됨")
        time.sleep(0.5)
        st.rerun()

    p1, p2, p3 = st.columns(3)
    with p1:
        CFG.EMA_PERIOD = st.number_input("EMA 기간", 10, 500, CFG.EMA_PERIOD, step=10)
    with p2:
        CFG.BB_PERIOD = st.number_input("BB 기간", 5, 100, CFG.BB_PERIOD, step=5)
        CFG.BB_STD = st.number_input("BB 편차 (x)", 1.0, 5.0, float(CFG.BB_STD), step=0.1)
    with p3:
        CFG.MACD_FAST = st.number_input("MACD 단기", 1, 50, CFG.MACD_FAST, step=1)
        CFG.MACD_SLOW = st.number_input("MACD 장기", 1, 100, CFG.MACD_SLOW, step=1)
        CFG.MACD_SIGNAL = st.number_input("MACD 시그널", 1, 50, CFG.MACD_SIGNAL, step=1)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 6: 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[5]:
    st.markdown(
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">STRATEGY PARAMETERS</p>',
        unsafe_allow_html=True,
    )

    s1, s2 = st.columns(2)
    with s1:
        # ── 초기 자본금 설정 (엔터 입력 시 저장) ──
        prev_cap = float(CFG.INITIAL_CAPITAL)
        
        # 실시간 수익률 미리보기 계산
        live_bal = engine.client.get_balance() if engine.is_ready else {}
        total_equity = live_bal.get("total", prev_cap)
        current_accu = ((total_equity - prev_cap) / prev_cap) * 100 if prev_cap > 0 else 0.0
        
        c_cap, c_preview = st.columns([2, 1])
        with c_cap:
            new_init_cap = st.number_input("초기 자본금 (USDT)", 1.0, 1000000.0, prev_cap, step=1.0, key="cfg_init_cap")
        with c_preview:
            st.metric("실시간 누적 수익률", f"{current_accu:+.2f}%")

        if new_init_cap != prev_cap:
            CFG.INITIAL_CAPITAL = new_init_cap
            set_key(".env", "INITIAL_CAPITAL", str(new_init_cap))
            os.environ["INITIAL_CAPITAL"] = str(new_init_cap)
            time.sleep(1.5)
            st.toast(f"✅ 초기 자본금 변경 완료: ${new_init_cap}")
            st.rerun()
            
        prev_lev = int(CFG.LEVERAGE)
        new_lev = st.slider("레버리지 (x)", 1, 20, prev_lev)
        if new_lev != prev_lev:
            CFG.LEVERAGE = new_lev
            os.environ["LEVERAGE"] = str(new_lev)
            set_key(".env", "LEVERAGE", str(new_lev))
            time.sleep(1.5)
            st.toast(f"✅ 레버리지 변경 완료: {new_lev}x")
            st.rerun()

        prev_margin = float(CFG.MARGIN_USDT)
        new_margin = st.number_input("1회 진입 증거금 (USDT)", 1.0, 10000.0, prev_margin, step=1.0)
        if new_margin != prev_margin:
            CFG.MARGIN_USDT = new_margin
            os.environ["MARGIN_USDT"] = str(new_margin)
            set_key(".env", "MARGIN_USDT", str(new_margin))
            time.sleep(1.5)
            st.toast(f"✅ 진입 증거금 변경 완료: ${new_margin}")
            st.rerun()

        prev_max_pos = int(CFG.MAX_POSITIONS)
        new_max_pos = st.slider("최대 동시 포지션 수", 1, 10, prev_max_pos)
        if new_max_pos != prev_max_pos:
            CFG.MAX_POSITIONS = new_max_pos
            os.environ["MAX_POSITIONS"] = str(new_max_pos)
            set_key(".env", "MAX_POSITIONS", str(new_max_pos))
            time.sleep(1.5)
            st.toast(f"✅ 최대 포지션 변경 완료: {new_max_pos}개")
            st.rerun()

        prev_sl = float(CFG.STOP_LOSS_PCT)
        new_sl_val = st.slider("손절 (%)", 1.0, 10.0, float(prev_sl * 100), step=0.5)
        new_sl = new_sl_val / 100.0
        if abs(new_sl - prev_sl) > 0.0001:
            CFG.STOP_LOSS_PCT = new_sl
            os.environ["STOP_LOSS_PCT"] = str(new_sl)
            set_key(".env", "STOP_LOSS_PCT", str(new_sl))
            time.sleep(1.5)
            st.toast(f"✅ 손절 라인 변경 완료: {new_sl_val}%")
            st.rerun()

    with s2:
        prev_tp = float(CFG.TAKE_PROFIT_PCT)
        new_tp_val = st.slider("익절 (%)", 1.0, 20.0, float(prev_tp * 100), step=0.5)
        new_tp = new_tp_val / 100.0
        if abs(new_tp - prev_tp) > 0.0001:
            CFG.TAKE_PROFIT_PCT = new_tp
            os.environ["TAKE_PROFIT_PCT"] = str(new_tp)
            set_key(".env", "TAKE_PROFIT_PCT", str(new_tp))
            time.sleep(1.5)
            st.toast(f"✅ 익절 라인 변경 완료: {new_tp_val}%")
            st.rerun()

        prev_vol = float(CFG.MIN_VOLUME_USDT)
        new_vol = st.number_input("최소 거래대금 (USDT)", 1_000_000.0, 50_000_000.0, prev_vol, step=1_000_000.0)
        if new_vol != prev_vol:
            CFG.MIN_VOLUME_USDT = new_vol
            os.environ["MIN_VOLUME_USDT"] = str(new_vol)
            set_key(".env", "MIN_VOLUME_USDT", str(new_vol))
            time.sleep(1.5)
            st.toast(f"✅ 최소 거래대금 변경 완료: ${new_vol:,.0f}")
            st.rerun()

        prev_scan = int(CFG.SCAN_INTERVAL_SEC)
        new_scan = st.slider("스캔 주기 (초)", 10, 300, prev_scan, step=10)
        if new_scan != prev_scan:
            CFG.SCAN_INTERVAL_SEC = new_scan
            os.environ["SCAN_INTERVAL_SEC"] = str(new_scan)
            set_key(".env", "SCAN_INTERVAL_SEC", str(new_scan))
            time.sleep(1.5)
            st.toast(f"✅ 스캔 주기 변경 완료: {new_scan}초")
            st.rerun()

        prev_mdd = float(CFG.MAX_DRAWDOWN_PCT)
        new_mdd_val = st.slider("MDD 한도 (%)", 5.0, 50.0, float(prev_mdd * 100), step=1.0)
        new_mdd = new_mdd_val / 100.0
        if abs(new_mdd - prev_mdd) > 0.0001:
            CFG.MAX_DRAWDOWN_PCT = new_mdd
            os.environ["MAX_DRAWDOWN_PCT"] = str(new_mdd)
            set_key(".env", "MAX_DRAWDOWN_PCT", str(new_mdd))
            time.sleep(1.5)
            st.toast(f"✅ MDD 한도 변경 완료: {new_mdd_val}%")
            st.rerun()
        
        if st.button("💾 모든 설정 영구 저장 (.env)", use_container_width=True):
            set_key(".env", "LEVERAGE", str(CFG.LEVERAGE))
            set_key(".env", "MARGIN_USDT", str(CFG.MARGIN_USDT))
            set_key(".env", "MAX_POSITIONS", str(CFG.MAX_POSITIONS))
            set_key(".env", "STOP_LOSS_PCT", str(CFG.STOP_LOSS_PCT))
            set_key(".env", "TAKE_PROFIT_PCT", str(CFG.TAKE_PROFIT_PCT))
            set_key(".env", "SCAN_INTERVAL_SEC", str(CFG.SCAN_INTERVAL_SEC))
            set_key(".env", "MIN_VOLUME_USDT", str(CFG.MIN_VOLUME_USDT))
            set_key(".env", "MAX_DRAWDOWN_PCT", str(CFG.MAX_DRAWDOWN_PCT))
            st.toast("✅ 모든 설정이 .env 파일에 영구 저장되었습니다.")
            time.sleep(0.5)
            st.rerun()

    st.markdown("---")
    st.markdown(
        f"""<div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#555;line-height:2;">
        손익비: 1 : {CFG.TAKE_PROFIT_PCT / CFG.STOP_LOSS_PCT:.1f} &nbsp;|&nbsp;
        증거금/종목: ${CFG.MARGIN_USDT:.2f} USDT &nbsp;|&nbsp;
        최대 노출: ${CFG.MARGIN_USDT * CFG.LEVERAGE * CFG.MAX_POSITIONS:.2f} USDT
        </div>""",
        unsafe_allow_html=True,
    )

# ── 자동 새로고침 ─────────────────────────────────
if st.session_state.auto_trading:
    time.sleep(15)
    st.rerun()
