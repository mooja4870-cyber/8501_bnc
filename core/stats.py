"""
통계 영구 저장 모듈
data/stats.json 에 승/패/금일주문 저장 → 앱 재시작 후에도 유지
"""
import json
import os
import logging
from datetime import datetime, timedelta
import pytz
from typing import Dict

logger = logging.getLogger(__name__)

STATS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "stats.json")


def _ensure_dir():
    os.makedirs(os.path.dirname(os.path.abspath(STATS_FILE)), exist_ok=True)


def get_current_cycle_start(perf_start_time_str: str, now: datetime) -> str:
    """
    초기화 클릭 시점(perf_start_time_str)부터 24시간 단위 주기로 계산하여
    현재 시간에 해당하는 주기의 시작 시각(문자열)을 반환합니다.
    """
    try:
        start_dt = datetime.strptime(perf_start_time_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        # 파싱 실패 시 현재 시각 반환 (기본동작)
        return now.strftime("%Y-%m-%d %H:%M:%S")
    
    diff = now - start_dt
    cycles = int(diff.total_seconds() // 86400)
    if cycles < 0:
        cycles = 0
    cycle_start = start_dt + timedelta(days=cycles)
    return cycle_start.strftime("%Y-%m-%d %H:%M:%S")


def load_stats() -> Dict:
    """stats.json 불러오기 — 없으면 기본값 반환"""
    _ensure_dir()
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                perf_start = data.get("perf_start_time", "2026-05-19 00:00:00")
                now_kst = datetime.utcnow() + timedelta(hours=9)
                current_cycle_start = get_current_cycle_start(perf_start, now_kst)
                
                # 기록된 주기의 시작 시각과 다르면 일별 카운터 초기화
                if data.get("cycle_start_time") != current_cycle_start:
                    data["orders_today"] = 0
                    data["daily_pnl_usdt"] = 0.0
                    data["cycle_start_time"] = current_cycle_start
                    _write(data)
                return data
    except Exception as e:
        logger.warning(f"stats.json 로드 실패: {e}")
    return _default()


def save_stats(data: Dict):
    """stats.json 저장"""
    _ensure_dir()
    _write(data)


def record_order():
    """주문 1건 기록"""
    data = load_stats()
    data["orders_today"] = data.get("orders_today", 0) + 1
    data["total_trades"] = data.get("total_trades", 0) + 1
    _write(data)


def record_result(pnl_usdt: float):
    """청산 결과 기록 (pnl_usdt > 0 → 승, < 0 → 패)"""
    data = load_stats()
    data["daily_pnl_usdt"] = round(data.get("daily_pnl_usdt", 0.0) + pnl_usdt, 4)
    data["total_pnl_usdt"] = round(data.get("total_pnl_usdt", 0.0) + pnl_usdt, 4)
    if pnl_usdt >= 0:
        data["total_wins"] = data.get("total_wins", 0) + 1
    else:
        data["total_losses"] = data.get("total_losses", 0) + 1
    _write(data)


def get_win_rate() -> float:
    """현재까지의 승률(%) 반환"""
    data = load_stats()
    wins = data.get("total_wins", 0)
    losses = data.get("total_losses", 0)
    total = wins + losses
    if total == 0:
        return 0.0
    return round(wins / total * 100, 1)


def reset_stats(current_balance: float):
    """stats.json 데이터를 현재 자산 및 현재각 기준(0)으로 초기화"""
    now_kst = datetime.utcnow() + timedelta(hours=9)
    now_str = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    
    data = {
        "cycle_start_time": now_str,
        "orders_today": 0,
        "daily_pnl_usdt": 0.0,
        "total_pnl_usdt": 0.0,
        "total_trades": 0,
        "total_wins": 0,
        "total_losses": 0,
        "seed_money": current_balance,
        "perf_start_time": now_str,
    }
    _write(data)


def _default() -> Dict:
    now_kst = datetime.utcnow() + timedelta(hours=9)
    now_str = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "cycle_start_time": now_str,
        "orders_today": 0,
        "daily_pnl_usdt": 0.0,
        "total_pnl_usdt": 0.0,
        "total_trades": 0,
        "total_wins": 0,
        "total_losses": 0,
        "seed_money": 30.0,
        "perf_start_time": "2026-05-19 00:00:00",
    }


def _write(data: Dict):
    _ensure_dir()
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sync_daily_stats_from_csv():
    """로컬 CSV 매매 이력을 읽어와서 '현재 24시간 주기' 동안의 실제 청산 손익을 계산하고 stats.json에 덮어씌움"""
    try:
        from core.history_helper import load_local_trade_history
        import pandas as pd
        
        trades = load_local_trade_history()
        if not trades:
            return 0.0
            
        df = pd.DataFrame(trades)
        if df.empty or 'timestamp' not in df.columns:
            return 0.0
            
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        kst = pytz.timezone('Asia/Seoul')
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = df['timestamp'].dt.tz_localize('UTC')
        df['timestamp'] = df['timestamp'].dt.tz_convert(kst)
        
        data = load_stats() # 이것이 cycle_start_time을 갱신합니다.
        cycle_start_str = data.get("cycle_start_time")
        cycle_start_dt = datetime.strptime(cycle_start_str, "%Y-%m-%d %H:%M:%S")
        cycle_start_dt = kst.localize(cycle_start_dt)
        
        # 현재 주기(cycle) 내의 청산 거래만 필터링
        cycle_exits = df[(df['timestamp'] >= cycle_start_dt) & (df['category'].str.contains('청산'))]
        
        daily_pnl = round(float(cycle_exits['pnl'].sum()), 4)
        orders_today = len(cycle_exits)
        
        data['daily_pnl_usdt'] = daily_pnl
        data['orders_today'] = orders_today
        _write(data)
        
        logger.info(f"[STATS] 24시간 주기({cycle_start_str}~) 수익금 재보정 완료: {daily_pnl} USDT (총 {orders_today}건)")
        return daily_pnl
    except Exception as e:
        logger.error(f"CSV 통계 재계산 중 오류: {e}")
        data = load_stats()
        return data.get('daily_pnl_usdt', 0.0)
