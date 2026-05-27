import os
import sys
import asyncio
from dotenv import load_dotenv

sys.path.append(os.getcwd())
from core.exchange import BinanceClient

async def main():
    load_dotenv()
    api_key = os.getenv('BINANCE_API_KEY')
    secret_key = os.getenv('BINANCE_SECRET_KEY')
    
    client = BinanceClient(api_key, secret_key)
    try:
        if await client.load_markets():
            bal = await client.get_balance()
            print("Balance Info:", bal)
    except Exception as e:
        print("Error:", e)
    finally:
        await client.close()

if __name__ == '__main__':
    asyncio.run(main())
