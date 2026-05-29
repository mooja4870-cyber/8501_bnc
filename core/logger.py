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
    """CSV 파일 및 헤더 생성 및 업데이트"""
    os.makedirs(os.path.dirname(os.path.abspath(LOG_FILE)), exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "시간", "심볼", "유형", "방향", "가격", "수량", "수익(USDT)", "수익률(%)", "레버리지", "주문ID", "체결ID"
            ])
    else:
        # 기존 파일이 있다면 헤더 검사하여 체결ID 추가
        try:
            with open(LOG_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
            if "체결ID" not in header:
                with open(LOG_FILE, "r", encoding="utf-8-sig") as f:
                    lines = list(csv.reader(f))
                if lines:
                    lines[0].append("체결ID")
                    for i in range(1, len(lines)):
                        while len(lines[i]) < len(lines[0]):
                            lines[i].append("")
                    with open(LOG_FILE, "w", encoding="utf-8-sig", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerows(lines)
        except Exception as e:
            print(f"[LOGGER HEADER UPDATE ERROR] {e}")

_logged_cache = set()

def _load_cache():
    if not _logged_cache and os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    oid = row.get("주문ID", "")
                    tid = row.get("체결ID", "")
                    status = row.get("유형", "")
                    if not oid and not tid: continue
                    _logged_cache.add(f"{oid}_{tid}_{status}")
        except Exception:
            pass

def log_trade(data: dict):
    """
    매매 내역 한 줄 추가
    data keys: timestamp, symbol, type, side, price, amount, pnl_usdt, pnl_pct, leverage, order_id, trade_id
    """
    try:
        _ensure_file()
        _load_cache()
        
        oid = f"ID_{data.get('order_id', '')}"
        tid = str(data.get("trade_id", ""))
        status = data.get("type", "")
        
        cache_key = f"{oid}_{tid}_{status}"
        if (oid != "ID_" or tid != "") and cache_key in _logged_cache:
            return  # 중복 기록 차단
            
        _logged_cache.add(cache_key)
        
        # 한국 시간 변환 (Timestamp 객체인 경우 처리)
        ts = data.get("timestamp")
        if hasattr(ts, "strftime"):
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(ts, (int, float)) and ts > 0:
            # 밀리초(ms) 단위 타임스탬프인 경우 초 단위로 변환 후 KST 적용
            ts_sec = ts / 1000.0 if ts > 10000000000 else ts
            ts_dt = datetime.fromtimestamp(ts_sec, timezone.utc) + timedelta(hours=9)
            ts_str = ts_dt.strftime("%Y-%m-%d %H:%M:%S")
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
                f"ID_{data.get('order_id', '')}",
                data.get("trade_id", "")
            ])
    except Exception as e:
        # 매매에 영향을 주지 않기 위해 에러는 출력만 하고 무시
        print(f"[LOGGER ERROR] {e}")

AUTOTUNE_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "autotune_history.csv")

def _ensure_autotune_file():
    os.makedirs(os.path.dirname(os.path.abspath(AUTOTUNE_LOG_FILE)), exist_ok=True)
    if not os.path.exists(AUTOTUNE_LOG_FILE):
        with open(AUTOTUNE_LOG_FILE, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "시간", "이전_익절(%)", "이전_손절(%)", "변경_익절(%)", "변경_손절(%)", "예상승률(%)", "예상수익(USDT)", "대상거래수"
            ])

def log_autotune(data: dict):
    """자동 튜닝 이력 영구 기록"""
    try:
        _ensure_autotune_file()
        ts_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        with open(AUTOTUNE_LOG_FILE, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                ts_str,
                data.get("old_tp", 0),
                data.get("old_sl", 0),
                data.get("new_tp", 0),
                data.get("new_sl", 0),
                data.get("winrate", 0),
                data.get("pnl", 0),
                data.get("count", 0)
            ])
    except Exception as e:
        print(f"[AUTOTUNE LOGGER ERROR] {e}")
