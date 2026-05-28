"""
AI QUANTUM — Thread-Safety of File I/O (CSV & JSON) Tests
"""
import pytest
import threading
import os
import csv
import core.logger
import core.stats

from core.logger import log_trade
from core.stats import record_order, record_result, load_stats, reset_stats

@pytest.fixture(autouse=True)
def setup_test_cache():
    """Clear logger cache to ensure all logged entries are written in isolation."""
    core.logger._logged_cache.clear()
    yield

def test_multithreaded_csv_logger():
    """Verify that multiple threads can write to the CSV log file concurrently without exceptions."""
    num_threads = 10
    writes_per_thread = 20
    
    errors = []
    
    def worker(thread_idx):
        for i in range(writes_per_thread):
            try:
                log_trade({
                    "timestamp": None,
                    "symbol": "BTC/USDT",
                    "type": "진입",
                    "side": "buy",
                    "price": 60000 + thread_idx * 10 + i,
                    "amount": 0.1,
                    "pnl_usdt": 0.0,
                    "pnl_pct": 0.0,
                    "leverage": 10,
                    "order_id": f"ord_{thread_idx}_{i}",
                    "trade_id": f"trd_{thread_idx}_{i}",
                })
            except Exception as e:
                errors.append(e)
                
    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    # Verify no exceptions occurred
    assert len(errors) == 0
    
    # Verify all records were written to the mocked/sandboxed LOG_FILE
    target_log_file = core.logger.LOG_FILE
    assert os.path.exists(target_log_file)
    with open(target_log_file, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)
        # Header + entries
        assert len(rows) == (num_threads * writes_per_thread) + 1

def test_multithreaded_stats_updater():
    """Verify that stats updates (orders_today, total_trades) are thread-safe and avoid lost updates."""
    reset_stats(100.0)
    
    num_threads = 10
    orders_per_thread = 15
    
    errors = []
    
    def worker():
        for _ in range(orders_per_thread):
            try:
                record_order()
            except Exception as e:
                errors.append(e)
                
    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    assert len(errors) == 0
    
    # Check final stats totals
    stats = load_stats()
    assert stats["orders_today"] == num_threads * orders_per_thread
    assert stats["total_trades"] == num_threads * orders_per_thread

def test_multithreaded_stats_results():
    """Verify that concurrently recording trading results increments wins, losses and PnL correctly."""
    reset_stats(100.0)
    
    num_threads = 10
    results_per_thread = 10
    
    errors = []
    
    def worker():
        for i in range(results_per_thread):
            try:
                # Even indices: wins (+1.0 USDT), Odd indices: losses (-0.5 USDT)
                pnl = 1.0 if i % 2 == 0 else -0.5
                record_result(pnl)
            except Exception as e:
                errors.append(e)
                
    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
        
    assert len(errors) == 0
    
    stats = load_stats()
    expected_wins = num_threads * (results_per_thread // 2)
    expected_losses = num_threads * (results_per_thread // 2)
    expected_pnl = num_threads * ((results_per_thread // 2) * 1.0 + (results_per_thread // 2) * -0.5)
    
    assert stats["total_wins"] == expected_wins
    assert stats["total_losses"] == expected_losses
    assert round(stats["total_pnl_usdt"], 2) == round(expected_pnl, 2)
