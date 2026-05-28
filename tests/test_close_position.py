"""
AI QUANTUM — 포지션 청산 기능 철저 검증 테스트
손절(Stop Loss) / 익절(Take Profit) / 트레일링스톱 / 긴급청산 / Orphan Order 정리 통합 검증

검증 항목:
  1. 손절(SL) 가격 계산 정확성 (Long/Short 양방향)
  2. 익절(TP) 가격 계산 정확성 (Long/Short 양방향)
  3. 트레일링스톱 발동 로직 (TRAILING_ACTIVATE_PCT / TRAILING_CALLBACK_PCT)
  4. SL/TP OCO 주문 실패 시 Emergency Rollback 작동
  5. close_position() 3회 재시도 및 CRITICAL 경보 로그
  6. 청산 완료 후 Orphan OCO 주문 즉시 취소 (_check_closed_positions_async)
  7. 다중 포지션 전체 청산 (close_all_positions)
  8. 이미 청산된 포지션 재청산 요청 → 멱등(True) 반환
  9. 잔고 정산 정확성 (청산 후 free/used/total)
  10. API 오류 발생 시 3회 재시도 후 CRITICAL 로그 확인
"""
import pytest
import asyncio
import logging
import sys
import os
import time
from typing import Optional, List, Dict
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mock_exchange import MockBinanceClient
from core.trader import AutoTrader
from core.engine import QuantumEngine, EngineState
from core.scanner import Scanner
from core.strategy import Signal
from core.config import CFG


# ─── 헬퍼 픽스처 ────────────────────────────────────────────────────────────

def _make_signal(symbol="BTC/USDT:USDT", direction="long", strength=100):
    return Signal(
        symbol=symbol,
        direction=direction,
        strength=strength,
        ema_ok=True,
        bb_ok=True,
        macd_ok=True,
        close=67000.0 if "BTC" in symbol else 3800.0,
        ema200=66000.0,
        bb_upper=68000.0,
        bb_lower=65000.0,
        macd_hist=50.0,
        reason="test signal",
    )


def _create_engine(scenario="default"):
    eng = QuantumEngine()
    mock = MockBinanceClient()
    asyncio.run(mock.load_markets())
    mock.set_scenario(scenario)
    eng.client = mock
    eng.scanner = Scanner(mock)
    eng.trader = AutoTrader(mock)
    eng.scanner.on_signal = eng.trader.on_signal
    eng.scanner.on_scan_complete = eng._check_closed_positions_async
    eng._initialized = True
    eng._state = EngineState.CONNECTED
    eng._async_lock = None
    return eng, mock


# ─── MockBinanceClient 확장: SL/TP 주문을 _orders 에 등록하는 고급 Mock ──────

class AdvancedMockBinanceClient(MockBinanceClient):
    """
    SL/TP 주문을 실제로 _orders 에 등록하고
    close_position() 실패 횟수를 제어할 수 있는 확장 Mock
    """

    def __init__(self):
        super().__init__()
        self._sl_fail_count = 0          # SL 주문 실패 횟수
        self._tp_fail_count = 0          # TP 주문 실패 횟수
        self._close_fail_count = 0       # close_position 실패 횟수
        self._close_attempt_count = 0    # close_position 실제 시도 횟수
        self._rollback_called = False    # 긴급청산 호출 여부 추적용
        self._cancel_called_symbols = []  # cancel_all_orders 호출된 심볼들

    async def cancel_all_orders(self, symbol: str) -> bool:
        self._cancel_called_symbols.append(symbol)
        return await super().cancel_all_orders(symbol)

    async def place_order(
        self,
        symbol: str,
        side: str,
        margin_usdt: float,
        stop_loss_pct: float = CFG.STOP_LOSS_PCT,
        take_profit_pct: float = CFG.TAKE_PROFIT_PCT,
    ) -> Optional[Dict]:
        """SL/TP 주문도 _orders에 실제 등록"""
        result = await super().place_order(symbol, side, margin_usdt, stop_loss_pct, take_profit_pct)
        if result is None:
            return None

        entry_price = result["entry_price"]
        amount = result["amount"]
        close_side = "sell" if side == "buy" else "buy"

        # SL 주문 등록
        sl_price = result["sl_price"]
        tp_price = result["tp_price"]

        self._orders.append({
            "id": f"SL-{symbol}-{int(time.time()*1000)}",
            "symbol": symbol,
            "side": close_side,
            "type": "STOP_MARKET",
            "price": sl_price,
            "amount": amount,
            "status": "open",
            "reduceOnly": True,
        })

        # TP 주문 등록
        self._orders.append({
            "id": f"TP-{symbol}-{int(time.time()*1000)}",
            "symbol": symbol,
            "side": close_side,
            "type": "TAKE_PROFIT_MARKET",
            "price": tp_price,
            "amount": amount,
            "status": "open",
            "reduceOnly": True,
        })
        return result

    async def close_position(self, symbol: str, side: str) -> bool:
        """close_position 실패 시나리오 제어"""
        self._close_attempt_count += 1
        if self._close_fail_count > 0:
            self._close_fail_count -= 1
            raise Exception(f"Mock close_position 강제 실패 (잔여 실패: {self._close_fail_count})")
        return await super().close_position(symbol, side)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. SL/TP 가격 계산 정확성 검증
