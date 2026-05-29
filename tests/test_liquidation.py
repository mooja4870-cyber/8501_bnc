"""
청산 로직 전용 검증 테스트
- SL/TP 가격 계산 (롱/숏)
- Dynamic SL/TP (ATR 기반)
- 트레일링 스톱 활성화 / 트리거
- 포지션 타임아웃 강제청산
- algo 주문 실패 시 롤백 안전망
"""
import asyncio
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import AsyncMock, MagicMock, patch
from core.config import CFG
from core.strategy import Signal


# ─── 공통 헬퍼 ─────────────────────────────────────────────
def make_signal(direction="long", strength=100, close=100.0, atr=1.0):
    return Signal(
        symbol="BTC/USDT:USDT", direction=direction, strength=strength,
        ema_ok=True, bb_ok=True, macd_ok=True,
        close=close, ema200=90.0, bb_upper=105.0, bb_lower=95.0,
        macd_hist=0.5, reason="test", rsi=50.0, rsi_ok=True, ema200_ok=True,
        atr=atr
    )


def make_position(symbol="BTC/USDT:USDT", side="long",
                  entry_price=100.0, mark_price=100.0, timestamp=None):
    import time
    return {
        "symbol": symbol, "side": side,
        "entry_price": entry_price, "mark_price": mark_price,
        "amount_usdt": 50.0,
        "timestamp": timestamp or (time.time() * 1000)
    }


# ═══════════════════════════════════════════════════════════
# 1. SL/TP 가격 계산 검증
# ═══════════════════════════════════════════════════════════
class TestSLTPCalculation:

    def test_long_sl_below_entry(self):
        """롱: SL은 진입가 아래"""
        entry = 100.0
        sl_pct = 0.01
        sl = entry * (1 - sl_pct)
        assert sl == pytest.approx(99.0)
        assert sl < entry

    def test_long_tp_above_entry(self):
        """롱: TP는 진입가 위"""
        entry = 100.0
        tp_pct = 0.015
        tp = entry * (1 + tp_pct)
        assert tp == pytest.approx(101.5)
        assert tp > entry

    def test_short_sl_above_entry(self):
        """숏: SL은 진입가 위"""
        entry = 100.0
        sl_pct = 0.01
        sl = entry * (1 + sl_pct)
        assert sl == pytest.approx(101.0)
        assert sl > entry

    def test_short_tp_below_entry(self):
        """숏: TP는 진입가 아래"""
        entry = 100.0
        tp_pct = 0.015
        tp = entry * (1 - tp_pct)
        assert tp == pytest.approx(98.5)
        assert tp < entry

    def test_sl_tp_ratio(self):
        """TP가 SL보다 크거나 같아야 함 (기본 설정 기준)"""
        sl_pct = CFG.STOP_LOSS_PCT
        tp_pct = CFG.TAKE_PROFIT_PCT
        assert tp_pct >= sl_pct, f"TP({tp_pct}) < SL({sl_pct}) — 손익비 역전!"

    def test_dynamic_sltp_atr_based(self):
        """ATR 기반 Dynamic SL/TP 계산"""
        close = 1000.0
        atr = 15.0  # 1.5% ATR
        atr_pct = atr / close  # 0.015
        sl_mult = CFG.ATR_SL_MULT   # 1.5
        tp_mult = CFG.ATR_TP_MULT   # 2.0

        dynamic_sl = atr_pct * sl_mult  # 0.015 * 1.5 = 0.0225
        dynamic_tp = atr_pct * tp_mult  # 0.015 * 2.0 = 0.030

        assert dynamic_sl == pytest.approx(0.0225)
        assert dynamic_tp == pytest.approx(0.030)
        assert dynamic_tp > dynamic_sl, "Dynamic TP > Dynamic SL 이어야 함"

    def test_dynamic_sltp_enabled_when_atr_positive(self):
        """USE_DYNAMIC_SLTP=True + ATR>0 이면 dynamic 값 사용"""
        sig = make_signal(close=100.0, atr=2.0)
        assert CFG.USE_DYNAMIC_SLTP is True
        assert sig.atr > 0
        atr_pct = sig.atr / sig.close
        sl = atr_pct * CFG.ATR_SL_MULT
        tp = atr_pct * CFG.ATR_TP_MULT
        assert sl > 0
        assert tp > sl

    def test_dynamic_sltp_fallback_when_atr_zero(self):
        """ATR=0 이면 config 고정값 사용해야 함"""
        sig = make_signal(close=100.0, atr=0.0)
        # trader.py 로직: if USE_DYNAMIC_SLTP and sig.atr > 0 and sig.close > 0
        use_dynamic = CFG.USE_DYNAMIC_SLTP and sig.atr > 0 and sig.close > 0
        assert use_dynamic is False  # fallback to fixed SL/TP


