# A股主线识别系统 V2.2.1 — MILESTONE C 断点恢复 / G4 FINAL

日期：2026-10-02（Asia/Shanghai）

G4 = FAIL。MILESTONE C = OPEN。正式生产开关及 MAINLINE_LIVE 保持 false。
G1/G2/G3 沿用 PASS；MILESTONE A/B 沿用 CLOSED。未进入下一阶段。

## 恢复结果

- 远端起点核验为 `33e615c39fec195a170b4dbfb932095c47de4824`。
- 从中断的工作区恢复了未提交的前端、状态读取、Workflow inputs、父子运行追踪、数据库 checkpoint 续跑修改。
- 已部署的函数与恢复源码逐文件一致，不重复部署：mainline-status v5、mainline-production-gateway v3、v43-daily-pipeline v19。
- 原 Sites v38 尚未包含这些前端修改。本轮构建并发布 v39；部署 succeeded。
- Sites 源码提交：`58d9b5274cf622a0476ed47b581fbcb816c732e8`。
- Sites 部署：`appgdep_6abf52fb627081918490130e6dce308e`。
- 正常登录边界保留，未使用登录绕过令牌。未登录访问页面与接口均返回 401。

## 验收证据

| 核验项 | 结果与边界 |
| --- | --- |
| 真实 snapshot / radar | 已部署 Edge API 返回 2026-09-30 的31个行业；S0=9、S1=14、S2=1、S3=2、S4=5、Frozen=1 |
| S1–S4 筛选 | 前端使用真实 rows 按 state 筛选；浏览器完整交互尚未认证 |
| sector detail / timeline / rule evidence | 轻工制造真实详情返回1条状态、10个日期、53条规则证据及真实 lifecycle |
| 质量与来源 | 已接入真实 quality/source 输出；NULL 保持为空 |
| latest success | 正式生产尚无成功记录，保持 null；simulation 日期独立展示，不冒充生产成功 |
| scheduler / Workflow input | business_date、run_type、pipeline_run_id 匹配；17:00 Asia/Shanghai（UTC cron 0 9 * * *）保持不变 |
| dispatch / business success | dispatch 仅记录运行中；数据库追踪与迟到回写的回滚测试通过；真实 GitHub dispatch 尚未验证 |
| 最新数据库 checkpoint | 下一交易日读取 seed=2026-09-30；9月30日重入使用9月29日 checkpoint；不默认回退到G3 seed |
| 兼容性与纯函数续跑 | 使用真实数据库 context 与既有真实结果的9项测试通过；版本、计数器、不完整checkpoint、未来历史等异常被拒绝 |
| 断点幂等 / lifecycle | 既有日期提交返回 idempotent；checkpoint 内容及 lifecycle 数量不变；未重复跑 simulation |
| backfill 安全 | 冲突 checksum 被拒绝，写库异常回滚；测试未留下持久化业务写入 |
| 三大赛道隔离 | 未修改 threeSectorJob 函数；父子追踪测试保留三大赛道结果，未改变筛选规则 |
| 前端发布 | 构建通过、Sites v39 succeeded；已部署函数接口通过；登录后的生产页面尚未完成完整交互验收 |

Node 合同检查18项通过，checkpoint续跑检查9项通过。数据库重入及父子追踪测试脚本保存在本目录。
追踪测试中的运行脚手架全部在异常子事务中回滚，不能算作真实生产成功。

## 本轮发现并修复的合同错误

恢复源码把主线步骤标为 running/partial，旧步骤表却只允许 succeeded/skipped/failed；同时 finished_at 不允许为空。
通过两条最小迁移修复：仅 mainline_job 可使用 running/partial 或暂时为空的完成时间，其他步骤保留原约束。
父子运行追踪、dispatch不算业务成功、迟到流水线收尾不覆盖业务结果、三大赛道结果保留均已在数据库回滚测试中通过。

继承的迁移：mainline_g4_repair、mainline_g4_runtime_trace。
本轮迁移：20261002065207_mainline_g4_step_status_contract、20261002065239_mainline_g4_step_finish_contract。

## 剩余 Blocking Issues（2项）

1. **每日生产派发凭据缺失。** 已部署函数明确返回 dispatch_credential_configured=false，缺少 MAINLINE_GITHUB_DISPATCH_TOKEN。因此不能认证 scheduler → Workflow → 数据库业务完成的真实链路。不得因代码合同测试通过而启用生产。
2. **登录后前端完整交互尚未认证。** 已部署与接口证据通过，但浏览器预览显示数据读取失败，直接检查预览API时浏览器返回 ERR_BLOCKED_BY_CLIENT。未绕过正常登录，也未把部署成功当作前端真实数据验收通过。

下一轮只配置并验证每日派发凭据、查明页面读取失败原因并完成正常登录下的前端验收；复用本目录证据和既有155条simulation快照。

## 范围保护

没有重跑G1/G2/G3、5日simulation、Provider/Universe/benchmark及状态规则验证。
没有变更状态规则、指标公式、profile、数据源；没有建立长期个股历史库；没有启用生产。
