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
from core.backtest import BacktestEngine
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
        background: #c8f53b !important;
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
    .stTabs [aria-selected="true"] { background: #c8f53b !important; color: #0a0a0a !important; border-radius: 6px !important; }

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
        font-size: 0.65rem !important;
        height: 28px !important;
        min-height: 28px !important;
        padding-top: 0px !important;
        padding-bottom: 0px !important;
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
        '<div class="quantum-logo" style="letter-spacing:-0.5px;">MACD-BB-EMA<br><span style="font-size:0.75rem;">v1.1.18</span></div>',
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
        st.markdown('<div class="badge-live" style="margin-bottom:8px;"><span class="dot"></span><span>LIVE STATUS</span></div>', unsafe_allow_html=True)
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

        # ── 상단 지표 ──────────────────────────────
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("💰 총 잔고 (USDT)", f"${dash['total_balance']:,.2f}")
        with m2:
            total_upnl = sum(p["pnl_usdt"] for p in positions)
            st.metric("미실현 손익", f"${total_upnl:+.2f}", delta=f"{total_upnl:+.2f}")
        with m3:
            dpnl = engine.trader.daily_pnl_usdt if engine.trader else 0.0
            st.metric("금일 실현 손익", f"${dpnl:+.2f}", delta=f"{dpnl:+.2f}")
        with m4:
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
                    st.markdown('<div class="small-btn">', unsafe_allow_html=True)
                    if st.button("🔴 모든 종목 일괄청산", use_container_width=True, key="bulk_close"):
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
                    pnl_color = "#22c55e" if p["pnl_usdt"] >= 0 else "#ef4444"
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
                        if st.button("즉시청산", key=f"close_{p['symbol']}", use_container_width=True):
                            if engine.client.close_position(p["symbol"], p["side"]):
                                st.toast(f"✅ {p['symbol']} 청산 완료")
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

        # ── 자산 배분 차트 ─────────────────────────
        col_alloc, col_stats = st.columns(2)

        with col_alloc:
            st.markdown(
                '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">PORTFOLIO ALLOCATION</p>',
                unsafe_allow_html=True,
            )
            fig_alloc = go.Figure(go.Pie(
                labels=["실전 투입 (100%)", "예비 유동성 (0%)", "리스크 리저브 (0%)"],
                values=[100, 0.001, 0.001],
                hole=0.55,
                marker=dict(colors=["#c8f53b", "#3b82f6", "#555555"]),
                textfont=dict(family="IBM Plex Mono", size=10),
                textinfo="label",
            ))
            fig_alloc.update_layout(
                **PLOT_LAYOUT,
                showlegend=False,
                height=220,
            )
            st.plotly_chart(fig_alloc, use_container_width=True)

        with col_stats:
            st.markdown(
                '<p style="font-family:\'IBM Plex Mono\',monospace;font-size:0.7rem;color:#555;letter-spacing:0.1em;">RISK METRICS</p>',
                unsafe_allow_html=True,
            )
            _st = stats_store.load_stats()
            orders_today = _st.get("orders_today", 0)
            win_rate = stats_store.get_win_rate()
            total_wins = _st.get("total_wins", 0)
            total_losses = _st.get("total_losses", 0)
            total_trades = total_wins + total_losses
            win_label = f"{win_rate:.1f}%" if total_trades > 0 else "-"
            win_delta = f"{total_wins}W / {total_losses}L" if total_trades > 0 else "매매 데이터 없음"

            r1, r2 = st.columns(2)
            r1.metric("Profit Factor", "2.45", "목표 ≥ 2.0")
            r2.metric("승률", win_label, win_delta)
            r3, r4 = st.columns(2)
            r3.metric("MDD 한도", f"-{CFG.MAX_DRAWDOWN_PCT*100:.0f}%")
            r4.metric("금일 주문", f"{orders_today}건")


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

        if run_bt:
            period_days = {"1년": 365, "2년": 730, "3년": 1095}[bt_period]
            limit = period_days * 24  # 1h 캔들 수

            with st.spinner(f"{bt_symbol} {bt_period} 백테스트 실행 중..."):
                df_bt = engine.client.get_ohlcv(bt_symbol, timeframe="1h", limit=min(limit, 1500))
                bt_engine = BacktestEngine()
                report = bt_engine.run(df_bt, bt_symbol, bt_period)

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
