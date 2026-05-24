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
    t1 = datetime.now() - timedelta(hours=2)
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

def test_aggregate_and_pair_trades_cross_check():
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
    
    # 1. 실제 보유하지 않고 있을 때 (빈 세트 전달)
    paired_not_held = aggregate_and_pair_trades(trades, active_positions_set=set())
    assert len(paired_not_held) == 1
    assert paired_not_held[0]["status"] == "청산 완료 (미기록)"
    assert paired_not_held[0]["exit_price"] == 3000.0
    assert paired_not_held[0]["pnl_usdt"] == 0.0
    assert paired_not_held[0]["exit_time"] == t1
    
    # 2. 실제 보유 중일 때 (세트에 포함시켜 전달)
    paired_held = aggregate_and_pair_trades(trades, active_positions_set={("ETH/USDT:USDT", "SHORT")})
    assert len(paired_held) == 1
    assert paired_held[0]["status"] == "보유 중"
    assert paired_held[0]["exit_time"] is None

def test_aggregate_and_pair_trades_mn_matching():
    t1 = datetime(2026, 5, 20, 10, 0, 0)
    t2 = datetime(2026, 5, 20, 10, 5, 0)
    t3 = datetime(2026, 5, 20, 10, 10, 0)
    
    trades = [
        # Entry: 10.0 amount, price 100
        {
            "timestamp": t1,
            "symbol": "DOGE/USDT:USDT",
            "category": "진입",
            "side": "buy",
            "price": 100.0,
            "amount": 10.0,
            "pnl": 0.0,
            "pnl_pct": 0.0,
            "leverage": 10,
            "order_id": "100"
        },
        # Exit 1: 3.0 amount, PnL +30.0, yield +30%
        {
            "timestamp": t2,
            "symbol": "DOGE/USDT:USDT",
            "category": "청산",
            "side": "sell",
            "price": 110.0,
            "amount": 3.0,
            "pnl": 30.0,
            "pnl_pct": 30.0,
            "leverage": 10,
            "order_id": "101"
        },
        # Exit 2: 7.0 amount, PnL +70.0, yield +30%
        {
            "timestamp": t3,
            "symbol": "DOGE/USDT:USDT",
            "category": "청산",
            "side": "sell",
            "price": 110.0,
            "amount": 7.0,
            "pnl": 70.0,
            "pnl_pct": 30.0,
            "leverage": 10,
            "order_id": "102"
        }
    ]
    
    paired = aggregate_and_pair_trades(trades)
    
    # It should split into 2 cycles in order of exit timestamp (descending in returned output)
    assert len(paired) == 2
    
    cycle_latest = paired[0] # Exit 2 at t3
    assert cycle_latest["exit_time"] == t3
    assert cycle_latest["amount"] == 7.0
    assert cycle_latest["pnl_usdt"] == 70.0
    assert cycle_latest["pnl_pct"] == 30.0
    assert cycle_latest["status"] == "청산 완료"
    
    cycle_earliest = paired[1] # Exit 1 at t2
    assert cycle_earliest["exit_time"] == t2
    assert cycle_earliest["amount"] == 3.0
    assert cycle_earliest["pnl_usdt"] == 30.0
    assert cycle_earliest["pnl_pct"] == 30.0
    assert cycle_earliest["status"] == "청산 완료"
