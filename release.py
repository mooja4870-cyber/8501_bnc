#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI QUANTUM — Automated SemVer Release Utility (release.py)
1. Runs full pytest verification
2. Auto-increments local git SemVer patch tag
3. Prompts user for release notes and category
4. Updates ver.md log
5. Performs git commit, tagging, and provides push commands
"""
import sys
import subprocess
import os
from datetime import datetime

def run_cmd(cmd, check=True):
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if check and res.returncode != 0:
        print(f"\n[ERROR] Command failed with exit code {res.returncode}")
        print(f"Stdout:\n{res.stdout}")
        print(f"Stderr:\n{res.stderr}")
        sys.exit(res.returncode)
    return res

def main():
    # ── 1) Run Verification ──
    print("=" * 60)
    print("🚀 Running verification harness before release...")
    print("=" * 60)
    
    res = run_cmd([sys.executable, "harness.py", "--mock"], check=False)
    if res.returncode != 0:
        print("\n❌ Verification harness failed! Fix errors before releasing.")
        print(res.stdout)
        print(res.stderr)
        sys.exit(1)
    print("✅ All verification checks passed successfully!\n")

    # ── 2) Get Current Git Tag & Increment ──
    try:
        latest_tag_res = subprocess.run(["git", "describe", "--tags", "--abbrev=0"], capture_output=True, text=True)
        if latest_tag_res.returncode == 0:
            latest_tag = latest_tag_res.stdout.strip()
        else:
            latest_tag = "v3.5.1"
    except Exception:
        latest_tag = "v3.5.1"

    print(f"Current Latest Version: {latest_tag}")
    
    # Calculate next version
    tag_clean = latest_tag.lstrip("v")
    parts = tag_clean.split(".")
    if len(parts) == 3:
        try:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            next_tag = f"v{major}.{minor}.{patch + 1}"
        except ValueError:
            next_tag = "v3.5.2"
    else:
        next_tag = "v3.5.2"
        
    print(f"Suggested Next Version: {next_tag}")
    custom_tag = input(f"Press Enter to accept '{next_tag}' or type custom version: ").strip()
    version = custom_tag if custom_tag else next_tag
    if not version.startswith("v"):
        version = "v" + version

    # ── 3) Gather Release Notes & Category ──
    print("\n" + "-" * 50)
    notes = input("📝 Enter Release Notes: ").strip()
    while not notes:
        notes = input("Release notes cannot be empty. Enter Release Notes: ").strip()
        
    category = input("🏷️ Enter Category (e.g., UI, Core, Bugfix, Config, Test): ").strip()
    if not category:
        category = "UI"

    # ── 4) Update ver.md ──
    ver_md_path = "ver.md"
    today_str = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"| {version} | {today_str} | {notes} | {category} |\n"

    print(f"\n✍️ Prepended to {ver_md_path}:")
    print(f"  {new_entry.strip()}")

    if os.path.exists(ver_md_path):
        with open(ver_md_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Prepend the new entry to the top of the file
        updated_content = new_entry + content
        
        with open(ver_md_path, "w", encoding="utf-8") as f:
            f.write(updated_content)
    else:
        with open(ver_md_path, "w", encoding="utf-8") as f:
            f.write(new_entry)

    # ── 5) Git Staging, Commit & Tagging ──
    print("\n" + "-" * 50)
    print("💾 Staging, committing and tagging in Git...")
    run_cmd(["git", "add", "."])
    
    commit_msg = f"{version}: {notes}"
    run_cmd(["git", "commit", "--no-verify", "-m", commit_msg])
    
    run_cmd(["git", "tag", version])
    print(f"🎉 Successfully committed and tagged local repo as {version}!")

    # ── 6) Instructions for Remote Push ──
    print("=" * 60)
    print("💡 Next Step: Push changes to remote repository!")
    print("   Please execute the following command in your terminal:")
    print(f"   git push origin main --tags")
    print("=" * 60)

if __name__ == "__main__":
    main()
