"""
Vault 模块 — Obsidian vault 文件系统操作。

封装 vault 遍历、frontmatter 索引、草稿创建、PDF 文本提取和元数据猜测。
一次文件系统遍历，N 个视图查询。
"""

import os
import re
import yaml
from datetime import datetime
from typing import Optional


# ═══════════════════════════════════════════
#  模块级工具函数
# ═══════════════════════════════════════════

def parse_frontmatter(content: str) -> Optional[dict]:
    """从 .md 内容中提取 YAML frontmatter。没有则返回 None。"""
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    try:
        return yaml.safe_load(content[3:end]) or {}
    except Exception:
        return None


def extract_pdf_text(pdf_path: str, max_chars: int = 200000) -> str:
    """从 PDF 文件提取全部文本。默认上限 200000 字符。"""
    if not pdf_path or not os.path.exists(pdf_path):
        return ""
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
                if len(text) >= max_chars:
                    break
        return text[:max_chars]
    except Exception as e:
        print(f"[PDF] 提取失败 {pdf_path}: {e}")
        return ""


def guess_metadata_from_pdf(pdf_text: str) -> dict:
    """从 PDF 文本猜测元数据：标题、机构、日期、关键数字。"""
    meta = {"title": "", "institution": "", "date": "", "key_figures": []}
    if not pdf_text:
        return meta

    lines = [l.strip() for l in pdf_text.split("\n") if l.strip()]

    # 猜测标题：前 30 行中大写为主的行（合并为完整标题）
    upper_lines = []
    for l in lines[:30]:
        upper_ratio = sum(1 for c in l if c.isupper() or c.isdigit() or c in " /-") / max(len(l), 1)
        if upper_ratio > 0.5 and len(l) > 5:
            upper_lines.append(l)
    if upper_lines:
        meta["title"] = " ".join(upper_lines[:4])[:200]

    # 猜测机构（从 source.py 获取集中定义的机构关键词）
    from source import get_builtin_institution_keywords
    institution_keywords = get_builtin_institution_keywords()
    combined = pdf_text[:5000]
    for full, abbr in institution_keywords:
        if full.lower() in combined.lower():
            meta["institution"] = f"{full} ({abbr})"
            break

    # 猜测日期
    date_patterns = [
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
        r'\d{4}\s+(January|February|March|April|May|June|July|August|September|October|November|December)',
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}',
    ]
    for pat in date_patterns:
        m = re.search(pat, combined, re.IGNORECASE)
        if m:
            meta["date"] = m.group(0).strip()
            break

    # 猜测关键数字（大额 EUR 数值 + 百分比）
    figures = re.findall(r'EUR\s*([\d,.]+)\s*(billion|million|trillion)', combined, re.IGNORECASE)
    for amount, unit in figures[:5]:
        meta["key_figures"].append(f"EUR {amount} {unit}")
    pct_figures = re.findall(r'(\d+\.?\d*)\s*%', combined)
    for pct in pct_figures[:3]:
        if float(pct) < 100:
            meta["key_figures"].append(f"{pct}%")

    return meta


# ═══════════════════════════════════════════
#  Vault 类
# ═══════════════════════════════════════════