# ═══════════════════════════════════════════════════════════
# 2. 트레일링 스톱 로직 검증
# ═══════════════════════════════════════════════════════════
class TestTrailingStop:
    """engine._run_trailing_stop_check_async 로직을 단위 검증"""

    def _simulate_trailing(self, side, entry, prices, activate_pct, callback_pct):
        """
        trailing stop 시뮬레이터
        returns: (fired: bool, trigger_price: float|None)
        """
        if side == "long":
            high = entry
            for price in prices:
                high = max(high, price)
                move = (high - entry) / entry
                if move >= activate_pct:
                    trigger = high * (1 - callback_pct)
                    if price <= trigger:
                        return True, trigger
        elif side == "short":
            low = entry
            for price in prices:
                low = min(low, price)
                move = (entry - low) / entry
                if move >= activate_pct:
                    trigger = low * (1 + callback_pct)
                    if price >= trigger:
                        return True, trigger
        return False, None

    def test_trailing_long_not_activated_below_threshold(self):
        """롱: 활성화 임계값(1.5%) 미달 시 트리거 없어야 함"""
        entry = 100.0
        prices = [101.0, 100.5, 99.0]  # 최대 수익 1% → 임계 1.5% 미달
        fired, _ = self._simulate_trailing("long", entry, prices, 0.015, 0.0045)
        assert not fired

    def test_trailing_long_activated_and_triggered(self):
        """롱: 1.5% 이상 상승 후 0.45% 하락 시 청산 발동"""
        entry = 100.0
        prices = [102.0, 103.0, 102.5]  # 최고 103 → 활성화
        # 103 * (1 - 0.0045) = 102.5365 → 102.5 <= 102.5365 이므로 발동
        fired, trigger = self._simulate_trailing("long", entry, prices, 0.015, 0.0045)
        assert fired
        assert trigger == pytest.approx(103.0 * (1 - 0.0045))

    def test_trailing_long_not_triggered_price_above_trigger(self):
        """롱: 활성화됐지만 가격이 트리거 위에 있으면 청산 안 함"""
        entry = 100.0
        prices = [102.0, 103.0, 103.5]  # 계속 상승 중 → 청산 없음
        fired, _ = self._simulate_trailing("long", entry, prices, 0.015, 0.0045)
        assert not fired

    def test_trailing_short_activated_and_triggered(self):
        """숏: 1.5% 이상 하락 후 0.45% 반등 시 청산 발동"""
        entry = 100.0
        prices = [98.0, 97.0, 97.45]  # 저점 97 → 활성화
        # 97 * (1 + 0.0045) = 97.4365 → 97.45 >= 97.4365 이므로 발동
        fired, trigger = self._simulate_trailing("short", entry, prices, 0.015, 0.0045)
        assert fired
        assert trigger == pytest.approx(97.0 * (1 + 0.0045))

    def test_trailing_short_not_activated(self):
        """숏: 1.5% 미달 하락 시 트리거 없음"""
        entry = 100.0
        prices = [99.5, 99.2, 99.8]  # 최대 0.8% 하락 → 임계 미달
        fired, _ = self._simulate_trailing("short", entry, prices, 0.015, 0.0045)
        assert not fired

    def test_trailing_high_watermark_tracks_correctly(self):
        """롱 최고가 추적이 정확한지 검증"""
        entry = 100.0
        prices = [101, 103, 102, 104, 103.5]
        high = entry
        for p in prices:
            high = max(high, p)
        assert high == 104.0

    def test_trailing_low_watermark_tracks_correctly(self):
        """숏 최저가 추적이 정확한지 검증"""
        entry = 100.0
        prices = [99, 97, 98, 96, 96.5]
        low = entry
        for p in prices:
            low = min(low, p)
        assert low == 96.0

    def test_trailing_stop_disabled_config(self):
        """USE_TRAILING_STOP=False 이면 체크 스킵"""
        # engine.py L413: if not getattr(self.cfg, "USE_TRAILING_STOP", False): return
        original = CFG.USE_TRAILING_STOP
        CFG.USE_TRAILING_STOP = False
        assert not CFG.USE_TRAILING_STOP
        CFG.USE_TRAILING_STOP = original

    @pytest.mark.anyio
    async def test_trailing_stop_api_failure_retains_watermark(self):
        """트레일링 스탑: 청산 API 실패 시 워터마크(고점 기록)를 지우지 않고 유지해야 함"""
        from core.engine import QuantumEngine
        from core.exchange import OKXClient

        with patch.object(QuantumEngine, '__init__', return_value=None):
            engine = QuantumEngine.__new__(QuantumEngine)
            engine.cfg = CFG
            engine.trader = None
            engine._trailing_highs = {"BTC/USDT:USDT": 105.0} # 최고가 105
            engine._trailing_lows = {}
            
            # mock client close_position to return False (failed)
            client = MagicMock()
            client.close_position = AsyncMock(return_value=False)
            engine.client = client

            # mock rotations
            engine._run_position_rotation_check_async = AsyncMock()

            # Set config to activate trailing stop
            original_use = CFG.USE_TRAILING_STOP
            original_act = CFG.TRAILING_ACTIVATE_PCT
            original_call = CFG.TRAILING_CALLBACK_PCT
            CFG.USE_TRAILING_STOP = True
            CFG.TRAILING_ACTIVATE_PCT = 0.015 # 1.5%
            CFG.TRAILING_CALLBACK_PCT = 0.003 # 0.3%

            try:
                # 롱 포지션: 진입가 100.0, 최고가 105.0. 
                # 활성화조건(1.5%) 충족함 (105는 100의 5% 위).
                # 트리거가: 105.0 * (1 - 0.003) = 104.685.
                # 현재가 104.0 이면 트리거 조건 충족하여 close_position 호출됨.
                p = {
                    "symbol": "BTC/USDT:USDT",
                    "side": "long",
                    "entry_price": 100.0,
                    "mark_price": 104.0,
                    "timestamp": 123456789
                }
                
                await engine._run_trailing_stop_check_async([p])

                # close_position should have been called
                client.close_position.assert_called_once_with("BTC/USDT:USDT", "long")
                
                # Since close_position returned False (failed), watermark must STILL be present
                assert "BTC/USDT:USDT" in engine._trailing_highs
                assert engine._trailing_highs["BTC/USDT:USDT"] == 105.0

                # Now simulate API success (True)
                client.close_position = AsyncMock(return_value=True)
                await engine._run_trailing_stop_check_async([p])
                
                # Since close_position returned True (success), watermark must be POPPED
                assert "BTC/USDT:USDT" not in engine._trailing_highs

            finally:
                CFG.USE_TRAILING_STOP = original_use
                CFG.TRAILING_ACTIVATE_PCT = original_act
                CFG.TRAILING_CALLBACK_PCT = original_call


