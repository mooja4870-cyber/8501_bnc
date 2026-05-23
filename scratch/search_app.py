with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "RSI" in line or "rsi" in line or "EMA" in line or "ema" in line or "Table" in line or "table" in line:
        if "st.dataframe" in line or "columns" in line or "markdown" in line or "pd.DataFrame" in line:
            print(f"Line {idx+1}: {line.strip()}")
