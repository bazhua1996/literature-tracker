# CONTEXT — 外文文献追踪与编译工作台

## 领域词汇

- **文献 (Paper)** — 一篇来自国际金融机构的外文报告。数据载体，不是编译产物。
- **编译稿 (Compilation)** — 对一篇文献进行 AI 辅助中文分析后生成的 `.md` 文件，是系统的 aggregate root。存储在 Obsidian Vault 中。
- **来源 (Source)** — 文献的发布机构：IMF、BOJ、ECB、BIS、Fed、BOE。每个 Source 是一个 entity，拥有独立的抓取策略、风格指南和文件命名规则。
- **Vault** — Obsidian 知识库的 Notes 目录。编译稿的持久化存储，与追踪器通过 YAML frontmatter 双向同步。
- **编译状态** — `已发现`（⚪）→ `编译中`（🟡）→ `已定稿`（🟢）。生命周期由 frontmatter 的 `status` 字段管理。
- **返工 (Rework)** — 将已编译稿回退到 `编译中` 状态并重新生成内容。三种模式：全量 AI 重译、指定章节重译、智能修订（给意见后手动操作）。
- **抓取策略** — `auto`（BOJ 网页爬虫）或 `manual`（提供引导链接，用户手动下载后追踪器识别本地 PDF）。
- **公文格式** — 遵循 FORMAT_SPEC.md 的 Word 输出标准：方正小标宋简体标题、黑体一级标题、楷体二级标题、仿宋正文、28 磅固定行距。

## 架构决策

- **Deep modules**：`vault.py`（Vault 类）、`compilation.py`（CompilationWorkflow）、`source.py`（Source dataclass）
- **Streamlit 是 UI adapter**，不包含业务逻辑
- **向后兼容 shim** 在 `sources.py` 中，委托给 `vault.py`
- **无循环依赖**：app → vault/compilation/source → sources

## 用户偏好

- 标题优先的信息层级
- 极简中性视觉风格（不自定义配色，靠间距/圆角/阴影）
- 操作按钮按状态分组显隐
- 中文标题展示（hover 显示原文），优先使用编译稿中的中文标题
