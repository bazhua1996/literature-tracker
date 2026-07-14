# 03b — AI 编译提示词组装

**What to build:** 追踪器根据 PDF 原文内容 + `COMPILATION_SPEC.md` 规范 + 来源类型，自动拼接结构化 Claude 编译提示词，用户可在界面预览、复制并直接发送给 Claude 进行编译。

**Blocked by:** 03a — 需要 PDF 文本提取能力预填提示词中的原文内容

**Status:** ready-for-agent

- [ ] 新增 `prompt_builder.py` 模块，包含 `build_compilation_prompt(pdf_text, spec, source_config) -> str` 函数
- [ ] 提示词结构：系统指令（编译规范摘要） + PDF 原文 + 输出格式要求
- [ ] 系统指令从 `COMPILATION_SPEC.md` 自动生成摘要版本注入提示词
- [ ] 根据来源类型调整风格偏好（央行报告偏政策解读、WP 偏学术分析、旗舰报告偏数据叙事）
- [ ] 点击 📝 时新增"🔮 生成提示词"选项：将拼接好的提示词展示在文本区域供复制
- [ ] 验证：用 ECB 报告测试，生成的提示词包含"8 章结构""摘要+关键词""政策启示"等规范要素
