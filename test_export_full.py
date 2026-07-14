"""完整模拟 Streamlit 导出流程"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"d:\chord\literature-tracker")

# 模拟 app.py 的完整路径
CONFIG_PATH = r"d:\chord\literature-tracker\config.json"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

DOWNLOAD_DIR = config["download_dir"]
VAULT_NOTES_DIR = config["vault_notes_dir"]

from sources import scan_vault_status, find_compilation_md, list_finalized_compilations
from md_to_docx import convert as convert_to_docx

# 步骤1: 扫描 vault 状态
print("Step 1: scan_vault_status")
status_map = scan_vault_status(VAULT_NOTES_DIR)
print(f"  Status map: {status_map}")

# 步骤2: 模拟 BOJ 论文的 detail_url
test_url = "https://www.boj.or.jp/en/mopo/mpmdeci/state_2026/index.htm"
status = status_map.get(test_url, "")
print(f"  BOJ paper status: '{status}'")

# 步骤3: find_compilation_md
md_path = find_compilation_md(test_url, VAULT_NOTES_DIR)
print(f"  Found .md: {md_path}")

# 步骤4: convert_to_docx
if md_path and os.path.exists(md_path):
    print("Step 4: convert_to_docx")
    try:
        b, s = convert_to_docx(md_path, DOWNLOAD_DIR)
        print(f"  ✅ {os.path.basename(b)}")
        print(f"  ✅ {os.path.basename(s)}")
    except Exception as e:
        print(f"  ❌ {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"Step 4: SKIP (md_path={md_path})")

# 步骤5: list_finalized_compilations
print("\nStep 5: list_finalized_compilations")
finalized = list_finalized_compilations(VAULT_NOTES_DIR)
for c in finalized:
    print(f"  [{c['source']}] {c['title'][:60]}")
    print(f"    path: {c['filepath']}")
print(f"  Total: {len(finalized)}")
