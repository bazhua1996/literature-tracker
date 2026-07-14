"""
AI 编译模块 — 调用兼容 OpenAI 协议的 API（DeepSeek、OpenAI 等）。
"""

import json
import requests
from prompt_builder import build_compilation_prompt


def compile_with_ai(pdf_text: str, source_key: str = "",
                    paper_title: str = "", paper_date: str = "",
                    paper_type: str = "", config: dict = None,
                    on_chunk=None) -> tuple[bool, str]:
    """
    调用 AI API 生成编译稿。
    返回 (成功, markdown_content | error_message)。

    on_chunk: 可选回调，接收每个增量文本片段用于流式展示
    """
    if not config:
        config = {}

    ai_config = config.get("ai", {})
    api_base = ai_config.get("api_base", "https://api.deepseek.com").rstrip("/")
    api_key = ai_config.get("api_key", "")
    model = ai_config.get("model", "deepseek-chat")

    if not api_key:
        return False, "请在 config.json → ai.api_key 中填入 API Key"

    prompt = build_compilation_prompt(
        pdf_text, source_key, paper_title, paper_date, paper_type
    )

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "temperature": 0.7,
        "max_tokens": 8192,
    }

    try:
        resp = requests.post(
            f"{api_base}/v1/chat/completions",
            headers=headers,
            json=payload,
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()

        full_content = ""
        for line in resp.iter_lines():
            if not line:
                continue
            text = line.decode("utf-8")
            if text.startswith("data: "):
                data_text = text[6:]
                if data_text.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_text)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full_content += content
                        if on_chunk:
                            on_chunk(content)
                except json.JSONDecodeError:
                    continue

        return True, full_content

    except requests.RequestException as e:
        return False, f"API 请求失败: {e}"
    except Exception as e:
        return False, f"未知错误: {e}"
