with open("core/engine.py", "r", encoding="utf-8", errors="ignore") as f:
    for i, line in enumerate(f):
        if "is_ready" in line:
            print(f"{i+1}: {line.strip()}")