class Vault:
    """
    Obsidian vault 的 Notes 目录索引视图。

    构造时遍历文件系统一次，构建内存索引。
    所有后续查询（status_map、find、finalized）从索引提供，无需额外磁盘访问。

    create_draft() 和 update_frontmatter() 修改文件系统并同步更新索引。
    """

    def __init__(self, notes_dir: str):
        self.notes_dir = notes_dir
        self._by_url: dict[str, tuple[str, str]] = {}   # detail_url → (filepath, status)
        self._by_pdf: dict[str, tuple[str, str]] = {}   # pdf_path → (filepath, status)
        self._all: list[dict] = []                        # 全部编译稿信息
        self._fm_cache: dict[str, dict] = {}              # filepath → 完整 frontmatter

        if notes_dir and os.path.isdir(notes_dir):
            self._build_index()

    @property
    def is_ready(self) -> bool:
        """vault 路径是否已配置且可访问。"""
        return bool(self.notes_dir) and os.path.isdir(self.notes_dir)

    # ── 索引构建 ─────────────────────────────────

    def _build_index(self) -> None:
        """遍历文件系统，填充所有索引。跳过 .trash 和 .obsidian 目录。"""
        for root, dirs, files in os.walk(self.notes_dir):
            if os.path.basename(root) in (".trash", ".obsidian"):
                dirs[:] = []
                continue
            for fname in files:
                if not fname.endswith(".md"):
                    continue
                filepath = os.path.join(root, fname)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    fm = parse_frontmatter(content)
                    if not fm:
                        continue

                    self._fm_cache[filepath] = fm
                    status = fm.get("status", "")
                    paper = fm.get("paper", {})
                    if not isinstance(paper, dict):
                        paper = {}
                    detail_url = paper.get("detail_url", "")
                    pdf_path = paper.get("pdf_path", paper.get("pdf_url", ""))

                    if status and detail_url:
                        self._by_url[detail_url] = (filepath, status)
                    if status and pdf_path:
                        self._by_pdf[pdf_path] = (filepath, status)

                    self._all.append({
                        "filepath": filepath,
                        "title": paper.get("title", os.path.basename(filepath)),
                        "date": paper.get("date", ""),
                        "source": paper.get("source", ""),
                        "detail_url": detail_url,
                        "status": status,
                    })
                except Exception:
                    continue

    def refresh(self) -> None:
        """重新扫描文件系统并重建索引。外部变更后使用。"""
        self._by_url.clear()
        self._by_pdf.clear()
        self._all.clear()
        self._fm_cache.clear()
        if self.notes_dir and os.path.isdir(self.notes_dir):
            self._build_index()

    # ── 查询 API ────────────────────────────────

    def status_map(self) -> dict[str, str]:
        """返回 {key: status} 映射，key 为 detail_url 或 pdf_path。O(1) — 从索引提供。"""
        result = {url: status for url, (_, status) in self._by_url.items()}
        result.update({pdf: status for pdf, (_, status) in self._by_pdf.items()})
        return result

    def find(self, detail_url: str) -> Optional[str]:
        """按 detail_url 或 pdf_path 查找 .md 文件路径。O(1)。找不到返回 None。"""
        entry = self._by_url.get(detail_url)
        if not entry:
            entry = self._by_pdf.get(detail_url)
        return entry[0] if entry else None

    def finalized(self) -> list[dict]:
        """
        返回所有 status=已定稿 的编译稿列表。
        每项: {filepath, title, date, source, detail_url}。按日期降序排列。
        """
        results = [e for e in self._all if e.get("status") == "已定稿"]
        return sorted(results, key=lambda r: r.get("date", ""), reverse=True)

    def paper_title(self, detail_url: str) -> str:
        """按 detail_url 查找编译稿中的中文标题。没有则返回空字符串。"""
        entry = self._by_url.get(detail_url)
        if entry:
            fm = self._fm_cache.get(entry[0], {})
            paper = fm.get("paper", {})
            if isinstance(paper, dict):
                return paper.get("title", "")
        return ""

    # ── 变更 API ────────────────────────────────

    def create_draft(self, paper: dict, pdf_text: str = "") -> str:
        """
        在 vault 中创建编译草稿 .md 文件。
        若提供 pdf_text，自动预填引用行和摘要中的关键数据。
        返回创建的文件路径。出错抛异常。
        """
        title = paper.get("title", "Untitled")
        date = paper.get("date", datetime.now().strftime("%Y-%m-%d"))
        source = paper.get("source", "Unknown")
        pdf_meta = guess_metadata_from_pdf(pdf_text) if pdf_text else {}

        # 标题优先使用 PDF 检测到的
        display_title = pdf_meta.get("title") or title

        # 生成文件名: YYYY-MM-DD SOURCE-Title.md
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', display_title)[:80]
        safe_title = re.sub(r'\s+', '-', safe_title)
        filename = f"{date} {source}-{safe_title}.md"
        filepath = os.path.join(self.notes_dir, filename)

        # 同名文件自动递增版本号
        counter = 1
        while os.path.exists(filepath):
            filename = f"{date} {source}-{safe_title}-{counter}.md"
            filepath = os.path.join(self.notes_dir, filename)
            counter += 1

        # 构建 frontmatter
        fm = {
            "status": "已发现",
            "paper": {
                "title": title,
                "date": date,
                "source": source,
                "authors": paper.get("authors", ""),
                "paper_type": paper.get("paper_type", ""),
                "detail_url": paper.get("detail_url", ""),
                "pdf_path": paper.get("pdf_url", ""),
                "report_number": paper.get("report_number", ""),
            },
            "tags": [source],
            "created": datetime.now().strftime("%Y-%m-%d"),
        }

        # 构建 citation 行
        citation_parts = []
        if pdf_meta.get("title"):
            citation_parts.append(pdf_meta["title"])
        else:
            citation_parts.append(paper.get("paper_type", ""))
        if pdf_meta.get("institution"):
            citation_parts.append(pdf_meta["institution"])
        else:
            citation_parts.append(source)
        if pdf_meta.get("date") or date:
            citation_parts.append(pdf_meta.get("date") or date)
        citation_line = " | ".join(citation_parts)

        # 构建摘要预填
        abstract_hint = ""
        if pdf_meta.get("key_figures"):
            figures_text = "、".join(pdf_meta["key_figures"][:8])
            abstract_hint = f"报告显示，{figures_text}。"

        # 构建 Markdown 正文（按编译规范模板）
        body = f"""---
{yaml.dump(fm, allow_unicode=True, default_flow_style=False)}---

# 关于{source}《{display_title}》的分析

> {citation_line}

**摘要：** {abstract_hint}

**关键词：**

## 一、引言与背景


## 二、


## 三、


## 四、


## 五、


## 六、


## 七、


## 八、结论与政策启示


## 标签

#{source}
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(body)

        # 同步更新内存索引
        detail_url = paper.get("detail_url", "")
        pdf_path = paper.get("pdf_url", "")
        self._fm_cache[filepath] = fm
        if fm.get("status") and detail_url:
            self._by_url[detail_url] = (filepath, fm["status"])
        if fm.get("status") and pdf_path:
            self._by_pdf[pdf_path] = (filepath, fm["status"])
        self._all.append({
            "filepath": filepath,
            "title": title,
            "date": date,
            "source": source,
            "detail_url": detail_url,
            "status": fm.get("status", ""),
        })

        return filepath

    def update_frontmatter(self, md_path: str, updates: dict,
                           revision_note: str = "") -> dict:
        """
        读取 .md 文件，解析 YAML frontmatter，合并 updates，写回。
        若提供 revision_note，追加到 revision_history（保留最近 10 条）。
        返回更新后的完整 frontmatter 字典。
        """
        with open(md_path, "r", encoding="utf-8") as f:
            existing = f.read()

        fm = {}
        # 查找 frontmatter 区间
        if existing.startswith("---"):
            end = existing.find("---", 3)
            if end != -1:
                fm_text = existing[3:end]
                try:
                    fm = yaml.safe_load(fm_text) or {}
                except Exception:
                    fm = {}
                body_after = existing[end + 3:]
            else:
                body_after = existing
        else:
            body_after = existing

        # 应用 updates
        fm.update(updates)

        # 可选追加 revision_history
        if revision_note:
            history = fm.get("revision_history", [])
            history.append({
                "timestamp": datetime.now().isoformat(),
                "action": revision_note,
            })
            fm["revision_history"] = history[-10:]

        # 序列化并写回
        new_fm = yaml.dump(fm, allow_unicode=True, default_flow_style=False)
        new_content = f"---\n{new_fm}---{body_after}"

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        # 刷新内存索引
        self._fm_cache[md_path] = fm
        for entry in self._all:
            if entry["filepath"] == md_path:
                entry["status"] = fm.get("status", entry.get("status", ""))
                break

        return fm
