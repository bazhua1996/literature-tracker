import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"d:\chord\literature-tracker")
from sources import find_compilation_md, _iter_vault_md

NOTES_DIR = r"D:\搭建知识库\个人工作流\成长日记\Notes"

# Test _iter_vault_md
print("=== _iter_vault_md ===")
count = 0
for filepath, fm in _iter_vault_md(NOTES_DIR):
    count += 1
    status = fm.get("status", "N/A")
    paper = fm.get("paper", {})
    url = paper.get("detail_url", "N/A") if isinstance(paper, dict) else "N/A"
    print(f"  [{status}] {os.path.basename(filepath)}")
    print(f"    url: {url[:80]}")
print(f"Total: {count}")

# Test find_compilation_md
print("\n=== find_compilation_md ===")
test_url = "https://www.boj.or.jp/en/mopo/mpmdeci/state_2026/index.htm"
result = find_compilation_md(test_url, NOTES_DIR)
print(f"BOJ URL match: {result}")
import os
