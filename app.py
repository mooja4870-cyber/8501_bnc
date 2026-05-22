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

# ── 앱 버전 (git tag와 동기화) ─────────────────────────
def get_git_tag():
    import subprocess
    try:
        tag = subprocess.check_output(["git", "describe", "--tags", "--always"], stderr=subprocess.DEVNULL).decode("utf-8").strip()
        if tag:
            return tag
    except Exception:
        pass
    return "v3.2.0" # Fallback 하드코딩

APP_VERSION = get_git_tag()

# ── 페이지 설정 ───────────────────────────────────────
st.set_page_config(
    page_title="AI QUANTUM · Binance Trader",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Wall Street Professional Terminal CSS ─────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;700&display=swap');
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

    :root {
        --terminal-bg: #030408;
        --terminal-surface: rgba(13, 17, 33, 0.45);
        --terminal-border: rgba(255, 255, 255, 0.08);
        --terminal-text: #e2e8f0;
        --terminal-dim: #718096;
        --terminal-accent: #00e0ff; /* 영롱한 아쿠아 블루 */
        --terminal-accent-glow: rgba(0, 224, 255, 0.15);
        --terminal-green: #10b981;
        --terminal-red: #ef4444;
        --glass-border: rgba(255, 255, 255, 0.06);
    }

    html, body, [data-testid="stAppViewContainer"] {
        background-color: var(--terminal-bg) !important;
        background-image: 
            /* 우상향 영롱한 글로우 (radial gradient at top right) */
            radial-gradient(circle at 90% 10%, rgba(139, 92, 246, 0.15) 0%, rgba(0, 224, 255, 0.08) 30%, rgba(244, 63, 94, 0.03) 60%, transparent 100%),
            /* 아주 흐릿한 격자무늬 (가로세로 약 1cm 크기: 38px) */
            linear-gradient(to right, rgba(255, 255, 255, 0.015) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.015) 1px, transparent 1px);
        background-size: 100% 100%, 38px 38px, 38px 38px;
        background-attachment: fixed;
        color: var(--terminal-text) !important;
        font-family: 'Pretendard', 'Inter', sans-serif !important;
    }

    [data-testid="stHeader"] { background: transparent !important; }

    [data-testid="stSidebar"] {
        background-color: rgba(6, 8, 18, 0.85) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border-right: 1px solid var(--glass-border) !important;
    }

    /* 메트릭 카드: 글래스모피즘 스타일 적용 */
    [data-testid="metric-container"] {
        background: var(--terminal-surface) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 8px !important;
        padding: 12px 18px !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
        transition: all 0.3s ease;
    }
    [data-testid="metric-container"]:hover {
        border-color: rgba(0, 224, 255, 0.25) !important;
        box-shadow: 0 8px 32px 0 rgba(0, 224, 255, 0.08) !important;
        transform: translateY(-1px);
    }
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        color: #ffffff !important;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.85rem !important;
        letter-spacing: 0.08em !important;
        color: #94a3b8 !important;
        text-transform: uppercase !important;
    }

    /* 버튼: 영롱한 네온 느낌 */
    .stButton > button {
        background: rgba(0, 224, 255, 0.03) !important;
        color: var(--terminal-accent) !important;
        border: 1px solid rgba(0, 224, 255, 0.3) !important;
        border-radius: 6px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        transition: all 0.25s ease !important;
        box-shadow: 0 2px 8px rgba(0, 224, 255, 0.05) !important;
        height: 38px !important;
        margin-top: 0px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    .stButton > button:hover {
        background: var(--terminal-accent) !important;
        color: #030408 !important;
        border-color: var(--terminal-accent) !important;
        box-shadow: 0 0 15px rgba(0, 224, 255, 0.3) !important;
    }

    /* 특수 버튼 (새로고침 등) */
    .refresh-btn button {
        border-color: #a78bfa !important;
        color: #a78bfa !important;
        background: rgba(167, 139, 250, 0.03) !important;
    }
    .refresh-btn button:hover {
        background: #a78bfa !important;
        color: #030408 !important;
        box-shadow: 0 0 15px rgba(167, 139, 250, 0.3) !important;
    }

    /* 탭 */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(10, 14, 28, 0.4) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 8px !important;
        padding: 4px !important;
    }
    .stTabs [data-baseweb="tab"] {
        color: #94a3b8 !important;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.9rem !important;
        padding: 8px 16px;
        border-radius: 6px !important;
        transition: all 0.2s;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(0, 224, 255, 0.15) !important;
        color: var(--terminal-accent) !important;
        border: 1px solid rgba(0, 224, 255, 0.35) !important;
        font-weight: 700 !important;
    }

    /* 인풋 필드 */
    .stTextInput input, .stSelectbox select, .stNumberInput input {
        background: rgba(5, 7, 15, 0.8) !important;
        border: 1px solid var(--glass-border) !important;
        color: var(--terminal-text) !important;
        font-family: 'JetBrains Mono', monospace !important;
        border-radius: 6px !important;
        font-size: 0.9rem !important;
    }
    .stTextInput input:focus, .stSelectbox select:focus, .stNumberInput input:focus {
        border-color: var(--terminal-accent) !important;
        box-shadow: 0 0 8px rgba(0, 224, 255, 0.2) !important;
    }

    /* 데이터프레임 */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--glass-border) !important;
        border-radius: 8px !important;
        background: rgba(10, 14, 28, 0.3) !important;
    }

    /* 로고: 우상향 심볼(↗) 및 영롱한 오로라 그라데이션 */
    .quantum-logo {
        font-family: 'Pretendard', 'Inter', sans-serif;
        font-size: calc(1.1rem * 1.55);
        font-weight: 800;
        color: var(--terminal-text);
        border-bottom: 1px solid var(--glass-border);
        padding-bottom: 12px;
        margin-bottom: 20px;
        position: relative;
    }
    .quantum-logo::after {
        content: " ↗";
        color: var(--terminal-accent);
        font-weight: 900;
        text-shadow: 0 0 8px rgba(0, 224, 255, 0.5);
    }

    @keyframes aurora-flow {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    .rainbow-text {
        font-family: 'Pretendard', 'Inter', sans-serif !important;
        background: linear-gradient(135deg, #00f0ff, #8b5cf6, #ec4899, #00f0ff);
        background-size: 300% 300%;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        color: transparent !important;
        font-weight: 900 !important;
        animation: aurora-flow 6s ease infinite;
        text-shadow: 0 0 20px rgba(0, 224, 255, 0.1);
    }

    /* 공통 버튼 스타일의 헤더 배지 */
    .header-btn-like {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        height: 38px !important;
        background: rgba(13, 17, 33, 0.4) !important;
        border: 1px solid var(--glass-border) !important;
        color: #94a3b8 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        text-align: center !important;
        box-sizing: border-box !important;
        border-radius: 6px !important;
        white-space: nowrap !important;
    }
    .header-badge-live {
        border-color: rgba(16, 185, 129, 0.4) !important;
        color: var(--terminal-green) !important;
        background: rgba(16, 185, 129, 0.08) !important;
        box-shadow: inset 0 0 8px rgba(16, 185, 129, 0.05) !important;
    }
    .header-badge-live .dot {
        width: 8px; height: 8px;
        background: var(--terminal-green) !important;
        border-radius: 50% !important;
        margin-right: 8px !important;
        display: inline-block !important;
        box-shadow: 0 0 6px var(--terminal-green);
    }
    .header-badge-stopped {
        border-color: rgba(239, 68, 68, 0.4) !important;
        color: var(--terminal-red) !important;
        background: rgba(239, 68, 68, 0.08) !important;
    }
    .header-badge-stopped .dot {
        width: 8px; height: 8px;
        background: var(--terminal-red) !important;
        border-radius: 50% !important;
        margin-right: 8px !important;
        display: inline-block !important;
        box-shadow: 0 0 6px var(--terminal-red);
    }

    /* 시스템 로그 박스 */
    .log-box {
        background: rgba(5, 7, 15, 0.85);
        border: 1px solid var(--glass-border);
        border-radius: 8px;
        padding: 12px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.9rem;
        color: #cbd5e1;
        height: 250px;
        overflow-y: auto;
        line-height: 1.5;
        white-space: pre-wrap;
    }
    @keyframes log-yellow-blink {
        0% { opacity: 1; }
        50% { opacity: 0.6; }
        100% { opacity: 1; }
    }
    .log-latest {
        color: #f59e0b !important;
        font-weight: bold;
        background: rgba(245, 158, 11, 0.06) !important;
        border-left: 3px solid #f59e0b;
        padding: 2px 8px;
        animation: log-yellow-blink 1.5s infinite ease-in-out;
    }

    /* 구분선 */
    hr { border-color: var(--glass-border) !important; margin: 15px 0 !important; }

    /* Wall Street Metric Bar */
    .metric-bar-container {
        display: flex;
        justify-content: space-between;
        background: rgba(13, 17, 33, 0.35);
        border: 1px solid var(--glass-border);
        border-radius: 8px;
        padding: 12px 0;
        margin-bottom: 20px;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
    }
    .terminal-metric-item {
        flex: 1;
        border-right: 1px solid var(--glass-border);
        padding: 0 20px;
        transition: all 0.3s ease;
    }
    .terminal-metric-item:last-child { border-right: none; }
    .terminal-metric-item:hover {
        background: rgba(255, 255, 255, 0.02);
    }
    .terminal-metric-label {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        margin-bottom: 4px;
        display: flex;
        align-items: center;
    }

    /* 커스텀 금융 터미널 툴팁 */
    .terminal-tooltip {
        position: relative;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: help;
        color: var(--terminal-accent);
        font-weight: bold;
        margin-left: 6px;
        font-size: 0.8rem;
        background: rgba(0, 224, 255, 0.1);
        border: 1px solid rgba(0, 224, 255, 0.3);
        width: 16px;
        height: 16px;
        border-radius: 4px;
    }
    .terminal-tooltip .tooltip-text {
        visibility: hidden;
        width: 250px;
        background-color: #0b0f19 !important;
        color: #ffffff !important;
        text-align: center;
        border: 1px solid rgba(0, 224, 255, 0.4) !important;
        border-radius: 6px !important;
        padding: 8px 12px !important;
        position: absolute;
        z-index: 9999 !important;
        bottom: 125%;
        left: 50%;
        transform: translateX(-50%);
        opacity: 0;
        transition: opacity 0.2s;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.8rem !important;
        font-weight: normal !important;
        text-transform: none !important;
        box-shadow: 0px 8px 24px rgba(0, 0, 0, 0.5) !important;
    }
    .terminal-tooltip:hover .tooltip-text {
        visibility: visible;
        opacity: 1;
    }
    .terminal-metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.3rem;
        font-weight: 700;
        color: #ffffff;
        line-height: 1.1;
    }
    .terminal-metric-sub {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        margin-top: 4px;
        display: flex;
        align-items: center;
        gap: 4px;
    }

    /* 청산 버튼 특화 (최소 14px 준수, 글래스모피즘 스타일 조화) */
    .small-btn-marker + div.stButton button,
    .small-btn-marker + div[data-testid="stButton"] button,
    div.small-btn-marker ~ div.stButton button {
        font-size: 14px !important;
        height: 28px !important;
        min-height: 28px !important;
        line-height: 1 !important;
        padding: 0 10px !important;
        border-color: var(--terminal-red) !important;
        color: var(--terminal-red) !important;
        border-radius: 6px !important;
        background: rgba(239, 68, 68, 0.05) !important;
        margin-top: -12px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.2s ease !important;
    }
    .small-btn-marker + div.stButton button:hover,
    .small-btn-marker + div[data-testid="stButton"] button:hover {
        background: var(--terminal-red) !important;
        color: white !important;
        box-shadow: 0 0 10px rgba(239, 68, 68, 0.4) !important;
    }

    /* 깜빡임 애니메이션 (터미널 스타일) */
    @keyframes terminal-blink {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    .badge-pink-blink, .badge-green-blink, .badge-red-blink {
        border-radius: 4px !important;
        animation: terminal-blink 1.2s infinite ease-in-out;
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

    /* 탭바와 헤더 배지 수평 정렬 */
    @media (min-width: 1024px) {
        .floating-header-wrapper + div[data-testid="stHorizontalBlock"] {
            margin-bottom: -46px !important;
            position: relative !important;
            z-index: 9999 !important;
            top: 4px !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            max-width: 55% !important;
        }
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
    if engine.is_ready:
        is_trading = (engine.state == EngineState.TRADING)

    defaults = {
        "engine": engine,
        "api_connected": engine.is_ready,
        "auto_trading": is_trading,
        "adx_auto_switch": CFG.ADX_AUTO_SWITCH,
        "rsi_auto_switch": CFG.USE_RSI_FILTER,
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
        f'<span class="rainbow-text">AKMCD-SSL-RSI</span><br><span style="font-size:calc(0.75rem * 1.33);">{APP_VERSION}</span></div>',
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

    auto = st.toggle(
        "자동매매 ON/OFF",
        value=st.session_state.auto_trading,
        help="ON: 실시간 마켓 스캐너 및 자동 매매 엔진을 기동하여 AKMCD+SSL+RSI 하이브리드 전략 조건 충족 시 포지션을 자동으로 진입/청산합니다. / OFF: 실시간 스캔을 즉시 중단하고 신규 자동 진입을 차단합니다. (기존 보유 포지션은 유지됩니다)"
    )
    rsi_auto = st.toggle(
        "⚡ RSI 자동 스위칭",
        value=st.session_state.rsi_auto_switch,
        help="ON: RSI 필터 활성화 (롱 < 60, 숏 > 40) 및 스캐너 노출 / OFF: RSI 필터 비활성화 및 스캐너 필드 숨김"
    )
    adx_auto = st.toggle(
        "🧠 ADX 자동 스위칭",
        value=st.session_state.adx_auto_switch,
        help="ON: ADX값이 25 이상이면 추세장(롱 EMA200 위 / 숏 EMA200 아래), 25 미만이면 횡보장(가격 BB 바로 안쪽) 모드로 자동 필터 전환 / OFF: RSI+EMA200 기본 전략 고정"
    )

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

    # ADX 자동 스위칭 토글 동기화
    if adx_auto != st.session_state.adx_auto_switch:
        st.session_state.adx_auto_switch = adx_auto
        CFG.ADX_AUTO_SWITCH = adx_auto

    # RSI 자동 스위칭 토글 동기화
    if rsi_auto != st.session_state.rsi_auto_switch:
        st.session_state.rsi_auto_switch = rsi_auto
        CFG.USE_RSI_FILTER = rsi_auto

    # 자동매매 상태 동기화 및 강력 자동시작 보장 로직 (API 연결 후 즉시 스캔/매매 기동 보장)
    if engine.is_ready and st.session_state.auto_trading:
        if engine.trader and not engine.trader.enabled:
            engine.enable_trading()
        if engine.scanner and not engine.scanner.is_running:
            engine.start_scanner()

    # 사이드바 전략 상태를 ADX/RSI 설정에 포인터 동기화
    st.session_state.adx_auto_switch = CFG.ADX_AUTO_SWITCH
    st.session_state.rsi_auto_switch = CFG.USE_RSI_FILTER

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

    with st.expander("⚡ RSI 필터 설정", expanded=False):
        st.number_input("RSI 기간", 2, 100, CFG.RSI_PERIOD, step=1, key="sb_rsi_period",
                        on_change=sync_p, args=("sb_rsi_period", "main_rsi_period,settings_rsi_period", "RSI_PERIOD"))
        col_rsi1, col_rsi2 = st.columns(2)
        with col_rsi1:
            st.number_input("RSI 롱 상한선", 10.0, 90.0, float(CFG.RSI_OVERBOUGHT), step=1.0, key="sb_rsi_overbought",
                            on_change=sync_p, args=("sb_rsi_overbought", "main_rsi_overbought,settings_rsi_overbought", "RSI_OVERBOUGHT"))
        with col_rsi2:
            st.number_input("RSI 숏 하한선", 10.0, 90.0, float(CFG.RSI_OVERSOLD), step=1.0, key="sb_rsi_oversold",
                            on_change=sync_p, args=("sb_rsi_oversold", "main_rsi_oversold,settings_rsi_oversold", "RSI_OVERSOLD"))

    with st.expander("⚡ 운용 및 포지션 설정", expanded=False):
        st.number_input("레버리지 (x)", 1, 20, CFG.LEVERAGE, step=1, key="sb_leverage",
                        on_change=sync_p, args=("sb_leverage", "main_leverage", "LEVERAGE"))
        st.number_input("1회 진입 증거금 (USDT)", 1.0, 100.0, CFG.MARGIN_USDT, step=0.5, key="sb_margin",
                        on_change=sync_p, args=("sb_margin", "main_margin", "MARGIN_USDT"))
        st.number_input("최대 동시 포지션 수", 1, 10, CFG.MAX_POSITIONS, step=1, key="sb_max_pos",
                        on_change=sync_p, args=("sb_max_pos", "main_max_pos", "MAX_POSITIONS"))

    with st.expander("🛡️ 리스크 및 한도 설정", expanded=False):
        st.number_input("익절 (%)", 0.1, 20.0, float(CFG.TAKE_PROFIT_PCT * 100), step=0.1, key="sb_tp",
                        on_change=sync_p, args=("sb_tp", "main_tp", "TAKE_PROFIT_PCT", True))
        st.number_input("손절 (%)", 0.1, 10.0, float(CFG.STOP_LOSS_PCT * 100), step=0.1, key="sb_sl",
                        on_change=sync_p, args=("sb_sl", "main_sl", "STOP_LOSS_PCT", True))

# ══════════════════════════════════════════════════════
# 메인 헤더 (한 줄 배치)
# ══════════════════════════════════════════════════════

# [v3.0.4] 시간, 상태, 버튼을 우측에 동일한 크기의 버튼 스타일로 나란히 배치
st.markdown('<div class="floating-header-wrapper"></div>', unsafe_allow_html=True)
col_empty, col_time, col_status, col_refresh = st.columns([5.5, 1.8, 1.5, 1.2])

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
                    <div class="terminal-metric-label">
                        누적 수익률
                        <span class="terminal-tooltip">
                            ℹ
                            <span class="tooltip-text">초기화 시점의 총 잔고: {seed_money:,.2f} USDT</span>
                        </span>
                    </div>
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
        if st.button("📊  수익률,승률 초기화", use_container_width=True, key="dashboard_stats_reset",
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
            if CFG.USE_RSI_FILTER:
                cols = ["symbol","price","change_pct","volume_m","signal","strength","ema_ok","macd_ok","bb_ok","ema200_ok","ema200","rsi_ok","rsi"]
                col_names = ["종목","현재가","등락(%)","거래대금(M)","신호","강도(%)","SSL 추세","AKMCD 영선","AKMCD 점전환","EMA 200 필터","EMA 200 수치","RSI 필터","RSI 수치"]
            else:
                cols = ["symbol","price","change_pct","volume_m","signal","strength","ema_ok","macd_ok","bb_ok","ema200_ok","ema200"]
                col_names = ["종목","현재가","등락(%)","거래대금(M)","신호","강도(%)","SSL 추세","AKMCD 영선","AKMCD 점전환","EMA 200 필터","EMA 200 수치"]

            display = df_scan[cols].copy()
            display.columns = col_names
            display["신호"] = display["신호"].map({"long":"🟢 LONG","short":"🔴 SHORT","none":"— "})
            display["SSL 추세"] = display["SSL 추세"].map({True:"✅",False:"❌"})
            display["AKMCD 영선"] = display["AKMCD 영선"].map({True:"✅",False:"❌"})
            display["AKMCD 점전환"] = display["AKMCD 점전환"].map({True:"✅",False:"❌"})
            display["EMA 200 필터"] = display["EMA 200 필터"].map({True:"✅",False:"❌"})
            if "RSI 필터" in display.columns:
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
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.9rem;color:#cccccc;letter-spacing:0.1em;">ENTRY CONDITIONS & STRATEGIC SYSTEM</p>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🟢 LONG 포지션 진입 조건**")
        st.markdown(
            """
            <div style="background:#0f0f0f; border:1px solid #ffcc00; padding:15px; margin-top:5px; margin-bottom:15px; border-radius:0px;">
                <p style="font-family:'Inter'; font-size:1.15rem; color:#ffcc00; margin:0; line-height:1.5; text-align:center; font-weight:600;">
                "🌊 큰 파도(SSL)가 밀어주고, 🟢 AKMCD 점이 상승하며, 🚀 히스토그램이 영선을 돌파하고, 🔵 양봉(Blue)이면서 🛡️ EMA 200 위에 위치할 때 롱 진입합니다!"
                </p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        st.markdown("- **추세:** 현재 종가가 SSL 파란선(ssl_up) 위 <span style='color:#ffcc00;'>☞ 대세 상승 추세 확인</span>", unsafe_allow_html=True)
        st.markdown("- **반전:** AKMCD 도트 색상이 빨간색에서 초록색으로 변경 <span style='color:#ffcc00;'>☞ 단기 모멘텀 상승 전환</span>", unsafe_allow_html=True)
        st.markdown("- **모멘텀:** MACD 히스토그램이 영선(0) 위 <span style='color:#ffcc00;'>☞ MACD 강도 양수 돌파</span>", unsafe_allow_html=True)
        st.markdown("- **캔들:** 현재 봉의 종가가 직전 봉의 종가보다 높은 양봉(Blue) <span style='color:#ffcc00;'>☞ 실시간 매수세 우위</span>", unsafe_allow_html=True)
        st.markdown("- **필터:** 현재 가격이 **EMA 200 장기이평선 위** <span style='color:#ffcc00;'>☞ 장기 대추세 부합 (필수)</span>", unsafe_allow_html=True)

    with c2:
        st.markdown("**🔴 SHORT 포지션 진입 조건**")
        st.markdown(
            """
            <div style="background:#0f0f0f; border:1px solid #ff3b30; padding:15px; margin-top:5px; margin-bottom:15px; border-radius:0px;">
                <p style="font-family:'Inter'; font-size:1.15rem; color:#ff3b30; margin:0; line-height:1.5; text-align:center; font-weight:600;">
                "📉 내리막길(SSL) 경사 아래에서, 🔴 AKMCD 점이 하락하며, 🌬 히스토그램이 영선 아래로 떨어지고, 🔴 음봉(Red)이면서 🛡️ EMA 200 아래에 위치할 때 숏 진입합니다!"
                </p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        st.markdown("- **추세:** 현재 종가가 SSL 빨간선(ssl_down) 아래 <span style='color:#ff3b30;'>☞ 대세 하락 추세 확인</span>", unsafe_allow_html=True)
        st.markdown("- **반전:** AKMCD 도트 색상이 초록색에서 빨간색으로 변경 <span style='color:#ff3b30;'>☞ 단기 모멘텀 하락 전환</span>", unsafe_allow_html=True)
        st.markdown("- **모멘텀:** MACD 히스토그램이 영선(0) 아래 <span style='color:#ff3b30;'>☞ MACD 강도 음수 돌파</span>", unsafe_allow_html=True)
        st.markdown("- **캔들:** 현재 봉의 종가가 직전 봉의 종가 이하인 음봉(Red) <span style='color:#ff3b30;'>☞ 실시간 매도세 우위</span>", unsafe_allow_html=True)
        st.markdown("- **필터:** 현재 가격이 **EMA 200 장기이평선 아래** <span style='color:#ff3b30;'>☞ 장기 대추세 부합 (필수)</span>", unsafe_allow_html=True)

    st.markdown("---")
    
    # ── 대혁신적인 진입 필터/엔진 시각화 체계 ─────────────────────
    st.markdown(
        """
        <div style="background:#0c0c0c; border:1px solid #262626; padding:20px; border-radius:0px; margin-bottom:20px;">
            <h4 style="font-family:'JetBrains Mono'; color:#ff9900; margin-top:0; margin-bottom:15px; font-size:1.1rem; letter-spacing:0.05em;">⚙️ AI QUANTUM 복합 진입 필터 & 엔진 스위칭 아키텍처</h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div style="background:#151515; padding:15px; border-left:4px solid #ffcc00;">
                    <p style="font-weight:bold; font-size:0.95rem; color:#ffffff; margin-top:0; margin-bottom:10px;">🛠️ 핵심 필수 기반 조건 (Base Base Base - 100% 필수)</p>
                    <ul style="font-size:0.85rem; color:#cccccc; line-height:1.6; padding-left:18px; margin:0;">
                        <li><b>SSL 추세 동기화:</b> 상하위 선 배열 일치 여부 실시간 검증</li>
                        <li><b>AKMCD Zero Line:</b> MACD 영선 상단(롱)/하단(숏) 진입 모멘텀</li>
                        <li><b>AKMCD Dot Switch:</b> 모멘텀 마디 전환(빨->초 / 초->빨) 타이밍 포착</li>
                        <li><b>EMA 200 장기 필터:</b> 장기 대이평 기준 가격 정배열/역배열 필터링</li>
                    </ul>
                </div>
                <div style="background:#151515; padding:15px; border-left:4px solid #ff9900;">
                    <p style="font-weight:bold; font-size:0.95rem; color:#ffffff; margin-top:0; margin-bottom:10px;">🚀 동적 전략 옵션 제어 (Optional Controls - 사이드바 토글)</p>
                    <ul style="font-size:0.85rem; color:#cccccc; line-height:1.6; padding-left:18px; margin:0;">
                        <li><b>⚡ RSI 자동 스위칭 (반필수):</b> 과열 진입 제한 롱 상한선(60) & 숏 하한선(40)을 적용해 노이즈를 완전 차단합니다. OFF 시 우회되며 스캐너에서도 제외됩니다.</li>
                        <li><b>🧠 ADX 자동 스위칭 (완전 옵션):</b> <b>ADX ≥ 25 (추세장)</b> 시 장기이평선 필터로 작동하고, <b>ADX < 25 (횡보장)</b> 시 가격 BB 채널 내에서만 거래를 승인하는 능동형 체계 장치입니다.</li>
                    </ul>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

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
    
    if st.button("📊  수익률,승률 초기화", use_container_width=True,
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
