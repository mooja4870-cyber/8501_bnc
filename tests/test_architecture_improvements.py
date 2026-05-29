import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from core.config import TradingConfig
from core.exchange import OKXClient
from core.engine import QuantumEngine, EngineState

def test_config_copy():
    # 1. TradingConfig copy() 일관성 및 독립성 검증
    cfg = TradingConfig()
    cfg.LEVERAGE = 10
    cfg.TELEGRAM_BOT_TOKEN = "TEST_TOKEN"
    
    cfg_copy = cfg.copy()
    assert cfg_copy.LEVERAGE == 10
    assert cfg_copy.TELEGRAM_BOT_TOKEN == "TEST_TOKEN"
    
    # 독립성 검증: copy본을 고쳤을 때 원본은 그대로인가?
    cfg_copy.LEVERAGE = 20
    assert cfg.LEVERAGE == 10
    assert cfg_copy.LEVERAGE == 20

@pytest.mark.asyncio
async def test_exchange_circuit_breaker():
    # 2. OKXClient 서킷 브레이커 연속 에러 발생 시 차단 검증
    client = OKXClient("api_key", "secret_key", "passphrase")
    
    # Mocking exchange to throw ExchangeError
    import ccxt
    mock_func = AsyncMock(side_effect=ccxt.ExchangeError("API Error"))
    
    # 1~4회차: 일반 예외 발생
    for _ in range(4):
        with pytest.raises(ccxt.ExchangeError):
            await client._execute_with_retry(mock_func, max_retries=1)
            
    assert client._consecutive_failures == 4
    assert client._circuit_open_until == 0.0
    
    # 5회차: 에러 유발하여 서킷 브레이커 작동(Open)
    with pytest.raises(ccxt.ExchangeError):
        await client._execute_with_retry(mock_func, max_retries=1)
        
    assert client._consecutive_failures == 5
    assert client._circuit_open_until > time.time()
    
    # 서킷 브레이커가 오픈된 상태에서 호출 시 즉시 Exception 발생하며, exchange API는 불리지 않음
    mock_func.reset_mock()
    with pytest.raises(Exception) as exc_info:
        await client._execute_with_retry(mock_func, max_retries=1)
        
    assert "Circuit breaker is open" in str(exc_info.value)
    mock_func.assert_not_called()

@pytest.mark.asyncio
async def test_engine_dashboard_caching():
    # 3. QuantumEngine 대시보드 API 캐싱 및 무효화 검증
    engine = QuantumEngine.get_instance()
    
    # Mock client and initialize
    mock_client = MagicMock()
    mock_client.load_markets = AsyncMock(return_value=True)
    mock_client.get_balance = AsyncMock(return_value={"total": 100.0, "free": 90.0, "used": 10.0, "pnl": 0.0})
    mock_client.get_positions = AsyncMock(return_value=[])
    
    engine.client = mock_client
    engine._initialized = True
    
    # Initial state
    engine._cached_balance = None
    engine._cached_positions = None
    
    # 1. First fetch triggers REST API call
    res = await engine._get_dashboard_data_async()
    assert res["total_balance"] == 100.0
    assert mock_client.get_balance.call_count == 1
    assert mock_client.get_positions.call_count == 1
    
    # 2. Subsequent fetch uses cache (REST API calls do not increase)
    res2 = await engine._get_dashboard_data_async()
    assert res2["total_balance"] == 100.0
    assert mock_client.get_balance.call_count == 1
    assert mock_client.get_positions.call_count == 1
    
    # 3. Invalidate cache
    engine._cached_positions = None
    engine._cached_balance = None
    
    # 4. Fetch triggers REST call again
    res3 = await engine._get_dashboard_data_async()
    assert mock_client.get_balance.call_count == 2
    assert mock_client.get_positions.call_count == 2
