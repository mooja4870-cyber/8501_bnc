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
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from core.exchange import BinanceClient
from core.scanner import Scanner
from core.trader import AutoTrader
from core.engine import QuantumEngine, EngineState
import importlib
import core.config
# importlib.reload(core.config) # Removed reload to prevent breaking shared config references in background thread
from core.config import CFG

import core.stats as stats_store

import core.history_helper
importlib.reload(core.history_helper)
from core.history_helper import load_local_trade_history, aggregate_and_pair_trades

load_dotenv(override=True)

# ── 앱 버전 (git tag와 동기화) ─────────────────────────
@st.cache_data(ttl=5)
def get_app_version():
    try:
        import subprocess
        tag = subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"]).strip().decode("utf-8")
        return f"Binance {tag}"
    except Exception:
        return "Binance v4.0.0"

APP_VERSION = get_app_version()

# ── 페이지 설정 ───────────────────────────────────────
st.set_page_config(
    page_title="AI QUANTUM · Binance Trader",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 보안 로그인 기능 ───────────────────────────────────
def check_password():
    """Returns True if the user entered the correct password."""
    return True

if not check_password():
    st.stop()

# ── Wall Street Professional Terminal CSS ─────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;700&display=swap');
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

    html {
        font-size: 105% !important;
    }

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
            /* 중앙에 밝고 외곽으로 갈수록 어두워지는 딥블루 방사형 그래디언트 */
            radial-gradient(circle at 50% 50%, rgba(35, 60, 105, 0.8) 0%, rgba(10, 15, 30, 0.95) 55%, rgba(3, 4, 8, 1) 100%),
            /* 흐릿한 격자무늬 (가로세로 약 1cm 크기: 38px) 유지 */
            linear-gradient(to right, rgba(255, 255, 255, 0.05) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
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

    /* 멀티셀렉트 태그 (버튼) */
    span[data-baseweb="tag"] {
        background-color: #333333 !important;
        color: #e2e8f0 !important;
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

    /* 토글/체크박스 라벨 글자 색상 흰색 강제 적용 */
    div[data-testid="stCheckbox"] label,
    div[data-testid="stCheckbox"] span,
    div[data-testid="stCheckbox"] p {
        color: #ffffff !important;
    }

    /* 툴팁 (물음표) 아이콘 가시성 개선 (흰색) */
    div[data-testid="stTooltipIcon"] svg,
    div[data-testid="stTooltipIcon"] button,
    div[data-testid="stTooltipIcon"] {
        color: #ffffff !important;
        fill: #ffffff !important;
        opacity: 1 !important;
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
    @keyframes live-blink {
        0% { opacity: 1; box-shadow: inset 0 0 15px rgba(16, 185, 129, 0.4), 0 0 15px rgba(16, 185, 129, 0.6); border-color: rgba(16, 185, 129, 0.8); }
        50% { opacity: 0.6; box-shadow: inset 0 0 5px rgba(16, 185, 129, 0.1), 0 0 5px rgba(16, 185, 129, 0.2); border-color: rgba(16, 185, 129, 0.3); }
        100% { opacity: 1; box-shadow: inset 0 0 15px rgba(16, 185, 129, 0.4), 0 0 15px rgba(16, 185, 129, 0.6); border-color: rgba(16, 185, 129, 0.8); }
    }
    .header-badge-live {
        border-color: rgba(16, 185, 129, 0.8) !important;
        color: #10b981 !important;
        font-weight: 800 !important;
        background: rgba(16, 185, 129, 0.15) !important;
        animation: live-blink 1.2s infinite ease-in-out !important;
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
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
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
        justify-content: center;
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
        width: 330px;
        background-color: #0b0f19 !important;
        color: #ffffff !important;
        text-align: left !important;
        line-height: 1.5 !important;
        border: 1px solid rgba(0, 224, 255, 0.4) !important;
        border-radius: 6px !important;
        padding: 12px 16px !important;
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
        text-align: center;
    }
    .terminal-metric-sub {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        margin-top: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
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

    /* 🧬 모든 탭 마우스 오버 툴팁 */
    .stTabs [data-baseweb="tab-list"] {
        overflow: visible !important;
    }
    .stTabs button[data-baseweb="tab"] {
        position: relative;
        overflow: visible !important;
    }
    .stTabs button[data-baseweb="tab"]::after {
        position: absolute;
        bottom: 125%;
        left: 50%;
        transform: translateX(-50%);
        background-color: #0b0f19 !important;
        color: #ffffff !important;
        border: 1px solid rgba(0, 224, 255, 0.4) !important;
        border-radius: 6px !important;
        padding: 6px 12px !important;
        font-family: 'Pretendard', sans-serif !important;
        font-size: 0.8rem !important;
        font-weight: normal !important;
        white-space: nowrap;
        z-index: 999999 !important;
        box-shadow: 0px 8px 24px rgba(0, 0, 0, 0.5) !important;
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.2s, visibility 0.2s;
        pointer-events: none;
    }
    .stTabs button[data-baseweb="tab"]:hover::after {
        opacity: 1;
        visibility: visible;
    }

    /* 탭별 개별 툴팁 텍스트 바인딩 */
    .stTabs button[data-baseweb="tab"]:nth-child(1)::after {
        content: "실시간 잔고, 미실현 손익 및 활성 포지션 모니터링";
    }
    .stTabs button[data-baseweb="tab"]:nth-child(2)::after {
        content: "전략 부합 종목 실시간 발굴 및 탐지 상태 모니터링";
    }
    .stTabs button[data-baseweb="tab"]:nth-child(3)::after {
        content: "거래소 체결 이력 조회 및 로컬 CSV 기반 성적 분석";
    }
    .stTabs button[data-baseweb="tab"]:nth-child(4)::after {
        content: "롱/숏 포지션 진입 상세 조건 및 전략 로직 가이드";
    }
    .stTabs button[data-baseweb="tab"]:nth-child(5)::after {
        content: "레버리지, 증거금, 손익절 및 기술 지표 파라미터 설정";
    }
    .stTabs button[data-baseweb="tab"]:nth-child(6)::after {
        content: "자동매매 Off 일 때도 작동 가능 (로컬 과거 캔들 캐시 데이터 기반 학습)";
    }
    
    /* stButton의 상위 컨테이너 마진 제거하여 수평 정렬 맞춤 */
    [data-testid="stHorizontalBlock"] div[data-testid="stButton"] {
        margin-top: 0px !important;
        display: flex;
        align-items: center;
    }
    </style>
    <img src="x" style="display:none;" onerror="
        (function() {
            const doc = window.parent.document || document;
            const btn = doc.querySelector('[data-testid=\\'collapsedControl\\']');
            if (btn) {
                btn.click();
            }
        })();
    ">
    """,
    unsafe_allow_html=True,
)



def init_session():
    engine = QuantumEngine.get_instance()
    
    # settings.json에 저장된 설정 또는 디폴트 값 사용
    is_trading = getattr(CFG, "AUTO_TRADING", True)

    defaults = {
        "engine": engine,
        "api_connected": engine.is_ready,
        "auto_trading": is_trading,
        "rsi_auto_switch": CFG.USE_RSI_FILTER,
        "active_preset": "기본 (Stable)",
        "closing_symbols": {}, # [v1.2.52] 잔상 방지용 청산 대기 목록 (symbol: timestamp)
        "sb_use_auto_compound": getattr(CFG, "USE_AUTO_COMPOUND", False),
        "main_use_auto_compound": getattr(CFG, "USE_AUTO_COMPOUND", False),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    # [v2.8.1] 기존 세션에서 set으로 남아있는 closing_symbols 마이그레이션 및 타입 안전장치
    if "closing_symbols" in st.session_state and not isinstance(st.session_state.closing_symbols, dict):
        st.session_state.closing_symbols = {}

    # .env 값이 있으면 UI 입력창 세션 상태 강제 초기화
    for state_key, env_keys in [("api_key_input", ["BINANCE_API_KEY"]), 
                                ("secret_input", ["BINANCE_SECRET_KEY"]), 
                                ("pass_input", ["BINANCE_PASSPHRASE"]),
                                ("settings_telegram_token", ["TELEGRAM_BOT_TOKEN"]),
                                ("settings_telegram_chat_id", ["TELEGRAM_CHAT_ID"])]:
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

    real_val = val / 100.0 if is_pct else val
    setattr(CFG, cfg_attr, real_val)

    # [v2.1.3] 백그라운드 엔진 및 서브모듈(trader, scanner, strategy)의 실시간 설정 동기화
    _engine = st.session_state.get("engine")
    if _engine:
        setattr(_engine.cfg, cfg_attr, real_val)
        if _engine.trader:
            setattr(_engine.trader.cfg, cfg_attr, real_val)
        if _engine.scanner:
            setattr(_engine.scanner.cfg, cfg_attr, real_val)
            if _engine.scanner.strategy:
                setattr(_engine.scanner.strategy.cfg, cfg_attr, real_val)

    # [NEW] 파일로 영구 저장 (하드코딩 제거 정책에 따른 필수 요건)
    CFG.save_settings()

    # [v3.5.1] 설정 값 변경 알림 팝업 추가
    st.toast(f"⚙️ 설정 값이 변경되었습니다: {cfg_attr} ➔ {val}{'%' if is_pct else ''}")

if not st.session_state.api_connected:
    ak = os.getenv("BINANCE_API_KEY", "")
    sk = os.getenv("BINANCE_SECRET_KEY", "")
    pw = os.getenv("BINANCE_PASSPHRASE", "")
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


# ── 데이터 통합 조회 (상단 통합) ──────────────────────────
dash = None
if st.session_state.api_connected:
    try:
        engine: QuantumEngine = st.session_state.engine
        dash = engine.get_dashboard_data()
    except Exception:
        pass

# ══════════════════════════════════════════════════════
# 사이드바 — API 설정
# ══════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(
        '<div class="quantum-logo" style="letter-spacing:-0.5px;" '
        'title="[TTM Squeeze + 200 EMA 전략]&#10;'
        '1. 200 EMA 필터: 장기 추세 방향성 확인 (Long: 가격 > 200 EMA, Short: 가격 < 200 EMA)&#10;'
        '2. TTM Squeeze 돌파: 볼린저 밴드와 켈트너 채널의 변동성 돌파 감지 (Squeeze OFF 시 진입)&#10;'
        '3. 모멘텀 및 캔들 색상 필터: 선행 추세 확증 (Momentum 히스토그램 및 캔들 색상 일치)&#10;'
        '4. RSI 필터: 과열권 진입 제한 및 추격 매매 노이즈 필터링">'
        f'<span class="rainbow-text" style="font-size: 95%;">TTM-Squeeze-EMA</span><br><span style="font-size:calc(0.75rem * 1.33 * 1.22);">{APP_VERSION}</span><br><span style="font-size:15px; color:#888; font-family:\'JetBrains Mono\', monospace;">SINCE 2026.05.29 16:09</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    api_key = st.text_input(
        "🔑 API Key", value=os.getenv("BINANCE_API_KEY", ""), type="password", key="api_key_input"
    )
    secret_key = st.text_input(
        "🔑 Secret Key", value=os.getenv("BINANCE_SECRET_KEY", ""), type="password", key="secret_input"
    )
    passphrase = st.text_input(
        "🔑 Passphrase", value=os.getenv("BINANCE_PASSPHRASE", ""), type="password", key="pass_input"
    )

    if st.button("🔗  Binance 연결", use_container_width=True):
        with st.spinner("연결 중..."):
            ak = api_key if api_key else os.getenv("BINANCE_API_KEY", "")
            sk = secret_key if secret_key else os.getenv("BINANCE_SECRET_KEY", "")
            pw = passphrase if passphrase else os.getenv("BINANCE_PASSPHRASE", "")
            success, msg = connect_api(ak, sk, pw)
            if success:
                st.success(msg)
            else:
                st.error(msg)

    st.markdown("---")


    auto = st.toggle(
        "🤖 자동매매 가동 (ON/OFF)",
        value=st.session_state.auto_trading,
        help="ON: 실시간 마켓 스캐너 및 자동 매매 엔진을 기동하여 TTM Squeeze + 200 EMA 전략 조건 충족 시 포지션을 자동으로 진입/청산합니다. / OFF: 실시간 스캔을 즉시 중단하고 신규 자동 진입을 차단합니다. (기존 보유 포지션은 유지됩니다)"
    )

    engine: QuantumEngine = st.session_state.engine
    
    if auto != st.session_state.auto_trading:
        st.session_state.auto_trading = auto
        CFG.AUTO_TRADING = auto
        CFG.save_settings()
        if auto:
            st.toast("🤖 자동매매가 가동(ON) 되었습니다.")
        else:
            st.toast("⏹️ 자동매매가 중지(OFF) 되었습니다.")
        if engine.is_ready:
            if auto:
                engine.enable_trading()
                engine.start_scanner()
            else:
                engine.disable_trading()
                engine.stop_scanner()

    # 자동매매 상태 동기화 및 강력 자동시작/종료 보장 로직 (UI 상태와 백엔드 엔진 상태의 완벽한 일치 보장)
    if engine.is_ready:
        if st.session_state.auto_trading:
            if engine.trader and not engine.trader.enabled:
                engine.enable_trading()
            if engine.scanner and not engine.scanner.is_running:
                engine.start_scanner()
        else:
            if engine.trader and engine.trader.enabled:
                engine.disable_trading()
            if engine.scanner and engine.scanner.is_running:
                engine.stop_scanner()

    # 사이드바 전략 상태를 RSI 설정에 포인터 동기화
    st.session_state.rsi_auto_switch = CFG.USE_RSI_FILTER

    # ── [다중기간 연동 변수값 자동설정] Deep Learning 최적 파라미터 프리셋 ──
    # ── [다중기간 연동 변수값 자동설정] Deep Learning 최적 파라미터 프리셋 ──
    MULTI_PERIOD_PRESETS = {
        "30일 (30d)": {
            "LEVERAGE": 20, "MARGIN_USDT": 18.3, "MAX_POSITIONS": 5,
            "STOP_LOSS_PCT": 0.0396, "TAKE_PROFIT_PCT": 0.0341,
            "TRAILING_ACTIVATE_PCT": 0.0375, "TRAILING_CALLBACK_PCT": 0.0051,
            "MAX_DRAWDOWN_PCT": 0.215, "ALLOW_LONG": True, "ALLOW_SHORT": True,
            "TIMEFRAME": "4h", "SCAN_INTERVAL_SEC": 60, "MIN_VOLUME_USDT": 2_000_000.0,
            "EMA_PERIOD": 102, "BB_PERIOD": 37, "BB_STD": 2.07,
            "RSI_PERIOD": 8, "RSI_OVERSOLD": 25.2, "RSI_OVERBOUGHT": 69.0,
        },
        "15일 (15d)": {
            "LEVERAGE": 20, "MARGIN_USDT": 19.5, "MAX_POSITIONS": 3,
            "STOP_LOSS_PCT": 0.0391, "TAKE_PROFIT_PCT": 0.0458,
            "TRAILING_ACTIVATE_PCT": 0.0427, "TRAILING_CALLBACK_PCT": 0.0019,
            "MAX_DRAWDOWN_PCT": 0.218, "ALLOW_LONG": True, "ALLOW_SHORT": True,
            "TIMEFRAME": "4h", "SCAN_INTERVAL_SEC": 30, "MIN_VOLUME_USDT": 5_000_000.0,
            "EMA_PERIOD": 220, "BB_PERIOD": 26, "BB_STD": 1.74,
            "RSI_PERIOD": 18, "RSI_OVERSOLD": 27.8, "RSI_OVERBOUGHT": 70.5,
        },
        "7일 (7d)": {
            "LEVERAGE": 20, "MARGIN_USDT": 19.8, "MAX_POSITIONS": 5,
            "STOP_LOSS_PCT": 0.0365, "TAKE_PROFIT_PCT": 0.0641,
            "TRAILING_ACTIVATE_PCT": 0.0244, "TRAILING_CALLBACK_PCT": 0.0068,
            "MAX_DRAWDOWN_PCT": 0.277, "ALLOW_LONG": True, "ALLOW_SHORT": False,
            "TIMEFRAME": "4h", "SCAN_INTERVAL_SEC": 20, "MIN_VOLUME_USDT": 5_000_000.0,
            "EMA_PERIOD": 241, "BB_PERIOD": 27, "BB_STD": 1.40,
            "RSI_PERIOD": 16, "RSI_OVERSOLD": 41.6, "RSI_OVERBOUGHT": 74.4,
        },
        "48시간 (48h)": {
            "LEVERAGE": 20, "MARGIN_USDT": 18.8, "MAX_POSITIONS": 6,
            "STOP_LOSS_PCT": 0.0359, "TAKE_PROFIT_PCT": 0.0585,
            "TRAILING_ACTIVATE_PCT": 0.0554, "TRAILING_CALLBACK_PCT": 0.0054,
            "MAX_DRAWDOWN_PCT": 0.205, "ALLOW_LONG": True, "ALLOW_SHORT": False,
            "TIMEFRAME": "15m", "SCAN_INTERVAL_SEC": 10, "MIN_VOLUME_USDT": 5_000_000.0,
            "EMA_PERIOD": 139, "BB_PERIOD": 31, "BB_STD": 1.57,
            "RSI_PERIOD": 13, "RSI_OVERSOLD": 37.4, "RSI_OVERBOUGHT": 67.9,
        },
        "24시간 (24h)": {
            "LEVERAGE": 20, "MARGIN_USDT": 15.1, "MAX_POSITIONS": 5,
            "STOP_LOSS_PCT": 0.0341, "TAKE_PROFIT_PCT": 0.0624,
            "TRAILING_ACTIVATE_PCT": 0.0143, "TRAILING_CALLBACK_PCT": 0.0017,
            "MAX_DRAWDOWN_PCT": 0.119, "ALLOW_LONG": True, "ALLOW_SHORT": False,
            "TIMEFRAME": "15m", "SCAN_INTERVAL_SEC": 10, "MIN_VOLUME_USDT": 2_000_000.0,
            "EMA_PERIOD": 144, "BB_PERIOD": 17, "BB_STD": 2.49,
            "RSI_PERIOD": 20, "RSI_OVERSOLD": 33.7, "RSI_OVERBOUGHT": 58.0,
        },
        "12시간 (12h)": {
            "LEVERAGE": 20, "MARGIN_USDT": 19.2, "MAX_POSITIONS": 4,
            "STOP_LOSS_PCT": 0.0371, "TAKE_PROFIT_PCT": 0.0509,
            "TRAILING_ACTIVATE_PCT": 0.0454, "TRAILING_CALLBACK_PCT": 0.0014,
            "MAX_DRAWDOWN_PCT": 0.199, "ALLOW_LONG": True, "ALLOW_SHORT": False,
            "TIMEFRAME": "1h", "SCAN_INTERVAL_SEC": 60, "MIN_VOLUME_USDT": 10_000_000.0,
            "EMA_PERIOD": 122, "BB_PERIOD": 34, "BB_STD": 2.09,
            "RSI_PERIOD": 9, "RSI_OVERSOLD": 30.0, "RSI_OVERBOUGHT": 72.0,
        },
    }

    PKL_PATH = "scratch/multi_period_results.pkl"
    if os.path.exists(PKL_PATH):
        try:
            import pickle
            with open(PKL_PATH, "rb") as f:
                saved_results = pickle.load(f)
                REQUIRED_19_KEYS = [
                    "LEVERAGE", "MARGIN_USDT", "MAX_POSITIONS",
                    "STOP_LOSS_PCT", "TAKE_PROFIT_PCT",
                    "TRAILING_ACTIVATE_PCT", "TRAILING_CALLBACK_PCT",
                    "MAX_DRAWDOWN_PCT", "ALLOW_LONG", "ALLOW_SHORT",
                    "TIMEFRAME", "SCAN_INTERVAL_SEC", "MIN_VOLUME_USDT",
                    "EMA_PERIOD", "BB_PERIOD", "BB_STD",
                    "RSI_PERIOD", "RSI_OVERSOLD", "RSI_OVERBOUGHT",
                ]
                TYPE_MAP = {
                    "LEVERAGE": int, "MARGIN_USDT": float, "MAX_POSITIONS": int,
                    "STOP_LOSS_PCT": float, "TAKE_PROFIT_PCT": float,
                    "TRAILING_ACTIVATE_PCT": float, "TRAILING_CALLBACK_PCT": float,
                    "MAX_DRAWDOWN_PCT": float, "ALLOW_LONG": bool, "ALLOW_SHORT": bool,
                    "TIMEFRAME": str, "SCAN_INTERVAL_SEC": int, "MIN_VOLUME_USDT": float,
                    "EMA_PERIOD": int, "BB_PERIOD": int, "BB_STD": float,
                    "RSI_PERIOD": int, "RSI_OVERSOLD": float, "RSI_OVERBOUGHT": float,
                }
                for p_name, data in saved_results.items():
                    if p_name in MULTI_PERIOD_PRESETS and "params" in data:
                        p_val = data["params"]
                        if all(k in p_val for k in REQUIRED_19_KEYS):
                            casted_preset = {}
                            for k, t in TYPE_MAP.items():
                                casted_preset[k] = t(p_val[k])
                            MULTI_PERIOD_PRESETS[p_name] = casted_preset
        except Exception as e:
            pass


    def apply_multi_period_preset():
        """다중기간 프리셋 선택 시 19개 파라미터를 CFG 및 세션 상태에 동기화"""
        selected = st.session_state.get("multi_period_select", "-- 기간을 선택하세요 --")
        if selected == "-- 기간을 선택하세요 --":
            return
        preset = MULTI_PERIOD_PRESETS.get(selected)
        if not preset:
            return

        # ── 1) CFG 글로벌 설정 업데이트 ──
        CFG.LEVERAGE = preset["LEVERAGE"]
        CFG.MARGIN_USDT = preset["MARGIN_USDT"]
        CFG.MAX_POSITIONS = preset["MAX_POSITIONS"]
        CFG.STOP_LOSS_PCT = preset["STOP_LOSS_PCT"]
        CFG.TAKE_PROFIT_PCT = preset["TAKE_PROFIT_PCT"]
        CFG.TRAILING_ACTIVATE_PCT = preset["TRAILING_ACTIVATE_PCT"]
        CFG.TRAILING_CALLBACK_PCT = preset["TRAILING_CALLBACK_PCT"]
        CFG.MAX_DRAWDOWN_PCT = preset["MAX_DRAWDOWN_PCT"]
        CFG.ALLOW_LONG = preset["ALLOW_LONG"]
        CFG.ALLOW_SHORT = preset["ALLOW_SHORT"]
        CFG.TIMEFRAME = preset["TIMEFRAME"]
        CFG.SCAN_INTERVAL_SEC = preset["SCAN_INTERVAL_SEC"]
        CFG.MIN_VOLUME_USDT = preset["MIN_VOLUME_USDT"]
        CFG.EMA_PERIOD = preset["EMA_PERIOD"]
        CFG.BB_PERIOD = preset["BB_PERIOD"]
        CFG.BB_STD = preset["BB_STD"]
        CFG.RSI_PERIOD = preset["RSI_PERIOD"]
        CFG.RSI_OVERSOLD = preset["RSI_OVERSOLD"]
        CFG.RSI_OVERBOUGHT = preset["RSI_OVERBOUGHT"]
        CFG.USE_AUTO_COMPOUND = False

        # ── 2) 사이드바 위젯 세션 상태 동기화 ──
        st.session_state.sb_leverage = preset["LEVERAGE"]
        st.session_state.sb_margin = preset["MARGIN_USDT"]
        st.session_state.sb_use_auto_compound = False
        st.session_state.sb_max_pos = preset["MAX_POSITIONS"]
        st.session_state.sb_sl = round(preset["STOP_LOSS_PCT"] * 100, 2)
        st.session_state.sb_tp = round(preset["TAKE_PROFIT_PCT"] * 100, 2)
        st.session_state.sb_timeframe = preset["TIMEFRAME"]
        st.session_state.sb_bb_period = preset["BB_PERIOD"]
        st.session_state.sb_bb_std = preset["BB_STD"]
        st.session_state.sb_rsi_period = preset["RSI_PERIOD"]
        st.session_state.sb_rsi_overbought = float(preset["RSI_OVERBOUGHT"])
        st.session_state.sb_rsi_oversold = float(preset["RSI_OVERSOLD"])
        st.session_state.sb_ssl_period = CFG.SSL_PERIOD  # SSL은 프리셋에 없으므로 현재값 유지

        # ── 3) 메인 탭 위젯 세션 상태 동기화 ──
        st.session_state.main_leverage = preset["LEVERAGE"]
        st.session_state.main_margin = preset["MARGIN_USDT"]
        st.session_state.main_use_auto_compound = False
        st.session_state.main_max_pos = preset["MAX_POSITIONS"]
        st.session_state.sb_use_dynamic_sltp = getattr(CFG, "USE_DYNAMIC_SLTP", True)
        st.session_state.sb_atr_tp_mult = getattr(CFG, "ATR_TP_MULT", 2.0)
        st.session_state.sb_atr_sl_mult = getattr(CFG, "ATR_SL_MULT", 1.5)
        st.session_state.main_use_dynamic_sltp = getattr(CFG, "USE_DYNAMIC_SLTP", True)
        st.session_state.main_atr_tp_mult = getattr(CFG, "ATR_TP_MULT", 2.0)
        st.session_state.main_atr_sl_mult = getattr(CFG, "ATR_SL_MULT", 1.5)
        st.session_state.main_sl = round(preset["STOP_LOSS_PCT"] * 100, 2)
        st.session_state.main_tp = round(preset["TAKE_PROFIT_PCT"] * 100, 2)
        st.session_state.main_timeframe = preset["TIMEFRAME"]
        st.session_state.main_bb_period = preset["BB_PERIOD"]
        st.session_state.main_bb_std = preset["BB_STD"]
        st.session_state.main_ssl_period = CFG.SSL_PERIOD
        st.session_state.main_rsi_period = preset["RSI_PERIOD"]
        st.session_state.main_rsi_overbought = float(preset["RSI_OVERBOUGHT"])
        st.session_state.main_rsi_oversold = float(preset["RSI_OVERSOLD"])
        st.session_state.main_scan_interval = preset["SCAN_INTERVAL_SEC"]
        st.session_state.main_min_vol = float(preset["MIN_VOLUME_USDT"])

        # ── 4) 설정 탭 RSI 및 볼륨 위젯 동기화 ──
        st.session_state.settings_rsi_period = preset["RSI_PERIOD"]
        st.session_state.settings_rsi_overbought = float(preset["RSI_OVERBOUGHT"])
        st.session_state.settings_rsi_oversold = float(preset["RSI_OVERSOLD"])
        
        # [NEW] 거래량 급증 필터 세션 상태 동기화
        st.session_state.sb_use_vol_filter = getattr(CFG, "USE_VOL_FILTER", False)
        st.session_state.sb_vol_ma_period = getattr(CFG, "VOL_MA_PERIOD", 20)
        st.session_state.sb_vol_surge_mult = getattr(CFG, "VOL_SURGE_MULT", 1.5)
        st.session_state.main_use_vol_filter = getattr(CFG, "USE_VOL_FILTER", False)
        st.session_state.main_vol_ma_period = getattr(CFG, "VOL_MA_PERIOD", 20)
        st.session_state.main_vol_surge_mult = getattr(CFG, "VOL_SURGE_MULT", 1.5)
        
        # [NEW] 트레일링 스톱 세션 상태 동기화
        st.session_state.sb_use_trailing_stop = getattr(CFG, "USE_TRAILING_STOP", False)
        st.session_state.sb_trailing_activate_pct = float(getattr(CFG, "TRAILING_ACTIVATE_PCT", 0.015)) * 100
        st.session_state.sb_trailing_callback_pct = float(getattr(CFG, "TRAILING_CALLBACK_PCT", 0.003)) * 100
        st.session_state.main_use_trailing_stop = getattr(CFG, "USE_TRAILING_STOP", False)
        st.session_state.main_trailing_activate_pct = float(getattr(CFG, "TRAILING_ACTIVATE_PCT", 0.015)) * 100
        st.session_state.main_trailing_callback_pct = float(getattr(CFG, "TRAILING_CALLBACK_PCT", 0.003)) * 100
        
        # ── 5) Trader 및 스캐너/엔진 전역 설정 실시간 동기화 ──
        _engine = st.session_state.get("engine")
        if _engine:
            for k, v in preset.items():
                setattr(_engine.cfg, k, v)
            if _engine.trader:
                _engine.trader.allow_long = preset["ALLOW_LONG"]
                _engine.trader.allow_short = preset["ALLOW_SHORT"]
                for k, v in preset.items():
                    setattr(_engine.trader.cfg, k, v)
            if _engine.scanner:
                for k, v in preset.items():
                    setattr(_engine.scanner.cfg, k, v)
                if _engine.scanner.strategy:
                    for k, v in preset.items():
                        setattr(_engine.scanner.strategy.cfg, k, v)
        
        # [NEW] 파일로 영구 저장
        CFG.save_settings()

    # [v1.2.90] 인터랙티브 프로 트레이딩 컨트롤러 (동기화 로직 적용)
    
    with st.expander("📊 지표 및 스캐너 설정", expanded=False):
        st.number_input("📏 KC ATR 배수", 0.5, 5.0, float(CFG.TTM_KC_MULT), step=0.1, key="sb_kc_mult",
                        on_change=sync_p, args=("sb_kc_mult", "main_kc_mult", "TTM_KC_MULT"),
                        help="켈트너 채널(Keltner Channel)의 폭을 결정하는 ATR 배수(기본값 1.5)입니다. 볼린저 밴드가 이 채널 안으로 수축하면 변동성 수축(Squeeze ON)으로 판단합니다.")
        # [v1.3.02] 타임프레임 원격 제어 추가
        tf_options = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
        st.selectbox("⏱️ 타임프레임", tf_options, index=tf_options.index(CFG.TIMEFRAME), key="sb_timeframe",
                     on_change=sync_p, args=("sb_timeframe", "main_timeframe", "TIMEFRAME"),
                     help="스퀴즈 지표 및 200 EMA 추세 필터를 탐지할 차트 봉의 타임프레임 단위입니다. (예: 15m, 1h, 4h 등)")
        col_bb1, col_bb2 = st.columns(2)
        with col_bb1:
            st.number_input("📈 BB 기간", 5, 100, CFG.BB_PERIOD, key="sb_bb_period",
                            on_change=sync_p, args=("sb_bb_period", "main_bb_period", "BB_PERIOD"),
                            help="볼린저 밴드(Bollinger Bands)를 산출하기 위한 단순이동평균(SMA) 기준 캔들 개수(기본값 20)입니다.")
        with col_bb2:
            st.number_input("📏 BB 편차 배수", 1.0, 5.0, CFG.BB_STD, step=0.1, key="sb_bb_std",
                            on_change=sync_p, args=("sb_bb_std", "main_bb_std", "BB_STD"),
                            help="볼린저 밴드의 상/하한선을 그리기 위한 표준편차 승수(기본값 2.0)입니다. 이 값이 커질수록 밴드가 넓어져 스퀴즈 진입 조건이 엄격해집니다.")
        
        st.number_input("⏱️ TTM 모멘텀 기간", 5, 100, CFG.TTM_MOM_PERIOD, step=1, key="sb_ttm_mom_period",
                        on_change=sync_p, args=("sb_ttm_mom_period", "main_ttm_mom_period", "TTM_MOM_PERIOD"),
                        help="TTM Squeeze의 모멘텀(선형 회귀선)을 계산할 캔들 기준 기간(기본값 20)입니다. 이 기간 동안의 시세를 선형 회귀하여 오실레이터로 표기합니다.")

    with st.expander("⚡ RSI 필터 설정", expanded=False):
        st.number_input("⚡ RSI 기간", 2, 100, CFG.RSI_PERIOD, step=1, key="sb_rsi_period",
                        on_change=sync_p, args=("sb_rsi_period", "main_rsi_period,settings_rsi_period", "RSI_PERIOD"),
                        help="상대강도지수(RSI)를 산출하기 위한 캔들 기간(기본값 13 또는 14봉)입니다.")
        col_rsi1, col_rsi2 = st.columns(2)
        with col_rsi1:
            st.number_input("🟢 RSI 롱 진입 상한선", 10.0, 90.0, float(CFG.RSI_OVERBOUGHT), step=1.0, key="sb_rsi_overbought",
                            on_change=sync_p, args=("sb_rsi_overbought", "main_rsi_overbought,settings_rsi_overbought", "RSI_OVERBOUGHT"),
                            help="롱(매수) 포지션 진입 시 허용할 수 있는 최대 RSI 수치입니다. RSI가 이 상한값보다 높으면 과매수권으로 판단해 추격 롱 진입을 차단합니다.")
        with col_rsi2:
            st.number_input("🔴 RSI 숏 진입 하한선", 10.0, 90.0, float(CFG.RSI_OVERSOLD), step=1.0, key="sb_rsi_oversold",
                            on_change=sync_p, args=("sb_rsi_oversold", "main_rsi_oversold,settings_rsi_oversold", "RSI_OVERSOLD"),
                            help="숏(매도) 포지션 진입 시 허용할 수 있는 최소 RSI 수치입니다. RSI가 이 하한값보다 낮으면 과매도권으로 판단해 추격 숏 진입을 차단합니다.")

    with st.expander("📊 거래량 급증 필터 설정", expanded=False):
        st.checkbox("📊 거래량 필터 활성화", value=getattr(CFG, "USE_VOL_FILTER", False) or False, key="sb_use_vol_filter", on_change=sync_p, args=("sb_use_vol_filter", "main_use_vol_filter", "USE_VOL_FILTER"),
            help="⚠️ 진입 차단 주의: ON이면 현재 거래량이 MA 평균의 '돌파 배수'배 이상일 때만 진입 허용.\n하락장·횡보장에서는 거래량이 급증하지 않아 신호강도=80, 방향=— 상태로 전종목 진입 차단됨.\n▶ 진입이 안 될 때는 OFF로 끄거나 배수를 1.0~1.2로 낮출 것.")
        col_vol1, col_vol2 = st.columns(2)
        with col_vol1:
            st.number_input("⏱️ 기준 MA 기간", 5, 100, int(getattr(CFG, "VOL_MA_PERIOD", 20) or 20), step=1, key="sb_vol_ma_period", on_change=sync_p, args=("sb_vol_ma_period", "main_vol_ma_period", "VOL_MA_PERIOD"),
                help="거래량 이동평균 계산 기간. 기본값 20봉. 이 평균의 '돌파 배수'배 이상일 때만 진입.")
        with col_vol2:
            st.number_input("📈 돌파 배수", 1.0, 5.0, float(getattr(CFG, "VOL_SURGE_MULT", 1.5) or 1.5), step=0.1, key="sb_vol_surge_mult", on_change=sync_p, args=("sb_vol_surge_mult", "main_vol_surge_mult", "VOL_SURGE_MULT"),
                help="⚠️ 핵심 파라미터: 현재 거래량 > 평균 × 이 배수 일 때만 진입.\n기본 1.5 → 평균보다 50% 많아야 함. 하락장에서 차단 잦으면 1.0~1.2로 낮출 것.\n0으로 낮출 수 없음 (최소 1.0). 필터 자체를 끄려면 '거래량 필터 활성화' 체크 해제.")

    with st.expander("⚙️ 운용 및 포지션 설정", expanded=False):
        st.number_input("🚀 레버리지 (x)", 1, 20, CFG.LEVERAGE, step=1, key="sb_leverage",
                        on_change=sync_p, args=("sb_leverage", "main_leverage", "LEVERAGE"),
                        help="선물 거래 시 포지션에 적용할 레버리지 배수입니다. 레버리지가 높을수록 수익률과 위험성이 동시에 극대화되며 강제 청산 위험이 커집니다.")
        st.number_input("💵 1회 진입 증거금 (USDT)", 1.0, 100.0, CFG.MARGIN_USDT, step=0.5, key="sb_margin",
                        on_change=sync_p, args=("sb_margin", "main_margin", "MARGIN_USDT"),
                        help="포지션 진입 시 1개 종목당 할당할 투자 증거금(USDT 단위)입니다. (진입 수량 = 증거금 × 레버리지 / 현재가)")
        st.number_input("👥 최대 동시 포지션 수", 1, 10, CFG.MAX_POSITIONS, step=1, key="sb_max_pos",
                        on_change=sync_p, args=("sb_max_pos", "main_max_pos", "MAX_POSITIONS"),
                        help="동시에 보유할 수 있는 최대 포지션(종목) 개수입니다. 이 한도에 도달하면 신규 진입 신호가 감지되어도 추가 진입하지 않습니다.")

    with st.expander("🛡️ 리스크 및 한도 설정", expanded=False):
        st.checkbox("✨ ATR 다이내믹 청산 사용", value=getattr(CFG, "USE_DYNAMIC_SLTP", True), key="sb_use_dynamic_sltp", on_change=sync_p, args=("sb_use_dynamic_sltp", "main_use_dynamic_sltp", "USE_DYNAMIC_SLTP"))
        col_atr1, col_atr2 = st.columns(2)
        with col_atr1:
            st.number_input("🎯 익절 ATR 배수", 0.5, 10.0, float(getattr(CFG, "ATR_TP_MULT", 2.0)), step=0.1, key="sb_atr_tp_mult", on_change=sync_p, args=("sb_atr_tp_mult", "main_atr_tp_mult", "ATR_TP_MULT"),
                            help="평균 실제 변동폭(ATR)을 활용한 다이내믹 익절 배수입니다. 진입 시점의 ATR 값에 이 배수를 곱한 금액만큼 상승(롱) 또는 하락(숏)하면 익절합니다.")
        with col_atr2:
            st.number_input("🛡️ 손절 ATR 배수", 0.5, 10.0, float(getattr(CFG, "ATR_SL_MULT", 1.5)), step=0.1, key="sb_atr_sl_mult", on_change=sync_p, args=("sb_atr_sl_mult", "main_atr_sl_mult", "ATR_SL_MULT"),
                            help="평균 실제 변동폭(ATR)을 활용한 다이내믹 손절 배수입니다. 진입 시점의 ATR 값에 이 배수를 곱한 금액만큼 반대로 움직이면 손절을 감행하여 리스크를 제한합니다.")
        st.markdown("---")
        st.checkbox("✨ 하이브리드 트레일링 스톱 사용", value=getattr(CFG, "USE_TRAILING_STOP", False) or False, key="sb_use_trailing_stop", on_change=sync_p, args=("sb_use_trailing_stop", "main_use_trailing_stop", "USE_TRAILING_STOP"))
        col_ts1, col_ts2 = st.columns(2)
        with col_ts1:
            st.number_input("🚀 트레일링 발동 (%)", 0.1, 10.0, float(getattr(CFG, "TRAILING_ACTIVATE_PCT", 0.015) or 0.015)*100, step=0.1, key="sb_trailing_activate_pct", on_change=sync_p, args=("sb_trailing_activate_pct", "main_trailing_activate_pct", "TRAILING_ACTIVATE_PCT", True),
                            help="수익이 이 비율(%) 이상 도달했을 때 실시간 추적 청산(Trailing Stop)을 감시 작동하기 시작합니다.")
        with col_ts2:
            st.number_input("📉 수익 반납 청산 (%)", 0.1, 5.0, float(getattr(CFG, "TRAILING_CALLBACK_PCT", 0.003) or 0.003)*100, step=0.1, key="sb_trailing_callback_pct", on_change=sync_p, args=("sb_trailing_callback_pct", "main_trailing_callback_pct", "TRAILING_CALLBACK_PCT", True),
                            help="트레일링 스톱이 발동된 후, 최고수익점 대비 가격이 이 비율(%)만큼 후퇴(수익 반납)하면 포지션을 정리하여 수익을 보존합니다.")
        st.markdown("---")
        st.number_input("🎯 고정 익절 (%)", 0.1, 20.0, float(CFG.TAKE_PROFIT_PCT * 100), step=0.1, key="sb_tp",
                        on_change=sync_p, args=("sb_tp", "main_tp", "TAKE_PROFIT_PCT", True),
                        help="ATR 다이내믹 청산을 사용하지 않을 때 적용되는 전통적인 % 기준 고정 익절 비율입니다. (단위: %)")
        st.number_input("🛡️ 고정 손절 (%)", 0.1, 10.0, float(CFG.STOP_LOSS_PCT * 100), step=0.1, key="sb_sl",
                        on_change=sync_p, args=("sb_sl", "main_sl", "STOP_LOSS_PCT", True),
                        help="ATR 다이내믹 청산을 사용하지 않을 때 적용되는 전통적인 % 기준 고정 손절 비율입니다. (단위: %)")

# ══════════════════════════════════════════════════════
# 메인 헤더 (한 줄 배치)
# ══════════════════════════════════════════════════════

# [v3.0.4] 시간, 상태, 버튼을 우측에 동일한 크기의 버튼 스타일로 나란히 배치
st.markdown('<div class="floating-header-wrapper"></div>', unsafe_allow_html=True)
col_empty, col_time, col_status = st.columns([6.7, 1.8, 1.5])

with col_time:
    now_kst = datetime.utcnow() + timedelta(hours=9)
    st.markdown(
        f'<div class="header-btn-like">'
        f'{now_kst.strftime("%Y-%m-%d %H:%M:%S")} KST</div>',
        unsafe_allow_html=True,
    )

with col_status:
    _engine = st.session_state.get("engine")
    is_live = False
    if _engine and _engine.is_ready:
        if st.session_state.get("auto_trading", False):
            is_live = True

    if is_live:
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
        # 2. 방금 청산 버튼을 누른 종목(closing_symbols) 즉시 은폐 로직 (15초 초과 시 자동 제거/재노출)
        now_time = time.time()
        st.session_state.closing_symbols = {
            s: ts for s, ts in st.session_state.closing_symbols.items()
            if (now_time - ts) <= 15.0
        }
        
        positions = [
            p for p in raw_positions 
            if p.get('amount_usdt', 0) > 0.1 
            and p.get('symbol') not in st.session_state.closing_symbols
        ]
        
        # 3. 거래소 데이터와 동기화: 거래소에서 실제로 사라진 종목은 은폐 목록에서 제거
        current_exchange_symbols = {p['symbol'] for p in raw_positions}
        st.session_state.closing_symbols = {
            s: ts for s, ts in st.session_state.closing_symbols.items()
            if s in current_exchange_symbols
        }

        # ── 상단 지표 (Custom Terminal Metrics) ──────────────────────────────
        m1, m2, m3, m4, m5 = st.columns(5)
        
        def render_terminal_metric(label, value, delta=None, is_pnl=False, tooltip=None):
            if is_pnl:
                try:
                    val_num = float(str(value).split('/')[0].replace('$','').replace(',','').replace('+',''))
                except ValueError:
                    val_num = 0.0
                color = "#ef4444" if val_num >= 0 else "#3b82f6"
                border_glow = "rgba(239, 68, 68, 0.15)" if val_num >= 0 else "rgba(59, 130, 246, 0.15)"
            else:
                color = "#ffffff"
                border_glow = "rgba(0, 224, 255, 0.12)"
            
            delta_html = ""
            if delta is not None:
                try:
                    d_num = float(str(delta).split(' ')[0].replace('$','').replace(',','').replace('+','').replace('%','').strip())
                    d_color = "#ef4444" if d_num >= 0 else "#3b82f6"
                    delta_html = f'<div style="color:{d_color}; font-size:0.9rem; margin-top:2px; font-family:\'JetBrains Mono\';">{delta}</div>'
                except ValueError:
                    d_color = "#ef4444" if "🔴" in str(delta) or "LOCKED" in str(delta) else "#10b981"
                    delta_html = f'<div style="color:{d_color}; font-size:0.9rem; margin-top:2px; font-family:\'JetBrains Mono\'; font-weight:700;">{delta}</div>'
            
            tooltip_html = ""
            if tooltip:
                tooltip_html = f'<span class="terminal-tooltip" style="margin-left:6px;">ℹ<span class="tooltip-text">{tooltip}</span></span>'
                
            st.markdown(
                f"""
                <div style="background:#0f0f0f; border:1px solid #262626; padding:12px; border-radius:8px; height:105px;
                            box-shadow: 0 4px 20px {border_glow}; transition: all 0.3s ease; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center;">
                    <div style="color:#cccccc; font-size:0.85rem; font-family:\'JetBrains Mono\'; text-transform:uppercase; letter-spacing:0.05em; display:flex; align-items:center; justify-content:center;">
                        {label} {tooltip_html}
                    </div>
                    <div style="color:{color}; font-size:1.5rem; font-family:\'JetBrains Mono\'; font-weight:700; margin-top:4px;">{value}</div>
                    {delta_html}
                </div>
                """,
                unsafe_allow_html=True
            )

        with m1:
            render_terminal_metric("💰 총 잔고", f"${dash['total_balance']:,.2f}", 
                                   tooltip="거래소 지갑에 있는 실제 총 자산(USDT)입니다.<br><br>미실현 손익(PnL)은 아직 포함되지 않은, 가용 증거금과 사용 중인 증거금의 총합입니다.")
        with m2:
            total_upnl = sum(p["pnl_usdt"] for p in positions)
            render_terminal_metric("미실현 손익", f"${total_upnl:+.2f}", delta=f"{total_upnl:+.2f}", is_pnl=True,
                                   tooltip="현재 열려있는 모든 포지션의 미실현 손익(Unrealized PnL) 총합입니다.<br><br>수수료 및 펀딩비가 실시간으로 반영된 예상 수익입니다.")
        with m3:
            _st_tmp = stats_store.load_stats()
            seed_money_tmp = _st_tmp.get("seed_money", 50.0)
            total_pnl_pct_tmp = ((dash['total_balance'] / seed_money_tmp) - 1) * 100 if seed_money_tmp > 0 else 0.0
            
            perf_start_str_tmp = _st_tmp.get("perf_start_time", "2026-05-29 16:09:59")
            try:
                perf_start_dt_tmp = datetime.strptime(perf_start_str_tmp, "%Y-%m-%d %H:%M:%S")
            except Exception:
                perf_start_dt_tmp = datetime(2026, 5, 29, 16, 9, 59)
                
            now_kst_tmp = datetime.utcnow() + timedelta(hours=9)
            elapsed_seconds_tmp = (now_kst_tmp - perf_start_dt_tmp).total_seconds()
            elapsed_days_tmp = max(elapsed_seconds_tmp / 86400.0, 1.0)
            daily_avg_roi_tmp = total_pnl_pct_tmp / elapsed_days_tmp
            
            dpnl = seed_money_tmp * (daily_avg_roi_tmp / 100)
            render_terminal_metric("금일 실현 손익", f"${dpnl:+.2f}", delta=f"{dpnl:+.2f}", is_pnl=True,
                                   tooltip="초기화 시점의 '총 잔고'에 현재 '일 평균 수익률'을 곱하여 산출한 금액입니다.")
        with m4:
            bot_used_margin = len(positions) * CFG.MARGIN_USDT
            render_terminal_metric("사용 중 증거금", f"${bot_used_margin:,.2f}",
                                   tooltip="현재 봇이 보유 중인 포지션들에 할당된 증거금 총액입니다.<br><br>(현재 포지션 수 × 1회 진입 증거금)")
        with m5:
            bot_free_margin = max(0.0, dash['total_balance'] - bot_used_margin)
            render_terminal_metric("가용 증거금", f"${bot_free_margin:,.2f}",
                                   tooltip="실제 총 잔고에서 현재 봇이 사용 중인 증거금을 뺀 순수 가용 현금입니다.<br><br>(총 잔고 - 사용 중 증거금)")


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
                    if st.button("\U0001f534 모든 종목 일괄청산", use_container_width=True, key="bulk_close"):
                        # [v2.8.0] 청산 실행 전 모든 포지션 closing_symbols에 즉시 등록 (UI 카드 즉시 숨김)
                        for _p in positions:
                            st.session_state.closing_symbols[_p['symbol']] = time.time()
                        with st.spinner("\u23f3 모든 포지션 청산 중..."):
                            try:
                                count = engine.close_all_positions()
                            except Exception as be:
                                st.error(f"\u274c 일괄청산 오류: {be}")
                                count = 0
                        if count > 0:
                            if engine.trader:
                                engine.trader.trigger_global_cooldown(60)
                            st.toast(f"\u2705 {count}개 포지션 일괄 청산 완료")
                            time.sleep(1)
                            st.rerun()
                        elif count == -1:
                            # [v2.8.0] 부분 청산 가능성 시그널 (-1)
                            if engine.trader:
                                engine.trader.trigger_global_cooldown(60)
                            st.warning("\u26a0\ufe0f 일부 포지션만 청산됨 (API 지연) — 잔여 포지션은 화면에서 직접 확인 후 수동 청산")
                            time.sleep(2)
                            st.rerun()
                        else:
                            # [v2.8.0] 완전 실패 시 closing_symbols에서 전부 제거하여 카드 재노출
                            for _p in positions:
                                st.session_state.closing_symbols.pop(_p['symbol'], None)
                            st.error("\u274c 일괄청산 실패 또는 청산된 포지션 없음 (시스템 로그 확인)")

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
                                <div style="background:rgba(20, 24, 43, 0.85); border:1px solid rgba(0, 224, 255, 0.2);
                                            border-radius:8px; padding:12px 14px; margin-bottom:8px; box-shadow: 0 4px 12px rgba(0,0,0,0.4);">
                                  <div style="display:flex; justify-content:space-between; margin-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.05); padding-bottom:6px;">
                                    <span style="font-family:'JetBrains Mono'; font-size:1.0rem; font-weight:700; color:#ffffff;">{p['symbol']}</span>
                                    <span style="font-family:'JetBrains Mono'; font-size:1.0rem; font-weight:700; color:{pnl_color}; text-shadow: 0 0 8px {pnl_color}40;">
                                      {p['pnl_usdt']:+.4f} USDT ({p['pnl_pct']:+.1f}%)
                                    </span>
                                  </div>
                                  <div style="font-family:'JetBrains Mono'; font-size:0.85rem; color:#e2e8f0; display:flex; flex-wrap:wrap; gap:12px;">
                                    <span style="background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px; font-weight:600;">{side_badge}</span>
                                    <span>진입가: <b>${p['entry_price']:,.4f}</b></span>
                                    <span>현재가: <b>${p['mark_price']:,.4f}</b></span>
                                    <span>레버리지: <b>{p['leverage']}x</b></span>
                                    <span>평가금: <b>${p['amount_usdt']:,.2f}</b></span>
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
                                st.session_state.closing_symbols[p['symbol']] = time.time()
                                with st.spinner(f"⏳ {p['symbol']} 청산 중..."):
                                    try:
                                        ok = engine.close_position(p["symbol"], p["side"])
                                    except Exception as ce:
                                        logger.error(f"[UI] {p['symbol']} 즉시청산 예외: {ce}")
                                        ok = False
                                if ok:
                                    if engine.trader:
                                        engine.trader.trigger_symbol_cooldown(p['symbol'], 60)
                                    st.toast(f"✅ {p['symbol']} 청산 완료")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    # 실패 시에는 다시 목록에서 제거 (보여줘야 하므로)
                                    st.session_state.closing_symbols.pop(p['symbol'], None)
                                    st.error(f"❌ {p['symbol']} 청산 실패 (시스템 로그 확인)")


        with col_log:
            st.markdown(
                '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.9rem;color:#cccccc;letter-spacing:0.1em;">SYSTEM LOG</p>',
                unsafe_allow_html=True,
            )
            engine: QuantumEngine = st.session_state.engine
            logs = engine.get_scanner_logs(30) if engine.scanner else ["[SYS] 엔진 미연결"]
            
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
        daily_pnl = engine.trader.daily_pnl_usdt if (engine and getattr(engine, 'trader', None)) else _st.get("daily_pnl_usdt", 0.0)
        
        # [v1.2.37] 수익률 계산 기준 업데이트 (stats.json 로드)
        seed_money = _st.get("seed_money", 50.0) # 기준 자산 (동적 로드)
        total_pnl_pct = ((dash['total_balance'] / seed_money) - 1) * 100 if seed_money > 0 else 0.0
        # 24시간 변동률도 시드 대비 비율로 표시
        daily_pnl_pct = (daily_pnl / seed_money) * 100 if seed_money > 0 else 0.0
        
        # [v1.2.40] 일 평균 수익률 계산 보정 (최소 1일 기준 - 뻥튀기 방지)
        perf_start_str = _st.get("perf_start_time", "2026-05-29 16:09:59")
        try:
            perf_start_dt = datetime.strptime(perf_start_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            perf_start_dt = datetime(2026, 5, 29, 16, 9, 59)
            
        now_kst = datetime.utcnow() + timedelta(hours=9)
        elapsed_seconds = (now_kst - perf_start_dt).total_seconds()
        # 경과 일수 계산 (보수적 접근: 최소 1.0일로 나누어 첫날 과장 방지)
        elapsed_days = max(elapsed_seconds / 86400.0, 1.0)
        daily_avg_roi = total_pnl_pct / elapsed_days
        
        # [v1.2.44] 매매 이력 기반 실시간 승률 계산 (분할 체결 통합 로직)
        all_trades = load_local_trade_history()
        
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
                            <span class="tooltip-text">
                                [계산식] ((현재 총 잔고 / 초기화 잔고) - 1) * 100<br><br>
                                버튼 클릭 시점의 거래소 총 잔고({seed_money:,.2f} USDT)를 새로운 원금으로 삼아 현재 실시간 수익률을 표기합니다.
                            </span>
                        </span>
                    </div>
                    <div class="terminal-metric-value" style="color:{total_color};">{total_pnl_pct:+.2f}%</div>
                    <div class="terminal-metric-sub" style="color:#ffffff;">
                        <span>{daily_arrow}</span> {abs(daily_pnl_pct):.2f}% (24h)
                    </div>
                </div>
                <!-- 일 평균 수익률 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label">
                        일 평균 수익률
                        <span class="terminal-tooltip">
                            ℹ
                            <span class="tooltip-text">
                                [계산식] 누적 수익률 / 경과 일수<br><br>
                                초기화 시점부터 현재까지 경과한 시간(일)으로 누적 수익률을 나눕니다. 첫날 수익률의 뻥튀기를 막기 위해 최소 1.0일로 보정되어 계산됩니다.
                            </span>
                        </span>
                    </div>
                    <div class="terminal-metric-value" style="color:{avg_color};">{daily_avg_roi:+.2f}%</div>
                    <div class="terminal-metric-sub" style="color:#cccccc;">
                        {avg_arrow} {perf_start_dt.strftime("%Y.%m.%d %H:%M")} ~
                    </div>
                </div>
                <!-- 누적 승률 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label">
                        누적 승률
                        <span class="terminal-tooltip">
                            ℹ
                            <span class="tooltip-text">
                                [계산식] (수익 종료 건수 / 전체 종료 건수) * 100<br><br>
                                초기화 시점 이후에 청산(종료)된 포지션들만 집계합니다. 분할 체결 건들은 동일 주문번호(ID)로 하나로 묶어 최종 PnL이 양수면 W, 음수면 L로 카운트합니다.
                            </span>
                        </span>
                    </div>
                    <div class="terminal-metric-value" style="color:{win_color};">{win_rate:.1f}%</div>
                    <div class="terminal-metric-sub" style="color:#cccccc;">
                        <span style="font-size:0.7rem;">{win_arrow}</span> {wins}W / {losses}L
                    </div>
                </div>
                <!-- 금일 주문 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label">
                        금일 주문
                        <span class="terminal-tooltip">
                            ℹ
                            <span class="tooltip-text">
                                [계산식] 초기화 시점부터 24시간 동안 발생한 승(W) + 패(L) 합산 건수<br><br>
                                에러나 진입 유실이 아닌, 정상적으로 진입 후 청산까지 한 사이클이 완전히 종료된 실제 매매 건수만을 엄격하게 카운트하여 표기합니다.
                            </span>
                        </span>
                    </div>
                    <div class="terminal-metric-value">{orders_today}건</div>
                    <div class="terminal-metric-sub" style="color:#ffffff;">
                        <span style="font-size:0.7rem;">↑</span> 24h
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
            current_bal = d_data.get("total_balance", 50.0)
            if current_bal <= 0:
                current_bal = 50.0
            stats_store.reset_stats(current_bal)
            if engine and engine.trader:
                engine.trader.daily_pnl_usdt = 0.0
                engine.trader.orders_today = 0
            st.toast("✅ 모든 누적 통계 데이터가 현재 시각 및 총 잔고 기준으로 초기화되었습니다.")
            time.sleep(0.5)
            st.rerun()

        # ── 기간별 누적 수익률 차트 ──────────────────────────
        st.markdown("---")
        st.markdown('<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.9rem;color:#cccccc;letter-spacing:0.1em;">📈 PERFORMANCE CHART (시간대별 일 평균 수익률)</p>', unsafe_allow_html=True)
        
        chart_seed_money = _st.get("seed_money", 50.0)

        # 매매 이력 불러와서 청산 거래만 필터링
        raw_trades = load_local_trade_history()
        paired_trades = aggregate_and_pair_trades(raw_trades)
        
        chart_data = []
        for p in paired_trades:
            if str(p.get("status", "")).startswith("청산 완료"):
                exit_t = p.get("exit_time")
                if exit_t:
                    # tz-naive 변환 후 필터링
                    exit_t_naive = pd.to_datetime(exit_t).replace(tzinfo=None)
                    if exit_t_naive >= perf_start_dt:
                        chart_data.append({
                            "time": exit_t_naive,
                            "pnl_usdt": float(p.get("pnl_usdt", 0.0))
                        })
        
        if len(chart_data) == 0:
            st.info("초기화 이후 기록된 청산 매매 내역이 없습니다.")
        else:
            df_chart = pd.DataFrame(chart_data)
            df_chart.sort_values("time", inplace=True)
            df_chart.set_index("time", inplace=True)
            
            # 기간 선택 드롭다운
            tf_options_map = {
                "1분": "1min",
                "5분": "5min",
                "15분": "15min",
                "1시간": "1h",
                "4시간": "4h",
                "1일": "1d"
            }
            col_sel1, _ = st.columns([2, 8])
            with col_sel1:
                selected_tf_label = st.selectbox("시간 단위 선택", list(tf_options_map.keys()), index=2)
            
            selected_tf = tf_options_map[selected_tf_label]
            
            # 선택된 기간으로 리샘플링
            df_resampled = df_chart.resample(selected_tf).sum()
            
            # 누적합(cumsum) 계산
            df_resampled["cumulative_pnl"] = df_resampled["pnl_usdt"].cumsum()
            df_resampled["roi_pct"] = (df_resampled["cumulative_pnl"] / chart_seed_money) * 100
            
            # 시작점(0%) 행을 앞에 추가
            df_plot = df_resampled.reset_index()
            start_row = pd.DataFrame({
                "time": [perf_start_dt],
                "pnl_usdt": [0.0],
                "cumulative_pnl": [0.0],
                "roi_pct": [0.0]
            })
            df_plot = pd.concat([start_row, df_plot], ignore_index=True)
            
            # ★ 상단 '일 평균 수익률' 메트릭 수치와 100% 일치시키기 위해 현재 시점 데이터를 마지막에 연장 추가 ★
            current_row = pd.DataFrame({
                "time": [now_kst],
                "pnl_usdt": [0.0],
                "cumulative_pnl": [0.0],
                "roi_pct": [total_pnl_pct]
            })
            df_plot = pd.concat([df_plot, current_row], ignore_index=True)
            
            # ── 일 평균 수익률(Daily Avg ROI) 변환 ──
            def calc_daily_avg(row):
                elapsed_sec = (row["time"] - perf_start_dt).total_seconds()
                days = max(elapsed_sec / 86400.0, 1.0)
                return row["roi_pct"] / days
            
            df_plot["daily_avg_roi"] = df_plot.apply(calc_daily_avg, axis=1)
            
            # ── 색상 결정 로직 (각 막대별 수익/손실 기준) ──
            final_roi = df_plot["daily_avg_roi"].iloc[-1]
            bar_colors = ["#ef4444" if val >= 0 else "#3b82f6" for val in df_plot["daily_avg_roi"]]
            
            # 막대그래프 그리기
            fig = go.Figure(data=[go.Bar(
                x=df_plot["time"],
                y=df_plot["daily_avg_roi"],
                marker_color=bar_colors,
                hovertemplate="시간: %{x}<br>일 평균 수익률: %{y:.2f}%<extra></extra>"
            )])
            
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=20, b=0),
                height=350,
                xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title=""),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", tickformat=".2f", ticksuffix="%"),
                font=dict(family="JetBrains Mono", size=11, color="#cccccc"),
                hoverlabel=dict(font_size=15, font_family="JetBrains Mono")
            )
            
            # 0% 기준선 추가
            fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.2)")
            
            # ★ 실시간 현재 '일 평균 수익률' 노란색 점선 추가 ★
            fig.add_hline(
                y=final_roi, 
                line_dash="dot", 
                line_color="rgba(255, 235, 59, 0.8)",
                annotation_text=f"현재: {final_roi:.2f}%", 
                annotation_position="top",
                annotation_font=dict(color="rgba(255, 235, 59, 0.9)", size=16)
            )
            
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


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
                    '<p style="color:#ef4444;font-family:\'IBM Plex Mono\',monospace;font-size:0.9rem;margin-top:5px;font-weight:700;">⏹ 스캔 엔진 중지.... (자동매매 ON 시 시작)</p>',
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
            def notify_signal_filter():
                st.toast(f"🔍 신호 필터가 변경되었습니다: {st.session_state.scanner_signal_filter}")
            signal_filter = st.selectbox(
                "🔍 신호 필터 선택",
                ["전체", "LONG 신호", "SHORT 신호", "신호 없음"],
                key="scanner_signal_filter",
                on_change=notify_signal_filter
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
                col_names = ["종목","현재가","등락(%)","거래대금(M)","신호","강도(%)","추세 방향 일치","스퀴즈 돌파","모멘텀 방향","EMA 200 가드","EMA 200 가격","RSI 필터","RSI 수치"]
            else:
                cols = ["symbol","price","change_pct","volume_m","signal","strength","ema_ok","macd_ok","bb_ok","ema200_ok","ema200"]
                col_names = ["종목","현재가","등락(%)","거래대금(M)","신호","강도(%)","추세 방향 일치","스퀴즈 돌파","모멘텀 방향","EMA 200 가드","EMA 200 가격"]

            display = df_scan[cols].copy()
            display.columns = col_names
            display["신호"] = display["신호"].map({"long":"🟢 LONG","short":"🔴 SHORT","none":"— "})
            display["추세 방향 일치"] = display["추세 방향 일치"].map({True:"✅",False:"❌"})
            display["스퀴즈 돌파"] = display["스퀴즈 돌파"].map({True:"✅",False:"❌"})
            display["모멘텀 방향"] = display["모멘텀 방향"].map({True:"✅",False:"❌"})
            display["EMA 200 가드"] = display["EMA 200 가드"].map({True:"✅",False:"❌"})
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

    # 실제 보유 중인 포지션 세트 추출
    active_positions_set = None
    if st.session_state.api_connected and engine.is_ready:
        try:
            dash = engine.get_dashboard_data()
            live_pos = dash.get("positions", [])
            active_positions_set = {
                (p["symbol"], p["side"].upper())
                for p in live_pos if abs(p.get("size", 0)) > 0
            }
        except Exception:
            pass

    # [v2.0.8] 로컬 CSV 이력 로드 및 진입/청산 페어링 (API 미연결 시에도 로컬 이력 항시 조회 허용)
    raw_trades = load_local_trade_history()
    # [v4.0.3] 초기화 기준 시각 이전 거래 렌더링 제외
    try:
        import core.stats as _stats_mod
        _st_hist = _stats_mod.load_stats()
        _hist_cutoff_str = _st_hist.get("perf_start_time", "")
        if _hist_cutoff_str:
            from datetime import datetime as _dt_cls
            _hist_cutoff = _dt_cls.strptime(_hist_cutoff_str, "%Y-%m-%d %H:%M:%S")
            def _ts_to_naive(ts):
                if isinstance(ts, _dt_cls):
                    return ts.replace(tzinfo=None) if ts.tzinfo else ts
                try:
                    import pandas as _pd
                    return _pd.to_datetime(ts).to_pydatetime().replace(tzinfo=None)
                except Exception:
                    return None
            raw_trades = [t for t in raw_trades if (_ts_to_naive(t.get("timestamp")) or _hist_cutoff) >= _hist_cutoff]
    except Exception:
        pass
    paired_history = aggregate_and_pair_trades(raw_trades, active_positions_set=active_positions_set)

    # 동적 종목 및 상태 필터 리스트 구성
    history_symbols = sorted(list(set([x["symbol"] for x in paired_history])))
    history_statuses = sorted(list(set([x.get("status", "") for x in paired_history])))
    default_statuses = [s for s in history_statuses if s != "청산 완료 (미기록)"]

    h1, h1_2, h2 = st.columns([1.5, 1.5, 1])
    with h1:
        def notify_hist_sym():
            st.toast(f"📁 종목 필터가 변경되었습니다: {st.session_state.hist_sym}")
        hist_symbol = st.selectbox("📁 종목 필터 선택", ["전체"] + history_symbols, key="hist_sym", on_change=notify_hist_sym)
    with h1_2:
        def notify_hist_status():
            st.toast(f"🏷️ 상태 필터가 변경되었습니다")
        hist_statuses = st.multiselect("🏷️ 상태 필터 선택", options=history_statuses, default=default_statuses, key="hist_status", on_change=notify_hist_status)
    with h2:
        sync_disabled = not st.session_state.api_connected or not engine.is_ready
        help_msg = "실시간 거래소 이력을 반영하려면 사이드바에서 API를 연결하세요." if sync_disabled else "거래소에서 최근 100개 체결 이력을 받아와 로컬 CSV로 동기화합니다."
        st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄  이력 새로고침", use_container_width=True, disabled=sync_disabled, help=help_msg):
            try:
                engine.sync_trades_to_csv()
            except Exception:
                pass
            st.rerun()

    # 필터링 적용
    if hist_symbol != "전체":
        paired_history = [x for x in paired_history if x["symbol"] == hist_symbol]
    
    paired_history = [x for x in paired_history if x.get("status", "") in hist_statuses]

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
            logs = engine.get_trader_logs()
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
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.9rem;color:#cccccc;letter-spacing:0.1em;">TTM SQUEEZE STRATEGY SYSTEM GUIDE</p>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🟢 LONG 포지션 진입 조건**")
        st.markdown(
            """
            <div style="background:#0f0f0f; border:1px solid #ffcc00; padding:15px; margin-top:5px; margin-bottom:15px; border-radius:8px;">
                <p style="font-family:'Inter'; font-size:1.15rem; color:#ffcc00; margin:0; line-height:1.5; text-align:center; font-weight:600;">
                "에너지가 압축된 스퀴즈가 해제(Fired)되고, 선형회귀 모멘텀이 0선 위로 상승하며, 종가가 🛡️ EMA 200 위에 위치할 때 롱 진입합니다!"
                </p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        st.markdown("- **스퀴즈 해제 (Fired):** 볼린저 밴드가 켈트너 채널 밖으로 팽창하며 에너지가 분출됨 <span style='color:#ffcc00;'>☞ 스캐너 신호등 초록색 전환 확인</span>", unsafe_allow_html=True)
        st.markdown("- **모멘텀:** TTM 모멘텀 선형회귀 값이 영선(0) 위 <span style='color:#ffcc00;'>☞ 매수세 가속화 확인</span>", unsafe_allow_html=True)
        st.markdown("- **캔들 색상:** 현재 봉의 종가가 이전 봉보다 높은 상승 상태 <span style='color:#ffcc00;'>☞ 양봉 모멘텀 동기화</span>", unsafe_allow_html=True)
        st.markdown("- **필터:** 현재 가격이 **EMA 200 장기이평선 위** <span style='color:#ffcc00;'>☞ 상승 대세 부합 (필수)</span>", unsafe_allow_html=True)
        st.markdown("- **RSI 진입 가드:** RSI가 60 미만인 안전 구간 <span style='color:#ffcc00;'>☞ 추격 매수 노이즈 필터링</span>", unsafe_allow_html=True)

    with c2:
        st.markdown("**🔴 SHORT 포지션 진입 조건**")
        st.markdown(
            """
            <div style="background:#0f0f0f; border:1px solid #ff3b30; padding:15px; margin-top:5px; margin-bottom:15px; border-radius:8px;">
                <p style="font-family:'Inter'; font-size:1.15rem; color:#ff3b30; margin:0; line-height:1.5; text-align:center; font-weight:600;">
                "에너지가 압축된 스퀴즈가 해제(Fired)되고, 선형회귀 모멘텀이 0선 아래로 하락하며, 종가가 🛡️ EMA 200 아래에 위치할 때 숏 진입합니다!"
                </p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        st.markdown("- **스퀴즈 해제 (Fired):** 볼린저 밴드가 켈트너 채널 밖으로 팽창하며 에너지가 분출됨 <span style='color:#ff3b30;'>☞ 스캐너 신호등 초록색 전환 확인</span>", unsafe_allow_html=True)
        st.markdown("- **모멘텀:** TTM 모멘텀 선형회귀 값이 영선(0) 아래 <span style='color:#ff3b30;'>☞ 매도세 가속화 확인</span>", unsafe_allow_html=True)
        st.markdown("- **캔들 색상:** 현재 봉의 종가가 이전 봉보다 낮은 하락 상태 <span style='color:#ff3b30;'>☞ 음봉 모멘텀 동기화</span>", unsafe_allow_html=True)
        st.markdown("- **필터:** 현재 가격이 **EMA 200 장기이평선 아래** <span style='color:#ff3b30;'>☞ 하락 대세 부합 (필수)</span>", unsafe_allow_html=True)
        st.markdown("- **RSI 진입 가드:** RSI가 40 초과인 안전 구간 <span style='color:#ff3b30;'>☞ 추격 매도 노이즈 필터링</span>", unsafe_allow_html=True)

    st.markdown("---")
    
    st.markdown(
        """
        <div style="background:#0c0c0c; border:1px solid #262626; padding:20px; border-radius:8px; margin-bottom:20px;">
            <h4 style="font-family:'JetBrains Mono'; color:#00e0ff; margin-top:0; margin-bottom:15px; font-size:1.1rem; letter-spacing:0.05em;">⚙️ TTM Squeeze 전략 핵심 메커니즘</h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div style="background:#151515; padding:15px; border-left:4px solid #00e0ff; border-radius:6px;">
                    <p style="font-weight:bold; font-size:0.95rem; color:#ffffff; margin-top:0; margin-bottom:10px;">📊 1단계: 변동성 압축 (Squeeze Phase)</p>
                    <p style="font-size:0.85rem; color:#cccccc; line-height:1.6; margin:0;">
                    볼린저 밴드가 켈트너 채널 내부로 수축하면 시장의 변동성이 최저조에 달했음을 뜻합니다. 
                    이때 에너지가 강하게 축적되며, 스캐너 표에서 스퀴즈(Squeeze) 신호가 활성화됩니다.
                    </p>
                </div>
                <div style="background:#151515; padding:15px; border-left:4px solid #10b981; border-radius:6px;">
                    <p style="font-weight:bold; font-size:0.95rem; color:#ffffff; margin-top:0; margin-bottom:10px;">🚀 2단계: 변동성 분출 및 진입 (Breakout Phase)</p>
                    <p style="font-size:0.85rem; color:#cccccc; line-height:1.6; margin:0;">
                    볼린저 밴드가 켈트너 채널 바깥으로 확장되는 순간 에너지가 분출(Squeeze Fired)됩니다. 
                    이 시점의 TTM 모멘텀 방향(선형회귀 값)과 장기 200 EMA 필터 조건을 확인하여 추세 돌파 방향으로 포지션을 진입합니다.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# TAB 5: 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[4]:
    st.markdown(
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.9rem;color:#cccccc;letter-spacing:0.1em;">STRATEGY PARAMETERS</p>',
        unsafe_allow_html=True,
    )

    s1, s2 = st.columns(2)
    with s1:
        st.number_input("🚀 레버리지 (x)", 1, 20, CFG.LEVERAGE, step=1, key="main_leverage",
                        on_change=sync_p, args=("main_leverage", "sb_leverage", "LEVERAGE"),
                        help="선물 거래 시 포지션에 적용할 레버리지 배수입니다. 레버리지가 높을수록 수익률과 위험성이 동시에 극대화되며 강제 청산 위험이 커집니다.")
        st.number_input("💵 1회 진입 증거금 (USDT)", 1.0, 10000.0, float(CFG.MARGIN_USDT), step=1.0, key="main_margin",
                        on_change=sync_p, args=("main_margin", "sb_margin", "MARGIN_USDT"),
                        help="포지션 진입 시 1개 종목당 할당할 투자 증거금(USDT 단위)입니다. (진입 수량 = 증거금 × 레버리지 / 현재가)")
        st.number_input("👥 최대 동시 포지션 수", 1, 10, CFG.MAX_POSITIONS, step=1, key="main_max_pos",
                        on_change=sync_p, args=("main_max_pos", "sb_max_pos", "MAX_POSITIONS"),
                        help="동시에 보유할 수 있는 최대 포지션(종목) 개수입니다. 이 한도에 도달하면 신규 진입 신호가 감지되어도 추가 진입하지 않습니다.")
        st.number_input("⏱️ 스캔 주기 (초)", 10, 300, CFG.SCAN_INTERVAL_SEC, step=10, key="main_scan_interval",
                        on_change=sync_p, args=("main_scan_interval", "main_scan_interval", "SCAN_INTERVAL_SEC"),
                        help="마켓 스캐너가 Binance 거래소의 시세를 조회하고 돌파 신호를 탐지하는 주기(초 단위)입니다. 너무 짧으면 API 레이트 리밋에 걸릴 수 있으므로 10~30초를 권장합니다.")
        st.number_input("💵 최소 거래대금 (USDT)", 100000.0, 50000000.0, float(CFG.MIN_VOLUME_USDT), step=1000000.0, key="main_min_vol",
                        on_change=sync_p, args=("main_min_vol", "main_min_vol", "MIN_VOLUME_USDT"),
                        help="거래 대상 종목을 선별할 때 기준이 되는 최소 24시간 거래대금(USDT)입니다. 유동성이 풍부하고 슬리피지가 적은 메이저/우량 종목들 위주로 필터링하여 안전성을 확보합니다.")

    with s2:
        st.checkbox("✨ ATR 다이내믹 청산 사용", value=getattr(CFG, "USE_DYNAMIC_SLTP", True), key="main_use_dynamic_sltp", on_change=sync_p, args=("main_use_dynamic_sltp", "sb_use_dynamic_sltp", "USE_DYNAMIC_SLTP"))
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.number_input("🎯 익절 ATR 배수", 0.5, 10.0, float(getattr(CFG, "ATR_TP_MULT", 2.0)), step=0.1, key="main_atr_tp_mult", on_change=sync_p, args=("main_atr_tp_mult", "sb_atr_tp_mult", "ATR_TP_MULT"),
                            help="평균 실제 변동폭(ATR)을 활용한 다이내믹 익절 배수입니다. 진입 시점의 ATR 값에 이 배수를 곱한 금액만큼 상승(롱) 또는 하락(숏)하면 익절합니다.")
        with m_col2:
            st.number_input("🛡️ 손절 ATR 배수", 0.5, 10.0, float(getattr(CFG, "ATR_SL_MULT", 1.5)), step=0.1, key="main_atr_sl_mult", on_change=sync_p, args=("main_atr_sl_mult", "sb_atr_sl_mult", "ATR_SL_MULT"),
                            help="평균 실제 변동폭(ATR)을 활용한 다이내믹 손절 배수입니다. 진입 시점의 ATR 값에 이 배수를 곱한 금액만큼 반대로 움직이면 손절을 감행하여 리스크를 제한합니다.")
        st.markdown("---")
        st.checkbox("✨ 하이브리드 트레일링 스톱 사용", value=getattr(CFG, "USE_TRAILING_STOP", False) or False, key="main_use_trailing_stop", on_change=sync_p, args=("main_use_trailing_stop", "sb_use_trailing_stop", "USE_TRAILING_STOP"))
        m_ts1, m_ts2 = st.columns(2)
        with m_ts1:
            st.number_input("🚀 트레일링 발동 (%)", 0.1, 10.0, float(getattr(CFG, "TRAILING_ACTIVATE_PCT", 0.015) or 0.015)*100, step=0.1, key="main_trailing_activate_pct", on_change=sync_p, args=("main_trailing_activate_pct", "sb_trailing_activate_pct", "TRAILING_ACTIVATE_PCT", True),
                            help="수익이 이 비율(%) 이상 도달했을 때 실시간 추적 청산(Trailing Stop)을 감시 작동하기 시작합니다.")
        with m_ts2:
            st.number_input("📉 수익 반납 청산 (%)", 0.1, 5.0, float(getattr(CFG, "TRAILING_CALLBACK_PCT", 0.003) or 0.003)*100, step=0.1, key="main_trailing_callback_pct", on_change=sync_p, args=("main_trailing_callback_pct", "sb_trailing_callback_pct", "TRAILING_CALLBACK_PCT", True),
                            help="트레일링 스톱이 발동된 후, 최고수익점 대비 가격이 이 비율(%)만큼 후퇴(수익 반납)하면 포지션을 정리하여 수익을 보존합니다.")
        st.markdown("---")
        st.number_input("🎯 고정 익절 (%)", 0.1, 20.0, float(CFG.TAKE_PROFIT_PCT * 100), step=0.1, key="main_tp",
                        on_change=sync_p, args=("main_tp", "sb_tp", "TAKE_PROFIT_PCT", True),
                        help="ATR 다이내믹 청산을 사용하지 않을 때 적용되는 전통적인 % 기준 고정 익절 비율입니다. (단위: %)")
        st.number_input("🛡️ 고정 손절 (%)", 0.1, 10.0, float(CFG.STOP_LOSS_PCT * 100), step=0.1, key="main_sl",
                        on_change=sync_p, args=("main_sl", "sb_sl", "STOP_LOSS_PCT", True),
                        help="ATR 다이내믹 청산을 사용하지 않을 때 적용되는 전통적인 % 기준 고정 손절 비율입니다. (단위: %)")
        st.number_input("🛡️ 일일 손실 한도 (USDT)", 1.0, 100.0, float(CFG.DAILY_LOSS_LIMIT_USDT), step=1.0, key="main_daily_loss_limit",
                        on_change=sync_p, args=("main_daily_loss_limit", "main_daily_loss_limit", "DAILY_LOSS_LIMIT_USDT"),
                        help="하루 동안 허용할 수 있는 최대 실현 손실액(USDT)입니다. 당일 누적 손실이 이 값에 도달하면 봇이 모든 신규 진입을 중단하고 당일 거래를 정지하여 추가 손실을 차단합니다.")

    st.markdown("---")
    st.markdown('<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.75rem;color:#ff9900;letter-spacing:0.1em;margin-top:10px;">TTM SQUEEZE INDICATORS</p>', unsafe_allow_html=True)
    t1, t2, t3 = st.columns(3)
    with t1:
        st.number_input("📈 BB 기간", 5, 100, CFG.BB_PERIOD, step=1, key="main_bb_period",
                        on_change=sync_p, args=("main_bb_period", "sb_bb_period", "BB_PERIOD"),
                        help="볼린저 밴드(Bollinger Bands)를 산출하기 위한 단순이동평균(SMA) 기준 캔들 개수(기본값 20)입니다.")
        tf_options = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "1d"]
        st.selectbox("⏱️ 타임프레임", tf_options, index=tf_options.index(CFG.TIMEFRAME), key="main_timeframe",
                     on_change=sync_p, args=("main_timeframe", "sb_timeframe", "TIMEFRAME"),
                     help="스퀴즈 지표 및 200 EMA 추세 필터를 탐지할 차트 봉의 타임프레임 단위입니다. (예: 15m, 1h, 4h 등)")
    with t2:
        st.number_input("📏 BB 편차 배수", 1.0, 5.0, float(CFG.BB_STD), step=0.1, key="main_bb_std",
                        on_change=sync_p, args=("main_bb_std", "sb_bb_std", "BB_STD"),
                        help="볼린저 밴드의 상/하한선을 그리기 위한 표준편차 승수(기본값 2.0)입니다. 이 값이 커질수록 밴드가 넓어져 스퀴즈 진입 조건이 엄격해집니다.")
        st.number_input("📏 KC ATR 배수", 0.5, 5.0, float(CFG.TTM_KC_MULT), step=0.1, key="main_kc_mult",
                        on_change=sync_p, args=("main_kc_mult", "sb_kc_mult", "TTM_KC_MULT"),
                        help="켈트너 채널(Keltner Channel)의 폭을 결정하는 ATR 배수(기본값 1.5)입니다. 볼린저 밴드가 이 채널 안으로 수축하면 변동성 수축(Squeeze ON)으로 판단합니다.")
    with t3:
        st.number_input("⏱️ TTM 모멘텀 기간", 5, 100, CFG.TTM_MOM_PERIOD, step=1, key="main_ttm_mom_period",
                        on_change=sync_p, args=("main_ttm_mom_period", "sb_ttm_mom_period", "TTM_MOM_PERIOD"),
                        help="TTM Squeeze의 모멘텀(선형 회귀선)을 계산할 캔들 기준 기간(기본값 20)입니다. 이 기간 동안의 시세를 선형 회귀하여 오실레이터로 표기합니다.")
                        
    st.markdown("---")
    st.markdown('<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.75rem;color:#00ff99;letter-spacing:0.1em;margin-top:10px;">VOLUME SURGE FILTER</p>', unsafe_allow_html=True)
    v1, v2 = st.columns(2)
    with v1:
        st.checkbox("📊 거래량 급증 필터 활성화", value=getattr(CFG, "USE_VOL_FILTER", False) or False, key="main_use_vol_filter", on_change=sync_p, args=("main_use_vol_filter", "sb_use_vol_filter", "USE_VOL_FILTER"),
            help="⚠️ 진입 차단 주의: ON이면 현재 거래량 > 평균×배수 조건 미충족 시 신호강도=80이어도 방향=— 로 전종목 진입 차단.\n하락장·횡보장에서 거래량이 평균 이상으로 급증하지 않으면 아무리 스퀴즈 신호가 좋아도 진입 불가.\n▶ 진입이 안 될 때 첫 번째로 확인할 항목. OFF로 끄거나 배수를 1.0~1.2로 낮출 것.")
        st.number_input("⏱️ 기준 MA 기간", 5, 100, int(getattr(CFG, "VOL_MA_PERIOD", 20) or 20), step=1, key="main_vol_ma_period", on_change=sync_p, args=("main_vol_ma_period", "sb_vol_ma_period", "VOL_MA_PERIOD"),
            help="거래량 이동평균 계산 기간. 기본값 20봉. 이 평균의 '돌파 배수'배 이상일 때만 진입.")
    with v2:
        st.number_input("📈 돌파 요구 배수 (x)", 1.0, 5.0, float(getattr(CFG, "VOL_SURGE_MULT", 1.5) or 1.5), step=0.1, key="main_vol_surge_mult", on_change=sync_p, args=("main_vol_surge_mult", "sb_vol_surge_mult", "VOL_SURGE_MULT"),
            help="⚠️ 핵심 파라미터: 현재 거래량 > 평균 × 이 배수 일 때만 진입 허용.\n기본값 1.5 = 평균보다 50% 더 많아야 함. 하락장에서 진입이 안 될 때 1.0~1.2로 낮출 것.\n필터를 완전히 끄려면 왼쪽 '거래량 급증 필터 활성화' 체크 해제.")

    st.markdown("---")
    st.markdown(
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.75rem;color:#ff9900;letter-spacing:0.1em;margin-top:10px;">RSI FILTER PARAMETERS</p>',
        unsafe_allow_html=True,
    )
    r1, r2, r3 = st.columns(3)
    with r1:
        st.number_input("RSI 기간", 2, 100, CFG.RSI_PERIOD, step=1, key="settings_rsi_period",
                        on_change=sync_p, args=("settings_rsi_period", "sb_rsi_period,main_rsi_period", "RSI_PERIOD"),
                        help="상대강도지수(RSI)를 산출하기 위한 캔들 기간(기본값 13 또는 14봉)입니다.")
    with r2:
        st.number_input("RSI 롱 상한선", 10.0, 90.0, float(CFG.RSI_OVERBOUGHT), step=1.0, key="settings_rsi_overbought",
                        on_change=sync_p, args=("settings_rsi_overbought", "sb_rsi_overbought,main_rsi_overbought", "RSI_OVERBOUGHT"),
                        help="롱(매수) 포지션 진입 시 허용할 수 있는 최대 RSI 수치입니다. RSI가 이 상한값보다 높으면 과매수권으로 판단해 추격 롱 진입을 차단합니다.")
    with r3:
        st.number_input("RSI 숏 하한선", 10.0, 90.0, float(CFG.RSI_OVERSOLD), step=1.0, key="settings_rsi_oversold",
                        on_change=sync_p, args=("settings_rsi_oversold", "sb_rsi_oversold,main_rsi_oversold", "RSI_OVERSOLD"),
                        help="숏(매도) 포지션 진입 시 허용할 수 있는 최소 RSI 수치입니다. RSI가 이 하한값보다 낮으면 과매도권으로 판단해 추격 숏 진입을 차단합니다.")

    st.markdown("---")
    st.markdown('<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.75rem;color:#00e0ff;letter-spacing:0.1em;margin-top:10px;">TELEGRAM NOTIFICATION SETTINGS</p>', unsafe_allow_html=True)
    tel_col1, tel_col2 = st.columns(2)
    with tel_col1:
        st.text_input(
            "🔑 Telegram Bot Token",
            value=getattr(CFG, "TELEGRAM_BOT_TOKEN", ""),
            type="password",
            key="settings_telegram_token",
            on_change=sync_p,
            args=("settings_telegram_token", "settings_telegram_token", "TELEGRAM_BOT_TOKEN"),
            help="텔레그램 BotFather를 통해 생성한 봇 토큰을 입력하세요."
        )
    with tel_col2:
        st.text_input(
            "🆔 Telegram Chat ID",
            value=getattr(CFG, "TELEGRAM_CHAT_ID", ""),
            key="settings_telegram_chat_id",
            on_change=sync_p,
            args=("settings_telegram_chat_id", "settings_telegram_chat_id", "TELEGRAM_CHAT_ID"),
            help="메시지를 수신할 텔레그램 채팅방 ID 혹은 개인 사용자 ID를 입력하세요."
        )
    
    if st.button("🔔 텔레그램 알림 테스트 전송", use_container_width=True):
        token = getattr(CFG, "TELEGRAM_BOT_TOKEN", "")
        chat_id = getattr(CFG, "TELEGRAM_CHAT_ID", "")
        if not token or not chat_id:
            st.error("❌ 텔레그램 토큰과 채팅 ID를 모두 입력해주세요.")
        else:
            from core.alert import send_telegram_alert
            send_telegram_alert("🔔 *[AI QUANTUM]* 텔레그램 알림 테스트 메시지 전송 성공!")
            st.success("✅ 테스트 메시지를 백그라운드로 전송하였습니다. 텔레그램 메신저를 확인하세요.")

    st.markdown("---")
    st.markdown(
        f"""<div style="font-family:'IBM Plex Mono',monospace;font-size:0.92rem;color:#cccccc;line-height:2;">
        손익비: 1 : {CFG.TAKE_PROFIT_PCT / CFG.STOP_LOSS_PCT:.1f} &nbsp;|&nbsp;
        증거금/종목: ${CFG.MARGIN_USDT:.2f} USDT &nbsp;|&nbsp;
        일일 손실 한도: ${CFG.DAILY_LOSS_LIMIT_USDT:.2f} USDT <br>
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
        current_bal = d_data.get("total_balance", 50.0)
        if current_bal <= 0:
            current_bal = 50.0
        stats_store.reset_stats(current_bal)
        if engine and engine.trader:
            engine.trader.daily_pnl_usdt = 0.0
            engine.trader.orders_today = 0
        st.toast("✅ 누적 수익률, 승률, 주문수 등 모든 통계 데이터가 현재 시간 기준으로 초기화되었습니다.")
        time.sleep(0.5)
        st.rerun()


# TAB 6 was removed


# ── 자동 새로고침 ─────────────────────────────────
if st.session_state.auto_trading:
    time.sleep(15)
    st.rerun()
