import os
import sys
import asyncio
sys.path.append('d:\\AI\\project\\8501_bnc')
from dotenv import load_dotenv
load_dotenv('d:\\AI\\project\\8501_bnc\\.env')
from core.exchange import BinanceClient

async def main():
    api_key = os.getenv('BINANCE_API_KEY') or os.getenv('OKX_API_KEY')
    secret_key = os.getenv('BINANCE_SECRET_KEY') or os.getenv('OKX_SECRET_KEY')
    passphrase = os.getenv('BINANCE_PASSPHRASE') or os.getenv('OKX_PASSPHRASE', '')
    
    if not api_key:
        print("API keys not found in .env")
        return
        
    client = BinanceClient(api_key, secret_key, passphrase)
    try:
        pos = await client.get_positions()
        print(pos[0])
    except Exception as e:
        print(f"Error fetching positions: {e}")
    finally:
        await client.close()

if __name__ == '__main__':
    asyncio.run(main())
