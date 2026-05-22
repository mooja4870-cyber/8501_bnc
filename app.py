"""
AI QUANTUM — Binance Auto-Trading Dashboard
Streamlit 기반 전문가용 실시간 대시보드
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv

from core.exchange import BinanceClient
from core.scanner import Scanner
from core.trader import AutoTrader
from core.engine import QuantumEngine, EngineState
from core.config import CFG
import core.stats as stats_store
from core.history_helper import load_local_trade_history, aggregate_and_pair_trades

load_dotenv(override=True)

# ── 페이지 설정 ───────────────────────────────────────
st.set_page_config(
    page_title="AI QUANTUM · Binance Trader",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Wall Street Professional Terminal CSS ─────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;700&display=swap');

    :root {
        --terminal-bg: #050505;
        --terminal-surface: #0f0f0f;
        --terminal-border: #262626;
        --terminal-text: #e0e0e0;
        --terminal-dim: #666666;
        --terminal-accent: #ff9900; /* Bloomberg Orange */
        --terminal-green: #00ff00;
        --terminal-red: #ff3b30;
    }

    html, body, [data-testid="stAppViewContainer"] {
        background-color: var(--terminal-bg) !important;
        color: var(--terminal-text) !important;
        font-family: 'Inter', sans-serif !important;
    }

    [data-testid="stHeader"] { background: transparent !important; }

    [data-testid="stSidebar"] {
        background-color: var(--terminal-surface) !important;
        border-right: 1px solid var(--terminal-border) !important;
    }

    /* 메트릭 카드: 각진 모서리, 그리드 스타일 */
    [data-testid="metric-container"] {
        background: var(--terminal-surface) !important;
        border: 1px solid var(--terminal-border) !important;
        border-radius: 0px !important;
        padding: 10px 15px !important;
    }
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 1.4rem !important;
        font-weight: 700 !important;
        color: var(--terminal-text) !important;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.9rem !important; /* 상향: 14px+ */
        letter-spacing: 0.1em !important;
        color: #cccccc !important; /* Bright Grey */
        text-transform: uppercase !important;
    }

    /* 버튼: 전문 터미널 감성 */
    .stButton > button {
        background: var(--terminal-surface) !important;
        color: var(--terminal-accent) !important;
        border: 1px solid var(--terminal-accent) !important;
        border-radius: 0px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important; /* 상향: 14px+ */
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: var(--terminal-accent) !important;
        color: var(--terminal-bg) !important;
    }

    /* 특수 버튼 (새로고침 등) */
    .refresh-btn button {
        border-color: #5de1ff !important;
        color: #5de1ff !important;
    }
    .refresh-btn button:hover {
        background: #5de1ff !important;
        color: #000 !important;
    }

    /* 탭 */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--terminal-surface);
        border: 1px solid var(--terminal-border);
        border-radius: 0px;
        padding: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        color: #cccccc !important; /* Bright Grey */
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.9rem !important; /* 상향: 14px+ */
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background: var(--terminal-accent) !important;
        color: var(--terminal-bg) !important;
        border-radius: 0px !important;
    }

    /* 인풋 필드 */
    .stTextInput input, .stSelectbox select, .stNumberInput input {
        background: #000000 !important;
        border: 1px solid var(--terminal-border) !important;
        color: var(--terminal-text) !important;
        font-family: 'JetBrains Mono', monospace !important;
        border-radius: 0px !important;
        font-size: 0.9rem !important;
    }

    /* 데이터프레임 */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--terminal-border) !important;
    }

    /* 로고 */
    .quantum-logo {
        font-family: 'JetBrains Mono', monospace;
        font-size: calc(1.1rem * 1.44);
        font-weight: 700;
        color: var(--terminal-accent);
        border-bottom: 2px solid var(--terminal-accent);
        padding-bottom: 5px;
        margin-bottom: 20px;
    }
    .quantum-logo span { color: #cccccc; font-weight: 400; }

    @keyframes rainbow-glow {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .rainbow-text {
        background: linear-gradient(to right, #ff2a2b, #ff9900, #00ff00, #00ffff, #cc33ff, #ff2a2b);
        background-size: 400% 400%;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        color: transparent !important;
        font-weight: 900 !important;
        animation: rainbow-glow 8s ease infinite;
    }

    /* 공통 버튼 스타일의 헤더 배지 */
    .header-btn-like {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        height: 38px !important;
        background: var(--terminal-surface) !important;
        border: 1px solid var(--terminal-border) !important;
        color: #cccccc !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        text-align: center !important;
        box-sizing: border-box !important;
        border-radius: 0px !important;
        white-space: nowrap !important;
    }
    .header-badge-live {
        border-color: var(--terminal-green) !important;
        color: var(--terminal-green) !important;
        background: #001a00 !important;
    }
    .header-badge-live .dot {
        width: 8px; height: 8px;
        background: var(--terminal-green) !important;
        border-radius: 0% !important;
        margin-right: 8px !important;
        display: inline-block !important;
    }
    .header-badge-stopped {
        border-color: var(--terminal-red) !important;
        color: var(--terminal-red) !important;
        background: #1a0000 !important;
    }
    .header-badge-stopped .dot {
        width: 8px; height: 8px;
        background: var(--terminal-red) !important;
        border-radius: 0% !important;
        margin-right: 8px !important;
        display: inline-block !important;
    }

    /* 시스템 로그 박스 */
    .log-box {
        background: #000000;
        border: 1px solid var(--terminal-border);
        border-radius: 0px;
        padding: 10px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.9rem;
        color: #cccccc;
        height: 250px;
        overflow-y: auto;
        line-height: 1.5;
        white-space: pre-wrap; /* 줄바꿈 보장 */
    }
    @keyframes log-yellow-blink {
        0% { opacity: 1; }
        50% { opacity: 0.4; }
        100% { opacity: 1; }
    }
    .log-latest {
        color: #ffcc00 !important;
        font-weight: bold;
        background: #1e1e0a !important; /* Subtle dark warm background */
        border-left: 3px solid #ffcc00;
        padding: 2px 8px;
        animation: log-yellow-blink 1.5s infinite ease-in-out;
    }

    /* 구분선 */
    hr { border-color: var(--terminal-border) !important; margin: 15px 0 !important; }

    /* Wall Street Metric Bar */
    .metric-bar-container {
        display: flex;
        justify-content: space-between;
        background: #050505;
        border: 1px solid var(--terminal-border);
        padding: 12px 0;
        margin-bottom: 20px;
    }
    .terminal-metric-item {
        flex: 1;
        border-right: 1px solid #1a1a1a;
        padding: 0 20px;
    }
    .terminal-metric-item:last-child { border-right: none; }
    .terminal-metric-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.9rem; /* 상향: 14px+ */
        color: #cccccc; /* Bright Grey */
        text-transform: uppercase;
        margin-bottom: 2px;
    }
    .terminal-metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.2rem;
        font-weight: 700;
        color: #fff;
        line-height: 1.1;
    }
    .terminal-metric-sub {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem; /* 상향 */
        margin-top: 2px;
        display: flex;
        align-items: center;
        gap: 2px;
    }

    /* 청산 버튼 특화 (상향 조정: 최소 14px 준수) */
    .small-btn-marker + div.stButton button,
    .small-btn-marker + div[data-testid="stButton"] button,
    div.small-btn-marker ~ div.stButton button {
        font-size: 14px !important; /* 최소 14px */
        height: 26px !important;
        min-height: 26px !important;
        line-height: 1 !important;
        padding: 0 8px !important;
        border-color: var(--terminal-red) !important;
        color: var(--terminal-red) !important;
        border-radius: 0px !important;
        background: transparent !important;
        margin-top: -12px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    .small-btn-marker + div.stButton button:hover,
    .small-btn-marker + div[data-testid="stButton"] button:hover {
        background: var(--terminal-red) !important;
        color: white !important;
    }

    /* 깜빡임 애니메이션 (터미널 스타일) */
    @keyframes terminal-blink {
        0% { opacity: 1; }
        50% { opacity: 0.4; }
        100% { opacity: 1; }
    }
    .badge-pink-blink, .badge-green-blink, .badge-red-blink {
        border-radius: 0px !important;
        animation: terminal-blink 1s infinite steps(1);
    }
    /* Streamlit Metric Delta Color Override (Profit: Red, Loss: Blue) */
    [data-testid="stMetricDelta"] > div {
        color: #ef4444 !important;
    }
    [data-testid="stMetricDelta"] > div:has(svg[data-testid="stMetricDeltaIconDown"]) {
        color: #3b82f6 !important;
    }
    /* Fallback for browsers not supporting :has */
    [data-testid="stMetricDelta"] > div[style*="color: rgb(9, 171,  green)"],
    [data-testid="stMetricDelta"] > div[style*="color: #09ab3b"] {
        color: #ef4444 !important;
    }
    [data-testid="stMetricDelta"] > div[style*="color: rgb(255, 43, 43)"],
    [data-testid="stMetricDelta"] > div[style*="color: #ff2b2b"] {
        color: #3b82f6 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)



# ── 세션 상태 초기화 ──────────────────────────────────

def init_session():
    engine = QuantumEngine.get_instance()
    
    # 만약 엔진이 이미 실행 중이라면 그 상태에 맞추어 세션 상태 초기화
    is_trading = True
    is_long = True
    is_short = True
    if engine.is_ready:
        is_trading = (engine.state == EngineState.TRADING)
        if engine.trader:
            is_long = engine.trader.allow_long
            is_short = engine.trader.allow_short

    defaults = {
        "engine": engine,
        "api_connected": engine.is_ready,
        "auto_trading": is_trading,
        "allow_long": is_long,
        "allow_short": is_short,
        "active_preset": "기본 (Stable)",
        "closing_symbols": set(), # [v1.2.52] 잔상 방지용 청산 대기 목록
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # .env 값이 있으면 UI 입력창 세션 상태 강제 초기화
    for state_key, env_keys in [("api_key_input", ["BINANCE_API_KEY", "OKX_API_KEY"]), 
                                ("secret_input", ["BINANCE_SECRET_KEY", "OKX_SECRET_KEY"]), 
                                ("pass_input", ["BINANCE_PASSPHRASE", "OKX_PASSPHRASE"])]:
        env_val = ""
        for k in env_keys:
            env_val = os.getenv(k, "")
            if env_val:
                break
        if env_val and (state_key not in st.session_state or not st.session_state[state_key]):
            st.session_state[state_key] = env_val

def connect_api(api_key, secret_key, passphrase):
    if not api_key or not secret_key:
        return False, "❌ API 키를 모두 입력해주세요."
    
    engine: QuantumEngine = st.session_state.engine
    success, msg = engine.initialize(api_key, secret_key, passphrase)
    
    if success:
        st.session_state.api_connected = True
        try:
            engine.sync_trades_to_csv()
        except Exception:
            pass
        return True, msg
    return False, msg

init_session()

# ── [v1.2.90] 파라미터 동기화 엔진 (Sidebar <-> Main Tab) ──
def sync_p(src_key: str, dst_key: str, cfg_attr: str, is_pct: bool = False):
    """위젯 간 값 동기화 및 CFG 반영 (콤마 구분 다중 목적지 지원)"""
    val = st.session_state[src_key]
    if isinstance(dst_key, str) and "," in dst_key:
        dst_keys = [k.strip() for k in dst_key.split(",") if k.strip()]
    elif isinstance(dst_key, (list, tuple)):
        dst_keys = dst_key
    else:
        dst_keys = [dst_key]

    for k in dst_keys:
        st.session_state[k] = val

    if is_pct:
        setattr(CFG, cfg_attr, val / 100.0)
    else:
        setattr(CFG, cfg_attr, val)

if not st.session_state.api_connected:
    ak = os.getenv("BINANCE_API_KEY") or os.getenv("OKX_API_KEY", "")
    sk = os.getenv("BINANCE_SECRET_KEY") or os.getenv("OKX_SECRET_KEY", "")
    pw = os.getenv("BINANCE_PASSPHRASE") or os.getenv("OKX_PASSPHRASE", "")
    if ak and sk:
        connect_api(ak, sk, pw)


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
        '<div class="quantum-logo" style="letter-spacing:-0.5px;" '
        'title="[AKMCD + SSL + RSI 하이브리드 전략]&#10;'
        '1. SSL 채널: 전체 추세 필터링 (파란선 위: 롱, 빨간선 아래: 숏)&#10;'
        '2. AKMCD 영선 돌파: 히스토그램이 영선(0) 위/아래인지 확인하여 진입 모멘텀 확인&#10;'
        '3. AKMCD 기울기(점 색상 전환): 이전 봉 대비 히스토그램 상승/하락에 따른 점 색깔 전환(초록/빨강)으로 타점 포착&#10;'
        '4. RSI 과열/과매도 필터: 과매수권 롱 제한(RSI < 60) 및 과매도권 숏 제한(RSI > 40)으로 추격 매매 노이즈 필터링">'
        '<span class="rainbow-text">AKMCD-SSL-RSI</span><br><span style="font-size:calc(0.75rem * 1.33);">v3.0.7</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown(
        '<p style="font-family:IBM Plex Mono;font-size:0.9rem;color:#cccccc;letter-spacing:0.08em;">API 연결 설정</p>',
        unsafe_allow_html=True,
    )

    api_key = st.text_input(
        "API Key", value=os.getenv("BINANCE_API_KEY") or os.getenv("OKX_API_KEY", ""), type="password", key="api_key_input"
    )
    secret_key = st.text_input(
        "Secret Key", value=os.getenv("BINANCE_SECRET_KEY") or os.getenv("OKX_SECRET_KEY", ""), type="password", key="secret_input"
    )
    passphrase = st.text_input(
        "Passphrase (Optional)", value=os.getenv("BINANCE_PASSPHRASE") or os.getenv("OKX_PASSPHRASE", ""), type="password", key="pass_input"
    )

    if st.button("🔗  Binance 연결", use_container_width=True):
        with st.spinner("연결 중..."):
            ak = api_key if api_key else (os.getenv("BINANCE_API_KEY") or os.getenv("OKX_API_KEY", ""))
            sk = secret_key if secret_key else (os.getenv("BINANCE_SECRET_KEY") or os.getenv("OKX_SECRET_KEY", ""))
            pw = passphrase if passphrase else (os.getenv("BINANCE_PASSPHRASE") or os.getenv("OKX_PASSPHRASE", ""))
            success, msg = connect_api(ak, sk, pw)
            if success:
                st.success(msg)
            else:
                st.error(msg)

    st.markdown("---")
    st.markdown(
        '<p style="font-family:IBM Plex Mono;font-size:0.9rem;color:#cccccc;letter-spacing:0.08em;">매매 제어</p>',
        unsafe_allow_html=True,
    )

    auto = st.toggle("자동매매 ON/OFF", value=st.session_state.auto_trading)
    longs = st.toggle("롱 포지션 허용", value=st.session_state.allow_long)
    shorts = st.toggle("숏 포지션 허용", value=st.session_state.allow_short)

    engine: QuantumEngine = st.session_state.engine
    
    if auto != st.session_state.auto_trading:
        st.session_state.auto_trading = auto
        if engine.is_ready:
            if auto:
                engine.enable_trading()
                engine.start_scanner()
            else:
                engine.disable_trading()
                engine.stop_scanner()

    # 자동매매 상태 동기화 및 강력 자동시작 보장 로직 (API 연결 후 즉시 스캔/매매 기동 보장)
    if engine.is_ready and st.session_state.auto_trading:
        if engine.trader and not engine.trader.enabled:
            engine.enable_trading()
        if engine.scanner and not engine.scanner.is_running:
            engine.start_scanner()

    if engine.is_ready and engine.trader:
        engine.trader.allow_long = longs
        engine.trader.allow_short = shorts

    # [v1.2.90] 인터랙티브 프로 트레이딩 컨트롤러 (동기화 로직 적용)
    st.markdown('<p style="font-family:\'JetBrains Mono\'; font-size:0.85rem; color:#ff9900; letter-spacing:0.05em; font-weight:700; margin-top:10px; margin-bottom:5px;">[ STRATEGY ENGINE ]</p>', unsafe_allow_html=True)
    
    with st.expander("📊 지표 및 스캐너 설정", expanded=False):
        st.number_input("SSL 기간", 2, 100, CFG.SSL_PERIOD, step=1, key="sb_ssl_period", 
                        on_change=sync_p, args=("sb_ssl_period", "main_ssl_period", "SSL_PERIOD"))
        # [v1.3.02] 타임프레임 원격 제어 추가
        tf_options = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
        st.selectbox("타임프레임", tf_options, index=tf_options.index(CFG.TIMEFRAME), key="sb_timeframe",
                     on_change=sync_p, args=("sb_timeframe", "main_timeframe", "TIMEFRAME"))
        col_bb1, col_bb2 = st.columns(2)
        with col_bb1:
            st.number_input("BB 기간", 5, 100, CFG.BB_PERIOD, key="sb_bb_period",
                            on_change=sync_p, args=("sb_bb_period", "main_bb_period", "BB_PERIOD"))
        with col_bb2:
            st.number_input("BB 편차", 1.0, 5.0, CFG.BB_STD, step=0.1, key="sb_bb_std",
                            on_change=sync_p, args=("sb_bb_std", "main_bb_std", "BB_STD"))
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.number_input("MACD 단기", 5, 50, CFG.MACD_FAST, key="sb_macd_fast",
                            on_change=sync_p, args=("sb_macd_fast", "main_macd_fast", "MACD_FAST"))
        with col_m2:
            st.number_input("MACD 장기", 10, 100, CFG.MACD_SLOW, key="sb_macd_slow",
                            on_change=sync_p, args=("sb_macd_slow", "main_macd_slow", "MACD_SLOW"))
        with col_m3:
            st.number_input("MACD 시그널", 2, 20, CFG.MACD_SIGNAL, key="sb_macd_signal",
                            on_change=sync_p, args=("sb_macd_signal", "main_macd_signal", "MACD_SIGNAL"))

        st.markdown("---")
        st.markdown('<p style="font-family:\'JetBrains Mono\'; font-size:0.8rem; color:#ff9900; margin-bottom:5px;">RSI 필터 설정</p>', unsafe_allow_html=True)
        st.number_input("RSI 기간", 2, 100, CFG.RSI_PERIOD, step=1, key="sb_rsi_period",
                        on_change=sync_p, args=("sb_rsi_period", "main_rsi_period,settings_rsi_period", "RSI_PERIOD"))
        col_rsi1, col_rsi2 = st.columns(2)
        with col_rsi1:
            st.number_input("RSI 롱 상한선", 10.0, 90.0, float(CFG.RSI_OVERBOUGHT), step=1.0, key="sb_rsi_overbought",
                            on_change=sync_p, args=("sb_rsi_overbought", "main_rsi_overbought,settings_rsi_overbought", "RSI_OVERBOUGHT"))
        with col_rsi2:
            st.number_input("RSI 숏 하한선", 10.0, 90.0, float(CFG.RSI_OVERSOLD), step=1.0, key="sb_rsi_oversold",
                            on_change=sync_p, args=("sb_rsi_oversold", "main_rsi_oversold,settings_rsi_oversold", "RSI_OVERSOLD"))

    with st.expander("⚡ 운용 및 포지션 설정", expanded=True):
        st.number_input("레버리지 (x)", 1, 20, CFG.LEVERAGE, step=1, key="sb_leverage",
                        on_change=sync_p, args=("sb_leverage", "main_leverage", "LEVERAGE"))
        st.number_input("1회 진입 증거금 (USDT)", 1.0, 100.0, CFG.MARGIN_USDT, step=0.5, key="sb_margin",
                        on_change=sync_p, args=("sb_margin", "main_margin", "MARGIN_USDT"))
        st.number_input("최대 동시 포지션 수", 1, 10, CFG.MAX_POSITIONS, step=1, key="sb_max_pos",
                        on_change=sync_p, args=("sb_max_pos", "main_max_pos", "MAX_POSITIONS"))

    with st.expander("🛡️ 리스크 및 한도 설정", expanded=True):
        st.number_input("익절 (%)", 0.1, 20.0, float(CFG.TAKE_PROFIT_PCT * 100), step=0.1, key="sb_tp",
                        on_change=sync_p, args=("sb_tp", "main_tp", "TAKE_PROFIT_PCT", True))
        st.number_input("손절 (%)", 0.1, 10.0, float(CFG.STOP_LOSS_PCT * 100), step=0.1, key="sb_sl",
                        on_change=sync_p, args=("sb_sl", "main_sl", "STOP_LOSS_PCT", True))

# ══════════════════════════════════════════════════════
# 메인 헤더 (한 줄 배치)
# ══════════════════════════════════════════════════════

# [v3.0.4] 시간, 상태, 버튼을 우측에 동일한 크기의 버튼 스타일로 나란히 배치
col_empty, col_time, col_status, col_refresh = st.columns([4.0, 2.0, 2.0, 2.0])

with col_time:
    now_kst = datetime.utcnow() + timedelta(hours=9)
    st.markdown(
        f'<div class="header-btn-like">'
        f'{now_kst.strftime("%Y-%m-%d %H:%M:%S")} KST</div>',
        unsafe_allow_html=True,
    )

with col_status:
    if st.session_state.auto_trading:
        st.markdown(
            '<div class="header-btn-like header-badge-live">'
            '<span class="dot"></span>LIVE CONNECTION</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="header-btn-like header-badge-stopped">'
            '<span class="dot"></span>STOPPED</div>',
            unsafe_allow_html=True,
        )

with col_refresh:
    if st.button("⟳ REFRESH", key="global_refresh", use_container_width=True):
        st.rerun()


st.markdown('<hr style="margin: 8px 0 16px;">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# 탭 구성
# ══════════════════════════════════════════════════════

tabs = st.tabs([
    "📊  대시보드",
    "🔍  스캐너",
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
        st.info("사이드바에서 Binance API를 연결하세요.")
    else:
        # ── 데이터 통합 조회 ──────────────────────────
        dash = engine.get_dashboard_data()
        if not dash:
            dash = {
                "total_balance": 0.0,
                "free_margin": 0.0,
                "used_margin": 0.0,
                "realized_pnl": 0.0,
                "positions": [],
                "is_scanning": False,
                "is_trading": False,
                "engine_state": "ERROR",
            }
            st.warning("⚠️ 거래소 API 연결이 끊겼거나 응답하지 않아 실시간 잔고를 불러올 수 없습니다.")
            if hasattr(engine, '_error_msg') and engine._error_msg:
                st.error(f"오류 상세: {engine._error_msg}")
        raw_positions = dash.get("positions", [])
        
        # [v1.2.52] 포지션 데이터 취득 및 잔상 방지 필터링
        # 1. 수량이 0이거나 먼지 잔고($0.1 미만)인 경우 원천 차단
        # 2. 방금 청산 버튼을 누른 종목(closing_symbols) 즉시 은폐 로직
        positions = [
            p for p in raw_positions 
            if p.get('amount_usdt', 0) > 0.1 
            and p.get('symbol') not in st.session_state.closing_symbols
        ]
        
        # 3. 거래소 데이터와 동기화: 거래소에서 실제로 사라진 종목은 은폐 목록에서 제거
        current_exchange_symbols = {p['symbol'] for p in raw_positions}
        st.session_state.closing_symbols = {
            s for s in st.session_state.closing_symbols if s in current_exchange_symbols
        }

        # ── 상단 지표 (Custom Terminal Metrics) ──────────────────────────────
        m1, m2, m3, m4, m5 = st.columns(5)
        
        def render_terminal_metric(label, value, delta=None, is_pnl=False):
            if is_pnl:
                val_num = float(str(value).replace('$','').replace(',','').replace('+',''))
                color = "#ef4444" if val_num >= 0 else "#3b82f6"
            else:
                color = "#ffffff" # 일반 지표는 중립 색상(White) 적용
            
            delta_html = ""
            if delta is not None:
                d_num = float(str(delta).replace('$','').replace(',','').replace('+',''))
                d_color = "#ef4444" if d_num >= 0 else "#3b82f6"
                delta_html = f'<div style="color:{d_color}; font-size:0.9rem; margin-top:2px;">{delta}</div>'
                
            st.markdown(
                f"""
                <div style="background:#0f0f0f; border:1px solid #262626; padding:12px; border-radius:0px; height:105px;">
                    <div style="color:#cccccc; font-size:0.9rem; font-family:\'JetBrains Mono\'; text-transform:uppercase; letter-spacing:0.05em;">{label}</div>
                    <div style="color:{color}; font-size:1.46rem; font-family:\'JetBrains Mono\'; font-weight:700; margin-top:4px;">{value}</div>
                    {delta_html}
                </div>
                """,
                unsafe_allow_html=True
            )

        with m1:
            render_terminal_metric("💰 총 잔고 (USDT)", f"${dash['total_balance']:,.2f}")
        with m2:
            total_upnl = sum(p["pnl_usdt"] for p in positions)
            render_terminal_metric("미실현 손익", f"${total_upnl:+.2f}", delta=f"{total_upnl:+.2f}", is_pnl=True)
        with m3:
            dpnl = engine.trader.daily_pnl_usdt if engine.trader else 0.0
            render_terminal_metric("금일 실현 손익", f"${dpnl:+.2f}", delta=f"{dpnl:+.2f}", is_pnl=True)
        with m4:
            render_terminal_metric("사용 중 증거금", f"${dash['used_margin']:,.2f}")
        with m5:
            render_terminal_metric("가용 증거금", f"${dash['free_margin']:,.2f}")

        st.markdown("---")

        # ── 포지션 / 로그 ──────────────────────────
        col_pos, col_log = st.columns([1.2, 1])

        with col_pos:
            col_title, col_bulk = st.columns([1, 1])
            with col_title:
                st.markdown(
                    '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.9rem;color:#cccccc;letter-spacing:0.1em;">ACTIVE POSITIONS</p>',
                    unsafe_allow_html=True,
                )
            with col_bulk:
                if positions:
                    st.markdown('<div class="small-btn-marker"></div>', unsafe_allow_html=True)
                    if st.button("🔴 모든 종목 일괄청산", use_container_width=True, key="bulk_close"):
                        count = engine.client.close_all_positions()
                        if count > 0:
                            st.toast(f"✅ {count}개 포지션 일괄 청산 완료")
                            time.sleep(1)
                            st.rerun()

            pos_placeholder = st.empty()
            with pos_placeholder.container():
                if not positions:
                    st.markdown(
                        '<p style="color:#444;font-family:\'IBM Plex Mono\',monospace;font-size:0.8rem;">포지션 없음</p>',
                        unsafe_allow_html=True,
                    )
                else:
                    for p in positions:
                        pnl_color = "#ef4444" if p["pnl_usdt"] >= 0 else "#3b82f6"
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
                                    <span style="font-family:'IBM Plex Mono';font-size:0.95rem;font-weight:600;">{p['symbol']}</span>
                                    <span style="font-family:'IBM Plex Mono';font-size:0.95rem;font-weight:600;color:{pnl_color};">
                                      {p['pnl_usdt']:+.4f} USDT ({p['pnl_pct']:+.1f}%)
                                    </span>
                                  </div>
                                  <div style="font-family:'IBM Plex Mono';font-size:0.9rem;color:#cccccc;display:flex;gap:16px;">
                                    <span>{side_badge}</span>
                                    <span>진입가 ${p['entry_price']:,.4f}</span>
                                    <span>현재가 ${p['mark_price']:,.4f}</span>
                                    <span>{p['leverage']}x LEV</span>
                                    <span>Amount ${p['amount_usdt']:,.2f}</span>
                                  </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        with pc2:
                            # 경과 시간 계산 및 스타일 결정
                            duration_str = "[00시간 00분]"
                            duration_style = "font-family:'JetBrains Mono'; font-size:0.98rem; color:#cccccc; text-align:center; margin-bottom:0px;"
                            
                            if p.get("timestamp"):
                                import datetime as dt_mod
                                entry_dt = dt_mod.datetime.fromtimestamp(p["timestamp"] / 1000, tz=dt_mod.timezone.utc)
                                diff = dt_mod.datetime.now(dt_mod.timezone.utc) - entry_dt
                                hrs, rem = divmod(int(diff.total_seconds()), 3600)
                                mins = rem // 60
                                duration_str = f"[{hrs:02d}시간 {mins:02d}분]"
                                
                                if hrs >= 3:
                                    duration_style = "font-family:'JetBrains Mono'; font-size:0.98rem; color:white; background:#ff3b30; text-align:center; margin-bottom:0px; font-weight:700;"
                                
                            st.markdown(
                                f'<div style="{duration_style}">{duration_str}</div>',
                                unsafe_allow_html=True
                            )
                            st.markdown('<div class="small-btn-marker"></div>', unsafe_allow_html=True)
                            if st.button("즉시청산", key=f"close_{p['symbol']}", use_container_width=True):
                                # [v1.2.52] 버튼 클릭 즉시 세션 캐시에 추가하여 화면에서 지움
                                st.session_state.closing_symbols.add(p['symbol'])
                                if engine.client.close_position(p["symbol"], p["side"]):
                                    st.toast(f"✅ {p['symbol']} 청산 완료")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    # 실패 시에는 다시 목록에서 제거 (보여줘야 하므로)
                                    st.session_state.closing_symbols.discard(p['symbol'])
                                    st.error(f"❌ {p['symbol']} 청산 실패")


        with col_log:
            st.markdown(
                '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.9rem;color:#cccccc;letter-spacing:0.1em;">SYSTEM LOG</p>',
                unsafe_allow_html=True,
            )
            engine: QuantumEngine = st.session_state.engine
            logs = engine.scanner.get_logs(30) if engine.scanner else ["[SYS] 엔진 미연결"]
            
            if logs:
                # 최신 로그(마지막 요소)에 특수 스타일 적용
                latest_line = f'<div class="log-latest" style="margin-bottom:4px;">{logs[-1]}</div>'
                other_lines = "".join([f'<div style="margin-bottom:4px; border-bottom:1px solid #1a1a1a;">{log}</div>' for log in reversed(logs[:-1])])
                log_html = f"{latest_line}{other_lines}"
            else:
                log_html = "로그 없음"

            st.markdown(
                f'<div class="log-box">{log_html}</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # ── 고밀도 터미널 메트릭 바 (Image 1 Style) ──────────
        _st = stats_store.load_stats()
        
        # 데이터 계산
        total_pnl = _st.get("total_pnl_usdt", 0.0)
        daily_pnl = _st.get("daily_pnl_usdt", 0.0)
        
        # [v1.2.37] 수익률 계산 기준 업데이트 (stats.json 로드)
        seed_money = _st.get("seed_money", 30.0) # 기준 자산 (동적 로드)
        total_pnl_pct = ((dash['total_balance'] / seed_money) - 1) * 100 if seed_money > 0 else 0.0
        # 24시간 변동률도 시드 대비 비율로 표시
        daily_pnl_pct = (daily_pnl / seed_money) * 100 if seed_money > 0 else 0.0
        
        # [v1.2.40] 일 평균 수익률 계산 보정 (최소 1일 기준 - 뻥튀기 방지)
        perf_start_str = _st.get("perf_start_time", "2026-05-15 00:00:00")
        try:
            perf_start_dt = datetime.strptime(perf_start_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            perf_start_dt = datetime(2026, 5, 15, 0, 0, 0)
            
        now_kst = datetime.utcnow() + timedelta(hours=9)
        elapsed_seconds = (now_kst - perf_start_dt).total_seconds()
        # 경과 일수 계산 (보수적 접근: 최소 1.0일로 나누어 첫날 과장 방지)
        elapsed_days = max(elapsed_seconds / 86400.0, 1.0)
        daily_avg_roi = total_pnl_pct / elapsed_days
        
        # [v1.2.44] 매매 이력 기반 실시간 승률 계산 (분할 체결 통합 로직)
        all_trades = engine.get_trade_history(limit=100)
        
        # 성과 측정 시작 시각(perf_start_dt) 이후의 '청산' 거래만 필터링
        today_exits = []
        for t in all_trades:
            if t.get('category') == '청산':
                t_time = t.get('timestamp')
                if isinstance(t_time, datetime):
                    t_time_naive = t_time.replace(tzinfo=None)
                    if t_time_naive >= perf_start_dt:
                        today_exits.append(t)
                else:
                    try:
                        t_dt = pd.to_datetime(t_time).replace(tzinfo=None)
                        if t_dt >= perf_start_dt:
                            today_exits.append(t)
                    except Exception:
                        pass
        
        # 주문 번호(order_id)별로 그룹화하여 분할 체결 건을 1건으로 통합
        order_results = {}
        for t in today_exits:
            oid = t.get('order_id')
            if oid:
                if oid not in order_results:
                    order_results[oid] = 0.0
                order_results[oid] += float(t.get('pnl', 0))
        
        # 통합된 주문별 손익 결과로 승/패 카운트
        wins = len([pnl for pnl in order_results.values() if pnl > 0])
        losses = len([pnl for pnl in order_results.values() if pnl < 0])
        total_exits = wins + losses
        win_rate = (wins / total_exits * 100) if total_exits > 0 else 0.0
        
        # [v1.2.46] 금일 주문 건수를 오늘 완료된 청산(Exit) 거래 수로 한정하여 지표 통일
        orders_today = total_exits
        
        # 수익률 색상 결정 (수익: 빨강, 손실: 파랑)
        total_color = "#ef4444" if total_pnl_pct >= 0 else "#3b82f6"
        daily_color = "#ef4444" if daily_pnl >= 0 else "#3b82f6"
        avg_color = "#ef4444" if daily_avg_roi >= 0 else "#3b82f6"
        win_color = "#ef4444" if win_rate > 50.0 else "#3b82f6"
        
        daily_arrow = "↑" if daily_pnl >= 0 else "↓"
        total_arrow = "↑" if total_pnl_pct >= 0 else "↓"
        avg_arrow = "↑" if daily_avg_roi >= 0 else "↓"
        win_arrow = "↑" if win_rate > 50.0 else "↓"
        
        st.markdown(
            f"""
            <div class="metric-bar-container">
                <!-- 누적 수익률 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label" title="초기화 시점의 총 잔고: {seed_money:,.2f} USDT">누적 수익률</div>
                    <div class="terminal-metric-value" style="color:{total_color};">{total_pnl_pct:+.2f}%</div>
                    <div class="terminal-metric-sub" style="color:#ffffff;">
                        <span>{daily_arrow}</span> {abs(daily_pnl_pct):.2f}% (24h)
                    </div>
                </div>
                <!-- 일 평균 수익률 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label">일 평균 수익률</div>
                    <div class="terminal-metric-value" style="color:{avg_color};">{daily_avg_roi:+.2f}%</div>
                    <div class="terminal-metric-sub" style="color:#cccccc;">
                        {avg_arrow} {perf_start_dt.strftime("%Y.%m.%d %H:%M")} ~
                    </div>
                </div>
                <!-- 누적 승률 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label">누적 승률</div>
                    <div class="terminal-metric-value" style="color:{win_color};">{win_rate:.1f}%</div>
                    <div class="terminal-metric-sub" style="color:#cccccc;">
                        <span style="font-size:0.7rem;">{win_arrow}</span> {wins}W / {losses}L
                    </div>
                </div>
                <!-- MDD 한도 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label">MDD 한도</div>
                    <div class="terminal-metric-value" style="color:#cccccc;">-{CFG.MAX_DRAWDOWN_PCT*100:.0f}%</div>
                    <div class="terminal-metric-sub" style="color:#cccccc;">
                        <span style="font-size:0.7rem;">↓</span> Max Risk
                    </div>
                </div>
                <!-- 금일 주문 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label">금일 주문</div>
                    <div class="terminal-metric-value">{orders_today}건</div>
                    <div class="terminal-metric-sub" style="color:#ffffff;">
                        <span style="font-size:0.7rem;">↑</span> Today
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # [v1.4.11] 누적 데이터 및 통계 초기화 긴 버튼 추가
        if st.button("📊  수익율,승률 초기화", use_container_width=True, key="dashboard_stats_reset",
                     help="이 버튼을 누르면 지금까지 쌓인 누적 수익률, 승률(W/L), 주문 횟수 등 모든 성적표가 싹 다 0으로 리셋됩니다. 현재 총 잔고를 새로운 '시드 머니'로 잡고 현재 시각부터 기록을 시작합니다."):
            d_data = engine.get_dashboard_data()
            current_bal = d_data.get("total_balance", 30.0)
            if current_bal <= 0:
                current_bal = 30.0
            stats_store.reset_stats(current_bal)
            if engine and engine.trader:
                engine.trader.daily_pnl_usdt = 0.0
                engine.trader.orders_today = 0
            st.toast("✅ 모든 누적 통계 데이터가 현재 시각 및 총 잔고 기준으로 초기화되었습니다.")
            time.sleep(0.5)
            st.rerun()



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 2: 스캐너
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[1]:
    engine: QuantumEngine = st.session_state.engine

    if not st.session_state.api_connected or not engine.is_ready:
        st.info("사이드바에서 Binance API를 연결하세요.")
    else:
        # 상태 배지 및 마지막 스캔 시각 표시 영역
        last = engine.scanner.last_scan_time if engine.scanner else None
        last_scan_str = f"마지막 스캔: {last.strftime('%H:%M:%S')}" if last else "마지막 스캔: 대기 중"
        
        c_status, c_time = st.columns([2, 1])
        with c_status:
            if engine.scanner and engine.scanner.is_running:
                preset = st.session_state.active_preset
                badge_class = "badge-green-blink"
                if "1차" in preset:
                    badge_class = "badge-pink-blink"
                elif "2차" in preset:
                    badge_class = "badge-red-blink"
                    
                st.markdown(
                    f'<div class="{badge_class}">📡 {preset} 스캐너 백그라운드 가동 중</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    '<p style="color:#666;font-family:\'IBM Plex Mono\',monospace;font-size:0.9rem;margin-top:5px;">⏹ 스캐너 중지 상태 (자동매매 ON 시 시작)</p>',
                    unsafe_allow_html=True
                )
        with c_time:
            st.markdown(
                f'<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.85rem;color:#888;text-align:right;margin-top:5px;">{last_scan_str}</p>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='margin-bottom:15px;'></div>", unsafe_allow_html=True)
        
        results = engine.get_scan_results()

        if results:
            df_scan = pd.DataFrame(results)

            # 신호 필터
            signal_filter = st.selectbox(
                "신호 필터",
                ["전체", "LONG 신호", "SHORT 신호", "신호 없음"],
                label_visibility="collapsed",
                key="scanner_signal_filter"
            )
            if signal_filter == "LONG 신호":
                df_scan = df_scan[df_scan["signal"] == "long"]
            elif signal_filter == "SHORT 신호":
                df_scan = df_scan[df_scan["signal"] == "short"]
            elif signal_filter == "신호 없음":
                df_scan = df_scan[df_scan["signal"] == "none"]

            # 표시용 포맷
            display = df_scan[["symbol","price","change_pct","volume_m","signal","strength","ema_ok","macd_ok","bb_ok","rsi_ok","rsi"]].copy()
            display.columns = ["종목","현재가","등락(%)","거래대금(M)","신호","강도(%)","SSL 추세","AKMCD 영선","AKMCD 점전환","RSI 필터","RSI 수치"]
            display["신호"] = display["신호"].map({"long":"🟢 LONG","short":"🔴 SHORT","none":"— "})
            display["SSL 추세"] = display["SSL 추세"].map({True:"✅",False:"❌"})
            display["AKMCD 영선"] = display["AKMCD 영선"].map({True:"✅",False:"❌"})
            display["AKMCD 점전환"] = display["AKMCD 점전환"].map({True:"✅",False:"❌"})
            display["RSI 필터"] = display["RSI 필터"].map({True:"✅",False:"❌"})

            def style_pnl(val):
                color = '#ef4444' if val >= 0 else '#3b82f6'
                return f'color: {color}; font-weight: bold;'

            st.dataframe(
                display.style.map(style_pnl, subset=["등락(%)"]),
                use_container_width=True,
                height=500,
                hide_index=True,
            )
        else:
            st.markdown(
                '<p style="color:#555;font-family:\'IBM Plex Mono\',monospace;">스캔 결과 없음 — 자동매매가 시작되면 결과가 이곳에 표시됩니다.</p>',
                unsafe_allow_html=True,
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB 3: 매매 이력
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[2]:
    engine: QuantumEngine = st.session_state.engine

    # [v2.0.8] 로컬 CSV 이력 로드 및 진입/청산 페어링 (API 미연결 시에도 로컬 이력 항시 조회 허용)
    raw_trades = load_local_trade_history()
    paired_history = aggregate_and_pair_trades(raw_trades)

    # 동적 종목 필터 리스트 구성
    history_symbols = sorted(list(set([x["symbol"] for x in paired_history])))

    h1, h2 = st.columns([2, 1])
    with h1:
        hist_symbol = st.selectbox("종목 필터", ["전체"] + history_symbols, key="hist_sym")
    with h2:
        sync_disabled = not st.session_state.api_connected or not engine.is_ready
        help_msg = "실시간 거래소 이력을 반영하려면 사이드바에서 API를 연결하세요." if sync_disabled else "거래소에서 최근 100개 체결 이력을 받아와 로컬 CSV로 동기화합니다."
        if st.button("🔄  이력 새로고침", use_container_width=True, disabled=sync_disabled, help=help_msg):
            try:
                engine.sync_trades_to_csv()
            except Exception:
                pass
            st.rerun()

    # 필터링 적용
    if hist_symbol != "전체":
        paired_history = [x for x in paired_history if x["symbol"] == hist_symbol]

    if paired_history:
        df_hist = pd.DataFrame(paired_history)
        
        # 시간 형식 변환 및 예외 처리
        df_hist["entry_time"] = df_hist["entry_time"].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if pd.notnull(x) else "-")
        df_hist["exit_time"] = df_hist["exit_time"].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if pd.notnull(x) else "-")
        
        # 컬럼 재구성 및 한글화
        df_hist = df_hist[[
            "entry_time", "exit_time", "symbol", "direction", 
            "entry_price", "exit_price", "amount", "pnl_usdt", "pnl_pct", "status"
        ]]
        df_hist.columns = [
            "진입시각", "청산시각", "종목", "포지션", 
            "진입가", "청산가", "수량", "손익 (USDT)", "수익률 (%)", "상태"
        ]

        def style_history(row):
            styles = [''] * len(row)
            status = row["상태"]
            pnl_val = row["손익 (USDT)"]
            
            if status == "보유 중":
                # 보유 중인 행은 노란색 bold 강조
                for i in range(len(styles)):
                    styles[i] = 'color: #ffcc00; font-weight: bold;'
            else:
                if pd.notnull(pnl_val):
                    # 실현 손익 색상 입히기 (수익 빨강, 손실 파랑)
                    color = '#ef4444' if pnl_val >= 0 else '#3b82f6'
                    styles[7] = f'color: {color}; font-weight: bold;'
                    styles[8] = f'color: {color}; font-weight: bold;'
            return styles

        st.dataframe(
            df_hist.style.apply(style_history, axis=1).format({
                "진입가": lambda x: f"{x:,.4f}" if pd.notnull(x) and isinstance(x, (int, float)) else "-",
                "청산가": lambda x: f"{x:,.4f}" if pd.notnull(x) and isinstance(x, (int, float)) else "-",
                "수량": "{:,.4f}",
                "손익 (USDT)": lambda x: f"{x:+,.4f}" if pd.notnull(x) and isinstance(x, (int, float)) else "-",
                "수익률 (%)": lambda x: f"{x:+,.2f}%" if pd.notnull(x) and isinstance(x, (int, float)) else "-"
            }),
            use_container_width=True,
            hide_index=True,
            height=550
        )
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


