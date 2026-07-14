import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"d:\chord\literature-tracker")
from sources import extract_pdf_text, _guess_metadata_from_pdf

pdf_path = r"D:\搭建知识库\个人工作流\ecb.ebaecb202512.en(1).pdf"
text = extract_pdf_text(pdf_path)
print(f"Extracted {len(text)} chars")
print("--- first 500 chars ---")
print(text[:500])

meta = _guess_metadata_from_pdf(text)
print("\n--- metadata ---")
for k, v in meta.items():
    print(f"  {k}: {v}")
