import os
import json

log_path = r"C:\Users\mooja\.gemini\antigravity-ide\brain\7136c0e7-4d75-46a6-a174-674b75def288\.system_generated\logs\transcript.jsonl"
out_path = r"d:\AI\project\8501_bnc\scratch\prompt_output.txt"

# If transcript.jsonl doesn't exist, search overview.txt or other files in the logs dir
logs_dir = os.path.dirname(log_path)
print("Logs dir contents:", os.listdir(logs_dir) if os.path.exists(logs_dir) else "Does not exist")

with open(out_path, "w", encoding="utf-8") as out:
    # Scan overview.txt
    overview_path = os.path.join(logs_dir, "overview.txt")
    if os.path.exists(overview_path):
        out.write("=== OVERVIEW.TXT ===\n")
        with open(overview_path, "r", encoding="utf-8", errors="ignore") as f:
            out.write(f.read())
        out.write("\n\n" + "="*80 + "\n\n")
        
    # Scan transcript.jsonl if exists
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    content = data.get("content", "")
                    if "소스 구조" in content or "감사" in content:
                        out.write(f"=== STEP {data.get('step_index')} ===\n")
                        out.write(content)
                        out.write("\n\n" + "="*80 + "\n\n")
                except Exception as e:
                    pass
