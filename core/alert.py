"""
AI QUANTUM — Telegram Alerting Manager
표준 라이브러리 urllib을 사용하여 비동기/동기 논블로킹으로 Telegram 메시지를 전송합니다.
"""
import logging
import urllib.request
import urllib.parse
import json
import asyncio
from core.config import CFG

logger = logging.getLogger(__name__)

def _send_sync(text: str) -> bool:
    token = getattr(CFG, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(CFG, "TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return True
            else:
                logger.error(f"[TELEGRAM] 메시지 전송 실패 (상태 코드: {response.status})")
                return False
    except Exception as e:
        logger.error(f"[TELEGRAM] 메시지 전송 예외 발생: {e}")
        return False

async def send_telegram_alert_async(text: str) -> bool:
    """비동기 방식으로 텔레그램 메시지 전송 (이벤트 루프 블로킹 방지)"""
    return await asyncio.to_thread(_send_sync, text)

def send_telegram_alert(text: str):
    """동기식/스레드 기반 텔레그램 메시지 전송 (UI 및 동기 컨텍스트용)"""
    import threading
    threading.Thread(target=_send_sync, args=(text,), daemon=True).start()
