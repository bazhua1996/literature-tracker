"""
Compilation workflow module.
Encapsulates AI compilation, rework, and prompt-building business logic.
"""

import os
from dataclasses import dataclass
from datetime import datetime

import yaml

from vault import Vault, extract_pdf_text
from ai_compile import compile_with_ai
from prompt_builder import build_compilation_prompt


@dataclass
class CompileResult:
    """AI 全量编译的结果。"""
    success: bool
    content: str = ""          # markdown 输出或错误信息
    filepath: str = ""         # 保存的 .md 文件路径
    pdf_char_count: int = 0    # 提取的 PDF 文本字符数


@dataclass
class ReworkResult:
    """返工操作的结果。"""
    success: bool
    content: str = ""          # AI 生成内容或错误信息
    filepath: str = ""         # 修改的 .md 文件路径（全量返工）
    prompt_text: str = ""      # 生成的提示词（章节/修订模式）


class CompilationWorkflow:
    """编排单篇文献的 AI 编译流水线。"""

    def __init__(self, vault: Vault, config: dict):
        """
        vault: Vault 实例（用于草稿创建和 frontmatter 更新）。
        config: 完整应用配置字典（需要 'ai' 部分用于 API 调用）。
        """
        self.vault = vault
        self.config = config

    # ── 公开接口 ──────────────────────────────────────

    def compile(self, paper: dict, pdf_path: str,
                on_chunk=None) -> CompileResult:
        """
        执行完整 AI 编译流水线：
        1. 提取 PDF 文本
        2. 调用 AI API（支持流式回调）
        3. 在 vault 中创建草稿 .md（一次写入，含 AI 内容）
        4. 更新内存索引

        paper 字典需要的键（中英文均可）:
          title/标题, date/日期, source/来源, authors/作者,
          paper_type/类型, detail_url, pdf_url, report_number

        on_chunk: 可选回调，接收每个增量文本片段用于流式展示
        """
        pdf_text, success, content = self._call_ai(pdf_path, paper, on_chunk=on_chunk)
        if not pdf_text:
            return CompileResult(success=False, content="PDF 文本提取失败或为空")
        if not success:
            return CompileResult(success=False, content=content)

        paper_normalized = self._normalize_paper(paper)

        # 一次写入：frontmatter + AI 内容，status 自动设为 "编译中"
        try:
            filepath = self.vault.create_draft(
                paper_normalized, pdf_text, content=content
            )
        except Exception as e:
            return CompileResult(success=False, content=str(e))

        return CompileResult(
            success=True,
            content=content,
            filepath=filepath,
            pdf_char_count=len(pdf_text),
        )

    def rework(self, md_path: str, mode: str, chapters: list[str],
               note: str, pdf_path: str, paper: dict) -> ReworkResult:
        """
        执行返工操作：
        - mode 含 "全量": 全量 AI 重译 → 覆写 .md（记录 revision_history）
        - mode 含 "章节" 或 "修订": 生成定向提示词（不调用 API）

        paper 字典需要的键（中英文均可）:
          source/来源, title/标题, date/日期, paper_type/类型
        """
        paper_normalized = self._normalize_paper(paper)

        if "全量" in mode:
            return self._rework_full(md_path, pdf_path, paper_normalized)
        else:
            return self._rework_prompt(md_path, mode, chapters, note,
                                       pdf_path, paper_normalized)

    def build_prompt(self, pdf_path: str, paper: dict) -> str:
        """
        生成 AI 编译提示词供手动复制粘贴。
        不调用 API，不写文件。
        """
        paper_normalized = self._normalize_paper(paper)
        pdf_text = extract_pdf_text(pdf_path)
        if not pdf_text:
            return ""

        return build_compilation_prompt(
            pdf_text,
            source_key=paper_normalized.get("source", "").lower(),
            paper_title=paper_normalized.get("title", ""),
            paper_date=paper_normalized.get("date", ""),
            paper_type=paper_normalized.get("paper_type", ""),
        )

    # ── 内部方法 ──────────────────────────────────────

    def _call_ai(self, pdf_path: str, paper: dict, on_chunk=None) -> tuple:
        """提取 PDF 文本并调用 AI 编译。返回 (pdf_text, success, content)。"""
        pdf_text = extract_pdf_text(pdf_path)
        if not pdf_text:
            return "", False, "PDF 文本提取失败或为空"
        paper_norm = self._normalize_paper(paper)
        success, content = compile_with_ai(
            pdf_text,
            source_key=paper_norm.get("source", "").lower(),
            paper_title=paper_norm.get("title", ""),
            paper_date=paper_norm.get("date", ""),
            paper_type=paper_norm.get("paper_type", ""),
            config=self.config,
            on_chunk=on_chunk,
        )
        return pdf_text, success, content

    def _apply_ai_result(self, filepath: str, content: str,
                         revision_note: str = "") -> None:
        """更新 frontmatter（可选追加 revision_history）并替换正文。"""
        try:
            self.vault.update_frontmatter(
                filepath, {"status": "编译中"}, revision_note=revision_note
            )
        except Exception:
            pass
        self._replace_body(filepath, content)

    def _rework_full(self, md_path: str, pdf_path: str,
                     paper: dict) -> ReworkResult:
        """全量 AI 重译模式。"""
        pdf_text, success, content = self._call_ai(pdf_path, paper)
        if not pdf_text:
            return ReworkResult(success=False, content="PDF 文本提取失败或为空")
        if not success:
            return ReworkResult(success=False, content=content)

        self._apply_ai_result(md_path, content, revision_note="全量 AI 重译")
        return ReworkResult(success=True, content=content, filepath=md_path)

    def _rework_prompt(self, md_path: str, mode: str,
                       chapters: list[str], note: str,
                       pdf_path: str, paper: dict) -> ReworkResult:
        """章节重译 / 智能修订模式 — 生成提示词但不调用 API。"""
        pdf_text = extract_pdf_text(pdf_path)
        if not pdf_text:
            return ReworkResult(success=False, content="PDF 文本提取失败或为空")

        prompt = build_compilation_prompt(
            pdf_text,
            source_key=paper.get("source", "").lower(),
            paper_title=paper.get("title", ""),
            paper_date=paper.get("date", ""),
            paper_type=paper.get("paper_type", ""),
        )

        # 追加特殊要求
        extra_parts = []
        if chapters:
            extra_parts.append(
                f"请仅重写以下章节，保持其他章节不变：{', '.join(chapters)}"
            )
        if note:
            extra_parts.append(f"修改要求：{note}")
        if extra_parts:
            prompt += "\n\n## 特殊要求\n" + "\n".join(extra_parts)

        return ReworkResult(
            success=True, content="提示词已生成",
            filepath=md_path, prompt_text=prompt,
        )

    @staticmethod
    def _normalize_paper(paper: dict) -> dict:
        """接受中英文键名的 paper 字典，返回全英文键名的副本。"""
        key_map = {
            "标题": "title", "日期": "date", "来源": "source",
            "作者": "authors", "类型": "paper_type",
        }
        result = {}
        for field in ("title", "date", "source", "authors", "paper_type",
                       "detail_url", "pdf_url", "report_number"):
            # 优先英文键，fallback 中文键
            result[field] = paper.get(field, paper.get(
                {v: k for k, v in key_map.items()}.get(field, ""), ""
            ))
        return result

    @staticmethod
    def _replace_body(md_path: str, new_content: str) -> None:
        """保留 frontmatter，替换正文为 new_content。"""
        with open(md_path, "r", encoding="utf-8") as f:
            existing = f.read()
        if existing.startswith("---"):
            end = existing.find("---", 3)
            if end != -1:
                new_body = existing[:end + 3] + "\n\n" + new_content
            else:
                new_body = f"---\nstatus: 编译中\n---\n\n{new_content}"
        else:
            new_body = f"---\nstatus: 编译中\n---\n\n{new_content}"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(new_body)
