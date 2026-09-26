# A股主线识别系统 V2.2 — Phase 1B G1 Closure 状态

日期：2026-09-26
结论：G1 仍为部分通过；禁止进入 Phase 2。

## 本次已完成

- 核清并修正 remote baseline 审计口径。
- 新增 GitHub Actions：Python mainline tests、Node tests、production build。
- 再次确认运行环境没有 TUSHARE_TOKEN、SUPABASE_URL、SUPABASE_SERVICE_ROLE_KEY。
- 核查 SECURITY DEFINER 遗留 WARN，并形成不破坏现有触发器的最小修复建议。
- 评估 BaoStock 作为历史行情 Backup：SDK 可安装，但当前执行环境连接数据服务器失败，错误为网络接收错误；未登记为已验证。
- 识别 AKShare 的交易所股票/退市列表和申万历史分类候选接口；在完成稳定性、字段日期语义和历史完整性验证前，不写入生产表。

## 真实数据状态

security_master=0
taxonomy_definitions=0
membership_history=0
stock_daily=0
float_market_cap_daily=0
benchmark_daily=0

没有用 fixture、当前截面或0值补写生产数据。

## G1核心阻塞

1. Tushare Primary 无 Token，未真实验证。
2. 2019年至今全A证券主数据、历史行情和流通市值未回放。
3. 申万一级 strict PIT 成分未取得，无法完成5个历史日期和调入/调出案例。
4. 合格 Backup 未完成稳定性与字段语义验收。
5. 真实停牌、新股、退市、双源冲突、Fallback和Freeze尚未全链路完成。
6. 新增CI需要远程Run实际成功后才能勾选“GitHub CI通过”。

Phase 2 的 RS、WIN、TURNOVER、Breadth、S1-S4、状态机、市场环境、标签及AI解释均未开发。
