# SPEC: 外文文献追踪与编译工作流

> 综合自 `/grill-with-docs` 领域建模 + `/implement` 多轮迭代 + `/code-review` 修复

## Problem Statement

国际金融与货币政策研究者需要持续追踪 IMF、BOJ、ECB、BIS、Fed、BOE 等机构发布的外文报告，将原文编译为 2000-5000 字中文分析报告，并按公文格式输出 Word 文档。当前流程完全依赖手动：逐个网站浏览 → 下载 PDF → AI 辅助编译 → 手动排版 Word。每个环节独立运行，缺乏统一入口，元数据散落各处，格式一致性难以保证。

## Solution

一个集**文献发现、PDF 下载、编译管理、公文格式输出**于一体的本地 Web 工作台（Streamlit 应用）。用户打开浏览器即可看到各来源最新文献列表，一键下载 PDF 或跳转源网页。对已下载的文献，通过结构化编译模板生成 `.md` 分析报告（YAML frontmatter 承载状态和元数据），审校后一键导出为遵循公文格式规范的 `.docx` 文件。所有编译稿存档于 Obsidian Vault，支持双向状态同步。

## User Stories

1. As a 研究者, I want to open a single web page and see recent publications from all configured sources (IMF, BOJ, ECB, BIS, Fed, BOE), so that I don't need to visit each website individually.

2. As a 研究者, I want to filter the publication list by source and date range, so that I can focus on the most relevant items.

3. As a 研究者, I want to click a button to download a PDF to my local Obsidian vault's Attachments folder, so that all source materials are centralized in one place.

4. As a 研究者, I want manually downloaded PDFs (from un-scrapable sources like IMF) to be automatically detected and matched to the correct source via filename keywords, so that they appear in the tracker alongside auto-scraped items.

5. As a 研究者, I want to click "Start Compilation" on any paper to generate a structured draft `.md` file in my Obsidian vault with YAML frontmatter (status, paper metadata, tags), so that I have a consistent starting point for AI-assisted compilation.

6. As a 研究者, I want papers without a source URL to prompt an inline metadata form (URL + corrected title) before draft generation, so that all compilations have complete citation information.

7. As a 研究者, I want compilation status (Discovered → In Progress → Finalized) to be tracked in the YAML frontmatter and reflected in the tracker UI as status emoji indicators (⚪🟡🟢), so that I know at a glance which papers have been compiled.

8. As a 研究者, I want finalized compilations to show an "Export" button that generates a single `.docx` file following Chinese government document formatting standards, so that the output is production-ready.

9. As a 研究者, I want to batch-export all finalized compilations from the sidebar with multiselect, so that I can update all outputs at once after making changes.

10. As a 研究者, I want exported `.docx` files to never overwrite existing ones — instead appending a version number `（1）`, `（2）` — so that no work is accidentally lost.

11. As a 研究者, I want the entire output format (fonts, margins, indentation, line spacing) governed by a standalone `FORMAT_SPEC.md` file, so that format adjustments require zero code changes.

12. As a 研究者, I want the compilation content structure (sections, style, data citation principles) governed by a standalone `COMPILATION_SPEC.md` file, so that quality standards are documented and portable.

13. As a 研究者, I want to add, enable/disable, and delete sources directly from the tracker sidebar without editing `config.json` manually, so that source management is self-service.

14. As a 研究者, I want to click a refresh button that clears all caches (in-memory and disk) and re-fetches all sources, so that I always see the latest data.

15. As a 研究者, I want the entire project to be self-contained in one folder with a minimal virtual environment and `requirements.txt`, so that it can be deployed on any Windows machine with Python installed.

## Implementation Decisions

### Domain Model

- **Core aggregate root**: `Compilation` (编译稿). A single `.md` file in the Obsidian vault.
- **Lifecycle**: `已发现` → `编译中` → `已定稿`. Rework: `已定稿` → `编译中` (simple rollback, no versioning needed for personal use).
- **Entities**: `Source` (independent, with key/name/url/scrape-type/filename-hints). `Compilation` (aggregate root).
- **Value Objects**: `Paper` (title, date, source, authors, paper_type, detail_url, pdf_url, report_number). `Tag` (flat string). `BilingualQuote` (not independently managed — data integrated into narrative).

### Architecture