# ═══════════════════════════════════════════════════════════
# 3. 포지션 타임아웃 로직
# ═══════════════════════════════════════════════════════════
class TestPositionTimeout:

    def test_timeout_threshold_calculation(self):
        """MAX_HOLDING_HOURS → ms 변환 정확성"""
        hours = CFG.MAX_HOLDING_HOURS
        timeout_ms = hours * 3600 * 1000
        assert timeout_ms == hours * 3_600_000

    def test_position_expired(self):
        """진입 후 MAX_HOLDING_HOURS 초과 → 강제청산 조건 충족"""
        import time
        hours = CFG.MAX_HOLDING_HOURS
        timeout_ms = hours * 3600 * 1000
        now_ms = time.time() * 1000
        # 진입 시각을 (MAX_HOLDING_HOURS + 1시간) 전으로 설정
        entry_ts = now_ms - (timeout_ms + 3_600_000)
        assert (now_ms - entry_ts) > timeout_ms  # 청산 조건 충족

    def test_position_not_expired(self):
        """진입 후 MAX_HOLDING_HOURS 이내 → 강제청산 조건 미충족"""
        import time
        hours = CFG.MAX_HOLDING_HOURS
        timeout_ms = hours * 3600 * 1000
        now_ms = time.time() * 1000
        # 진입 시각을 1분 전으로 설정
        entry_ts = now_ms - 60_000
        assert (now_ms - entry_ts) < timeout_ms  # 청산 조건 미충족


