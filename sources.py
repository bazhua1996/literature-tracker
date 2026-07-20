"""
文献来源抓取模块。
- BOJ: 直接抓取 MPM 声明列表
- IMF: 因 Akamai 反爬保护，改为链接跳转 + 本地文件扫描
- Vault: Obsidian vault 状态扫描 + 编译草稿生成
"""

import re
import os
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ── 源注册表 ──────
from source import Source, register_fetcher as _reg_fetcher

# [已弃用] SOURCE_REGISTRY — 新代码请使用 source.get_source(key).fetcher
SOURCE_REGISTRY: dict[str, Source] = {}


def register_fetcher(key: str, fetcher, manual_links: list[dict] = None):
    """
    [已弃用] 请使用 source.register_fetcher(key, fetcher)。
    保留此函数以维护向后兼容。
    """
    _reg_fetcher(key, fetcher)  # 委托给 source.py 的统一注册表
    source = Source(
        key=key, name=key.upper(), url="",
        fetcher=fetcher,
        manual_links=manual_links or [],
    )
    SOURCE_REGISTRY[key] = source


def get_fetcher(key: str):
    """获取抓取函数。优先从 source.py 注册表，fallback 本地。"""
    from source import get_source
    src = get_source(key)
    if src and src.fetcher:
        return src.fetcher
    # 向后兼容 fallback
    local = SOURCE_REGISTRY.get(key)
    return local.fetcher if local else None


# 向后兼容别名
SOURCE_FETCHERS = SOURCE_REGISTRY
FALLBACK_MANUAL: dict[str, list[dict]] = {}  # 已弃用，改用 Source.manual_links


@dataclass
class Paper:
    title: str
    date: str          # "2026-06-16"
    source: str        # "IMF" / "BOJ" / "本地"
    authors: str       # 作者（机构发布则为空）
    paper_type: str    # "Working Paper" / "MPM Statement" / "PDF文件"
    detail_url: str    # 源网页链接
    pdf_url: str       # PDF 直链或本地路径
    report_number: str # 报告期号，如 "WP/26/133"


