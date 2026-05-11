import unittest

from core.config import CFG
from core.exchange import OKXClient
from core.strategy import Signal
from core.trader import AutoTrader
import core.trader as trader_module


class FakeExchange:
    def __init__(self, precision_amount=None):
        self.precision_amount = precision_amount
        self.created_orders = []

    def set_leverage(self, leverage, symbol, params=None):
        self.leverage = leverage

    def fetch_ticker(self, symbol):
        return {
            "last": 100.0,
            "bid": 99.9,
            "ask": 100.1,
            "quoteVolume": 1_000_000,
            "percentage": 0,
        }

    def amount_to_precision(self, symbol, amount):
        return str(self.precision_amount if self.precision_amount is not None else amount)

    def price_to_precision(self, symbol, price):
        return str(round(price, 4))

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        self.created_orders.append({
            "symbol": symbol,
            "type": type,
            "side": side,
            "amount": amount,
            "price": price,
            "params": params or {},
        })
        return {"id": f"order-{len(self.created_orders)}", "average": 100.0}


class FakeTraderClient:
    def __init__(self):
        self.orders = []

    def get_positions(self):
        return []

    def get_open_orders(self):
        return []

    def get_balance(self):
        return {"total": 100.0, "free": 100.0, "used": 0.0}

    def place_order(self, symbol, side, margin_usdt):
        self.orders.append({"symbol": symbol, "side": side, "margin_usdt": margin_usdt})
        return {"entry_price": 100.0, "sl_price": 98.5, "tp_price": 102.0}


def make_signal(symbol="BTC/USDT:USDT"):
    return Signal(
        symbol=symbol,
        direction="long",
        strength=80,
        ema_ok=True,
        bb_ok=True,
        macd_ok=True,
        close=100.0,
        ema200=90.0,
        bb_upper=110.0,
        bb_lower=95.0,
        macd_hist=1.0,
        reason="test",
    )


class TradeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.original_leverage = CFG.LEVERAGE
        self.original_margin = CFG.MARGIN_USDT
        self.original_cooldown = CFG.ENTRY_COOLDOWN_SEC
        self.original_record_order = trader_module.stats_store.record_order

    def tearDown(self):
        CFG.LEVERAGE = self.original_leverage
        CFG.MARGIN_USDT = self.original_margin
        CFG.ENTRY_COOLDOWN_SEC = self.original_cooldown
        trader_module.stats_store.record_order = self.original_record_order

    def test_place_order_rejects_margin_above_configured_one_x(self):
        CFG.LEVERAGE = 10
        fake_exchange = FakeExchange(precision_amount=2.0)
        client = object.__new__(OKXClient)
        client.exchange = fake_exchange
        client._markets = {"BTC/USDT:USDT": {"contractSize": 1.0}}

        result = OKXClient.place_order(client, "BTC/USDT:USDT", "buy", margin_usdt=5.0)

        self.assertIsNone(result)
        self.assertEqual(fake_exchange.created_orders, [])

    def test_place_order_uses_configured_margin_when_precision_allows(self):
        CFG.LEVERAGE = 10
        fake_exchange = FakeExchange()
        client = object.__new__(OKXClient)
        client.exchange = fake_exchange
        client._markets = {"BTC/USDT:USDT": {"contractSize": 1.0}}

        result = OKXClient.place_order(client, "BTC/USDT:USDT", "buy", margin_usdt=5.0)

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["estimated_margin_usdt"], 5.0)
        self.assertAlmostEqual(fake_exchange.created_orders[0]["amount"], 0.5)

    def test_same_symbol_signal_is_blocked_by_entry_cooldown(self):
        CFG.MARGIN_USDT = 5.0
        CFG.ENTRY_COOLDOWN_SEC = 180
        trader_module.stats_store.record_order = lambda: None

        client = FakeTraderClient()
        trader = AutoTrader(client)
        trader.enable()
        signal = make_signal()

        trader.on_signal(signal)
        trader.on_signal(signal)

        self.assertEqual(len(client.orders), 1)


if __name__ == "__main__":
    unittest.main()
