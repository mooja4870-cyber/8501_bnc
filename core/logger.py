"""
매매 이력 로깅 모듈 (CSV 저장)
트레이딩 로직과 분리되어 실행되며, data/trade_history.csv 에 영구 보관합니다.
"""
import os
import csv
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "trade_history.csv")

def _ensure_file():
    """CSV 파일 및 헤더 생성"""
    os.makedirs(os.path.dirname(os.path.abspath(LOG_FILE)), exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "시간", "심볼", "유형", "방향", "가격", "수량", "수익(USDT)", "수익률(%)", "레버리지", "주문ID"
            ])

def log_trade(data: dict):
    """
    매매 내역 한 줄 추가
    data keys: timestamp, symbol, type, side, price, amount, pnl_usdt, pnl_pct, leverage, order_id
    """
    try:
        _ensure_file()
        
        # 한국 시간 변환 (Timestamp 객체인 경우 처리)
        ts = data.get("timestamp")
        if hasattr(ts, "strftime"):
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        else:
            ts_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

        with open(LOG_FILE, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                ts_str,
                data.get("symbol", ""),
                data.get("type", ""),
                data.get("side", ""),
                data.get("price", 0),
                data.get("amount", 0),
                data.get("pnl_usdt", 0),
                data.get("pnl_pct", 0),
                data.get("leverage", ""),
                f"ID_{data.get('order_id', '')}"
            ])
    except Exception as e:
        # 매매에 영향을 주지 않기 위해 에러는 출력만 하고 무시
        print(f"[LOGGER ERROR] {e}")
