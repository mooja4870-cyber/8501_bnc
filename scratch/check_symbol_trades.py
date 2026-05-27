import sys
import os
import pandas as pd

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def check_symbol(symbol):
    df = pd.read_csv('data/trade_history.csv')
    df.columns = [c.strip() for c in df.columns]
    sym_df = df[df['심볼'] == symbol]
    print(f"Total raw trades for {symbol}: {len(sym_df)}")
    for _, row in sym_df.iterrows():
        print(f"{row['시간']} | {row['유형']} | {row['방향']} | 가격: {row['가격']} | 수량: {row['수량']} | PnL: {row['수익(USDT)']} | 주문ID: {row['주문ID']}")

if __name__ == '__main__':
    symbol = 'BSB/USDT:USDT'
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    check_symbol(symbol)
