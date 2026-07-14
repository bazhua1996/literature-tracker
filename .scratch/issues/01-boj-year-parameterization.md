# 01 — BOJ 年份参数化

**What to build:** BOJ 抓取 URL 从硬编码 `state_2026` 迁移为 `state_{year}` 模板，使得 2027 年 1 月 1 日后 BOJ 自动抓取新年度页面，无需手动修改代码。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] `config.json` 中 BOJ 来源的 URL 从 `state_2026/index.htm` 改为 `state_{year}/index.htm` 占位符
- [ ] `fetch_boj()` 中按 `datetime.now().year` 填入年份，同时保留 `source_year` 配置覆盖项以便回看历史年份
- [ ] MPR URL 同样参数化
- [ ] 验证：2026 年 7 月抓取后 `boj_cache.json` 中包含正确的 2026 年声明
- [ ] 手动将系统时间模拟到 2027-01-15，验证自动抓取 `state_2027` 页面