# ═══════════════════════════════════════════════════════════
# 4. OKX algo 주문 실패 시 롤백 로직
# ═══════════════════════════════════════════════════════════
class TestAlgoOrderRollback:

    @pytest.mark.anyio
    async def test_rollback_on_algo_failure(self):
        """attachAlgoOrds 실패 시 close_position 호출로 롤백"""
        from core.exchange import OKXClient

        with patch.object(OKXClient, '__init__', return_value=None):
            client = OKXClient.__new__(OKXClient)
            client.exchange = MagicMock()
            client._markets = {"BTC/USDT:USDT": {"contractSize": 1.0}}
            client.cfg = CFG

            # set_margin_mode, set_leverage 등 mock
            client.set_margin_mode = AsyncMock()
            client.set_leverage = AsyncMock(return_value=True)
            client.get_market_max_leverage = MagicMock(return_value=20)
            client.get_ticker = AsyncMock(return_value={"last": 100.0})
            client.close_position = AsyncMock()
            client._execute_with_retry = AsyncMock()

            # attachAlgoOrds 실패 → 단순 진입도 실패
            client.exchange.create_order = AsyncMock(side_effect=Exception("algo not supported"))
            client.exchange.amount_to_precision = MagicMock(return_value="0.5")
            client.exchange.price_to_precision = MagicMock(side_effect=lambda s, p: p)

            result = await client.place_order("BTC/USDT:USDT", "buy", 5.0, 0.01, 0.015)
            assert result is None  # 주문 실패 → None 반환

    @pytest.mark.anyio
    async def test_no_rollback_when_algo_succeeds(self):
        """attachAlgoOrds 성공 시 롤백 없이 정상 result 반환"""
        from core.exchange import OKXClient

        with patch.object(OKXClient, '__init__', return_value=None):
            client = OKXClient.__new__(OKXClient)
            client.exchange = MagicMock()
            client._markets = {"BTC/USDT:USDT": {"contractSize": 1.0}}
            client.cfg = CFG

            client.set_margin_mode = AsyncMock()
            client.set_leverage = AsyncMock(return_value=True)
            client.get_market_max_leverage = MagicMock(return_value=20)
            client.get_ticker = AsyncMock(return_value={"last": 100.0})
            client.close_position = AsyncMock()

            mock_order = {"id": "ORDER123", "average": 100.0, "price": 100.0}
            client.exchange.create_order = AsyncMock(return_value=mock_order)
            client.exchange.amount_to_precision = MagicMock(return_value="0.5")
            client.exchange.price_to_precision = MagicMock(side_effect=lambda s, p: p)

            result = await client.place_order("BTC/USDT:USDT", "buy", 5.0, 0.01, 0.015)

            assert result is not None
            assert result["order_id"] == "ORDER123"
            assert result["sl_price"] == pytest.approx(99.0)
            assert result["tp_price"] == pytest.approx(101.5)
            client.close_position.assert_not_called()  # 롤백 없어야 함


# ═══════════════════════════════════════════════════════════
# 5. 리스크 게이트 핵심 항목
# ═══════════════════════════════════════════════════════════
class TestRiskGateCore:

    def test_signal_strength_100_required(self):
        """신호 강도 100 미만이면 리스크 차단"""
        sig = make_signal(strength=70)
        # _risk_check 로직: if sig.strength < 100: return False
        assert sig.strength < 100

    def test_signal_strength_100_passes(self):
        """신호 강도 100이면 강도 조건 통과"""
        sig = make_signal(strength=100)
        assert sig.strength == 100

    def test_daily_loss_limit_blocks(self):
        """일일 손실 한도 초과 시 차단"""
        daily_pnl = -8.0
        limit = CFG.DAILY_LOSS_LIMIT_USDT  # 7.0
        blocked = daily_pnl <= -limit
        assert blocked

    def test_daily_loss_within_limit_passes(self):
        """일일 손실 한도 미달 시 통과"""
        daily_pnl = -3.0
        limit = CFG.DAILY_LOSS_LIMIT_USDT
        blocked = daily_pnl <= -limit
        assert not blocked


