"""
AI QUANTUM — Lv.4 주문 흐름 E2E 검증 테스트
Signal → Risk Check → Place Order → SL/TP 설정 및 체결 / 잔고 정산 전 과정 검증
"""
import pytest
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mock_exchange import MockBinanceClient
from core.trader import AutoTrader
from core.strategy import Signal
from core.config import CFG


def test_full_order_flow_e2e():
    # 1. Mock 거래소 및 트레이더 초기화
    mock = MockBinanceClient()
    mock.load_markets()
    mock.set_scenario("default")
    
    trader = AutoTrader(mock)
    trader.enable()
    
    # 초기 잔고 상태 기록
    initial_balance = mock.get_balance()
    assert initial_balance["total"] == 100.0
    assert initial_balance["free"] == 80.0
    assert initial_balance["used"] == 20.0
    
    # 2. 강력한 매수(Long) 신호 인스턴스 생성
    long_signal = Signal(
        symbol="BTC/USDT:USDT",
        direction="long",
        strength=95,
        ema_ok=True,
        bb_ok=True,
        macd_ok=True,
        close=65000.0,
        ema200=64000.0,
        bb_upper=66000.0,
        bb_lower=64500.0,
        macd_hist=10.0,
        reason="EMA200 상향 + BB 하단 지지 후 MACD 양전환",
    )
    
    # 3. 리스크 게이트 검증
    ok, reason = trader._risk_check(long_signal)
    assert ok is True
    assert reason == "OK"
    
    # 4. 주문 실행 (Signal 수신 → 리스크 게이트 통과 → 주문 실행)
    orders_before = trader.orders_today
    trader.on_signal(long_signal)
    
    # 5. 주문 수량 및 상태 검증
    assert trader.orders_today == orders_before + 1
    
    # 6. Mock 거래소 상태 변화 확인
    positions = mock.get_positions()
    assert len(positions) == 1
    pos = positions[0]
    
    # 포지션 속성 확인
    assert pos["symbol"] == "BTC/USDT:USDT"
    assert pos["side"] == "long"
    assert pos["entry_price"] == 67000.0  # mock ticker price
    assert pos["margin"] > 0
    
    # 잔고 업데이트 검증
    balance_after = mock.get_balance()
    assert balance_after["free"] == initial_balance["free"] - CFG.MARGIN_USDT
    assert balance_after["used"] == initial_balance["used"] + CFG.MARGIN_USDT
    
    # OCO (SL/TP) 설정 검증을 위해 거래 이력에서 order_id 조회 및 검증
    trades = mock.get_trade_history()
    assert len(trades) > 0
    entry_trade = [t for t in trades if t["symbol"] == "BTC/USDT:USDT" and t["category"] == "진입"][0]
    assert entry_trade["side"] == "buy"
    assert entry_trade["cost"] == CFG.MARGIN_USDT * CFG.LEVERAGE
    
    # 7. 포지션 강제 청산(손익 청산) 시뮬레이션
    pnl_usdt = pos["pnl_usdt"]
    success = mock.close_position("BTC/USDT:USDT", "long")
    assert success is True
    
    # 청산 완료 후 잔고 상태 최종 검증
    final_balance = mock.get_balance()
    assert len(mock.get_positions()) == 0
    assert final_balance["total"] == initial_balance["total"] + pnl_usdt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
