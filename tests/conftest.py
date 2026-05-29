import pytest
import os
import core.logger
import core.stats

@pytest.fixture(autouse=True)
def mock_log_file(monkeypatch, tmp_path):
    """테스트 실행 시 실제 파일들이 오염되는 것을 방지하기 위해 임시 파일 경로로 모킹"""
    test_log_file = os.path.join(tmp_path, "test_trade_history.csv")
    test_autotune_file = os.path.join(tmp_path, "test_autotune_history.csv")
    test_stats_file = os.path.join(tmp_path, "test_stats.json")
    monkeypatch.setattr(core.logger, "LOG_FILE", test_log_file)
    monkeypatch.setattr(core.logger, "AUTOTUNE_LOG_FILE", test_autotune_file)
    monkeypatch.setattr(core.stats, "STATS_FILE", test_stats_file)

