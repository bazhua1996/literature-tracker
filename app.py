"""
外文文献追踪 — Streamlit 应用
"""

import json
import os
from datetime import datetime

import streamlit as st
import pandas as pd

from sources import (
    fetch_local_pdfs, download_pdf,
    update_imf_metadata, clear_disk_cache,
    get_fetcher,
)
from vault import Vault, extract_pdf_text
from md_to_docx import convert as convert_to_docx
from compilation import CompilationWorkflow
from source import load_sources, get_source, get_icon


def _has_local_pdf(pdf_url: str) -> bool:
    """检查 pdf_url 对应文件是否存在于本地。支持直接路径和 HTTP URL。"""
    if not pdf_url:
        return False
    if pdf_url.startswith("http"):
        # HTTP URL: 检查下载目录中是否有匹配文件
        fname = pdf_url.rstrip("/").split("/")[-1]
        if not fname.endswith(".pdf"):
            fname += ".pdf"
        return os.path.exists(os.path.join(DOWNLOAD_DIR, fname))
    return os.path.exists(pdf_url)


def _resolve_pdf_path(pdf_url: str) -> str:
    """将 pdf_url 解析为本地路径。非本地或不存在返回空字符串。"""
    if not pdf_url:
        return ""
    if pdf_url.startswith("http"):
        fname = pdf_url.rstrip("/").split("/")[-1]
        if not fname.endswith(".pdf"):
            fname += ".pdf"
        local = os.path.join(DOWNLOAD_DIR, fname)
        return local if os.path.exists(local) else ""
    return pdf_url if os.path.exists(pdf_url) else ""


# ── 页面配置 ──────────────────────────────────────────
st.set_page_config(
    page_title="外文文献追踪",
    page_icon="📊",
    layout="wide",
)

# ── 加载配置 ──────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


config = load_config()
load_sources(config.get("sources", []))
DOWNLOAD_DIR = config.get("download_dir", os.path.join(os.path.dirname(__file__), "downloads"))
EXPORT_DIR = config.get("export_dir", DOWNLOAD_DIR)
VAULT_NOTES_DIR = config.get("vault_notes_dir", "")
CACHE_TTL = config.get("cache_ttl_minutes", 60)
DEFAULT_FROM_DATE = config.get("filter_from_date", "2026-05-01")

# ── Session State ─────────────────────────────────────
if "download_log" not in st.session_state:
    st.session_state.download_log = []

STATUS_EMOJI = {
    "已发现": "⚪",
    "编译中": "🟡",
    "已定稿": "🟢",
}


def _invalidate_caches(scope: str = "all") -> None:
    """统一缓存刷新。scope: 'all' | 'papers' | 'vault'"""
    if scope == "all":
        st.cache_data.clear()
    elif scope == "papers":
        fetch_all.clear()
    elif scope == "vault":
        fetch_vault.clear()


# ── 标题栏 ──────────────────────────────────────────
st.title("📊 外文文献追踪")

with st.expander("🚀 操作指引（点击展开/收起）", expanded=False):
    st.markdown("""
    ### 四步工作流

    | 步骤 | 操作 | 按钮 | 产出 |
    |------|------|------|------|
    | **1. 获取原文** | 找到文献 → 下载 PDF | 📥 | `Attachments/PDFs/*.pdf` |
    | **2. AI 编译** | 有本地 PDF 后 → 一键编译 | 🤖 | `Notes/*.md`（AI 写完整报告） |
    | **3. 审校定稿** | Obsidian 中修改 → 改 status | — | 追踪器显示 🟢 |
    | **4. 导出 Word** | 回到追踪器 → 导出 | 📄 | `Attachments/*.docx`（公文格式） |

    ### 按钮说明

    📥下载PDF　📝空模板草稿　🔮生成提示词　**🤖AI一键编译**　📄导出Word　🔄返工
    """)

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    source_filter = st.selectbox(
        "来源筛选",
        ["全部"] + [s["name"] for s in config["sources"] if s.get("enabled", True)],
    )
with col2:
    from_date = st.date_input(
        "发布日起始",
        value=datetime.strptime(DEFAULT_FROM_DATE, "%Y-%m-%d"),
    )
with col3:
    st.caption("")
    refresh_clicked = st.button("🔄 刷新数据", use_container_width=True)

