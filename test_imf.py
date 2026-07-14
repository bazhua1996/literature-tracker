import sys
sys.path.insert(0, r"d:\chord\literature-tracker")
from sources import fetch_imf
papers = fetch_imf(cache_ttl=0)
print(f"IMF papers found: {len(papers)}")
for p in papers:
    print(f"  [{p['date']}] {p['title'][:100]}")
