import pandas as pd
import os

path = "data/trade_history.csv"
if os.path.exists(path):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    ada_df = df[df["심볼"].str.contains("ADA", na=False)]
    for idx, row in ada_df.iterrows():
        print(f"Row {idx}: Time={row['시간']}, Symbol={row['심볼']}, Type={repr(row['유형'])}, Side={row['방향']}, Price={row['가격']}, Qty={row['수량']}, PnL={row['수익(USDT)']}, OrderID={row['주문ID']}")
else:
    print("File not found")
