import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"d:\chord\literature-tracker")
from sources import list_finalized_compilations
from md_to_docx import convert as convert_to_docx

NOTES_DIR = r"D:\搭建知识库\个人工作流\成长日记\Notes"
OUT_DIR = r"D:\搭建知识库\个人工作流\成长日记\Attachments"

finalized = list_finalized_compilations(NOTES_DIR)
print(f"Found {len(finalized)} finalized compilations:")
for c in finalized:
    print(f"  [{c['source']}] {c['title'][:60]}")
    print(f"    filepath: {c['filepath']}")
    print(f"    exists: {__import__('os').path.exists(c['filepath'])}")

    # Test convert
    try:
        b_path, s_path = convert_to_docx(c["filepath"], OUT_DIR)
        print(f"    ✅ {__import__('os').path.basename(b_path)}")
    except Exception as e:
        print(f"    ❌ ERROR: {e}")
    print()
