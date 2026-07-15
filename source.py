"""
Source 定义模块 — 将所有文献来源相关的知识集中在一个地方。

整合了原先分散在 sources.py（URLs、fetcher）、prompt_builder.py（style_guide、label）、
config.json（filename_hints、scrape）和 app.py（icon、is_imf_manual）中的来源元数据。
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Source:
    """单个文献来源的完整元数据。"""
    key: str                              # "imf"、"boj"、"ecb" 等
    name: str                             # "IMF Working Papers"
    url: str                              # 主页 URL
    enabled: bool = True
    scrape: str = "manual"                # "auto" 或 "manual"
    filename_hints: list[str] = field(default_factory=list)
    style_guide: str = ""                 # AI 提示词写作风格偏好
    label: str = ""                       # 中文显示标签，如 "BOJ（日本央行）"
    icon: str = "📄"                      # UI 表情符号
    institution_keywords: list = field(default_factory=list)
    # [(full_name, abbreviation), ...] 用于 PDF 元数据猜测
    source_year: Optional[int] = None     # BOJ 等需要年份参数的来源
    fetcher: object = None                # 抓取函数（在 sources.py 中赋值）
    manual_links: list[dict] = field(default_factory=list)  # 手动来源的引导链接


# ═══════════════════════════════════════════
#  内置来源元数据（硬编码知识）
# ═══════════════════════════════════════════

_BUILTIN_STYLE_GUIDES: dict[str, str] = {
    "imf": "- 偏学术分析\n- 关注方法论和数据来源\n- 政策启示侧重全球视角",
    "boj": "- 偏政策解读\n- 关注利率路径和市场影响\n- 政策启示侧重亚洲/中国对比",
    "ecb": "- 偏制度分析\n- 关注监管框架和欧洲一体化\n- 政策启示侧重金融监管",
    "bis": "- 偏宏观审慎\n- 关注全球金融稳定和系统性风险\n- 政策启示侧重宏观审慎政策",
    "fed": "- 偏货币政策\n- 关注利率决议和就业/通胀双目标\n- 政策启示侧重央行独立性",
    "boe": "- 偏货币政策\n- 关注通胀目标和金融稳定\n- 政策启示侧重央行沟通",
    "wb": "- 偏发展经济学\n- 关注全球发展、减贫和基础设施建设\n- 政策启示侧重国际发展合作",
    "oecd": "- 偏政策分析\n- 关注经济展望、结构性改革和跨国比较\n- 政策启示侧重最佳实践和标准",
    "wto": "- 偏贸易政策\n- 关注全球贸易规则、争端解决和市场准入\n- 政策启示侧重贸易自由化",
    "nber": "- 偏学术研究\n- 关注前沿经济学实证研究\n- 政策启示侧重学术发现的政策含义",
    "cepr": "- 偏政策研究\n- 关注欧洲经济政策议题\n- 政策启示侧重欧洲经验借鉴",
    "adb": "- 偏区域发展\n- 关注亚洲基础设施建设、区域合作和可持续发展\n- 政策启示侧重区域经验",
    "aiib": "- 偏基础设施融资\n- 关注可持续基础设施和跨境互联互通\n- 政策启示侧重多边融资机制",
    "eib": "- 偏投资银行业务\n- 关注气候融资、创新投资和中小企业支持\n- 政策启示侧重政策性金融",
    "ebrd": "- 偏转型经济\n- 关注市场经济转型和私营部门发展\n- 政策启示侧重制度转型经验",
    "wef": "- 偏全球议题\n- 关注竞争力、第四次工业革命和全球风险\n- 政策启示侧重前瞻性趋势",
    "piie": "- 偏国际经济政策\n- 关注贸易、汇率和全球治理\n- 政策启示侧重美国视角的国际经济政策",
    "bruegel": "- 偏欧洲经济政策\n- 关注创新、竞争和数字政策\n- 政策启示侧重欧洲前沿研究",
}

_BUILTIN_LABELS: dict[str, str] = {
    "imf": "IMF",
    "boj": "BOJ（日本央行）",
    "ecb": "ECB（欧洲央行）",
    "bis": "BIS（国际清算银行）",
    "fed": "Fed（美联储）",
    "boe": "BOE（英格兰银行）",
    "wb": "WB（世界银行）",
    "oecd": "OECD（经合组织）",
    "wto": "WTO（世界贸易组织）",
    "nber": "NBER（美国国家经济研究局）",
    "cepr": "CEPR（欧洲经济政策研究中心）",
    "adb": "ADB（亚洲开发银行）",
    "aiib": "AIIB（亚投行）",
    "eib": "EIB（欧洲投资银行）",
    "ebrd": "EBRD（欧洲复兴开发银行）",
    "wef": "WEF（世界经济论坛）",
    "piie": "PIIE（彼得森研究所）",
    "bruegel": "Bruegel（布鲁盖尔研究所）",
    "eu": "EU（欧盟委员会）",
}

_BUILTIN_ICONS: dict[str, str] = {
    "imf": "🏛️",
    "boj": "🏦",
}

_BUILTIN_INSTITUTION_KEYWORDS: dict[str, list] = {
    "imf": [("International Monetary Fund", "IMF")],
    "boj": [("Bank of Japan", "BOJ")],
    "ecb": [("European Central Bank", "ECB"), ("European Banking Authority", "EBA")],
    "bis": [("Bank for International Settlements", "BIS")],
    "fed": [("Federal Reserve", "Fed")],
    "boe": [("Bank of England", "BOE")],
    "wb": [("World Bank", "WB")],
    "oecd": [("Organisation for Economic Co-operation and Development", "OECD"), ("Organization for Economic Cooperation and Development", "OECD")],
    "wto": [("World Trade Organization", "WTO")],
    "nber": [("National Bureau of Economic Research", "NBER")],
    "cepr": [("Centre for Economic Policy Research", "CEPR")],
    "adb": [("Asian Development Bank", "ADB")],
    "aiib": [("Asian Infrastructure Investment Bank", "AIIB")],
    "eib": [("European Investment Bank", "EIB")],
    "ebrd": [("European Bank for Reconstruction and Development", "EBRD")],
    "wef": [("World Economic Forum", "WEF")],
    "piie": [("Peterson Institute for International Economics", "PIIE")],
    "bruegel": [("Bruegel", "Bruegel")],
}

_DEFAULT_STYLE_GUIDE = "- 偏数据叙事\n- 关注核心发现和趋势\n- 政策启示侧重可借鉴经验"

# 模块级来源注册表（load_sources 填充）
_sources: dict[str, Source] = {}


# ═══════════════════════════════════════════
#  公开 API
# ═══════════════════════════════════════════

def load_sources(config_sources: list[dict]) -> dict[str, Source]:
    """
    合并 config.json 的 sources 数组与内置元数据。
    返回 lowercase key → Source 的映射。同时填充模块级缓存。
    """
    global _sources
    _sources.clear()
    for entry in config_sources:
        key = entry.get("key", "").lower().strip()
        if not key:
            continue
        source = Source(
            key=key,
            name=entry.get("name", ""),
            url=entry.get("url", ""),
            enabled=entry.get("enabled", True),
            scrape=entry.get("scrape", "manual"),
            filename_hints=entry.get("filename_hints", []),
            style_guide=_BUILTIN_STYLE_GUIDES.get(key, _DEFAULT_STYLE_GUIDE),
            label=_BUILTIN_LABELS.get(key, entry.get("name", "")),
            icon=_BUILTIN_ICONS.get(key, "📄"),
            institution_keywords=_BUILTIN_INSTITUTION_KEYWORDS.get(key, []),
            source_year=entry.get("source_year"),
        )
        _sources[key] = source
    return _sources


def get_source(key: str) -> Optional[Source]:
    """按 key（大小写不敏感）查找 Source。"""
    return _sources.get(key.lower().strip())


def get_style_guide(source_key: str) -> str:
    """获取来源的写作风格指南。"""
    source = _sources.get(source_key.lower().strip())
    return source.style_guide if source else _DEFAULT_STYLE_GUIDE


def get_label(source_key: str) -> str:
    """获取来源的中文显示标签。"""
    source = _sources.get(source_key.lower().strip())
    return source.label if source else source_key


def get_icon(source_key: str) -> str:
    """获取来源的表情符号图标。"""
    source = _sources.get(source_key.lower().strip())
    return source.icon if source else "📄"


def get_all_institution_keywords() -> list:
    """收集所有来源的机构关键词（供 PDF 元数据猜测使用）。需要先调用 load_sources()。"""
    result = []
    for src in _sources.values():
        result.extend(src.institution_keywords)
    return result


def get_builtin_institution_keywords() -> list:
    """收集内置来源的机构关键词（无需 load_sources，始终可用）。"""
    result = []
    for keywords in _BUILTIN_INSTITUTION_KEYWORDS.values():
        result.extend(keywords)
    return result