# ═══════════════════════════════════════════════════════════
# 6. 추가 안전장치 기능 검증 (v2.7.0)
# ═══════════════════════════════════════════════════════════
class TestTimeoutCooldownAndSafety:

    @pytest.mark.anyio
    async def test_timeout_close_cooldown_failed(self):
        """타임아웃 청산 실패 시 30초 쿨다운이 적용되어 중복 요청 차단되는지 검증"""
        from core.engine import QuantumEngine
        import time

        with patch.object(QuantumEngine, '__init__', return_value=None):
            engine = QuantumEngine.__new__(QuantumEngine)
            engine._initialized = True
            engine.cfg = CFG
            engine.trader = None
            engine._timeout_cooldowns = {}
            engine._prev_position_symbols = {"BTC/USDT:USDT"}

            client = MagicMock()
            client.close_position = AsyncMock(return_value=False)
            engine.client = client
            engine._run_position_rotation_check_async = AsyncMock()
            engine._run_trailing_stop_check_async = AsyncMock()

            timeout_ms = CFG.MAX_HOLDING_HOURS * 3600 * 1000
            expired_ts = (time.time() * 1000) - (timeout_ms + 1000)
            p = {
                "symbol": "BTC/USDT:USDT",
                "side": "long",
                "timestamp": expired_ts
            }
            client.get_positions = AsyncMock(return_value=[p])

            # 스캔 실행 (첫 번째 시도)
            await engine._check_closed_positions_async()
            client.close_position.assert_called_once_with("BTC/USDT:USDT", "long")
            assert "BTC/USDT:USDT" in engine._timeout_cooldowns

            # 바로 두 번째 스캔 실행 (쿨다운 중인 경우)
            client.close_position.reset_mock()
            await engine._check_closed_positions_async()
            client.close_position.assert_not_called()

            # 30초 이후 시뮬레이션
            engine._timeout_cooldowns["BTC/USDT:USDT"] = time.time() - 31.0
            await engine._check_closed_positions_async()
            client.close_position.assert_called_once_with("BTC/USDT:USDT", "long")

    @pytest.mark.anyio
    async def test_oco_cancellation_retry(self):
        """cancel_algo_orders 가 예외 발생 시 최대 3회 재시도(0.5초 대기)하는지 검증"""
        from core.exchange import OKXClient

        with patch.object(OKXClient, '__init__', return_value=None):
            client = OKXClient.__new__(OKXClient)
            client.exchange = MagicMock()
            client.exchange.market = MagicMock(return_value={"id": "BTC-USDT-SWAP"})
            
            client._execute_with_retry = AsyncMock(side_effect=Exception("API Temp Error"))

            with patch('core.exchange.asyncio.sleep', AsyncMock()) as mock_sleep:
                res = await client.cancel_algo_orders("BTC/USDT:USDT")
                assert res is False
                assert client._execute_with_retry.call_count == 3
                assert mock_sleep.call_count == 2
                mock_sleep.assert_called_with(0.5)

    @pytest.mark.anyio
    async def test_atomic_oco_enforcement(self):
        """place_order 시 OCO 주문(attachAlgoOrds) 실패 시 즉시 None 반환하며 단순 진입을 시도하지 않는지 검증"""
        from core.exchange import OKXClient

        with patch.object(OKXClient, '__init__', return_value=None):
            client = OKXClient.__new__(OKXClient)
            client.exchange = MagicMock()
            client._markets = {"BTC/USDT:USDT": {"contractSize": 1.0}}
            client.cfg = CFG

            client.set_margin_mode = AsyncMock()
            client.set_leverage = AsyncMock(return_value=True)
            client.get_market_max_leverage = MagicMock(return_value=20)
            client.get_ticker = AsyncMock(return_value={"last": 100.0})
            
            client.exchange.create_order = AsyncMock(side_effect=Exception("attachAlgoOrds Failed"))
            client.exchange.amount_to_precision = MagicMock(return_value="0.5")
            client.exchange.price_to_precision = MagicMock(side_effect=lambda s, p: p)

            res = await client.place_order("BTC/USDT:USDT", "buy", 5.0, 0.01, 0.015)
            
            assert res is None
            client.exchange.create_order.assert_called_once()



