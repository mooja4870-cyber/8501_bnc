"""
AI QUANTUM — OKX Auto-Trading Dashboard
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

from core.exchange import OKXClient
from core.scanner import Scanner
from core.trader import AutoTrader
from core.engine import QuantumEngine
from core.config import CFG
import core.stats as stats_store

load_dotenv(override=True)

# ── 페이지 설정 ───────────────────────────────────────
st.set_page_config(
    page_title="AI QUANTUM · OKX Trader",
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
        font-size: 0.65rem !important;
        letter-spacing: 0.1em !important;
        color: var(--terminal-dim) !important;
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
        font-size: 0.75rem !important;
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
        color: var(--terminal-dim) !important;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
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
        font-size: 0.8rem !important;
    }

    /* 데이터프레임 */
    [data-testid="stDataFrame"] {
        border: 1px solid var(--terminal-border) !important;
    }

    /* 로고 */
    .quantum-logo {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1rem;
        font-weight: 700;
        color: var(--terminal-accent);
        border-bottom: 2px solid var(--terminal-accent);
        padding-bottom: 5px;
        margin-bottom: 20px;
    }
    .quantum-logo span { color: var(--terminal-dim); font-weight: 400; }

    /* 상태 뱃지 */
    .badge-live {
        display: inline-flex; align-items: center; gap: 8px;
        background: #003300;
        border: 1px solid var(--terminal-green);
        padding: 4px 12px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        font-weight: 700;
        color: var(--terminal-green);
    }
    .badge-live .dot {
        width: 8px; height: 8px;
        background: var(--terminal-green);
        border-radius: 0%; /* Sharp dot */
    }
    .badge-stopped {
        display: inline-flex; align-items: center; gap: 8px;
        background: #330000;
        border: 1px solid var(--terminal-red);
        padding: 4px 12px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        color: var(--terminal-red);
    }

    /* 시스템 로그 박스 */
    .log-box {
        background: #000000;
        border: 1px solid var(--terminal-border);
        border-radius: 0px;
        padding: 10px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        color: var(--terminal-dim);
        height: 250px;
        overflow-y: auto;
        line-height: 1.5;
    }
    .log-latest {
        color: #ffffff !important;
        background: #222;
        padding: 0 4px;
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
        font-size: 0.55rem;
        color: #555;
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
        font-size: 0.55rem;
        margin-top: 2px;
        display: flex;
        align-items: center;
        gap: 2px;
    }

    /* 청산 버튼 특화 (Extreme Small & Sharp - 66% of original) */
    /* Streamlit의 마크다운-위젯 간격 및 구조를 고려한 형제 셀렉터 적용 */
    .small-btn-marker + div.stButton button,
    .small-btn-marker + div[data-testid="stButton"] button,
    div.small-btn-marker ~ div.stButton button {
        font-size: 9px !important;
        height: 16px !important;
        min-height: 16px !important;
        line-height: 1 !important;
        padding: 0 5px !important;
        border-color: var(--terminal-red) !important;
        color: var(--terminal-red) !important;
        border-radius: 0px !important;
        background: transparent !important;
        margin-top: 0px !important;
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
    </style>
    """,
    unsafe_allow_html=True,
)



# ── 세션 상태 초기화 ──────────────────────────────────