# TAB 4: 포지션 진입
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[3]:
    st.markdown(
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.9rem;color:#cccccc;letter-spacing:0.1em;">ENTRY CONDITIONS</p>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🟢 LONG 포지션 진입 조건**")
        st.markdown(
            """
            <div style="background:#0f0f0f; border:1px solid #444; padding:15px; margin-top:5px; margin-bottom:15px; border-radius:5px;">
                <p style="font-family:'Inter'; font-size:1.25rem; color:#ffcc00; margin:0; line-height:1.5; text-align:center; font-weight:600;">
                "🌊 큰 파도(SSL)가 위에서 밀어주고, 🟢 AKMCD 점이 상승 전환되었으며, 🚀 히스토그램 강도마저 양수로 돌파하고, 🔵 캔들마저 양봉(Blue)일 때 롱 진입합니다!"
                </p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        st.markdown("- **추세:** 현재 종가가 SSL 파란선(ssl_up) 위 <span style='color:#ffcc00;'>☞ 대세 상승 추세인지 확인합니다.</span>", unsafe_allow_html=True)
        st.markdown("- **반전:** AKMCD 도트 색상이 빨간색에서 초록색으로 변경 <span style='color:#ffcc00;'>☞ 단기 모멘텀이 상승으로 전환되었음을 의미합니다.</span>", unsafe_allow_html=True)
        st.markdown("- **모멘텀:** MACD 히스토그램이 영선(0) 위 <span style='color:#ffcc00;'>☞ MACD가 시그널 선보다 높게 있어 힘이 실렸음을 나타냅니다.</span>", unsafe_allow_html=True)
        st.markdown("- **캔들:** 현재 봉의 종가가 직전 봉의 종가보다 높은 양봉(Blue) <span style='color:#ffcc00;'>☞ 실시간 매수세가 우위임을 확인합니다.</span>", unsafe_allow_html=True)

    with c2:
        st.markdown("**🔴 SHORT 포지션 진입 조건**")
        st.markdown(
            """
            <div style="background:#0f0f0f; border:1px solid #444; padding:15px; margin-top:5px; margin-bottom:15px; border-radius:5px;">
                <p style="font-family:'Inter'; font-size:1.25rem; color:#ffcc00; margin:0; line-height:1.5; text-align:center; font-weight:600;">
                "📉 내리막길(SSL) 경사가 가파르고, 🔴 AKMCD 점이 하락 전환되었으며, 🌬 히스토그램 강도마저 음수로 떨어지고, 🔴 캔들마저 음봉(Red)일 때 숏 진입합니다!"
                </p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        st.markdown("- **추세:** 현재 종가가 SSL 빨간선(ssl_down) 아래 <span style='color:#ffcc00;'>☞ 대세 하락 추세인지 확인합니다.</span>", unsafe_allow_html=True)
        st.markdown("- **반전:** AKMCD 도트 색상이 초록색에서 빨간색으로 변경 <span style='color:#ffcc00;'>☞ 단기 모멘텀이 하락으로 전환되었음을 의미합니다.</span>", unsafe_allow_html=True)
        st.markdown("- **모멘텀:** MACD 히스토그램이 영선(0) 아래 <span style='color:#ffcc00;'>☞ MACD가 시그널 선보다 낮게 있어 낙폭이 예상됨을 나타냅니다.</span>", unsafe_allow_html=True)
        st.markdown("- **캔들:** 현재 봉의 종가가 직전 봉의 종가 이하인 음봉(Red) <span style='color:#ffcc00;'>☞ 실시간 매도세가 우위임을 확인합니다.</span>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">INDICATOR PARAMETERS & PRESETS</p>',
        unsafe_allow_html=True,
    )

    # 프리셋 정의
    PRESETS = {
        "기본 (Stable)": {
            "ssl_p": 10, "bb_p": 20, "bb_s": 2.0, "macd_f": 12, "macd_sl": 26, "macd_si": 9,
            "rsi_p": 14, "rsi_ob": 60.0, "rsi_os": 40.0
        },
        "1차 공격적 (Trend)": {
            "ssl_p": 8, "bb_p": 20, "bb_s": 1.8, "macd_f": 10, "macd_sl": 22, "macd_si": 7,
            "rsi_p": 14, "rsi_ob": 65.0, "rsi_os": 35.0
        },
        "2차 공격적 (Scalping)": {
            "ssl_p": 6, "bb_p": 14, "bb_s": 1.5, "macd_f": 8, "macd_sl": 18, "macd_si": 5,
            "rsi_p": 14, "rsi_ob": 70.0, "rsi_os": 30.0
        }
    }

    preset_name = st.selectbox("전략 프리셋 선택", list(PRESETS.keys()), index=0)
    
    if st.button("🪄 프리셋 적용"):
        p = PRESETS[preset_name]
        st.session_state.active_preset = preset_name
        CFG.SSL_PERIOD = p["ssl_p"]
        CFG.BB_PERIOD = p["bb_p"]
        CFG.BB_STD = p["bb_s"]
        CFG.MACD_FAST = p["macd_f"]
        CFG.MACD_SLOW = p["macd_sl"]
        CFG.MACD_SIGNAL = p["macd_si"]
        CFG.RSI_PERIOD = p.get("rsi_p", 14)
        CFG.RSI_OVERBOUGHT = p.get("rsi_ob", 60.0)
        CFG.RSI_OVERSOLD = p.get("rsi_os", 40.0)
        
        # 세션 상태 위젯 키들도 명시적 업데이트
        st.session_state.sb_ssl_period = p["ssl_p"]
        st.session_state.main_ssl_period = p["ssl_p"]
        st.session_state.sb_bb_period = p["bb_p"]
        st.session_state.main_bb_period = p["bb_p"]
        st.session_state.sb_bb_std = p["bb_s"]
        st.session_state.main_bb_std = p["bb_s"]
        st.session_state.sb_macd_fast = p["macd_f"]
        st.session_state.main_macd_fast = p["macd_f"]
        st.session_state.sb_macd_slow = p["macd_sl"]
        st.session_state.main_macd_slow = p["macd_sl"]
        st.session_state.sb_macd_signal = p["macd_si"]
        st.session_state.main_macd_signal = p["macd_si"]
        st.session_state.sb_rsi_period = p.get("rsi_p", 14)
        st.session_state.main_rsi_period = p.get("rsi_p", 14)
        st.session_state.settings_rsi_period = p.get("rsi_p", 14)
        st.session_state.sb_rsi_overbought = p.get("rsi_ob", 60.0)
        st.session_state.main_rsi_overbought = p.get("rsi_ob", 60.0)
        st.session_state.settings_rsi_overbought = p.get("rsi_ob", 60.0)
        st.session_state.sb_rsi_oversold = p.get("rsi_os", 40.0)
        st.session_state.main_rsi_oversold = p.get("rsi_os", 40.0)
        st.session_state.settings_rsi_oversold = p.get("rsi_os", 40.0)

        st.toast(f"✅ {preset_name} 파라미터 적용됨")
        time.sleep(0.5)
        st.rerun()

    p1, p2, p3 = st.columns(3)
    with p1:
        st.number_input("SSL 기간", 2, 100, CFG.SSL_PERIOD, step=1, key="main_ssl_period",
                        on_change=sync_p, args=("main_ssl_period", "sb_ssl_period", "SSL_PERIOD"))
        # [v1.3.02] 타임프레임 원격 제어 추가
        tf_options = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
        st.selectbox("타임프레임", tf_options, index=tf_options.index(CFG.TIMEFRAME), key="main_timeframe",
                     on_change=sync_p, args=("main_timeframe", "sb_timeframe", "TIMEFRAME"))
        st.number_input("RSI 기간", 2, 100, CFG.RSI_PERIOD, step=1, key="main_rsi_period",
                        on_change=sync_p, args=("main_rsi_period", "sb_rsi_period,settings_rsi_period", "RSI_PERIOD"))
    with p2:
        st.number_input("BB 기간", 5, 100, CFG.BB_PERIOD, step=5, key="main_bb_period",
                        on_change=sync_p, args=("main_bb_period", "sb_bb_period", "BB_PERIOD"))
        st.number_input("BB 편차 (x)", 1.0, 5.0, float(CFG.BB_STD), step=0.1, key="main_bb_std",
                        on_change=sync_p, args=("main_bb_std", "sb_bb_std", "BB_STD"))
        st.number_input("RSI 롱 상한선", 10.0, 90.0, float(CFG.RSI_OVERBOUGHT), step=1.0, key="main_rsi_overbought",
                        on_change=sync_p, args=("main_rsi_overbought", "sb_rsi_overbought,settings_rsi_overbought", "RSI_OVERBOUGHT"))
    with p3:
        st.number_input("MACD 단기", 1, 50, CFG.MACD_FAST, step=1, key="main_macd_fast",
                        on_change=sync_p, args=("main_macd_fast", "sb_macd_fast", "MACD_FAST"))
        st.number_input("MACD 장기", 1, 100, CFG.MACD_SLOW, step=1, key="main_macd_slow",
                        on_change=sync_p, args=("main_macd_slow", "sb_macd_slow", "MACD_SLOW"))
        st.number_input("MACD 시그널", 1, 50, CFG.MACD_SIGNAL, step=1, key="main_macd_signal",
                        on_change=sync_p, args=("main_macd_signal", "sb_macd_signal", "MACD_SIGNAL"))
        st.number_input("RSI 숏 하한선", 10.0, 90.0, float(CFG.RSI_OVERSOLD), step=1.0, key="main_rsi_oversold",
                        on_change=sync_p, args=("main_rsi_oversold", "sb_rsi_oversold,settings_rsi_oversold", "RSI_OVERSOLD"))

# TAB 5: 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[4]:
    st.markdown(
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.9rem;color:#cccccc;letter-spacing:0.1em;">STRATEGY PARAMETERS</p>',
        unsafe_allow_html=True,
    )

    s1, s2 = st.columns(2)
    with s1:
        st.number_input("레버리지 (x)", 1, 20, CFG.LEVERAGE, step=1, key="main_leverage",
                        on_change=sync_p, args=("main_leverage", "sb_leverage", "LEVERAGE"))
        st.number_input("1회 진입 증거금 (USDT)", 1.0, 10000.0, float(CFG.MARGIN_USDT), step=1.0, key="main_margin",
                        on_change=sync_p, args=("main_margin", "sb_margin", "MARGIN_USDT"))
        st.number_input("최대 동시 포지션 수", 1, 10, CFG.MAX_POSITIONS, step=1, key="main_max_pos",
                        on_change=sync_p, args=("main_max_pos", "sb_max_pos", "MAX_POSITIONS"))
        st.number_input("*** 스캔 주기 (초)", 10, 300, CFG.SCAN_INTERVAL_SEC, step=10, key="main_scan_interval",
                        on_change=sync_p, args=("main_scan_interval", "sb_scan_interval", "SCAN_INTERVAL_SEC"))

    with s2:
        st.number_input("익절 (%)", 0.1, 20.0, float(CFG.TAKE_PROFIT_PCT * 100), step=0.1, key="main_tp",
                        on_change=sync_p, args=("main_tp", "sb_tp", "TAKE_PROFIT_PCT", True))
        st.number_input("손절 (%)", 0.1, 10.0, float(CFG.STOP_LOSS_PCT * 100), step=0.1, key="main_sl",
                        on_change=sync_p, args=("main_sl", "sb_sl", "STOP_LOSS_PCT", True))
        st.number_input("*** 최소 거래대금 (USDT)", 100000.0, 50000000.0, float(CFG.MIN_VOLUME_USDT), step=1000000.0, key="main_min_vol",
                        on_change=sync_p, args=("main_min_vol", "sb_min_vol", "MIN_VOLUME_USDT"))

    st.markdown("---")
    st.markdown(
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.75rem;color:#ff9900;letter-spacing:0.1em;margin-top:10px;">RSI FILTER PARAMETERS (AKMCD-SSL-RSI)</p>',
        unsafe_allow_html=True,
    )
    r1, r2, r3 = st.columns(3)
    with r1:
        st.number_input("RSI 기간", 2, 100, CFG.RSI_PERIOD, step=1, key="settings_rsi_period",
                        on_change=sync_p, args=("settings_rsi_period", "sb_rsi_period,main_rsi_period", "RSI_PERIOD"))
    with r2:
        st.number_input("RSI 롱 상한선", 10.0, 90.0, float(CFG.RSI_OVERBOUGHT), step=1.0, key="settings_rsi_overbought",
                        on_change=sync_p, args=("settings_rsi_overbought", "sb_rsi_overbought,main_rsi_overbought", "RSI_OVERBOUGHT"))
    with r3:
        st.number_input("RSI 숏 하한선", 10.0, 90.0, float(CFG.RSI_OVERSOLD), step=1.0, key="settings_rsi_oversold",
                        on_change=sync_p, args=("settings_rsi_oversold", "sb_rsi_oversold,main_rsi_oversold", "RSI_OVERSOLD"))

    st.markdown("---")
    st.markdown(
        f"""<div style="font-family:'IBM Plex Mono',monospace;font-size:0.92rem;color:#cccccc;line-height:2;">
        손익비: 1 : {CFG.TAKE_PROFIT_PCT / CFG.STOP_LOSS_PCT:.1f} &nbsp;|&nbsp;
        증거금/종목: ${CFG.MARGIN_USDT:.2f} USDT &nbsp;|&nbsp;
        최대 노출: ${CFG.MARGIN_USDT * CFG.LEVERAGE * CFG.MAX_POSITIONS:.2f} USDT <br>
        RSI 설정: 기간 {CFG.RSI_PERIOD} &nbsp;|&nbsp;
        롱 진입 상한: {CFG.RSI_OVERBOUGHT:.1f} &nbsp;|&nbsp;
        숏 진입 하한: {CFG.RSI_OVERSOLD:.1f}
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown(
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">SYSTEM UTILITIES</p>',
        unsafe_allow_html=True,
    )
    
    if st.button("📊  수익율,승률 초기화", use_container_width=True,
                 help="이 버튼을 누르면 지금까지 쌓인 누적 수익률, 승률(몇 번 이기고 졌는지), 주문 횟수 같은 모든 성적표가 싹 다 0으로 리셋돼요! 현재 잔고를 새로운 '원금'으로 잡고 처음부터 다시 기록을 시작해요. 한 번 누르면 되돌릴 수 없으니 신중하게!"):
        d_data = engine.get_dashboard_data()
        current_bal = d_data.get("total_balance", 30.0)
        if current_bal <= 0:
            current_bal = 30.0
        stats_store.reset_stats(current_bal)
        if engine and engine.trader:
            engine.trader.daily_pnl_usdt = 0.0
            engine.trader.orders_today = 0
        st.toast("✅ 누적 수익률, 승률, 주문수 등 모든 통계 데이터가 현재 시간 기준으로 초기화되었습니다.")
        time.sleep(0.5)
        st.rerun()


# ── 자동 새로고침 ─────────────────────────────────
if st.session_state.auto_trading:
    time.sleep(15)
    st.rerun()
