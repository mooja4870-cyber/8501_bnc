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
    
    if not api_key:
        print("API keys not found in .env")
        return
        
    client = BinanceClient(api_key, secret_key)
    try:
        positions = await client.get_positions()
        print(f"Total open positions on exchange: {len(positions)}")
        for p in positions:
            print(p)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await client.close()

if __name__ == '__main__':
    asyncio.run(main())
