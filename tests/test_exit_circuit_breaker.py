"""
AI QUANTUM — Risk Circuit Breaker Unit Tests
Verify Daily Loss Limit and Max Drawdown circuit breakers.
"""
import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import QuantumEngine, EngineState
from core.mock_exchange import MockBinanceClient
from core.scanner import Scanner
from core.trader import AutoTrader
import core.stats as stats_store

@pytest.mark.anyio
async def test_daily_loss_circuit_breaker():
    # 1. Setup engine with mock client
    engine = QuantumEngine()
    mock = MockBinanceClient()
    await mock.load_markets()
    
    engine.client = mock
    engine.scanner = Scanner(mock)
    engine.trader = AutoTrader(mock)
    engine.scanner.on_signal = engine.trader.on_signal
    engine.scanner.on_scan_complete = engine._check_closed_positions_async
    engine._initialized = True
    engine._state = EngineState.SCANNING
    engine.trader.enable()
    engine.scanner.start()
    
    # Configure daily loss limit
    engine.cfg.DAILY_LOSS_LIMIT_USDT = 5.0
    engine.trader.daily_pnl_usdt = -1.0 # Realized daily loss of 1 USDT
    
    # Mock positions with a floating loss of -4.5 USDT (total daily loss: -5.5 USDT, violating 5.0 limit)
    async def mock_get_positions():
        return [
            {
                "symbol": "BTC/USDT:USDT",
                "side": "long",
                "size": 1.0,
                "entry_price": 100.0,
                "mark_price": 95.5,
                "pnl_pct": -4.5,
                "pnl_usdt": -4.5,
                "leverage": 10,
                "margin": 10.0,
                "timestamp": 123456789,
                "amount_usdt": 100.0
            }
        ]
    
    mock.get_positions = mock_get_positions
    
    # Run check
    await engine._check_closed_positions_async()
    
    # Verify that:
    # 1. Trading is disabled
    assert engine.trader.enabled is False
    # 2. Scanner is stopped
    assert engine.scanner.is_running is False
    # 3. Engine is in CONNECTED state (stopped scanner)
    assert engine.state == EngineState.CONNECTED

@pytest.mark.anyio
async def test_mdd_circuit_breaker():
    engine = QuantumEngine()
    mock = MockBinanceClient()
    await mock.load_markets()
    
    engine.client = mock
    engine.scanner = Scanner(mock)
    engine.trader = AutoTrader(mock)
    engine._initialized = True
    engine._state = EngineState.SCANNING
    engine.trader.enable()
    engine.scanner.start()
    
    # Configure MDD and seed money
    engine.cfg.MAX_DRAWDOWN_PCT = 0.10 # 10%
    _stats = stats_store.load_stats()
    _stats["seed_money"] = 100.0
    stats_store.save_stats(_stats)
    
    # Mock get_balance to return total balance of 89.0 (11% drawdown, violating 10% limit)
    async def mock_get_balance():
        return {
            "total": 89.0,
            "free": 89.0,
            "used": 0.0,
            "pnl": 0.0
        }
    mock.get_balance = mock_get_balance
    
    # Empty positions (no daily loss violation)
    async def mock_get_positions():
        return []
    mock.get_positions = mock_get_positions
    
    # Run check
    await engine._check_closed_positions_async()
    
    # Verify circuit breaker triggered
    assert engine.trader.enabled is False
    assert engine.scanner.is_running is False
    assert engine.state == EngineState.CONNECTED
