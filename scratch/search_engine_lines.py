with open("core/engine.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "get_scan_results" in line or "def get_scan_results" in line or "scan_results" in line:
        print(f"Line {idx+1}: {line.strip()}")
