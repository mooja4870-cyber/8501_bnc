with open("core/scanner.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "get_results" in line or "def get_results" in line or "results" in line:
        if "def " in line or "append" in line or "dict" in line or "return" in line:
            print(f"Line {idx+1}: {line.strip()}")
