import sys
sys.path.insert(0, r"d:\chord\literature-tracker")
from sources import fetch_boj
papers = fetch_boj(cache_ttl=0)
print(f"BOJ papers found: {len(papers)}")
for p in papers[:8]:
    print(f"  [{p['date']}] {p['title'][:100]}")
    print(f"    PDF: {p.get('pdf_url','N/A')[:100]}")
    print()
