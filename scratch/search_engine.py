import os

for root, dirs, files in os.walk("."):
    if ".git" in root or "__pycache__" in root or ".pytest_cache" in root:
        continue
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                if "def get_scan_results" in content or "get_scan_results" in content:
                    print(f"Found in {path}")