- **Subsystem 1 — Tracker (Streamlit)**: Discovers papers, downloads PDFs, monitors vault status, triggers compilation drafts. Aggregate root: Paper (read-only display).
- **Subsystem 2 — Compilation (AI + Obsidian)**: Transforms Paper → Compilation. Aggregate root: Compilation.
- **Decoupling point**: "Start Compilation" button generates draft `.md` with YAML frontmatter. Status read-back via vault scanning.
- **Matching key**: `detail_url` (primary), `title` (fallback for backward compatibility).

### Source Registry

- `SOURCE_FETCHERS` dict in `sources.py`: maps source key → fetch function. New sources added by writing a `fetch_xxx()` function and calling `register_fetcher("key", fetch_xxx)`.
- `config.json` `sources` array: each entry has `key`, `name`, `url`, `enabled`, `scrape` (auto/manual), `filename_hints` (list of lowercase keywords for local PDF matching).
- `app.py` uses `get_fetcher(key)` to dispatch — no if/elif chain.

### Output Pipeline

- Compilation template (in `generate_draft`): 8-chapter structure with abstract, keywords, and Chinese-numeral headings.
- `.md → .docx` conversion: `md_to_docx.py` → `parse_md()` extracts structured data → `generate_report()` produces single `.docx` following `FORMAT_SPEC.md` constants.
- Format spec requirements: A4 page, 方正小标宋简体 title (22pt), 黑体 H1 (16pt), 楷体_GB2312 H2 (16pt), 仿宋_GB2312 body (16pt), 28pt fixed line spacing, first-line indent ~1.13cm (2 chars at 三号), title centered with blank lines above and below.

### Caching Strategy

- Two-layer: Streamlit `@st.cache_data` (in-memory, 60-min TTL) + disk JSON cache for cross-restart persistence.
- Refresh button: clears both `st.cache_data` and disk cache files.
- Draft generation: uses `fetch_vault_status.clear()` (targeted) instead of `st.cache_data.clear()` (sledgehammer).
- `imf_metadata.json`: atomic write (`.tmp` → `os.replace`) with `.bak` backup, JSON corruption auto-detected and logged.

### Data Safety

- Atomic file writes for caches and metadata (temp file + rename).
- `.docx` export: never overwrites — auto-increments version number.
- Corrupted cache files: auto-detected (JSONDecodeError) and removed.
- IMF metadata: `.bak` backup file created before each write.

## Testing Decisions

- **What is a good test**: Test external behavior (given input .md, output .docx has correct structure; given URL, fetch returns expected paper list shape). Do not test implementation details (internal helper functions, Streamlit widget rendering).
- **Seams to test at**:
  - `sources.py` fetch functions: given live URL → returns list of dicts with expected keys. Mock network for deterministic tests.
  - `md_to_docx.py` `convert()`: given known .md fixture → produces .docx with correct paragraph count, fonts, and structure.
  - `sources.py` `scan_vault_status()`: given a test vault directory → returns correct `{detail_url: status}` mapping.
  - `sources.py` `generate_draft()`: given paper dict → creates .md with correct YAML frontmatter and template structure.
- **No Streamlit UI tests**: Streamlit's rendering model makes end-to-end UI tests fragile. Rely on function-level tests for business logic.

## Out of Scope

- Automated scraping for IMF, ECB, BIS, Fed, BOE (currently manual with guide links due to Akamai/JS-rendering protection). Future: Playwright/Selenium-based browser automation.
- Multi-user support (single-user local workstation by design).
- DeepL/Google Translate API integration for machine-assisted translation.
- Automatic GB/T 7714 reference citation generation.
- Scheduled/cron-based automatic refresh (currently manual refresh button only).
- Mobile access (currently `localhost:8501` only; future: `server.address 0.0.0.0`).
- Rework history/versioning (simple status rollback is sufficient for personal use).
- BOJ year parameterization (currently hardcoded to `state_2026`; future: `state_{year}` template).

## Further Notes

- The project is self-contained in `d:\chord\literature-tracker\` with its own `.venv` and `requirements.txt` (8 direct dependencies).
- Obsidian vault path and PDF download path are configured in `config.json` and can be changed without code modification.
- The `文献追踪与编译工作流` was domain-modeled via `/grill-with-docs`; the resulting model is documented in the Obsidian vault at `领域模型-外文文献编译工作流.md`.
- Code review (`/code-review` at max effort) identified and fixed 11 bugs across correctness, efficiency, and Streamlit-specific categories.