def _save_cache(key: str, papers: list[dict]) -> None:
    path = os.path.join(CACHE_DIR, f"{key}_cache.json")
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"timestamp": datetime.now().isoformat(), "papers": papers}, f, ensure_ascii=False)
        os.replace(tmp_path, path)  # 原子替换
    except Exception as e:
        print(f"[缓存] 写入失败 {path}: {e}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def clear_disk_cache() -> None:
    """清除所有磁盘 JSON 缓存文件"""
    for fname in os.listdir(CACHE_DIR):
        if fname.endswith("_cache.json") or fname.endswith(".tmp") or fname.endswith(".bak"):
            try:
                os.remove(os.path.join(CACHE_DIR, fname))
            except Exception:
                pass


def _load_cache(key: str, ttl_minutes: int = 60) -> Optional[list[dict]]:
    path = os.path.join(CACHE_DIR, f"{key}_cache.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ts = datetime.fromisoformat(data["timestamp"])
        if (datetime.now() - ts).total_seconds() < ttl_minutes * 60:
            return data["papers"]
    except json.JSONDecodeError as e:
        print(f"[缓存] JSON 损坏 {path}: {e}，删除后重新抓取")
        try:
            os.remove(path)
        except Exception:
            pass
    except Exception as e:
        print(f"[缓存] 读取失败 {path}: {e}")
    return None


# ═══════════════════════════════════════════
#  IMF — 因 Akamai 反爬，返回引导链接
# ═══════════════════════════════════════════

IMF_WP_URL = "https://www.imf.org/en/publications/wp"
IMF_GFSR_URL = "https://www.imf.org/en/publications/gfsr"
IMF_WEO_URL = "https://www.imf.org/en/publications/weo"


def fetch_imf(cache_ttl: int = 60) -> list[dict]:
    """
    IMF 网站有 Akamai 机器人保护，程序化抓取不可用。
    引导链接已移至 source.py 的 _BUILTIN_MANUAL_LINKS，由 app.py 直接渲染。
    """
    return []


# ═══════════════════════════════════════════
#  BOJ
# ═══════════════════════════════════════════

BOJ_MPM_TEMPLATE = "https://www.boj.or.jp/en/mopo/mpmdeci/state_{year}/index.htm"
BOJ_MPR_TEMPLATE = "https://www.boj.or.jp/en/mopo/mpmdeci/mpr_{year}/"


def _get_boj_year(source_config: dict = None) -> int:
    """获取 BOJ 抓取年份：优先用配置的 source_year，否则当前年份"""
    if source_config and source_config.get("source_year"):
        return int(source_config["source_year"])
    return datetime.now().year


def fetch_boj(cache_ttl: int = 60, source_config: dict = None) -> list[dict]:
    """抓取 BOJ 货币政策声明（年份参数化）"""
    year = _get_boj_year(source_config)
    cache_key = f"boj_{year}"
    cached = _load_cache(cache_key, cache_ttl)
    if cached:
        return cached

    papers = []
    seen_urls = set()

    mpm_url = BOJ_MPM_TEMPLATE.format(year=year)
    mpr_url = BOJ_MPR_TEMPLATE.format(year=year)

    def _scrape_page(url: str, default_type: str) -> None:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            for link in soup.select("a[href$='.pdf']"):
                href = link.get("href", "")
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)

                if href.startswith("/"):
                    pdf_url = "https://www.boj.or.jp" + href
                elif href.startswith("http"):
                    pdf_url = href
                else:
                    # 去除相对路径前缀 ./ 或 ../
                    clean_href = href
                    while clean_href.startswith("../"):
                        clean_href = clean_href[3:]
                    while clean_href.startswith("./"):
                        clean_href = clean_href[2:]
                    pdf_url = "https://www.boj.or.jp/" + clean_href

                title = link.get_text(strip=True)
                if not title:
                    parent = link.parent
                    title = parent.get_text(strip=True)[:200] if parent else ""
                title = re.sub(r'\[PDF\s*\d+KB\]', '', title, flags=re.IGNORECASE).strip()

                date_str = _parse_date_from_context(link)

                papers.append(asdict(Paper(
                    title=title[:200],
                    date=date_str,
                    source="BOJ",
                    authors="",
                    paper_type=default_type,
                    detail_url=pdf_url,     # 使用 PDF URL 确保唯一性
                    pdf_url=pdf_url,
                    report_number="",
                )))
        except Exception as e:
            print(f"[BOJ] 抓取失败 {url}: {e}")

    _scrape_page(mpm_url, "MPM Statement")
    _scrape_page(mpr_url, "Monetary Policy Release")
    papers.sort(key=lambda p: p["date"] or "", reverse=True)

    _save_cache(cache_key, papers)
    return papers


# ═══════════════════════════════════════════
#  本地 PDF 文件扫描
# ═══════════════════════════════════════════

# ── IMF 元数据缓存 ─────────────────────────────────

IMF_META_PATH = os.path.join(CACHE_DIR, "imf_metadata.json")


def _load_imf_metadata() -> dict:
    """加载手动补录的 IMF 元数据缓存"""
    if not os.path.exists(IMF_META_PATH):
        return {}
    try:
        with open(IMF_META_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[元数据] JSON 损坏 {IMF_META_PATH}: {e}")
        # 尝试从备份恢复
        backup_path = IMF_META_PATH + ".bak"
        if os.path.exists(backup_path):
            try:
                with open(backup_path, "r", encoding="utf-8") as bf:
                    return json.load(bf)
            except Exception:
                pass
        return {}
    except Exception as e:
        print(f"[元数据] 读取失败 {IMF_META_PATH}: {e}")
        return {}


def _save_imf_metadata(meta: dict) -> None:
    """保存 IMF 元数据缓存（原子写入 + 备份）"""
    tmp_path = IMF_META_PATH + ".tmp"
    try:
        # 先备份旧文件
        if os.path.exists(IMF_META_PATH):
            bak_path = IMF_META_PATH + ".bak"
            try:
                os.replace(IMF_META_PATH, bak_path)
            except Exception:
                pass
        # 原子写入新文件
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, IMF_META_PATH)
    except Exception as e:
        print(f"[元数据] 写入失败 {IMF_META_PATH}: {e}")
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def update_imf_metadata(filepath: str, title: str, detail_url: str,
                        paper_type: str = "", report_number: str = "") -> None:
    """补录单篇 IMF 文献的元数据"""
    meta = _load_imf_metadata()
    meta[filepath] = {
        "title": title,
        "detail_url": detail_url,
        "paper_type": paper_type or "Working Paper",
        "report_number": report_number,
        "updated_at": datetime.now().isoformat(),
    }
    _save_imf_metadata(meta)


def _guess_source_from_filename(fname: str, sources_config: list[dict]) -> str:
    """根据文件名关键词匹配来源，匹配不到返回 '本地'"""
    fname_lower = fname.lower()
    for src in sources_config:
        for hint in src.get("filename_hints", []):
            if hint.lower() in fname_lower:
                return src["key"].upper()
    return "本地"


def fetch_local_pdfs(pdf_dir: str, sources_config: list[dict] = None) -> list[dict]:
    """扫描指定目录下的 PDF 文件，合并 IMF 元数据缓存，按 filename_hints 归类来源"""
    if not os.path.isdir(pdf_dir):
        return []

    if sources_config is None:
        sources_config = []

    imf_meta = _load_imf_metadata()
    papers = []
    try:
        for fname in sorted(os.listdir(pdf_dir), reverse=True):
            if not fname.lower().endswith(".pdf"):
                continue

            filepath = os.path.join(pdf_dir, fname)
            mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            size_kb = os.path.getsize(filepath) // 1024

            source = _guess_source_from_filename(fname, sources_config)

            # 优先使用缓存的元数据
            if filepath in imf_meta:
                cached = imf_meta[filepath]
                title = cached.get("title", "")
                detail_url = cached.get("detail_url", "")
                paper_type = cached.get("paper_type", f"PDF ({size_kb}KB)")
                report_number = cached.get("report_number", "")
            else:
                title = os.path.splitext(fname)[0]
                title = re.sub(r'[-_]+', ' ', title)[:200]
                detail_url = ""
                paper_type = f"PDF ({size_kb}KB)"
                report_number = ""

            papers.append(asdict(Paper(
                title=title,
                date=mtime.strftime("%Y-%m-%d"),
                source=source,
                authors="",
                paper_type=paper_type,
                detail_url=detail_url,
                pdf_url=filepath,
                report_number=report_number,
            )))
    except Exception as e:
        print(f"[本地] 扫描失败: {e}")

    return papers


# ═══════════════════════════════════════════
#  Obsidian Vault 状态扫描
# ═══════════════════════════════════════════

# ── Vault 操作已迁移至 vault.py ──────────────────
# 以下为向后兼容 shim，委托给 vault.Vault。
# 新代码应直接使用 vault.Vault 类。

from vault import (
    Vault, extract_pdf_text, parse_frontmatter as _parse_frontmatter,
    guess_metadata_from_pdf as _guess_metadata_from_pdf,
)


def _iter_vault_md(notes_dir: str):
    """
    [已弃用] 遍历 vault 中所有 .md 文件，yield (filepath, frontmatter)。
    新代码请使用 vault.Vault 类。
    """
    if not os.path.isdir(notes_dir):
        return
    for root, dirs, files in os.walk(notes_dir):
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
                fm = _parse_frontmatter(content)
                if fm:
                    yield filepath, fm
            except Exception:
                continue


def scan_vault_status(notes_dir: str) -> dict[str, str]:
    """[已弃用] 新代码请使用 vault.Vault(notes_dir).status_map()"""
    return Vault(notes_dir).status_map()


def list_finalized_compilations(notes_dir: str) -> list[dict]:
    """[已弃用] 新代码请使用 vault.Vault(notes_dir).finalized()"""
    return Vault(notes_dir).finalized()


def find_compilation_md(detail_url: str, notes_dir: str) -> Optional[str]:
    """[已弃用] 新代码请使用 vault.Vault(notes_dir).find(detail_url)"""
    return Vault(notes_dir).find(detail_url)


def generate_draft(paper: dict, notes_dir: str, pdf_text: str = "") -> tuple:
    """
    [已弃用] 新代码请使用 vault.Vault(notes_dir).create_draft(paper, pdf_text)。
    返回 (成功: bool, 文件路径或错误信息: str)。
    """
    try:
        filepath = Vault(notes_dir).create_draft(paper, pdf_text)
        return True, filepath
    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════

def _parse_date_from_context(element) -> str:
    """从链接元素的上下文提取日期"""
    parent_text = element.parent.get_text() if element.parent else ""

    month_pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})'
    match = re.search(month_pattern, parent_text, re.IGNORECASE)
    if match:
        groups = match.groups()
        month_map = {m: i + 1 for i, m in enumerate(
            ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
             'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])}
        m = month_map.get(groups[0][:3].lower(), 1)
        return f"{groups[2]}-{m:02d}-{int(groups[1]):02d}"

    match = re.search(r'(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})日?', parent_text)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"

    return ""


def download_pdf(pdf_url: str, save_dir: str, filename: str = "") -> tuple:
    """下载 PDF 到指定目录。返回 (success, filepath_or_error)"""
    try:
        resp = requests.get(pdf_url, headers=HEADERS, timeout=60, stream=True)
        resp.raise_for_status()

        if not filename:
            cd = resp.headers.get("Content-Disposition", "")
            match = re.search(r'filename[^;=\n]*=["\']?([^"\'\n;]+)', cd)
            if match:
                filename = match.group(1)
            else:
                filename = pdf_url.rstrip("/").split("/")[-1]
                if not filename.endswith(".pdf"):
                    filename += ".pdf"

        filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
        filepath = os.path.join(save_dir, filename)
        os.makedirs(save_dir, exist_ok=True)

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        return True, filepath
    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════════════
#  源注册（新增来源在此注册即可）
# ═══════════════════════════════════════════

# ── ECB ──
ECB_MP_URL = "https://www.ecb.europa.eu/press/pressconf/"
ECB_BULL_URL = "https://www.ecb.europa.eu/pub/economic-bulletin/"


def fetch_ecb(cache_ttl: int = 60) -> list[dict]:
    """ECB 网站 JS 渲染，程序化抓取暂不可用。引导链接在 source.py 的 _BUILTIN_MANUAL_LINKS 中。"""
    return []


# ── BIS ──
BIS_PUB_URL = "https://www.bis.org/publ/"


def fetch_bis(cache_ttl: int = 60) -> list[dict]:
    """BIS 出版物引导链接已移至 source.py 的 _BUILTIN_MANUAL_LINKS。"""
    return []


# ── Fed ──
FED_BASE = "https://www.federalreserve.gov"
FED_FOMC_URL = f"{FED_BASE}/monetarypolicy/fomccalendars.htm"
FED_BEIGE_URL = f"{FED_BASE}/monetarypolicy/beige-book-default.htm"


def _parse_fed_date(url: str) -> str:
    """从 Fed URL 提取日期: fomcpresconf20260128.htm → 2026-01-28"""
    m = re.search(r'(\d{4})(\d{2})(\d{2})', url)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ""


def fetch_fed(cache_ttl: int = 60) -> list[dict]:
    """抓取 Fed FOMC 会议日历的新闻发布会声明链接"""
    cached = _load_cache("fed", cache_ttl)
    if cached:
        return cached

    papers = []
    seen_urls = set()

    def _scrape_fomc(url: str, paper_type: str) -> None:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                text = a.get_text(strip=True)
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)
                # 匹配 FOMC 新闻发布会链接
                if "fomcpresconf" not in href.lower() and "fomcpressconf" not in href.lower():
                    continue
                if href.startswith("/"):
                    detail_url = FED_BASE + href
                elif href.startswith("http"):
                    detail_url = href
                else:
                    detail_url = f"{FED_BASE}/{href}"

                date_str = _parse_fed_date(href)
                title = f"FOMC Press Conference" if not text or len(text) < 3 else text[:200]
                if date_str:
                    title = f"{title} ({date_str})"

                papers.append(asdict(Paper(
                    title=title,
                    date=date_str,
                    source="Fed",
                    authors="",
                    paper_type=paper_type,
                    detail_url=detail_url,
                    pdf_url="",
                    report_number="",
                )))
        except Exception as e:
            print(f"[Fed] 抓取失败 {url}: {e}")

    _scrape_fomc(FED_FOMC_URL, "FOMC Press Conference")
    papers.sort(key=lambda p: p["date"] or "", reverse=True)
    _save_cache("fed", papers)
    return papers


# ── BOE ──
BOE_MPC_URL = "https://www.bankofengland.co.uk/monetary-policy-summary-and-minutes"
BOE_REPORT_URL = "https://www.bankofengland.co.uk/monetary-policy-report"


def fetch_boe(cache_ttl: int = 60) -> list[dict]:
    """BOE 引导链接已移至 source.py 的 _BUILTIN_MANUAL_LINKS 中。"""
    return []


# ═══════════════════════════════════════════
#  源注册（新增来源在此注册 fetcher 即可）
# ═══════════════════════════════════════════

_reg_fetcher("imf", fetch_imf)
_reg_fetcher("boj", fetch_boj)
_reg_fetcher("ecb", fetch_ecb)
_reg_fetcher("bis", fetch_bis)
_reg_fetcher("fed", fetch_fed)
_reg_fetcher("boe", fetch_boe)
