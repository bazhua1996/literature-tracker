"""
AI 编译提示词组装模块。
根据 PDF 原文 + COMPILATION_SPEC.md + 来源配置，生成结构化 Claude 编译提示词。
"""

import os

from source import get_label, get_style_guide


def _load_spec_summary() -> str:
    """从 COMPILATION_SPEC.md 提取编译规范摘要"""
    spec_path = os.path.join(os.path.dirname(__file__), "COMPILATION_SPEC.md")
    if not os.path.exists(spec_path):
        return ""
    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def build_compilation_prompt(pdf_text: str, source_key: str = "",
                             paper_title: str = "", paper_date: str = "",
                             paper_type: str = "") -> str:
    """
    构建 Claude 编译提示词。
    返回完整 prompt 字符串，用户可直接复制发送给 Claude。
    """
    spec = _load_spec_summary()
    source_label = get_label(source_key)
    style = get_style_guide(source_key)

    # 提取规范核心结构
    structure_section = ""
    if spec:
        # 从规范中提取章节模板
        for section in ["一、引言与背景", "二、", "八、结论与政策启示",
                         "摘要：", "关键词：", "## 三、内容规范"]:
            if section in spec:
                idx = spec.find(section)
                structure_section += spec[idx:idx+500] + "\n\n"

    prompt = f"""你是一位国际金融与货币政策研究分析师。请将以下{source_label}发布的{paper_type}原文编译为一份中文深度分析报告。

## 原文内容

{pdf_text}

## 编译要求

### 格式规范
{structure_section[:3000] if structure_section else _default_structure()}

### 风格偏好（{source_label}）
{style}

### 关键要求
1. **不是翻译，是深度分析报告**——站在中国政策研究者的视角解读和评析
2. **数据融入叙事**——关键数字在分析段落中自然引用并解读其含义，不简单罗列
3. **章节结构**：摘要 → 关键词 → 引言与背景 → 4-6章核心分析 → 结论与政策启示（5条左右）
4. **英文术语首次出现时标注原文和缩写**，后续用缩写
5. **政策启示必须结合中国国情**：监管框架、市场特征、发展阶段
6. **正文长度**：3500-5000 中文字符
7. **Markdown 格式输出**：章节用 ## 标题，子节用 ### 标题
8. 引用行格式：`> 原文标题 | 机构 | 日期`

## 输出格式

```markdown
# 关于{source_label}《{paper_title or '报告全称'}》的分析

> {paper_title or '原文标题'} | {source_label} | {paper_date or '日期'}

**摘要：** [150-200字]

**关键词：** [3-5个]

## 一、引言与背景
[发布背景、数据来源、方法论、覆盖范围]

## 二、[第一核心主题]
（一）[子主题]
...

## 八、结论与政策启示
[综合结论 + 5条中国视角政策建议]

## 标签
#[来源] #[主题1] #[主题2]
```

请直接输出 Markdown 格式的报告全文，不要有多余的对话。
"""
    return prompt


def _default_structure() -> str:
    return """## 一、引言与背景
## 二、[核心主题]
（一）[子主题]
## 八、结论与政策启示
## 标签"""
