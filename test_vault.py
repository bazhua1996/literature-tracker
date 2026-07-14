import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"d:\chord\literature-tracker")
from sources import scan_vault_status, generate_draft

NOTES_DIR = r"D:\搭建知识库\个人工作流\成长日记\Notes"

# 测试 1: 扫描现有 vault
print("=" * 50)
print("📊 扫描 Vault 编译状态")
status_map = scan_vault_status(NOTES_DIR)
print(f"找到 {len(status_map)} 篇编译稿:")
for url, status in status_map.items():
    print(f"  [{status}] {url[-60:]}")

# 测试 2: 生成编译草稿
print("\n" + "=" * 50)
print("📝 测试生成编译草稿")
test_paper = {
    "title": "Test Paper - This is a test",
    "date": "2026-07-10",
    "source": "BOJ",
    "authors": "",
    "paper_type": "MPM Statement",
    "detail_url": "https://www.boj.or.jp/test/test.pdf",
    "pdf_url": "https://www.boj.or.jp/test/test.pdf",
    "report_number": "",
}
success, result = generate_draft(test_paper, NOTES_DIR)
if success:
    print(f"✅ 草稿已生成: {result}")
else:
    print(f"❌ 生成失败: {result}")

# 再次扫描验证
print("\n" + "=" * 50)
print("📊 再次扫描（验证草稿已发现）")
status_map2 = scan_vault_status(NOTES_DIR)
test_url = test_paper["detail_url"]
if test_url in status_map2:
    print(f"✅ 测试草稿状态: {status_map2[test_url]}")
else:
    print("⚠️ 未找到测试草稿")
