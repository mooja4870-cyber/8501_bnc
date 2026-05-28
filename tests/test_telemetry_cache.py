"""
AI QUANTUM — Telemetry Cache & Config Snapshot Unit Tests
"""
import pytest
import asyncio
import copy
from unittest.mock import AsyncMock, patch

from core.engine import QuantumEngine, EngineState
from core.mock_exchange import MockBinanceClient
from core.scanner import Scanner
from core.trader import AutoTrader
from core.config import CFG, TradingConfig

@pytest.mark.anyio
async def test_config_snapshot():
    """Verify that TradingConfig.snapshot creates a thread-safe decoupled copy."""
    original_leverage = CFG.LEVERAGE
    original_margin = CFG.MARGIN_USDT

    # Take snapshot
    snap = CFG.snapshot()
    assert isinstance(snap, TradingConfig)
    assert snap.LEVERAGE == original_leverage
    assert snap.MARGIN_USDT == original_margin

    # Modify global config
    CFG.LEVERAGE = 99
    CFG.MARGIN_USDT = 999.0

    try:
        # Snapshot values should NOT change
        assert snap.LEVERAGE == original_leverage
        assert snap.MARGIN_USDT == original_margin
    finally:
        # Restore global values
        CFG.LEVERAGE = original_leverage
        CFG.MARGIN_USDT = original_margin

@pytest.mark.anyio
async def test_telemetry_cache_non_blocking():
    """Verify that get_dashboard_data serves from cache instead of querying Binance REST API repeatedly."""
    engine = QuantumEngine()
    mock_client = MockBinanceClient()
    await mock_client.load_markets()

    # Wrap balance and position calls with AsyncMock to count calls
    mock_client.get_balance = AsyncMock(side_effect=mock_client.get_balance)
    mock_client.get_positions = AsyncMock(side_effect=mock_client.get_positions)

    engine.client = mock_client
    engine.scanner = Scanner(mock_client)
    engine.trader = AutoTrader(mock_client)
    engine.scanner.on_signal = engine.trader.on_signal
    engine.scanner.on_scan_complete = engine._check_closed_positions_async

    # Force initialization states
    engine._initialized = True
    engine._state = EngineState.CONNECTED

    # Verify cache is empty initially
    assert engine._cached_balance == {}
    assert engine._cached_positions == []

    # Update cache once
    await engine._update_dashboard_cache_async()
    assert engine._cached_balance != {}
    assert len(engine._cached_positions) >= 0

    # Record call counts
    balance_calls_before = mock_client.get_balance.call_count
    positions_calls_before = mock_client.get_positions.call_count
    assert balance_calls_before > 0
    assert positions_calls_before > 0

    # Call get_dashboard_data multiple times (via sync wrapper helper context or async method)
    data1 = await engine._get_dashboard_data_async()
    data2 = await engine._get_dashboard_data_async()

    assert data1["total_balance"] == 100.0
    assert data2["total_balance"] == 100.0

    # Ensure no new REST calls were made during get_dashboard_data retrieval
    assert mock_client.get_balance.call_count == balance_calls_before
    assert mock_client.get_positions.call_count == positions_calls_before

    # Clean up engine resources if any
    if engine._cache_task:
        engine._cache_task.cancel()
