import sys
import os
import pandas as pd

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    df = pd.read_csv('data/trade_history.csv')
    df.columns = [c.strip() for c in df.columns]
    bsb = df[(df['심볼'] == 'BSB/USDT:USDT') & (df['시간'].str.contains('2026-05-27 02:24:29'))]
    print("=== Raw CSV rows for BSB at 02:24:29 ===")
    print(bsb)

if __name__ == '__main__':
    main()
