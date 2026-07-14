# SPEC: 文献卡片式界面

> 2026-07-14 | 来自 `/grill-with-docs` 界面改版 grilling session

## Problem Statement

当前文献列表使用 7 列水平布局渲染每篇文献的信息和操作按钮，在狭窄的 Streamlit 默认列宽中信息拥挤、视觉层级模糊。用户扫一眼列表时，标题、日期、状态、操作按钮混杂在一条密集水平带中，难以快速定位目标文献或判断处理状态。

## Solution

将每篇文献从水平行布局改为**卡片式布局**。每张卡片是一个 `st.container(border=True)`，内部信息按垂直层级排列：状态角标 → 中文标题 → 元数据条 → 操作按钮。保持来源分组折叠结构不变，仅在 expander 内部替换渲染方式。

## User Stories

1. As a 研究者, I want each paper rendered as a distinct visual card with clear vertical hierarchy, so that I can scan the list faster and identify papers by title rather than squinting at a dense horizontal row.

2. As a 研究者, I want the card to display the Chinese compilation title (from the compilation draft's frontmatter) as the primary title, so that I read Chinese titles without mental translation overhead.

3. As a 研究者, I want to hover over the Chinese title to see the original foreign-language title as a tooltip, so that I can verify the paper identity when needed.

4. As a 研究者, I want the card's metadata bar to show only date and source (not paper type), so that the card stays clean and the most relevant context — when and who published it — is immediately visible.

5. As a 研究者, I want action buttons to appear only when they are relevant to the paper's current state (e.g., show 📥 when no local PDF exists, show 🤖 when PDF is downloaded, show 📄 when status is 已定稿), so that the card surface is not cluttered with disabled or irrelevant buttons.

6. As a 研究者, I want the visual style to stay minimal and neutral — relying on card spacing, border-radius, and subtle shadows rather than custom color schemes — so that the interface feels polished without deviating from Streamlit's native theme.

7. As a 研究者, I want the source-grouped expander structure to remain unchanged, so that I can still collapse/focus on specific institutions as before.

## Implementation Decisions

### 卡片结构

每张卡片使用 `st.container(border=True)` 包裹，内部垂直排列四个区域：

1. **状态角标区** — 卡片右上角（或左上角）显示编译状态图标（🟢🟡⚪）。非编译状态文献不显示状态图标。
2. **标题区** — 中文显示标题，字号通过 `st.markdown` 加大（`###` 级别）。hover 时用 HTML `title` 属性显示原文标题。
3. **元数据条** — `{日期} · {来源}`。灰色小字，用 `st.caption` 渲染。
4. **操作按钮区** — 按状态分组显隐的图标按钮，用 `st.columns` 小宽度平分。

### 中文标题来源

- 若文献已有编译稿（`detail_url` 在 vault 的 `status_map` 中存在且对应 `.md` 文件存在 frontmatter），取 `frontmatter.paper.title` 作为中文展示标题。
- 若未编译，显示原文标题，不显示 hover tooltip。
- 中文标题截断至 80 字符，超出部分用 `…`。

### 按钮状态分组

| 状态 | 显示按钮 |
|------|---------|
| 无本地 PDF（`pdf_url` 为 HTTP） | 📥 下载 PDF |
| 有本地 PDF + 未编译 | 📝 生成草稿 · 🤖 AI 一键编译 · 🔮 生成提示词 |
| 状态 = 编译中 | 🔄 返工（popover） |
| 状态 = 已定稿 | 📄 导出 Word |
| detail_url 缺失 | 📝 补录元数据（弹出表单） |

🔗 源网页链接始终显示，作为卡片底部的文字链接而非按钮。

### 交互行为

- 📝 生成草稿、🤖 AI 编译、🔮 提示词、📄 导出、🔄 返工的逻辑与现有实现完全一致（委托给 `CompilationWorkflow` 和 `Vault` 的已有方法）。
- 📥 下载 PDF 逻辑不变（调用 `sources.download_pdf`）。
- 补录表单、AI 编译执行区、返工执行区、提示词展示区的位置和渲染逻辑不变，仅其触发按钮从行内移至卡片中。

### 不修改的模块

- `vault.py`、`compilation.py`、`source.py`、`ai_compile.py`、`prompt_builder.py`、`md_to_docx.py` — 全部不变。
- 仅 `app.py` 中文献列表渲染部分（约第 229-382 行）被替换。

### 向后兼容

- 所有 `st.session_state` 键名不变。
- 所有 Streamlit 缓存逻辑不变。
- 所有执行块（AI 编译、返工、提示词展示、补录表单）的渲染代码位置和逻辑不变。

## Testing Decisions

- **什么是好测试**：验证卡片渲染不崩溃（`streamlit run app.py` 后 UI 正常加载），验证按钮逻辑不变（点击 📝 生成草稿、点击 🤖 触发 AI 编译、点击 📄 导出 Word）。
- **Seam**：在 `app.py` 的 UI 层测试，通过浏览器手动验证卡片视觉和交互。
- **不测试**：Streamlit 内部渲染细节、CSS 像素级精度。

## Out of Scope

- 自定义 CSS 主题或色彩方案
- 响应式移动端适配
- 卡片动画/过渡效果
- 列表布局以外的改动（sidebar、标题栏、图例栏不变）
- 新增编译/导出功能

## Further Notes

- 卡片圆角和间距由 Streamlit 的 `st.container(border=True)` 原生提供，无需额外 CSS。
- 中文标题的 hover tooltip 通过 `<span title="原标题">中文标题</span>` 实现，需要 `unsafe_allow_html=True`。
- 按钮分组显隐逻辑需新增一个 `_card_buttons(paper, status, pdf_url)` 辅助函数来集中管理。