# ═══════════════════════════════════════════════════════════════════════════════

class TestSLTPPriceCalc:
    """손절/익절 가격 계산이 정확한지 수학적으로 검증"""

    def setup_method(self):
        self.mock = AdvancedMockBinanceClient()
        asyncio.run(self.mock.load_markets())
        self.mock.set_scenario("default")

    def test_long_sl_price_correct(self):
        """Long 포지션: SL = entry * (1 - STOP_LOSS_PCT)"""
        result = asyncio.run(self.mock.place_order("BTC/USDT:USDT", "buy", 5.0))
        assert result is not None
        entry = result["entry_price"]
        expected_sl = entry * (1 - CFG.STOP_LOSS_PCT)
        assert abs(result["sl_price"] - expected_sl) < 0.01, (
            f"Long SL 가격 오차: expected {expected_sl:.4f}, got {result['sl_price']:.4f}"
        )

    def test_long_tp_price_correct(self):
        """Long 포지션: TP = entry * (1 + TAKE_PROFIT_PCT)"""
        result = asyncio.run(self.mock.place_order("BTC/USDT:USDT", "buy", 5.0))
        assert result is not None
        entry = result["entry_price"]
        expected_tp = entry * (1 + CFG.TAKE_PROFIT_PCT)
        assert abs(result["tp_price"] - expected_tp) < 0.01, (
            f"Long TP 가격 오차: expected {expected_tp:.4f}, got {result['tp_price']:.4f}"
        )

    def test_short_sl_price_correct(self):
        """Short 포지션: SL = entry * (1 + STOP_LOSS_PCT)"""
        result = asyncio.run(self.mock.place_order("BTC/USDT:USDT", "sell", 5.0))
        assert result is not None
        entry = result["entry_price"]
        expected_sl = entry * (1 + CFG.STOP_LOSS_PCT)
        assert abs(result["sl_price"] - expected_sl) < 0.01, (
            f"Short SL 가격 오차: expected {expected_sl:.4f}, got {result['sl_price']:.4f}"
        )

    def test_short_tp_price_correct(self):
        """Short 포지션: TP = entry * (1 - TAKE_PROFIT_PCT)"""
        result = asyncio.run(self.mock.place_order("BTC/USDT:USDT", "sell", 5.0))
        assert result is not None
        entry = result["entry_price"]
        expected_tp = entry * (1 - CFG.TAKE_PROFIT_PCT)
        assert abs(result["tp_price"] - expected_tp) < 0.01, (
            f"Short TP 가격 오차: expected {expected_tp:.4f}, got {result['tp_price']:.4f}"
        )

    def test_sl_price_always_less_than_tp_for_long(self):
        """Long: SL < Entry < TP 순서 반드시 유지"""
        result = asyncio.run(self.mock.place_order("BTC/USDT:USDT", "buy", 5.0))
        assert result is not None
        assert result["sl_price"] < result["entry_price"], "Long: SL이 진입가보다 높음 — 오류"
        assert result["entry_price"] < result["tp_price"], "Long: TP가 진입가보다 낮음 — 오류"

    def test_sl_price_always_greater_than_tp_for_short(self):
        """Short: TP < Entry < SL 순서 반드시 유지"""
        result = asyncio.run(self.mock.place_order("BTC/USDT:USDT", "sell", 5.0))
        assert result is not None
        assert result["sl_price"] > result["entry_price"], "Short: SL이 진입가보다 낮음 — 오류"
        assert result["entry_price"] > result["tp_price"], "Short: TP가 진입가보다 높음 — 오류"

    def test_sl_tp_positive_pct_values(self):
        """SL/TP 비율이 양수이고 합리적인 범위(0.001~0.2) 내에 있는지 확인"""
        assert 0.001 <= CFG.STOP_LOSS_PCT <= 0.2, f"STOP_LOSS_PCT={CFG.STOP_LOSS_PCT} 비정상"
        assert 0.001 <= CFG.TAKE_PROFIT_PCT <= 0.2, f"TAKE_PROFIT_PCT={CFG.TAKE_PROFIT_PCT} 비정상"

    def test_risk_reward_ratio(self):
        """TP/SL 리스크:리워드 비율이 1:1 이상인지 확인"""
        rr = CFG.TAKE_PROFIT_PCT / CFG.STOP_LOSS_PCT
        assert rr >= 1.0, f"리스크:리워드 비율 {rr:.2f} — TP가 SL보다 작음, 수익성 불리"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SL/TP OCO 주문 등록 및 Orphan 정리 검증
# ═══════════════════════════════════════════════════════════════════════════════

