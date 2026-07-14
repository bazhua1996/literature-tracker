# 03c — 一键 AI 编译

**What to build:** 追踪器中点击"🤖 AI 编译"按钮后，后台自动调用 Claude API，将 PDF 原文按编译规范直接生成完整的 8 章中文分析报告 `.md`，用户只需在 Obsidian 中审校。

**Blocked by:** 03b — 需要提示词组装模块作为 AI 调用的输入

**Status:** ready-for-agent

- [ ] `config.json` 新增 `ai` 配置节：`api_base`、`api_key`、`model`
- [ ] 新增 `ai_compile.py` 模块，包含 `compile_with_ai(pdf_text, spec, config) -> str` 函数
- [ ] 调用兼容 OpenAI 协议的 API（适配 Claude、DeepSeek 等模型）
- [ ] 流式输出：编译进度实时展示在追踪器界面上（章节标题逐个出现）
- [ ] 编译完成后自动覆盖草稿 `.md`，状态设为"编译中"
- [ ] 超时与错误处理：API 调用失败时保留已生成的部分内容，不丢失
- [ ] 验证：用 ECB 报告和 IMF 论文分别测试，生成的 `.md` 符合 COMPILATION_SPEC.md 结构规范