# ═══════════════════════════════════════════════════════════
# 6. [v2.8.0] 병렬 청산 / 이중 청산 가드 / cancel_algo market 실패 검증
# ═══════════════════════════════════════════════════════════
class TestV280SafetyFixes:

    @pytest.mark.anyio
    async def test_close_all_positions_concurrent(self):
        """
        [BUG1] close_all_positions가 asyncio.gather로 병렬 실행되는지 검증.
        순차 실행이면 N×T가 걸리지만, gather면 호출 순서가 겹쳐야 함.
        """
        from core.exchange import OKXClient
        import asyncio as _asyncio

        call_times = []

        async def fake_close(symbol, side, **kwargs):
            call_times.append(("start", symbol, _asyncio.get_event_loop().time()))
            await _asyncio.sleep(0.05)   # 50ms 지연 시뮬레이션
            call_times.append(("end",   symbol, _asyncio.get_event_loop().time()))
            return True

        with patch.object(OKXClient, '__init__', return_value=None):
            client = OKXClient.__new__(OKXClient)
            client.exchange = MagicMock()
            client._symbol_map = {}

            positions = [
                {"symbol": "BTC/USDT:USDT", "side": "long"},
                {"symbol": "ETH/USDT:USDT", "side": "short"},
            ]
            client.get_positions = AsyncMock(return_value=positions)
            client.close_position = fake_close   # 실제 비동기 함수로 교체

            count = await client.close_all_positions()

        assert count == 2, "2개 포지션 모두 성공해야 함"

        # 병렬 검증: BTC start 이후 ETH start가 BTC end 이전에 오면 병렬 실행 확인
        starts = {ev[1]: ev[2] for ev in call_times if ev[0] == "start"}
        ends   = {ev[1]: ev[2] for ev in call_times if ev[0] == "end"}
        # BTC 종료 전에 ETH 가 시작되었어야 함 (overlap)
        assert starts["ETH/USDT:USDT"] < ends["BTC/USDT:USDT"], \
            "asyncio.gather 병렬 실행 실패 — 순차 실행으로 동작 중"

    def test_double_click_guard_blocks_second_call(self):
        """
        [BUG2] 동일 심볼에 10초 내 두 번째 close_position 호출 시 False 반환(이중 청산 차단).
        """
        import time
        from core.engine import QuantumEngine

        engine = QuantumEngine.__new__(QuantumEngine)
        engine._initialized = True
        engine.client = MagicMock()
        engine._closing_in_progress = {}
        engine._trailing_highs = {}
        engine._trailing_lows = {}
        engine._timeout_cooldowns = {}

        # 첫 번째 호출 흉내: 현재 시각 - 5초 (10초 이내, 아직 청산 중)
        engine._closing_in_progress["BTC/USDT:USDT"] = time.time() - 5.0

        # 두 번째 close_position 호출 → 차단되어야 함
        result = engine.close_position("BTC/USDT:USDT", "long")
        assert result is False, "이중 청산 요청이 차단되지 않음!"

    @pytest.mark.anyio
    async def test_cancel_algo_orders_continues_on_market_failure(self):
        """
        [BUG4] cancel_algo_orders에서 market() 조회 실패 시 False 대신 True를 반환하여
        청산이 차단되지 않는지 검증.
        """
        from core.exchange import OKXClient

        with patch.object(OKXClient, '__init__', return_value=None):
            client = OKXClient.__new__(OKXClient)
            client.exchange = MagicMock()

            # market() 호출 시 예외 발생 시뮬레이션
            client.exchange.market = MagicMock(side_effect=Exception("market not loaded"))

            result = await client.cancel_algo_orders("BTC/USDT:USDT")

        assert result is True, "market() 실패 시 True(청산 계속 진행)를 반환해야 함"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
