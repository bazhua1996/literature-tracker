# 03a — PDF 文本提取集成

**What to build:** 点击 📝 生成编译草稿时，追踪器自动读取 PDF 原文并预填"摘要"和"引言"两节的基本信息（报告标题、发布机构、日期、核心数据摘要），替代当前的全空模板。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] `sources.py` 中新增 `extract_pdf_text(pdf_path) -> str` 函数，用 PyPDF2 提取 PDF 文本
- [ ] `generate_draft` 新增可选参数 `pdf_text: str = ""`
- [ ] 从 PDF text 前 2000 字符中提取：报告标题（匹配全大写/NUMBER 行）、发布机构、发布日期
- [ ] 预填草稿模板的 citation 行（`> 原文标题 | 机构 | 日期`）
- [ ] 预填摘要占位：列出 PDF 中检测到的关键数字（如 "EUR 4.2 billion"、"fraud rate 0.002%"）
- [ ] 不可自动推断的内容保持章节标题空模板
- [ ] 验证：用 ECB 报告 PDF 测试，生成的草稿 `.md` citation 行和摘要区域有预填内容
