import pandas as pd
import os

path = "data/trade_history.csv"
if os.path.exists(path):
    df = pd.read_csv(path, encoding="utf-8-sig")
    print("Columns:", list(df.columns))
    print("Columns (repr):", [repr(c) for c in df.columns])
else:
    print("File not found")
