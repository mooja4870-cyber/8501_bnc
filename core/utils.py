import os
import sys
import ctypes
import logging

logger = logging.getLogger(__name__)

class ServerLock:
    """
    Windows Mutex를 이용한 서버 중복 실행 방지 유틸리티
    """
    _mutex = None

    @classmethod
    def acquire(cls, mutex_name="Global\\AI_QUANTUM_OKX_TRADER_LOCK"):
        """
        시스템 전체에서 유일한 Mutex를 생성하여 중복 실행 여부를 확인합니다.
        """
        if os.name != 'nt':
            # Windows가 아닌 경우 일단 통과 (필요 시 파일 락 구현 가능)
            return True

        try:
            # 커널 Mutex 생성
            cls._mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
            last_error = ctypes.windll.kernel32.GetLastError()
            
            # ERROR_ALREADY_EXISTS = 183
            if last_error == 183:
                return False
            return True
        except Exception as e:
            logger.error(f"Lock acquire error: {e}")
            return True # 에러 시에는 안전을 위해 실행 허용

    @classmethod
    def release(cls):
        """Mutex 해제 (프로세스 종료 시 자동 해제되지만 명시적 호출용)"""
        if cls._mutex:
            ctypes.windll.kernel32.CloseHandle(cls._mutex)
            cls._mutex = None