st.caption(f"📂 PDF 下载: `{DOWNLOAD_DIR}`")
if VAULT_NOTES_DIR:
    st.caption(f"📝 编译草稿输出: `{VAULT_NOTES_DIR}`")


# ── 数据抓取 ──────────────────────────────────────────

@st.cache_data(ttl=CACHE_TTL * 60, show_spinner="正在抓取文献数据...")
def fetch_all(_cache_ttl: int) -> list[dict]:
    """抓取所有来源 + 本地文件"""
    all_papers = []
    for source in config["sources"]:
        if not source.get("enabled", True):
            continue
        key = source["key"]
        fetcher = get_fetcher(key)
        if fetcher:
            try:
                papers = fetcher(_cache_ttl, source_config=source)
            except TypeError:
                papers = fetcher(_cache_ttl)  # 兼容不接受 source_config 的旧 fetcher
        else:
            continue
        all_papers.extend(papers)

    # 追加本地 PDF（传入 sources 配置以按 filename_hints 归类）
    # 去重：同源按标题+日期去重，跨来源按 detail_url + 标题+日期 hash 兜底
    seen_titles = set()
    deduped = []
    for p in all_papers:
        key = (p["title"][:80].lower().strip(), p.get("date", ""))
        if key not in seen_titles:
            seen_titles.add(key)
            deduped.append(p)
    all_papers = deduped

    seen_urls = {p["detail_url"] for p in all_papers if p.get("detail_url")}
    seen_keys = {(p["title"].lower(), p["date"]) for p in all_papers}
    local_pdfs = fetch_local_pdfs(DOWNLOAD_DIR, config.get("sources", []))
    for lp in local_pdfs:
        lp_url = lp.get("detail_url", "")
        lp_key = (lp["title"].lower(), lp["date"])
        if lp_url and lp_url in seen_urls:
            continue
        if not lp_url and lp_key in seen_keys:
            continue
        all_papers.append(lp)
        if lp_url:
            seen_urls.add(lp_url)
        seen_keys.add(lp_key)

    return all_papers


@st.cache_data(ttl=CACHE_TTL * 60, show_spinner="正在扫描编译状态...")
def fetch_vault(_notes_dir: str) -> "Vault":
    """扫描 Obsidian vault 获取编译状态。返回 Vault 索引实例。"""
    return Vault(_notes_dir) if _notes_dir else Vault("")


if refresh_clicked:
    _invalidate_caches("all")
    clear_disk_cache()
    st.rerun()

all_raw = fetch_all(CACHE_TTL)
vault = fetch_vault(VAULT_NOTES_DIR)
workflow = CompilationWorkflow(vault, config)

# ── 数据筛选 ──────────────────────────────────────────

df = pd.DataFrame(all_raw) if all_raw else pd.DataFrame()

