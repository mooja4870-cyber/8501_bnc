import pandas as pd
import os

path = "data/trade_history.csv"
if os.path.exists(path):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    
    # Check if 1872798559 is in any column
    matched = df[df.astype(str).apply(lambda x: x.str.contains("1872798559")).any(axis=1)]
    print(f"Matched rows for 1872798559: {len(matched)}")
    for idx, row in matched.iterrows():
        print(f"Row {idx}: {row.to_dict()}")
else:
    print("File not found")
