import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from dotenv import load_dotenv
from core.exchange import BinanceClient
from core.engine import QuantumEngine
from core.history_helper import load_local_trade_history, _trade_dedupe_key

async def main():
    load_dotenv(override=True)
    api_key = os.getenv("BINANCE_API_KEY")
    secret_key = os.getenv("BINANCE_SECRET_KEY")
    
    engine = QuantumEngine()
    await engine._initialize_async(api_key, secret_key, "")
    
    local_trades = load_local_trade_history()
    logged_keys = {_trade_dedupe_key(t) for t in local_trades}
    lots = engine._remaining_lots(local_trades)
    
    symbol = "ADA/USDT:USDT"
    print(f"=== Debugging Sync for {symbol} ===")
    exchange_trades = await engine.client.get_trade_history(symbol=symbol, limit=100)
    print(f"Found {len(exchange_trades)} trades on exchange.")
    
    for trade in sorted(exchange_trades, key=lambda x: x.get("timestamp")):
        key = engine._exchange_trade_key(trade)
        in_logged = key in logged_keys
        category = engine._infer_trade_category(trade, lots)
        print(f"ID={trade['id']}, Time={trade['timestamp']}, Side={trade['side']}, Qty={trade['amount']}, PnL={trade['pnl']}, Key={key}, InLogged={in_logged}, InferredCategory={category}")
        
    await engine.client.exchange.close()

if __name__ == "__main__":
    asyncio.run(main())