if not df.empty:
    rename_map = {
        "paper_type": "类型", "title": "标题", "date": "日期",
        "source": "来源", "authors": "作者",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    if "日期" in df.columns:
        # 空日期不丢弃，赋予一个可筛选的默认值
        unknown_dates = df["日期"] == ""
        unknown_count = unknown_dates.sum()
        df_filtered = df[df["日期"] >= from_date.strftime("%Y-%m-%d")]
        # 把空日期也保留（它们无法比较，在前面已被排除）
        df = pd.concat([df_filtered, df[unknown_dates]]) if unknown_count > 0 else df_filtered
        if unknown_count > 0:
            st.warning(f"⚠️ {unknown_count} 篇论文日期缺失，显示在列表末尾。请点击 🔄 刷新数据重试。")

    if source_filter != "全部" and "来源" in df.columns:
        src_key = source_filter.split(" ")[0].upper()
        df = df[df["来源"].str.upper() == src_key]

    if "日期" in df.columns:
        df = df.sort_values("日期", ascending=False)

    # 匹配编译状态 — 优先 detail_url，fallback pdf_url
    _status_map = vault.status_map() if vault.is_ready else {}
    def _get_status(row) -> str:
        url = row.get("detail_url", "")
        status = _status_map.get(url, "")
        if not status:
            pdf = row.get("pdf_url", "")
            status = _status_map.get(pdf, "")
        return status

    df["状态"] = df.apply(_get_status, axis=1)

total_count = len(df)

# ── 图例 ──────────────────────────────────────────
st.divider()
legend_cols = st.columns(4)
legend_cols[0].caption("🟢 已定稿  🟡 编译中  ⚪ 未编译（草稿）")
legend_cols[1].caption("📥 下载 PDF")
legend_cols[2].caption("📝 编译 / 📄 导出报告")
legend_cols[3].caption("🔗 源网页")

st.divider()

st.subheader(f"📋 文献列表（共 {total_count} 篇）")

if df.empty:
    st.info("暂无符合条件的文献。请调整筛选条件或点击 🔄 刷新数据。")
else:
    sources_in_df = df["来源"].unique() if "来源" in df.columns else []

    for src in sources_in_df:
        src_df = df[df["来源"] == src]
        src_count = len(src_df)

        if src == "本地":
            src_icon = "📁"
            src_full_name = "本地"
            is_manual_source = True
        else:
            source_obj = get_source(src)
            src_icon = source_obj.icon if source_obj else "📄"
            src_full_name = source_obj.name if source_obj else src
            is_manual_source = (source_obj.scrape == "manual") if source_obj else True

        with st.expander(f"{src_icon} {src_full_name}（{src_count} 篇）", expanded=True):
            for idx, (orig_idx, paper) in enumerate(src_df.iterrows()):
                title = paper.get("标题", "Unknown")
                date = paper.get("日期", "")
                ptype = paper.get("类型", "")
                pdf_url = paper.get("pdf_url", "")
                detail_url = paper.get("detail_url", "")
                status = paper.get("状态", "")
                status_icon = STATUS_EMOJI.get(status, "")

                # 查找编译稿中的中文标题
                cn_title = ""
                if detail_url and vault.is_ready:
                    cn_title = vault.paper_title(detail_url)

                has_local_pdf = _has_local_pdf(pdf_url)
                is_manual = is_manual_source or "🌐" in str(ptype) or VAULT_NOTES_DIR == ""

                with st.container(border=True):
                    # ── 状态角标 ──
                    if status_icon:
                        st.markdown(f"<span style='font-size:1.2em'>{status_icon}</span>", unsafe_allow_html=True)

                    # ── 标题 ──
                    if is_manual_source or "🌐" in str(ptype):
                        st.markdown(f"🌐 **{title}**")
                    elif cn_title:
                        # 中文标题 + hover 显示原文
                        safe_cn = cn_title.replace('"', '&quot;')[:120]
                        safe_en = str(title).replace('"', '&quot;')[:200]
                        st.markdown(
                            f'<p style="font-weight:bold;font-size:1.05em;margin:0.3em 0" '
                            f'title="{safe_en}">{safe_cn}</p>',
                            unsafe_allow_html=True,
                        )
                    else:
                        title_display = str(title)[:120] + ('…' if len(str(title)) > 120 else '')
                        st.markdown(f"**{title_display}**")

                    # ── 元数据条 ──
                    meta_parts = []
                    # 只展示真实日期（排除占位符 2099-12-31 和空值）
                    if date and date != "2099-12-31":
                        # 美化日期格式: 2026-06-16 → 2026年6月16日
                        try:
                            dt = datetime.strptime(date, "%Y-%m-%d")
                            meta_parts.append(f"{dt.year}年{dt.month}月{dt.day}日")
                        except ValueError:
                            meta_parts.append(date)
                    if cn_title:
                        meta_parts.append(ptype) if ptype else None
                    st.caption(" · ".join(meta_parts) if meta_parts else "")

                    # ── 操作按钮（状态驱动显隐）──
                    # 优先级: 编译状态 > 手动来源 > 缺元数据 > 无PDF > 可编译
                    if status == "已定稿":
                        btn_cols = st.columns([1, 1, 4])
                        with btn_cols[0]:
                            if st.button("📄 导出", key=f"export_{src}_{orig_idx}",
                                         help=f"导出 Word", use_container_width=True):
                                with st.spinner("导出 Word..."):
                                    md_path = vault.find(detail_url)
                                    if md_path:
                                        try:
                                            docx_path = convert_to_docx(md_path, EXPORT_DIR)
                                            docx_name = os.path.basename(docx_path)
                                            st.session_state.download_log.append(f"📄 {docx_name}")
                                            st.toast(f"📄 已导出: {docx_name}")
                                        except Exception as e:
                                            st.toast(f"❌ 导出失败: {e}")
                                    else:
                                        st.toast("❌ 未找到对应编译稿 .md 文件")
                                st.rerun()
                        with btn_cols[1]:
                            if detail_url:
                                st.link_button("🔗 原文", detail_url, help=f"打开源网页")

                    elif status == "编译中":
                        btn_cols = st.columns([1, 1, 4])
                        with btn_cols[0]:
                            with st.popover("🔄 返工", use_container_width=True):
                                md_path = vault.find(detail_url)
                                if md_path and os.path.exists(md_path):
                                    st.caption(f"当前: {os.path.basename(md_path)}")
                                    rew_mode = st.radio("返工模式",
                                        ["🤖 全量 AI 重译", "✂️ 指定章节重译", "💬 智能修订（给意见）"],
                                        key=f"r_mode_{src}_{orig_idx}")
                                    rew_chapters = []
                                    rew_note = ""
                                    if "章节" in rew_mode:
                                        rew_chapters = st.multiselect("选择章节",
                                            ["一、引言与背景","二、","三、","四、","五、","六、","七、","八、结论与政策启示"],
                                            key=f"r_ch_{src}_{orig_idx}")
                                    if "修订" in rew_mode:
                                        rew_note = st.text_area("修改意见",
                                            placeholder="例如：数据太干，增加解释；第二部分需要加日本央行对比...",
                                            key=f"r_note_{src}_{orig_idx}")
                                    if st.button("🚀 执行", key=f"r_go_{src}_{orig_idx}"):
                                        st.session_state[f"rewrite_{src}_{orig_idx}"] = {
                                            "md_path": md_path, "mode": rew_mode,
                                            "chapters": rew_chapters, "note": rew_note,
                                            "pdf_url": pdf_url,
                                        }
                                        st.rerun()
                                else:
                                    st.caption("未找到对应编译稿")
                        with btn_cols[1]:
                            if detail_url:
                                st.link_button("🔗 原文", detail_url, help=f"打开源网页")

                    elif is_manual_source and "🌐" not in str(ptype) and not detail_url:
                        # 手动来源 + 无元数据：补录
                        btn_cols = st.columns([1, 5])
                        with btn_cols[0]:
                            form_key = f"form_{src}_{orig_idx}"
                            if st.button("📝 补录", key=f"compile_{src}_{orig_idx}",
                                         help=f"补录元数据后编译", use_container_width=True):
                                st.session_state[f"edit_form_{form_key}"] = True
                                st.rerun()

                    elif not detail_url:
                        # 缺 detail_url：补录
                        btn_cols = st.columns([1, 5])
                        with btn_cols[0]:
                            form_key = f"form_{src}_{orig_idx}"
                            if st.button("📝 补录元数据", key=f"compile_{src}_{orig_idx}",
                                         help=f"补录元数据后编译", use_container_width=True):
                                st.session_state[f"edit_form_{form_key}"] = True
                                st.rerun()

                    elif not has_local_pdf:
                        # 无本地 PDF：下载按钮可用 + 编译按钮灰掉（先下载才能编译）
                        btn_cols = st.columns([1, 1, 1, 1, 3])
                        with btn_cols[0]:
                            if pdf_url and pdf_url.startswith("http"):
                                if st.button("📥 PDF", key=f"pdf_{src}_{orig_idx}",
                                             help=f"下载: {str(title)[:60]}", use_container_width=True):
                                    with st.spinner("下载中..."):
                                        success, result = download_pdf(pdf_url, DOWNLOAD_DIR)
                                        if success:
                                            fname = os.path.basename(result)
                                            st.session_state.download_log.append(f"✅ {fname}")
                                            st.toast(f"✅ 已保存: {fname}")
                                            _invalidate_caches("papers")
                                        else:
                                            st.toast(f"❌ 下载失败: {result}")
                                    st.rerun()
                            elif pdf_url and not pdf_url.startswith("http"):
                                st.button("📂 本地", key=f"pdf_{src}_{orig_idx}", disabled=True,
                                          help="本地已有 PDF", use_container_width=True)
                            else:
                                st.button("—", key=f"pdf_{src}_{orig_idx}", disabled=True,
                                          help="无下载链接", use_container_width=True)
                        with btn_cols[1]:
                            st.button("📝", key=f"compile_{src}_{orig_idx}", disabled=True,
                                      help="请先下载 PDF", use_container_width=True)
                        with btn_cols[2]:
                            st.button("🤖", key=f"ai_{src}_{orig_idx}", disabled=True,
                                      help="请先下载 PDF", use_container_width=True)
                        with btn_cols[3]:
                            if detail_url:
                                st.link_button("🔗", detail_url, help=f"打开源网页")

                    else:
                        # 有本地 PDF + 可编译：📝草稿 + 🔮提示词 + 🤖AI编译 + 🔗原文
                        btn_cols = st.columns([1, 1, 1, 1])
                        key_cpl = f"compile_{src}_{orig_idx}"
                        with btn_cols[0]:
                            if st.button("📝 草稿", key=key_cpl, help=f"生成空模板草稿", use_container_width=True):
                                paper_data = {
                                    "title": cn_title or title, "date": date, "source": src,
                                    "authors": paper.get("作者", ""),
                                    "paper_type": ptype, "detail_url": detail_url,
                                    "pdf_url": pdf_url, "report_number": paper.get("report_number", ""),
                                }
                                with st.spinner("生成编译草稿..."):
                                    pdf_path = _resolve_pdf_path(pdf_url)
                                    pdf_text = extract_pdf_text(pdf_path) if pdf_path else ""
                                    try:
                                        filepath = vault.create_draft(paper_data, pdf_text)
                                        st.session_state.download_log.append(f"📝 {os.path.basename(filepath)}")
                                        st.toast(f"📝 草稿已生成: {os.path.basename(filepath)}")
                                        _invalidate_caches("vault")
                                    except Exception as e:
                                        st.toast(f"❌ 生成失败: {e}")
                                st.rerun()
                        with btn_cols[1]:
                            prompt_key = f"prompt_{src}_{orig_idx}"
                            if st.button("🔮 提示词", key=prompt_key, help=f"生成 AI 编译提示词", use_container_width=True):
                                st.session_state[f"show_prompt_{src}_{orig_idx}"] = True
                                st.rerun()
                        with btn_cols[2]:
                            ai_key = f"ai_{src}_{orig_idx}"
                            if st.button("🤖 AI编译", key=ai_key, help=f"AI 一键编译", use_container_width=True):
                                st.session_state[f"running_ai_{src}_{orig_idx}"] = True
                                st.rerun()
                        with btn_cols[3]:
                            if detail_url:
                                st.link_button("🔗 原文", detail_url, help=f"打开源网页")

                # ═══════════════════════════════════════
                #  内联执行区 — 跟卡片同位置渲染
                # ═══════════════════════════════════════

                # ── 补录表单 ──
                form_key = f"form_{src}_{orig_idx}"
                if st.session_state.get(f"edit_form_{form_key}"):
                    with st.form(key=f"meta_form_{src}_{orig_idx}"):
                        st.markdown("**📝 补录文献元数据**")
                        st.caption("请填入源网页链接和论文真实标题")
                        file_pdf_in = paper.get("pdf_url", "")
                        new_url = st.text_input(
                            "源网页 URL (detail_url) *",
                            placeholder="https://www.imf.org/en/publications/wp/issues/...",
                            key=f"url_{src}_{orig_idx}",
                        )
                        new_title_in = st.text_input(
                            "论文标题",
                            value=str(title)[:120],
                            key=f"title_{src}_{orig_idx}",
                        )
                        col_f1, col_f2, col_f3 = st.columns([1, 1, 3])
                        with col_f1:
                            submitted = st.form_submit_button("✅ 确认并生成草稿", use_container_width=True)
                        with col_f2:
                            cancelled = st.form_submit_button("✖ 取消", use_container_width=True)
                        if submitted and new_url.strip():
                            if file_pdf_in and not file_pdf_in.startswith("http"):
                                update_imf_metadata(file_pdf_in, new_title_in.strip() or str(title), new_url.strip())
                            paper_data = {
                                "title": new_title_in.strip() or str(title),
                                "date": date, "source": src,
                                "authors": paper.get("作者", ""),
                                "paper_type": ptype if ptype else "Working Paper",
                                "detail_url": new_url.strip(),
                                "pdf_url": file_pdf_in,
                                "report_number": paper.get("report_number", ""),
                            }
                            with st.spinner("生成编译草稿..."):
                                pdf_path = file_pdf_in if file_pdf_in and not file_pdf_in.startswith("http") else ""
                                pdf_text = extract_pdf_text(pdf_path) if pdf_path else ""
                                try:
                                    filepath = vault.create_draft(paper_data, pdf_text)
                                    st.session_state.download_log.append(f"📝 {os.path.basename(filepath)}")
                                    st.toast(f"📝 草稿已生成: {os.path.basename(filepath)}")
                                    _invalidate_caches("vault")
                                except Exception as e:
                                    st.toast(f"❌ 生成失败: {e}")
                            st.session_state[f"edit_form_{form_key}"] = False
                            st.rerun()
                        elif cancelled:
                            st.session_state[f"edit_form_{form_key}"] = False
                            st.rerun()
                        elif submitted:
                            st.error("请填入源网页 URL")

                # ── AI 编译进度（🤖 触发）──
                run_key = f"running_ai_{src}_{orig_idx}"
                if st.session_state.get(run_key):
                    pdf_path_ai = _resolve_pdf_path(pdf_url)
                    if pdf_path_ai:
                        with st.status(f"🤖 AI 正在编译: {str(title)[:60]}...", expanded=True) as status_box:
                            ai_cfg = config.get("ai", {})
                            st.caption(f"API: {ai_cfg.get('api_base','?')} | 模型: {ai_cfg.get('model','?')}")
                            output_placeholder = st.empty()
                            char_counter = st.empty()

                            # 流式回调：实时显示 AI 输出
                            _streamed = [""]  # 用 list 承载可变字符串
                            def _on_chunk(chunk: str) -> None:
                                _streamed[0] += chunk
                                output_placeholder.markdown(
                                    f'<div style="max-height:300px;overflow-y:auto;font-size:0.9em;'
                                    f'white-space:pre-wrap;background:#f8faf8;padding:0.5em;border-radius:4px">'
                                    f'{_streamed[0]}</div>',
                                    unsafe_allow_html=True,
                                )
                                char_counter.caption(f"已生成 {len(_streamed[0])} 字符...")
                            # 使用 on_chunk 的 compile_with_ai —— 暂时复用 compile 方法
                            # compile 内部调用 compile_with_ai 但 on_chunk 未传递
                            # 所以直接在此调用 compile_with_ai + 后续处理
                            from ai_compile import compile_with_ai as _cwa
                            pdf_text = extract_pdf_text(pdf_path_ai)
                            success, content = _cwa(
                                pdf_text,
                                source_key=src.lower(),
                                paper_title=str(title),
                                paper_date=date,
                                paper_type=ptype,
                                config=config,
                                on_chunk=_on_chunk,
                            )
                            output_placeholder.empty()
                            char_counter.empty()

                            if success and content:
                                paper_data = {
                                    "title": cn_title or str(title), "date": date, "source": src,
                                    "authors": paper.get("作者", ""),
                                    "paper_type": ptype, "detail_url": detail_url,
                                    "pdf_url": pdf_url, "report_number": paper.get("report_number", ""),
                                }
                                try:
                                    filepath = vault.create_draft(paper_data, pdf_text)
                                    vault.update_frontmatter(filepath, {"status": "编译中"})
                                    # 替换正文为 AI 内容
                                    with open(filepath, "r", encoding="utf-8") as f:
                                        existing = f.read()
                                    end = existing.find("---", 3)
                                    if end != -1:
                                        new_body = existing[:end + 3] + "\n\n" + content
                                    else:
                                        new_body = f"---\nstatus: 编译中\n---\n\n{content}"
                                    with open(filepath, "w", encoding="utf-8") as f:
                                        f.write(new_body)
                                    st.session_state.download_log.append(f"🤖 {os.path.basename(filepath)}")
                                    status_box.update(label=f"✅ AI 编译完成: {os.path.basename(filepath)}", state="complete")
                                    _invalidate_caches("vault")
                                except Exception as e:
                                    status_box.update(label=f"❌ 保存失败: {e}", state="error")
                            else:
                                st.error(f"❌ AI 编译失败")
                                if content:
                                    st.code(content, language=None)
                                status_box.update(label="❌ AI 编译失败", state="error")
                            if st.button("✖ 关闭", key=f"close_ai_{src}_{orig_idx}"):
                                st.session_state[run_key] = False
                                st.rerun()
                    else:
                        st.warning("PDF 文件不存在，请先下载。")
                        if st.button("✖ 关闭", key=f"close_ai2_{src}_{orig_idx}"):
                            st.session_state[run_key] = False
                            st.rerun()

                # ── 返工进度（🔄 触发）──
                rw_state = st.session_state.get(f"rewrite_{src}_{orig_idx}")
                if rw_state:
                    md_path = rw_state["md_path"]
                    rew_mode = rw_state["mode"]
                    pdf_url_rw = rw_state["pdf_url"]
                    chapters = rw_state.get("chapters", [])
                    note = rw_state.get("note", "")
                    with st.status(f"🔄 返工中: {str(title)[:60]}...", expanded=True) as rw_box:
                        pdf_path_rw = _resolve_pdf_path(pdf_url_rw)
                        if pdf_path_rw:
                            st.write(f"模式: {rew_mode}")
                            result = workflow.rework(
                                md_path, rew_mode, chapters, note,
                                pdf_path_rw, paper.to_dict(),
                            )
                            if "全量" in rew_mode:
                                if result.success:
                                    st.session_state.download_log.append(f"🔄 返工完成: {os.path.basename(md_path)}")
                                    rw_box.update(label="✅ 返工完成", state="complete")
                                    _invalidate_caches("vault")
                                else:
                                    rw_box.update(label=f"❌ 返工失败: {result.content}", state="error")
                            else:
                                if result.success and result.prompt_text:
                                    st.text_area("🔮 定制提示词（复制发送给 Claude）", value=result.prompt_text, height=300, key=f"rw_prompt_{src}_{orig_idx}")
                                    rw_box.update(label="📋 提示词已生成", state="complete")
                                else:
                                    rw_box.update(label=f"❌ 提示词生成失败: {result.content}", state="error")
                        else:
                            rw_box.update(label="❌ PDF 不存在，无法返工", state="error")
                        if st.button("✖ 关闭", key=f"close_rw_{src}_{orig_idx}"):
                            del st.session_state[f"rewrite_{src}_{orig_idx}"]
                            st.rerun()

                # ── 提示词展示（🔮 触发）──
                show_key = f"show_prompt_{src}_{orig_idx}"
                if st.session_state.get(show_key):
                    pdf_path_p = _resolve_pdf_path(pdf_url)
                    if pdf_path_p:
                        prompt = workflow.build_prompt(pdf_path_p, paper.to_dict())
                        if prompt:
                            st.text_area(
                                "🔮 AI 编译提示词（复制后发送给 Claude）",
                                value=prompt, height=400,
                                key=f"prompt_text_{src}_{orig_idx}",
                            )
                        else:
                            st.warning("PDF 文本提取失败或为空")
                        col_p1, col_p2 = st.columns([1, 5])
                        with col_p1:
                            if st.button("✖ 关闭", key=f"close_prompt_{src}_{orig_idx}"):
                                st.session_state[show_key] = False
                                st.rerun()
                    else:
                        st.warning("PDF 文件不存在，请先下载。")

            st.divider()

# ── 侧边栏 ──────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 设置")
    st.markdown("**PDF 下载目录:**")
    st.code(DOWNLOAD_DIR, language=None)
    if VAULT_NOTES_DIR:
        st.markdown("**编译草稿目录:**")
        st.code(VAULT_NOTES_DIR, language=None)
    st.markdown(f"**缓存时效:** {CACHE_TTL} 分钟")
    st.markdown(f"**起始筛选日期:** {DEFAULT_FROM_DATE}")

    st.divider()

    # Vault 状态统计
    if vault.is_ready:
        status_map = vault.status_map()
        st.markdown("### 📊 编译进度")
        final = sum(1 for v in status_map.values() if v == "已定稿")
        progress = sum(1 for v in status_map.values() if v == "编译中")
        draft = sum(1 for v in status_map.values() if v == "已发现")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("🟢 已定稿", final)
        col_b.metric("🟡 编译中", progress)
        col_c.metric("⚪ 草稿", draft)

    # ── 批量导出面板 ──
    if VAULT_NOTES_DIR:
        finalized = vault.finalized()
        if finalized:
            st.divider()
            st.markdown(f"### 📄 批量导出 Word（{len(finalized)} 篇已定稿）")

            # 用 multiselect 代替独立 checkbox，避免 session state 冲突
            titles = [f"{c['source']} | {c['title'][:60]}" for c in finalized]
            selected_titles = st.multiselect(
                "选择要导出的编译稿",
                options=titles,
                default=titles,
                label_visibility="collapsed",
            )

            if selected_titles:
                selected = [finalized[titles.index(t)] for t in selected_titles]
                col_x1, col_x2 = st.columns(2)
                with col_x1:
                    if st.button(f"📄 导出选中 ({len(selected)})", use_container_width=True):
                        count = 0
                        for comp in selected:
                            try:
                                convert_to_docx(comp["filepath"], EXPORT_DIR)
                                count += 1
                            except Exception as e:
                                st.error(f"失败: {comp['title'][:30]} - {e}")
                        st.session_state.download_log.append(f"📄 批量导出 {count} 篇")
                        st.toast(f"📄 已导出 {count} 份文件到 Attachments")
                        st.rerun()
                with col_x2:
                    st.caption(f"→ `{os.path.basename(EXPORT_DIR)}`")
        else:
            st.caption("📄 暂无已定稿的编译稿")

    st.divider()

    # ── 来源管理 ──
    with st.expander("### 📖 管理数据源", expanded=False):
        for i, src in enumerate(config["sources"]):
            col_s1, col_s2, col_s3, col_s4 = st.columns([2.5, 1, 1, 1])
            status_icon = "✅" if src.get("enabled", True) else "⏸️"
            scrape_type = src.get("scrape", "manual")
            scrape_icon = "🔄" if scrape_type == "auto" else "🌐"
            col_s1.markdown(f"{status_icon} **{src['name']}** `({src['key']})`")
            col_s1.caption(f"[{src['url']}]({src['url']})")
            with col_s2:
                if st.button(f"{scrape_icon} {'自动' if scrape_type == 'auto' else '手动'}",
                             key=f"scrape_{src['key']}",
                             help="点击切换抓取策略（auto=程序抓取, manual=引导链接）"):
                    config["sources"][i]["scrape"] = "manual" if scrape_type == "auto" else "auto"
                    with open(CONFIG_PATH, "w", encoding="utf-8") as cf:
                        json.dump(config, cf, ensure_ascii=False, indent=2)
                    _invalidate_caches("all")
                    st.rerun()
            with col_s3:
                if st.button("⏸️ 禁用" if src.get("enabled", True) else "✅ 启用",
                             key=f"toggle_{src['key']}"):
                    config["sources"][i]["enabled"] = not src.get("enabled", True)
                    with open(CONFIG_PATH, "w", encoding="utf-8") as cf:
                        json.dump(config, cf, ensure_ascii=False, indent=2)
                    _invalidate_caches("all")
                    st.rerun()
            with col_s4:
                if st.button("🗑️", key=f"del_{src['key']}", help=f"删除 {src['name']}"):
                    del config["sources"][i]
                    with open(CONFIG_PATH, "w", encoding="utf-8") as cf:
                        json.dump(config, cf, ensure_ascii=False, indent=2)
                    _invalidate_caches("all")
                    st.rerun()

        st.divider()
        st.markdown("**➕ 新增来源**")
        with st.form("add_source_form"):
            new_key = st.text_input("简称 (key)", placeholder="ecb", max_chars=20)
            new_name = st.text_input("显示名称", placeholder="ECB 货币政策")
            new_url = st.text_input("主页 URL", placeholder="https://www.ecb.europa.eu/...")
            new_scrape = st.selectbox("抓取类型", ["manual", "auto"])
            new_hints = st.text_input("文件名关键词（逗号分隔）", placeholder="ecb, european central bank")
            submitted = st.form_submit_button("➕ 添加来源")
            if submitted and new_key.strip() and new_name.strip() and new_url.strip():
                hints = [h.strip().lower() for h in new_hints.split(",") if h.strip()]
                config["sources"].append({
                    "name": new_name.strip(),
                    "key": new_key.strip().lower(),
                    "url": new_url.strip(),
                    "enabled": True,
                    "scrape": new_scrape,
                    "filename_hints": hints,
                })
                with open(CONFIG_PATH, "w", encoding="utf-8") as cf:
                    json.dump(config, cf, ensure_ascii=False, indent=2)
                st.toast(f"✅ 已添加来源: {new_name.strip()}")
                st.cache_data.clear()
                st.rerun()

    st.divider()

    if st.session_state.download_log:
        st.markdown("### 📥 最近操作")
        for log_entry in st.session_state.download_log[-10:]:
            st.caption(log_entry)
        if st.button("清空日志"):
            st.session_state.download_log = []
            st.rerun()

    # 从已加载数据中统计本地 PDF（避免重复磁盘扫描）
    local_count = len([p for p in all_raw if p.get("source") == "本地"])
    st.caption(f"📁 本地已有 PDF: {local_count} 个")
    st.caption(f"⏱️ 加载时间: {datetime.now().strftime('%H:%M:%S')}")
