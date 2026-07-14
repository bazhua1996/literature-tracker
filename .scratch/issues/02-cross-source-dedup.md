# 02 — 跨来源去重

**What to build:** `fetch_all` 中的 dedup 逻辑从仅检查 BOJ 标题，扩展为对所有来源按 `detail_url` 做精确匹配去重，fallback 到标题 hash。同一个文献不会因为文件名推断来源不同而在列表中重复出现。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] `fetch_all` 中新增 `seen_urls` 集合，所有来源的 paper 按 `detail_url` 去重（空 URL 跳过）
- [ ] `detail_url` 为空时 fallback 到标题 + 日期的 hash 去重
- [ ] 本地 PDF 追加时不仅检查 BOJ 标题，也检查 IMF/ECB/BIS/Fed/BOE
- [ ] 验证：同一个 IMF PDF 通过 `fetch_local_pdfs` 和 `fetch_imf` 同时出现时只保留一份