def init_session():
    defaults = {
        "engine": QuantumEngine(),
        "api_connected": False,
        "auto_trading": False,
        "allow_long": True,
        "allow_short": True,
        "active_preset": "기본 (Stable)",
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

def connect_api(api_key, secret_key, passphrase):
    if not api_key or not secret_key or not passphrase:
        return False, "❌ API 키를 모두 입력해주세요."
    
    engine: QuantumEngine = st.session_state.engine
    success, msg = engine.initialize(api_key, secret_key, passphrase)
    
    if success:
        st.session_state.api_connected = True
        return True, msg
    return False, msg

init_session()

if not st.session_state.api_connected:
    ak = os.getenv("OKX_API_KEY", "")
    sk = os.getenv("OKX_SECRET_KEY", "")
    pw = os.getenv("OKX_PASSPHRASE", "")
    if ak and sk and pw:
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
        '<div class="quantum-logo" style="letter-spacing:-0.5px;">MACD-BB-EMA<br><span style="font-size:0.75rem;">v1.1.28</span></div>',
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
            success, msg = connect_api(ak, sk, pw)
            if success:
                st.success(msg)
            else:
                st.error(msg)

    st.markdown("---")
    st.markdown(
        '<p style="font-family:IBM Plex Mono;font-size:0.65rem;color:#555;letter-spacing:0.08em;">매매 제어</p>',
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

    if engine.is_ready and engine.trader:
        engine.trader.allow_long = longs
        engine.trader.allow_short = shorts

    st.markdown("---")
    st.markdown(
        f"""<div style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;color:#444;">
        레버리지: {CFG.LEVERAGE}x ISOLATED<br>
        1회 증거금: {CFG.MARGIN_USDT} USDT<br>
        최대 포지션: {CFG.MAX_POSITIONS}개<br>
        SL: {CFG.STOP_LOSS_PCT*100:.0f}% / TP: {CFG.TAKE_PROFIT_PCT*100:.0f}%
        </div>""",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════
# 메인 헤더
# ══════════════════════════════════════════════════════

col_logo, col_time, col_status = st.columns([3, 2, 1])

with col_logo:
    st.markdown(
        '',
        unsafe_allow_html=True,
    )

with col_time:
    now_kst = datetime.utcnow() + timedelta(hours=9)
    st.markdown(
        f'<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.75rem;color:#555;margin-top:6px;">'
        f'{now_kst.strftime("%Y-%m-%d %H:%M:%S")} KST</p>',
        unsafe_allow_html=True,
    )

with col_status:
    if st.session_state.auto_trading:
        st.markdown('<div class="badge-live" style="margin-bottom:8px;"><span class="dot"></span><span>LIVE CONNECTION</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="badge-stopped" style="margin-bottom:8px;">● STOPPED</div>', unsafe_allow_html=True)
    st.markdown('<div class="refresh-btn">', unsafe_allow_html=True)
    if st.button("⟳ REFRESH", key="global_refresh", use_container_width=True):
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

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
        st.info("사이드바에서 OKX API를 연결하세요.")
    else:
        # ── 데이터 통합 조회 ──────────────────────────
        dash = engine.get_dashboard_data()
        positions = dash.get("positions", [])

        # ── 상단 지표 ──────────────────────────────
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            st.metric("💰 총 잔고 (USDT)", f"${dash['total_balance']:,.2f}")
        with m2:
            total_upnl = sum(p["pnl_usdt"] for p in positions)
            st.metric("미실현 손익", f"${total_upnl:+.2f}", delta=f"{total_upnl:+.2f}")
        with m3:
            dpnl = engine.trader.daily_pnl_usdt if engine.trader else 0.0
            st.metric("금일 실현 손익", f"${dpnl:+.2f}", delta=f"{dpnl:+.2f}")
        with m4:
            st.metric("사용 중 증거금", f"${dash['used_margin']:,.2f}")
        with m5:
            st.metric("가용 증거금", f"${dash['free_margin']:,.2f}")

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
                    st.markdown('<div class="small-btn-marker"></div>', unsafe_allow_html=True)
                    if st.button("🔴 모든 종목 일괄청산", use_container_width=True, key="bulk_close"):
                        count = engine.client.close_all_positions()
                        if count > 0:
                            st.toast(f"✅ {count}개 포지션 일괄 청산 완료")
                            time.sleep(1)
                            st.rerun()

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
                                <span style="font-family:'IBM Plex Mono';font-size:0.85rem;font-weight:600;">{p['symbol']}</span>
                                <span style="font-family:'IBM Plex Mono';font-size:0.85rem;font-weight:600;color:{pnl_color};">
                                  {p['pnl_usdt']:+.4f} USDT ({p['pnl_pct']:+.1f}%)
                                </span>
                              </div>
                              <div style="font-family:'IBM Plex Mono';font-size:0.77rem;color:#cccccc;display:flex;gap:16px;">
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
                        duration_style = "font-family:'JetBrains Mono'; font-size:0.98rem; color:#666; text-align:center; margin-bottom:4px;"
                        
                        if p.get("timestamp"):
                            entry_dt = datetime.utcfromtimestamp(p["timestamp"] / 1000)
                            diff = datetime.utcnow() - entry_dt
                            hrs, rem = divmod(int(diff.total_seconds()), 3600)
                            mins = rem // 60
                            duration_str = f"[{hrs:02d}시간 {mins:02d}분]"
                            
                            if hrs >= 3:
                                duration_style = "font-family:'JetBrains Mono'; font-size:0.98rem; color:white; background:#ff3b30; text-align:center; margin-bottom:4px; font-weight:700;"
                            
                        st.markdown(
                            f'<div style="{duration_style}">{duration_str}</div>',
                            unsafe_allow_html=True
                        )
                        st.markdown('<div class="small-btn-marker"></div>', unsafe_allow_html=True)
                        if st.button("즉시청산", key=f"close_{p['symbol']}", use_container_width=True):
                            if engine.client.close_position(p["symbol"], p["side"]):
                                st.toast(f"✅ {p['symbol']} 청산 완료")
                                time.sleep(1)
                                st.rerun()

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

        # ── 고밀도 터미널 메트릭 바 (Image 1 Style) ──────────
        _st = stats_store.load_stats()
        
        # 데이터 계산
        total_pnl = _st.get("total_pnl_usdt", 0.0)
        daily_pnl = _st.get("daily_pnl_usdt", 0.0)
        
        # 수익률 계산 (기본 자산 1000 USDT 가정 또는 잔고 기준)
        base_equity = max(dash['total_balance'] - total_pnl, 1000)
        total_pnl_pct = (total_pnl / base_equity) * 100
        daily_pnl_pct = (daily_pnl / base_equity) * 100
        
        win_rate = stats_store.get_win_rate()
        wins = _st.get("total_wins", 0)
        losses = _st.get("total_losses", 0)
        orders_today = _st.get("orders_today", 0)
        
        pnl_color = "#ef4444" if total_pnl >= 0 else "#3b82f6"
        daily_color = "#ef4444" if daily_pnl >= 0 else "#3b82f6"
        daily_arrow = "↑" if daily_pnl >= 0 else "↓"
        
        st.markdown(
            f"""
            <div class="metric-bar-container">
                <!-- 누적 수익률 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label">누적 수익률</div>
                    <div class="terminal-metric-value">{total_pnl_pct:+.2f}%</div>
                    <div class="terminal-metric-sub" style="color:{daily_color};">
                        <span>{daily_arrow}</span> {abs(daily_pnl_pct):.2f}% (24h)
                    </div>
                </div>
                <!-- 연 평균 수익률 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label">연 평균 수익률</div>
                    <div class="terminal-metric-value">{total_pnl_pct:+.2f}%</div>
                    <div class="terminal-metric-sub" style="color:#22c55e;">
                        2026.05.14 ~
                    </div>
                </div>
                <!-- 누적 승률 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label">누적 승률</div>
                    <div class="terminal-metric-value">{win_rate:.1f}%</div>
                    <div class="terminal-metric-sub" style="color:#22c55e;">
                        <span style="font-size:0.7rem;">↑</span> {wins}W / {losses}L
                    </div>
                </div>
                <!-- MDD 한도 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label">MDD 한도</div>
                    <div class="terminal-metric-value">-{CFG.MAX_DRAWDOWN_PCT*100:.0f}%</div>
                    <div class="terminal-metric-sub" style="color:#22c55e;">
                        <span style="font-size:0.7rem;">↑</span> Max Risk
                    </div>
                </div>
                <!-- 금일 주문 -->
                <div class="terminal-metric-item">
                    <div class="terminal-metric-label">금일 주문</div>
                    <div class="terminal-metric-value">{orders_today}건</div>
                    <div class="terminal-metric-sub" style="color:#22c55e;">
                        <span style="font-size:0.7rem;">↑</span> Today
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


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




# TAB 3: 매매 이력
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[2]:
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
            df_hist.columns = ["시각","종목","방향","체결가","수량","금액(USDT)","수수료","주문ID"]
            df_hist["방향"] = df_hist["방향"].map({"buy":"🟢 BUY","sell":"🔴 SELL"}).fillna(df_hist["방향"])
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


# TAB 4: 포지션 진입
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[3]:
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

    # 프리셋 정의
    PRESETS = {
        "기본 (Stable)": {
            "ema": 200, "bb_p": 20, "bb_s": 2.0, "macd_f": 12, "macd_sl": 26, "macd_si": 9
        },
        "1차 공격적 (Trend)": {
            "ema": 100, "bb_p": 20, "bb_s": 1.8, "macd_f": 10, "macd_sl": 22, "macd_si": 7
        },
        "2차 공격적 (Scalping)": {
            "ema": 50, "bb_p": 14, "bb_s": 1.5, "macd_f": 8, "macd_sl": 18, "macd_si": 5
        }
    }

    preset_name = st.selectbox("전략 프리셋 선택", list(PRESETS.keys()), index=0)
    
    if st.button("🪄 프리셋 적용"):
        p = PRESETS[preset_name]
        st.session_state.active_preset = preset_name
        CFG.EMA_PERIOD = p["ema"]
        CFG.BB_PERIOD = p["bb_p"]
        CFG.BB_STD = p["bb_s"]
        CFG.MACD_FAST = p["macd_f"]
        CFG.MACD_SLOW = p["macd_sl"]
        CFG.MACD_SIGNAL = p["macd_si"]
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

# TAB 5: 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tabs[4]:
    st.markdown(
        '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">STRATEGY PARAMETERS</p>',
        unsafe_allow_html=True,
    )

    s1, s2 = st.columns(2)
    with s1:
        CFG.LEVERAGE = st.slider("레버리지 (x)", 1, 20, CFG.LEVERAGE)
        CFG.MARGIN_USDT = st.number_input("1회 진입 증거금 (USDT)", 1.0, 10000.0, float(CFG.MARGIN_USDT), step=1.0)
        CFG.MAX_POSITIONS = st.slider("최대 동시 포지션 수", 1, 10, CFG.MAX_POSITIONS)
        sl_val = st.slider("손절 (%)", 1.0, 10.0, float(CFG.STOP_LOSS_PCT * 100), step=0.5)
        CFG.STOP_LOSS_PCT = sl_val / 100.0
    with s2:
        tp_val = st.slider("익절 (%)", 1.0, 20.0, float(CFG.TAKE_PROFIT_PCT * 100), step=0.5)
        CFG.TAKE_PROFIT_PCT = tp_val / 100.0
        CFG.MIN_VOLUME_USDT = st.number_input("최소 거래대금 (USDT)", 1_000_000.0, 50_000_000.0, float(CFG.MIN_VOLUME_USDT), step=1_000_000.0)
        CFG.SCAN_INTERVAL_SEC = st.slider("스캔 주기 (초)", 10, 300, CFG.SCAN_INTERVAL_SEC, step=10)
        mdd_val = st.slider("MDD 한도 (%)", 5.0, 50.0, float(CFG.MAX_DRAWDOWN_PCT * 100), step=1.0)
        CFG.MAX_DRAWDOWN_PCT = mdd_val / 100.0

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
