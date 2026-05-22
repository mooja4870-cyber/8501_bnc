import pytest
import pandas as pd
from datetime import datetime, timedelta
from core.history_helper import get_position_direction, aggregate_and_pair_trades

def test_get_position_direction():
    assert get_position_direction("진입", "buy") == "LONG"
    assert get_position_direction("진입", "sell") == "SHORT"
    assert get_position_direction("청산", "sell") == "LONG"
    assert get_position_direction("청산", "buy") == "SHORT"
    assert get_position_direction("청산(로테이션)", "sell") == "LONG"
    assert get_position_direction("청산(로테이션)", "buy") == "SHORT"
    assert get_position_direction("진입", "LONG") == "LONG"
    assert get_position_direction("청산", "SHORT") == "SHORT"

def test_aggregate_and_pair_trades_empty():
    assert aggregate_and_pair_trades([]) == []

def test_aggregate_and_pair_trades_basic():
    t1 = datetime(2026, 5, 20, 10, 0, 0)
    t2 = datetime(2026, 5, 20, 10, 5, 0)
    trades = [
        {
            "timestamp": t1,
            "symbol": "BTC/USDT:USDT",
            "category": "진입",
            "side": "buy",
            "price": 60000.0,
            "amount": 0.1,
            "pnl": 0.0,
            "pnl_pct": 0.0,
            "leverage": 10,
            "order_id": "100"
        },
        {
            "timestamp": t2,
            "symbol": "BTC/USDT:USDT",
            "category": "청산",
            "side": "sell",
            "price": 61000.0,
            "amount": 0.1,
            "pnl": 100.0,
            "pnl_pct": 16.67,
            "leverage": 10,
            "order_id": "101"
        }
    ]
    
    paired = aggregate_and_pair_trades(trades)
    assert len(paired) == 1
    cycle = paired[0]
    assert cycle["symbol"] == "BTC/USDT:USDT"
    assert cycle["entry_time"] == t1
    assert cycle["exit_time"] == t2
    assert cycle["direction"] == "🟢 LONG"
    assert cycle["entry_price"] == 60000.0
    assert cycle["exit_price"] == 61000.0
    assert cycle["amount"] == 0.1
    assert cycle["pnl_usdt"] == 100.0
    assert cycle["pnl_pct"] == 16.67
    assert cycle["status"] == "청산 완료"

def test_aggregate_and_pair_trades_fills_aggregation():
    t1 = datetime(2026, 5, 20, 10, 0, 0)
    t2 = datetime(2026, 5, 20, 10, 5, 0)
    trades = [
        # Fill 1 of entry
        {
            "timestamp": t1,
            "symbol": "BTC/USDT:USDT",
            "category": "진입",
            "side": "buy",
            "price": 60000.0,
            "amount": 0.04,
            "pnl": 0.0,
            "pnl_pct": 0.0,
            "leverage": 10,
            "order_id": "100"
        },
        # Fill 2 of entry
        {
            "timestamp": t1 + timedelta(seconds=1),
            "symbol": "BTC/USDT:USDT",
            "category": "진입",
            "side": "buy",
            "price": 60500.0,
            "amount": 0.06,
            "pnl": 0.0,
            "pnl_pct": 0.0,
            "leverage": 10,
            "order_id": "100"
        },
        # Fill 1 of exit
        {
            "timestamp": t2,
            "symbol": "BTC/USDT:USDT",
            "category": "청산",
            "side": "sell",
            "price": 61000.0,
            "amount": 0.05,
            "pnl": 40.0,
            "pnl_pct": 13.33,
            "leverage": 10,
            "order_id": "101"
        },
        # Fill 2 of exit
        {
            "timestamp": t2 + timedelta(seconds=1),
            "symbol": "BTC/USDT:USDT",
            "category": "청산",
            "side": "sell",
            "price": 62000.0,
            "amount": 0.05,
            "pnl": 90.0,
            "pnl_pct": 29.03,
            "leverage": 10,
            "order_id": "101"
        }
    ]
    
    paired = aggregate_and_pair_trades(trades)
    assert len(paired) == 1
    cycle = paired[0]
    
    # Expected weighted entry price: (60000*0.04 + 60500*0.06) / 0.1 = 60300.0
    assert cycle["entry_price"] == 60300.0
    # Expected weighted exit price: (61000*0.05 + 62000*0.05) / 0.1 = 61500.0
    assert cycle["exit_price"] == 61500.0
    assert cycle["amount"] == 0.1
    # Expected summed PnL: 40 + 90 = 130
    assert cycle["pnl_usdt"] == 130.0
    assert cycle["status"] == "청산 완료"

def test_aggregate_and_pair_trades_open_position():
    t1 = datetime(2026, 5, 20, 10, 0, 0)
    trades = [
        {
            "timestamp": t1,
            "symbol": "ETH/USDT:USDT",
            "category": "진입",
            "side": "sell",
            "price": 3000.0,
            "amount": 1.0,
            "pnl": 0.0,
            "pnl_pct": 0.0,
            "leverage": 10,
            "order_id": "200"
        }
    ]
    
    paired = aggregate_and_pair_trades(trades)
    assert len(paired) == 1
    cycle = paired[0]
    assert cycle["symbol"] == "ETH/USDT:USDT"
    assert cycle["entry_time"] == t1
    assert cycle["exit_time"] is None
    assert cycle["direction"] == "🔴 SHORT"
    assert cycle["entry_price"] == 3000.0
    assert cycle["exit_price"] is None
    assert cycle["amount"] == 1.0
    assert cycle["pnl_usdt"] is None
    assert cycle["pnl_pct"] is None
    assert cycle["status"] == "보유 중"

def test_aggregate_and_pair_trades_orphan_exit():
    t2 = datetime(2026, 5, 20, 10, 5, 0)
    trades = [
        {
            "timestamp": t2,
            "symbol": "SOL/USDT:USDT",
            "category": "청산",
            "side": "sell",
            "price": 150.0,
            "amount": 2.0,
            "pnl": -10.0,
            "pnl_pct": -3.33,
            "leverage": 10,
            "order_id": "301"
        }
    ]
    
    paired = aggregate_and_pair_trades(trades)
    assert len(paired) == 1
    cycle = paired[0]
    assert cycle["symbol"] == "SOL/USDT:USDT"
    assert cycle["entry_time"] is None
    assert cycle["exit_time"] == t2
    assert cycle["direction"] == "🟢 LONG"
    assert cycle["entry_price"] is None
    assert cycle["exit_price"] == 150.0
    assert cycle["amount"] == 2.0
    assert cycle["pnl_usdt"] == -10.0
    assert cycle["pnl_pct"] == -3.33
    assert cycle["status"] == "청산 완료 (진입유실)"