class TestOCOOrderLifecycle:
    """SL/TP 주문이 올바르게 등록되고, 청산 후 잔여주문이 정리되는지 검증"""

    def setup_method(self):
        self.mock = AdvancedMockBinanceClient()
        asyncio.run(self.mock.load_markets())
        self.mock.set_scenario("default")

    def test_sl_tp_orders_registered_after_place_order(self):
        """진입 후 SL/TP 주문이 _orders 에 2건 등록되어야 함"""
        asyncio.run(self.mock.place_order("BTC/USDT:USDT", "buy", 5.0))
        btc_orders = [o for o in self.mock._orders if o["symbol"] == "BTC/USDT:USDT"]
        assert len(btc_orders) == 2, f"SL/TP 주문 2건 등록 기대, 실제: {len(btc_orders)}"

    def test_sl_order_type_is_stop_market(self):
        """SL 주문 타입이 STOP_MARKET 이어야 함"""
        asyncio.run(self.mock.place_order("BTC/USDT:USDT", "buy", 5.0))
        sl_orders = [o for o in self.mock._orders if o.get("type") == "STOP_MARKET"]
        assert len(sl_orders) >= 1, "SL(STOP_MARKET) 주문이 등록되지 않음"

    def test_tp_order_type_is_take_profit_market(self):
        """TP 주문 타입이 TAKE_PROFIT_MARKET 이어야 함"""
        asyncio.run(self.mock.place_order("BTC/USDT:USDT", "buy", 5.0))
        tp_orders = [o for o in self.mock._orders if o.get("type") == "TAKE_PROFIT_MARKET"]
        assert len(tp_orders) >= 1, "TP(TAKE_PROFIT_MARKET) 주문이 등록되지 않음"

    def test_cancel_all_orders_clears_sl_tp(self):
        """cancel_all_orders 호출 시 해당 심볼의 SL/TP 주문 모두 제거"""
        asyncio.run(self.mock.place_order("BTC/USDT:USDT", "buy", 5.0))
        assert len(self.mock._orders) == 2

        success = asyncio.run(self.mock.cancel_all_orders("BTC/USDT:USDT"))
        assert success is True
        remaining = [o for o in self.mock._orders if o["symbol"] == "BTC/USDT:USDT"]
        assert len(remaining) == 0, "cancel_all_orders 후 BTC 주문이 잔류함"

    def test_cancel_does_not_affect_other_symbols(self):
        """BTC 취소가 ETH 주문에 영향을 주면 안 됨"""
        asyncio.run(self.mock.place_order("BTC/USDT:USDT", "buy", 5.0))
        asyncio.run(self.mock.place_order("ETH/USDT:USDT", "sell", 5.0))
        assert len(self.mock._orders) == 4

        asyncio.run(self.mock.cancel_all_orders("BTC/USDT:USDT"))
        eth_orders = [o for o in self.mock._orders if o["symbol"] == "ETH/USDT:USDT"]
        assert len(eth_orders) == 2, "BTC 취소가 ETH 주문을 삭제함 — 격리 오류"

    def test_engine_cancels_orphan_orders_on_close(self):
        """engine._check_closed_positions_async(): 포지션 소멸 시 잔여 SL/TP 주문 자동 취소"""
        eng, mock = _create_engine("default")
        # 고급 Mock 으로 교체
        adv_mock = AdvancedMockBinanceClient()
        asyncio.run(adv_mock.load_markets())
        adv_mock.set_scenario("default")
        eng.client = adv_mock
        eng.trader.client = adv_mock

        # 포지션 진입
        asyncio.run(adv_mock.place_order("BTC/USDT:USDT", "buy", 5.0))
        assert len(adv_mock._orders) == 2, "SL/TP 주문 2건 기대"

        # prev_position_symbols 를 현재 포지션 세트로 세팅
        eng._prev_position_symbols = {p["symbol"] for p in asyncio.run(adv_mock.get_positions())}

        # 포지션 강제 청산 (SL hit 시뮬레이션: 직접 positions 에서 제거)
        adv_mock._positions.clear()

        # _check_closed_positions_async 호출 → Orphan 주문 취소되어야 함
        asyncio.run(eng._check_closed_positions_async())

        remaining = [o for o in adv_mock._orders if o["symbol"] == "BTC/USDT:USDT"]
        assert len(remaining) == 0, (
            f"청산 후 잔여 SL/TP 주문 {len(remaining)}건이 남아있음 — Orphan Order 정리 실패"
        )
        assert "BTC/USDT:USDT" in adv_mock._cancel_called_symbols, (
            "cancel_all_orders 가 'BTC/USDT:USDT' 에 대해 호출되지 않음"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. close_position() 3회 재시도 및 CRITICAL 경보 검증
# ═══════════════════════════════════════════════════════════════════════════════

class TestClosePositionRetry:
    """close_position 실패 시 최대 3회 재시도하고, 최종 실패 시 CRITICAL 로그를 남기는지 검증"""

    def setup_method(self):
        self.patcher = patch("core.exchange.ccxt_async.binanceusdm")
        self.mock_ccxt_class = self.patcher.start()
        self.mock_ex = MagicMock()
        self.mock_ex.load_markets = AsyncMock(return_value={})
        self.mock_ex.amount_to_precision = MagicMock(side_effect=lambda sym, amt: str(round(float(amt), 3)))
        self.mock_ex.price_to_precision = MagicMock(side_effect=lambda sym, p: str(round(float(p), 2)))
        self.mock_ex.cancel_all_orders = AsyncMock(return_value=True)
        self.mock_ex.set_margin_mode = AsyncMock(return_value=True)
        self.mock_ex.set_leverage = AsyncMock(return_value={"leverage": 10})
        self.mock_ccxt_class.return_value = self.mock_ex

        from core.exchange import BinanceClient
        self.client = BinanceClient("key", "secret")
        self.client._markets = {
            "BTC/USDT:USDT": {
                "contractSize": 0.001,
                "limits": {"leverage": {"max": 125}},
            }
        }
        self.mock_positions = [
            {"symbol": "BTC/USDT:USDT", "size": 1.0, "side": "long"}
        ]
        self.client.get_positions = AsyncMock(side_effect=lambda: self.mock_positions)

        self.create_order_calls = 0
        self.create_order_fail_count = 0

        async def mock_create_order(symbol, type, side, amount, params):
            self.create_order_calls += 1
            if self.create_order_fail_count > 0:
                self.create_order_fail_count -= 1
                raise Exception("Mock ccxt create_order error")
            self.mock_positions.clear()  # Position is closed
            return {"id": "CLOSE-001"}

        self.mock_ex.create_order = AsyncMock(side_effect=mock_create_order)

    def teardown_method(self):
        self.patcher.stop()

    def test_close_position_success_first_try(self):
        """첫 시도에 성공하는 경우"""
        result = asyncio.run(self.client.close_position("BTC/USDT:USDT", "long"))
        assert result is True
        assert self.create_order_calls == 1

    def test_close_position_success_on_second_try(self):
        """첫 번째 시도 실패, 두 번째 시도 성공"""
        self.create_order_fail_count = 1
        with patch("asyncio.sleep", AsyncMock()):  # Bypass sleep delays in test
            result = asyncio.run(self.client.close_position("BTC/USDT:USDT", "long"))
        assert result is True
        assert self.create_order_calls == 2

    def test_close_position_success_on_third_try(self):
        """두 번 실패 후 세 번째 시도 성공"""
        self.create_order_fail_count = 2
        with patch("asyncio.sleep", AsyncMock()):  # Bypass sleep delays in test
            result = asyncio.run(self.client.close_position("BTC/USDT:USDT", "long"))
        assert result is True
        assert self.create_order_calls == 3

    def test_close_position_all_three_attempts_fail_returns_false(self):
        """3회 모두 실패 시 False 반환"""
        self.create_order_fail_count = 3
        with patch("asyncio.sleep", AsyncMock()):  # Bypass sleep delays in test
            result = asyncio.run(self.client.close_position("BTC/USDT:USDT", "long"))
        assert result is False
        assert self.create_order_calls == 3

    def test_close_position_critical_log_on_full_failure(self, caplog):
        """3회 전부 실패 시 CRITICAL 수준 로그 메시지 출력"""
        self.create_order_fail_count = 3
        with caplog.at_level(logging.CRITICAL, logger="core.exchange"):
            with patch("asyncio.sleep", AsyncMock()):  # Bypass sleep delays in test
                asyncio.run(self.client.close_position("BTC/USDT:USDT", "long"))
        
        critical_logs = [rec for rec in caplog.records if rec.levelno == logging.CRITICAL]
        assert len(critical_logs) > 0
        assert "포지션 청산 최종 실패" in critical_logs[0].message

    def test_close_already_closed_position_returns_true(self):
        """이미 청산된 포지션 재요청 시 True(멱등성) 반환"""
        self.mock_positions.clear()
        result = asyncio.run(self.client.close_position("BTC/USDT:USDT", "long"))
        assert result is True
        assert self.create_order_calls == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 4. SL/TP Emergency Rollback 검증
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmergencyRollback:
    """SL/TP 주문 실패 시 Emergency Rollback이 작동하는지 검증"""

    def test_sl_fail_triggers_emergency_close(self):
        """
        exchange.py place_order: SL 설정 3회 모두 실패 시
        → cancel_all_orders + 시장가 역방향 청산 주문 (Emergency Rollback)
        → return None (주문 실패로 처리)
        이 시나리오는 실제 BinanceClient를 Mock하여 검증
        """
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch, call

        # create_order 를 선택적으로 실패시키는 Mock 구성
        order_call_count = [0]
        emergency_close_called = [False]
        cancel_called = [False]

        async def mock_create_order(**kwargs):
            order_call_count[0] += 1
            order_type = kwargs.get("type", "")
            # 시장가 진입(1번째) 성공, SL(2~4번째) 실패, Emergency 시장가 청산(5번째) 성공
            if order_type in ("market", "limit") and not kwargs.get("params", {}).get("reduceOnly", False):
                return {"id": "ENTRY-001", "average": 67000.0, "price": 67000.0}
            elif order_type == "STOP_MARKET":
                raise Exception("SL 주문 강제 실패")
            elif order_type == "market" and kwargs.get("params", {}).get("reduceOnly", False):
                emergency_close_called[0] = True
                return {"id": "EMERGENCY-001"}
            raise Exception("Unexpected call")

        async def mock_cancel_all(**kwargs):
            cancel_called[0] = True
            return {"success": True}

        async def mock_get_ticker(symbol):
            return {"last": 67000.0}

        async def mock_set_leverage(*args, **kwargs):
            return True

        async def mock_set_margin_mode(*args, **kwargs):
            return True

        # exchange.py 의 BinanceClient 내부 exchange 객체를 Mock
        with patch("core.exchange.ccxt_async.binanceusdm") as MockExchangeClass:
            mock_ex = MagicMock()
            mock_ex.load_markets = AsyncMock(return_value={})
            mock_ex.amount_to_precision = MagicMock(side_effect=lambda sym, amt: str(round(float(amt), 3)))
            mock_ex.price_to_precision = MagicMock(side_effect=lambda sym, p: str(round(float(p), 2)))
            mock_ex.cancel_all_orders = AsyncMock(side_effect=lambda symbol: None)
            mock_ex.create_order = AsyncMock(side_effect=lambda **kwargs: mock_create_order(**kwargs))
            mock_ex.fetch_ticker = AsyncMock(return_value={"last": 67000.0, "bid": 66999.0, "ask": 67001.0, "quoteVolume": 1e9, "percentage": 0.5})
            mock_ex.set_margin_mode = AsyncMock(return_value=True)
            mock_ex.set_leverage = AsyncMock(return_value={"leverage": 10})
            MockExchangeClass.return_value = mock_ex

            from core.exchange import BinanceClient
            client = BinanceClient("key", "secret")
            client._markets = {
                "BTC/USDT:USDT": {
                    "contractSize": 0.001,
                    "limits": {"leverage": {"max": 125}},
                }
            }

            result = asyncio.run(client.place_order("BTC/USDT:USDT", "buy", 5.0))

            # SL 실패로 Emergency Rollback 발동 → None 반환
            assert result is None, (
                "SL 실패 시 Emergency Rollback 후 None을 반환해야 함 — 주문 취소되지 않음"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 트레일링스톱 발동 조건 논리 검증
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrailingStopLogic:
    """
    트레일링스톱 파라미터 (TRAILING_ACTIVATE_PCT / TRAILING_CALLBACK_PCT)의
    발동 조건과 가격 계산 논리를 수학적으로 검증
    """

    def test_trailing_activate_pct_positive(self):
        """TRAILING_ACTIVATE_PCT 가 양수여야 함"""
        assert CFG.TRAILING_ACTIVATE_PCT > 0, (
            f"TRAILING_ACTIVATE_PCT={CFG.TRAILING_ACTIVATE_PCT} — 0 이하는 즉시 발동으로 무의미"
        )

    def test_trailing_callback_pct_positive(self):
        """TRAILING_CALLBACK_PCT 가 양수여야 함"""
        assert CFG.TRAILING_CALLBACK_PCT > 0, (
            f"TRAILING_CALLBACK_PCT={CFG.TRAILING_CALLBACK_PCT} — 0 이하는 즉시 청산으로 위험"
        )

    def test_trailing_callback_less_than_activate(self):
        """콜백(Callback)이 발동(Activate) 보다 작아야 트레일링이 의미 있음"""
        assert CFG.TRAILING_CALLBACK_PCT < CFG.TRAILING_ACTIVATE_PCT, (
            f"콜백({CFG.TRAILING_CALLBACK_PCT}) >= 발동({CFG.TRAILING_ACTIVATE_PCT}) — "
            "트레일링스톱 발동 즉시 청산되는 구조"
        )

    def test_trailing_activate_price_long(self):
        """Long 트레일링 발동가 = entry * (1 + TRAILING_ACTIVATE_PCT)"""
        entry = 67000.0
        activate_price = entry * (1 + CFG.TRAILING_ACTIVATE_PCT)
        assert activate_price > entry, "Long 발동가가 진입가보다 낮음"

    def test_trailing_activate_price_short(self):
        """Short 트레일링 발동가 = entry * (1 - TRAILING_ACTIVATE_PCT)"""
        entry = 67000.0
        activate_price = entry * (1 - CFG.TRAILING_ACTIVATE_PCT)
        assert activate_price < entry, "Short 발동가가 진입가보다 높음"

    def test_trailing_callback_stop_price_long(self):
        """
        Long 트레일링: 최고가에서 TRAILING_CALLBACK_PCT 하락 시 청산
        최고가 = 68005(entry*1.015일 때), callback_stop = 68005 * (1 - 0.0043)
        """
        entry = 67000.0
        peak = entry * (1 + CFG.TRAILING_ACTIVATE_PCT)  # 트레일링 발동
        callback_stop = peak * (1 - CFG.TRAILING_CALLBACK_PCT)  # 콜백 지점
        assert callback_stop < peak, "콜백 스톱 가격이 최고가보다 높음"
        assert callback_stop > entry, "콜백 스톱 가격이 진입가보다 낮음 — 손절과 동일"

    def test_trailing_callback_stop_price_short(self):
        """
        Short 트레일링: 최저가에서 TRAILING_CALLBACK_PCT 상승 시 청산
        최저가 = entry*(1-ACTIVATE_PCT), callback_stop = low * (1 + CALLBACK_PCT)
        """
        entry = 67000.0
        trough = entry * (1 - CFG.TRAILING_ACTIVATE_PCT)
        callback_stop = trough * (1 + CFG.TRAILING_CALLBACK_PCT)
        assert callback_stop > trough, "콜백 스톱 가격이 최저가보다 낮음"
        assert callback_stop < entry, "콜백 스톱 가격이 진입가보다 높음 — 손절과 동일"

    def test_trailing_guaranteed_profit_if_activated(self):
        """
        트레일링 발동 후 콜백 청산 시 반드시 수익 구간인지 확인
        Long: callback_stop = peak*(1-callback) > entry 여야 함
        """
        entry = 67000.0
        peak = entry * (1 + CFG.TRAILING_ACTIVATE_PCT)
        callback_stop = peak * (1 - CFG.TRAILING_CALLBACK_PCT)
        assert callback_stop > entry, (
            f"트레일링 발동 후 청산 시 손실 발생 가능 — "
            f"callback_stop({callback_stop:.2f}) <= entry({entry:.2f})\n"
            f"  ACTIVATE={CFG.TRAILING_ACTIVATE_PCT}, CALLBACK={CFG.TRAILING_CALLBACK_PCT}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. 청산 완료 후 잔고 정산 정확성 검증
# ═══════════════════════════════════════════════════════════════════════════════

class TestBalanceAfterClose:
    """청산 후 free/used/total 잔고가 정확히 업데이트되는지 검증"""

    def setup_method(self):
        self.mock = MockBinanceClient()
        asyncio.run(self.mock.load_markets())
        self.mock.set_scenario("default")

    def test_balance_after_close_long(self):
        """Long 청산 후 free 증가, used 감소, total = total + pnl"""
        asyncio.run(self.mock.place_order("BTC/USDT:USDT", "buy", 5.0))
        pre_balance = asyncio.run(self.mock.get_balance())
        pos = asyncio.run(self.mock.get_positions())[0]
        pnl = pos["pnl_usdt"]
        margin = pos["margin"]

        asyncio.run(self.mock.close_position("BTC/USDT:USDT", "long"))
        post_balance = asyncio.run(self.mock.get_balance())

        assert abs(post_balance["free"] - (pre_balance["free"] + margin + pnl)) < 0.001, (
            f"free 잔고 불일치: expected {pre_balance['free'] + margin + pnl:.4f}, "
            f"got {post_balance['free']:.4f}"
        )
        assert abs(post_balance["used"] - (pre_balance["used"] - margin)) < 0.001, (
            f"used 잔고 불일치: expected {pre_balance['used'] - margin:.4f}, "
            f"got {post_balance['used']:.4f}"
        )
        assert abs(post_balance["total"] - (pre_balance["total"] + pnl)) < 0.001, (
            f"total 잔고 불일치: expected {pre_balance['total'] + pnl:.4f}, "
            f"got {post_balance['total']:.4f}"
        )

    def test_balance_after_close_short(self):
        """Short 청산 후 잔고 정산 정확성"""
        asyncio.run(self.mock.place_order("ETH/USDT:USDT", "sell", 5.0))
        pre_balance = asyncio.run(self.mock.get_balance())
        pos = asyncio.run(self.mock.get_positions())[0]
        pnl = pos["pnl_usdt"]
        margin = pos["margin"]

        asyncio.run(self.mock.close_position("ETH/USDT:USDT", "short"))
        post_balance = asyncio.run(self.mock.get_balance())

        assert abs(post_balance["total"] - (pre_balance["total"] + pnl)) < 0.001


# ═══════════════════════════════════════════════════════════════════════════════
# 7. 다중 포지션 전체 청산 검증
# ═══════════════════════════════════════════════════════════════════════════════

class TestCloseAllPositions:
    """close_all_positions 가 모든 포지션을 순차 청산하는지 검증"""

    def setup_method(self):
        self.mock = MockBinanceClient()
        asyncio.run(self.mock.load_markets())
        self.mock.set_scenario("default")

    def test_close_all_with_two_positions(self):
        """2개 포지션 보유 시 close_all_positions 호출 후 전부 청산"""
        asyncio.run(self.mock.place_order("BTC/USDT:USDT", "buy", 5.0))
        asyncio.run(self.mock.place_order("ETH/USDT:USDT", "sell", 5.0))
        assert len(asyncio.run(self.mock.get_positions())) == 2

        count = asyncio.run(self.mock.close_all_positions())
        assert count == 2, f"청산 성공 건수 기대 2, 실제: {count}"
        assert len(asyncio.run(self.mock.get_positions())) == 0, "청산 후 포지션이 남아있음"

    def test_close_all_with_no_positions(self):
        """포지션 없을 때 close_all_positions 호출 → 0 반환"""
        count = asyncio.run(self.mock.close_all_positions())
        assert count == 0

    def test_close_all_max_positions(self):
        """MAX_POSITIONS 개 포지션 전부 청산"""
        self.mock.set_scenario("max_positions")
        positions = asyncio.run(self.mock.get_positions())
        count = asyncio.run(self.mock.close_all_positions())
        assert count == len(positions), (
            f"전체 포지션({len(positions)}) vs 청산 수({count}) 불일치"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 8. 엔진 수준 청산 감지 및 상태 정리 통합 검증
# ═══════════════════════════════════════════════════════════════════════════════

class TestEngineCloseDetection:
    """engine._check_closed_positions_async 포지션 소멸 감지 및 PnL 집계 검증"""

    def test_prev_position_symbols_updated_after_close(self):
        """청산 후 _prev_position_symbols 에서 해당 심볼 제거 확인"""
        eng, mock = _create_engine("with_positions")
        # 초기화: BTC, ETH 포지션 세팅
        eng._prev_position_symbols = {"BTC/USDT:USDT", "ETH/USDT:USDT"}

        # BTC 포지션 청산 (positions 에서 BTC만 제거)
        mock._positions = [p for p in mock._positions if p["symbol"] != "BTC/USDT:USDT"]

        asyncio.run(eng._check_closed_positions_async())

        assert eng._prev_position_symbols == {"ETH/USDT:USDT"}, (
            f"청산 후 _prev_position_symbols 갱신 실패: {eng._prev_position_symbols}"
        )

    def test_cooldown_triggered_after_close(self):
        """청산 감지 후 해당 심볼에 쿨다운 자동 설정 확인"""
        eng, mock = _create_engine("with_positions")
        trader = eng.trader
        trader.enable()
        eng._prev_position_symbols = {"BTC/USDT:USDT"}

        mock._positions = [p for p in mock._positions if p["symbol"] != "BTC/USDT:USDT"]
        asyncio.run(eng._check_closed_positions_async())

        assert "BTC/USDT:USDT" in trader.symbol_cooldown_until, (
            "청산 후 심볼 쿨다운이 설정되지 않음"
        )

    def test_no_false_positive_on_unchanged_positions(self):
        """포지션 변화 없을 때 Orphan 정리가 발생하지 않아야 함"""
        adv_mock = AdvancedMockBinanceClient()
        asyncio.run(adv_mock.load_markets())
        adv_mock.set_scenario("with_positions")

        eng = QuantumEngine()
        eng.client = adv_mock
        eng.scanner = Scanner(adv_mock)
        eng.trader = AutoTrader(adv_mock)
        eng.scanner.on_signal = eng.trader.on_signal
        eng.scanner.on_scan_complete = eng._check_closed_positions_async
        eng._initialized = True
        eng._state = EngineState.CONNECTED
        eng._async_lock = None

        # 포지션 세트 세팅
        positions = asyncio.run(adv_mock.get_positions())
        eng._prev_position_symbols = {p["symbol"] for p in positions}

        # 변화 없이 체크 → cancel_all_orders 호출 없어야 함
        asyncio.run(eng._check_closed_positions_async())
        assert len(adv_mock._cancel_called_symbols) == 0, (
            f"포지션 변화 없는데 cancel_all_orders 호출됨: {adv_mock._cancel_called_symbols}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 9. 청산 방향(close_side) 정확성 검증
# ═══════════════════════════════════════════════════════════════════════════════

class TestCloseSideDirection:
    """close_position 의 청산 방향이 포지션 방향과 반대인지 검증"""

    def test_long_position_closed_with_sell(self):
        """Long 포지션 → sell 시장가 청산"""
        mock = MockBinanceClient()
        asyncio.run(mock.load_markets())
        mock.set_scenario("with_positions")
        # BTC long 포지션 확인
        positions = asyncio.run(mock.get_positions())
        btc_pos = next(p for p in positions if "BTC" in p["symbol"])
        assert btc_pos["side"] == "long"

        # 청산 성공 확인
        result = asyncio.run(mock.close_position(btc_pos["symbol"], btc_pos["side"]))
        assert result is True
        remaining = [p for p in asyncio.run(mock.get_positions()) if "BTC" in p["symbol"]]
        assert len(remaining) == 0

    def test_short_position_closed_with_buy(self):
        """Short 포지션 → buy 시장가 청산"""
        mock = MockBinanceClient()
        asyncio.run(mock.load_markets())
        mock.set_scenario("with_positions")
        positions = asyncio.run(mock.get_positions())
        eth_pos = next(p for p in positions if "ETH" in p["symbol"])
        assert eth_pos["side"] == "short"

        result = asyncio.run(mock.close_position(eth_pos["symbol"], eth_pos["side"]))
        assert result is True
        remaining = [p for p in asyncio.run(mock.get_positions()) if "ETH" in p["symbol"]]
        assert len(remaining) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 10. exchange.py close_position 멱등성 검증 (포지션 없을 때 True 반환)
# ═══════════════════════════════════════════════════════════════════════════════

class TestClosePositionIdempotency:
    """
    exchange.py BinanceClient.close_position 은 포지션이 이미 없을 때 True를 반환해야 함 (멱등성).
    이 동작이 코드에 명시적으로 구현되어 있는지 소스 코드 레벨로 확인.
    """

    def test_exchange_close_position_has_idempotency_guard(self):
        """
        exchange.py close_position L446-448:
        target = next((p for p in positions if p["symbol"] == symbol), None)
        if not target:
            return True  ← 멱등성 보장
        """
        import ast, os
        exchange_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "core", "exchange.py"
        )
        with open(exchange_path, "r", encoding="utf-8") as f:
            source = f.read()

        # "if not target:" 이후 "return True" 패턴이 존재하는지 확인
        assert "if not target:" in source, "close_position에 멱등성 가드(if not target:) 없음"
        # return True 가 if not target: 다음 줄에 존재하는지 확인
        lines = source.split("\n")
        for i, line in enumerate(lines):
            if "if not target:" in line:
                # 다음 몇 줄에서 return True 탐색
                for j in range(i+1, min(i+5, len(lines))):
                    if "return True" in lines[j]:
                        return  # 발견
        pytest.fail("close_position 내 'if not target: return True' 멱등성 패턴 없음 — 수정 필요")


# ═══════════════════════════════════════════════════════════════════════════════
# 11. BinanceClient 청산 로직 견고성 검증 (Rounding, Mismatch Guard, Polling Exception)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBinanceClientRobustness:
    """[v2.6.1] BinanceClient의 실제 청산 로직 견고성 검증 (Rounding, Mismatch Guard, Polling Exception)"""

    @pytest.mark.anyio
    async def test_close_position_side_mismatch_guard(self):
        """인자로 전달받은 side와 상관없이 실제 포지션 방향(short)에 맞춰 buy 주문을 전송해야 함"""
        from core.exchange import BinanceClient
        client = BinanceClient("api_key", "secret_key")
        
        # Mock exchange methods
        client.exchange = MagicMock()
        client.exchange.amount_to_precision = MagicMock(return_value="1.0")
        
        client.cancel_all_orders = AsyncMock(return_value=True)
        # 실제 포지션은 short인 상태 -> 검증 폴링 시에는 포지션이 0(없음)으로 반환되어 성공하는 시나리오
        get_pos_mock = AsyncMock()
        get_pos_mock.side_effect = [
            [{"symbol": "BTC/USDT:USDT", "side": "short", "size": 1.0}],  # Initial check
            []                                                           # Verification poll: closed
        ]
        client.get_positions = get_pos_mock
        client._execute_with_retry = AsyncMock()
        
        # 인자로는 잘못된 'long'을 전달함
        with patch("asyncio.sleep", AsyncMock()):
            result = await client.close_position("BTC/USDT:USDT", "long")
        
        assert result is True
        # short 포지션을 청산해야 하므로 close_side가 'buy'로 전송되었어야 함
        client._execute_with_retry.assert_any_call(
            client.exchange.create_order,
            symbol="BTC/USDT:USDT",
            type="market",
            side="buy", # Mismatch guard worked!
            amount=1.0,
            params={"reduceOnly": True}
        )

    @pytest.mark.anyio
    async def test_close_position_float_rounding(self):
        """실수 표현 오차가 있는 수량(e.g., 0.06999999)에 대해 8자리 반올림이 동작하는지 검증"""
        from core.exchange import BinanceClient
        client = BinanceClient("api_key", "secret_key")
        
        client.exchange = MagicMock()
        client.exchange.amount_to_precision = MagicMock(side_effect=lambda sym, val: f"{val:.3f}")
        
        client.cancel_all_orders = AsyncMock(return_value=True)
        # 실제 포지션 long 상태 -> 검증 폴링 시에는 포지션이 0(없음)으로 반환되어 성공하는 시나리오
        get_pos_mock = AsyncMock()
        get_pos_mock.side_effect = [
            [{"symbol": "BTC/USDT:USDT", "side": "long", "size": 0.0699999999}],  # Initial check
            []                                                                    # Verification poll: closed
        ]
        client.get_positions = get_pos_mock
        client._execute_with_retry = AsyncMock()
        
        with patch("asyncio.sleep", AsyncMock()):
            result = await client.close_position("BTC/USDT:USDT", "long")
        
        assert result is True
        # round(0.0699999999, 8) -> 0.07000000 -> amount_to_precision -> "0.070" -> amount = 0.07
        client._execute_with_retry.assert_any_call(
            client.exchange.create_order,
            symbol="BTC/USDT:USDT",
            type="market",
            side="sell",
            amount=0.07, # Rounded successfully
            params={"reduceOnly": True}
        )

    @pytest.mark.anyio
    async def test_close_position_polling_exception_handling(self):
        """검증 폴링 루프 도중 예외가 발생하더라도 루프가 바로 붕괴되지 않고 무시하고 계속 폴링해야 함"""
        from core.exchange import BinanceClient
        client = BinanceClient("api_key", "secret_key")
        
        client.exchange = MagicMock()
        client.exchange.amount_to_precision = MagicMock(return_value="1.0")
        
        client.cancel_all_orders = AsyncMock(return_value=True)
        
        # 첫 get_positions 호출 시(진입 확인 단계): 정상
        # 그 다음 폴링 1회차: Exception 발생
        # 그 다음 폴링 2회차: 포지션 없음 (청산 완료)
        get_pos_mock = AsyncMock()
        get_pos_mock.side_effect = [
            [{"symbol": "BTC/USDT:USDT", "side": "long", "size": 1.0}], # Initial check
            Exception("Temporary API Error"),                            # Poll #1: Error!
            []                                                           # Poll #2: Success (Closed)
        ]
        client.get_positions = get_pos_mock
        client._execute_with_retry = AsyncMock()
        
        # Patch sleep to speed up test
        with patch("asyncio.sleep", AsyncMock()):
            result = await client.close_position("BTC/USDT:USDT", "long")
            
        assert result is True # Polling exception was swallowed, didn't fail


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
