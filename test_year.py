import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"d:\chord\literature-tracker")
from sources import fetch_boj, _get_boj_year

print("Default year:", _get_boj_year())
print("Override year:", _get_boj_year({"source_year": 2025}))

papers = fetch_boj(0, {"source_year": 2026})
print(f"Papers found: {len(papers)}")
for p in papers[:3]:
    print(f"  [{p['date']}] {p['title'][:80]}")
