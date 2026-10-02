# A股主线识别系统 V2.2.1 — MILESTONE C G4 FINAL PRODUCTION CLOSE 交付包

G4 = PASS；MILESTONE C = CLOSED。现有主线每日任务已启用，等待首个自然交易日正式生产。当前历史数据仍为 SIMULATION，不是 LIVE。

## 交付字段

| 项目 | 实际结果 |
|---|---|
| 起始 SHA | 388029858e6aa01e4badb16b85dced375661a5a8；已核对远端 HEAD |
| 最终运行代码 SHA | 8d9537b7737b1e71f234f2f415e60fc2ee296a30；此后交付记录提交只保存证据 |
| 代码修改 | 是：现有验证类型、派发复用、回调结算、数字表示保留、partial/latest success 语义和约束兼容；核心指标、状态规则、Universe、Provider、三大赛道业务未改 |
| Token 验证 | PASS：现有 Edge Function 内部使用 Secret，GitHub dispatch 接受；没有读取或输出明文 |
| GitHub dispatch | PASS；GitHub HTTP 204 后 Daily Pipeline 返回 DISPATCHED，业务完成仍待回调 |
| 最终 Workflow run ID | 36990602935 |
| pipeline_run_id | 69ba9ab1-5b05-44f3-aab2-5d3d325fe872 |
| business_date | 2026-09-30，真实已完成历史交易日 |
| run_type | production_validation |
| Workflow 状态 | completed / success |
| business completion | partial；31 个行业完成保存验收，原有 1 个 Frozen 保留；父级和业务子运行均正确标记 partial |
| checkpoint source | database；没有 G3 bootstrap |
| checkpoint date | 2026-09-29 |
| checkpoint version | taxonomy SW2021；rule mainline_v2.2.1_state_completion_v1；profile industry_trend_v221_state_completion_v1；metric availability mainline_metric_availability_v2.2.1_deferred_circ_mv |
| DB 续跑 | PASS；31 个兼容 checkpoint，306 个历史交易日；来源 run_id 21a8f577-5de8-46d4-8e1a-5b30e7fd0a5a |
| 幂等 | PASS；同日重复 Workflow 和最终 Workflow 内两次 commit；业务 checksum 完全一致 |
| lifecycle | PASS；1351 条且整表校验不变，没有重复或累计污染 |
| latest success | 正式 production 成功日仍为 null；validation、失败和 partial 不提升正式最近成功日 |
| Sites | /mainline 读取真实 2026-09-30 snapshot；SIMULATION；S0=9、S1=14、S2=1、S3=2、S4=5、Frozen=1 |
| mainline_job.is_scheduled | true |
| three_sector_daily_job | 业务函数逐字不变，独立异常/写入；本次隔离验证跳过该模块。2026-10-02 17:00 既有正式模块状态 failed，原因 p0_failed_checks=1；最近成功保留 2026-10-01，本轮不修复该独立业务问题 |
| Edge Function | v43-daily-pipeline v22；mainline-production-gateway v5；mainline-status v6，均 ACTIVE |
| Sites 版本 | v40；既有部署 succeeded；前端和 API 源码与部署版本匹配，本轮无需重新部署 |
| G4 | PASS |
| PRODUCTION_MAINLINE_ENABLED | true |
| MAINLINE_LIVE | READY_WAITING_FIRST_PRODUCTION_RUN |
| MANUAL_UI_CHECK_REQUIRED | S1–S4 标签切换、行业详情抽屉、状态时间轴、指标历史；正常登录后人工检查，未绕过登录 |
| technical debt | 首次正式自然交易日 production 尚待运行；保留既有 knowledge_time_unverified 与 circ_mv deferred 约定；验证复用真实历史证据，未重新抓取全量 Provider 数据 |

## G4 FRONTEND + PRODUCTION TRACEABILITY GATE — FINAL

- [x] GitHub dispatch 凭据可用
- [x] Daily Pipeline 可触发 mainline Workflow
- [x] Workflow 真实启动
- [x] pipeline_run_id 贯穿
- [x] dispatch/business success 语义正确
- [x] 最新 DB checkpoint 被真实读取
- [x] checkpoint 版本兼容检查通过
- [x] production-style continuation 通过
- [x] rerun 幂等通过
- [x] lifecycle 无重复
- [x] backfill 安全
- [x] latest success 语义正确
- [x] simulation 与 production 区分
- [x] /mainline 真实 snapshot
- [x] S1–S4：API 和已部署源码验证通过，点击交互保留人工检查
- [x] sector detail：四类状态详情均有真实记录
- [x] timeline：每个受检行业均返回 10 个已保存日期
- [x] rule evidence：每个受检行业均返回 53 条规则
- [x] data quality：真实质量与四个来源记录可读，Frozen 如实保留
- [x] Sites 部署有效：v40 succeeded；无登录会话 HTTP401，未绕过
- [x] three-sector 逻辑未改
- [x] 17:00 调度未改

## 运行与恢复证据

最终工作流：https://github.com/bruce233cu/three-sector-research/actions/runs/36990602935

真实历史连续性：从 2026-09-29 的数据库 checkpoint 进入现有 evolve 引擎，对真实 9月30日行业指标执行正式规则和状态演进，再进入同一个 mainline_commit_day 原子保存函数。真实 membership 来自既有工作流 36970118460 的证据文件，逐行业重算 checksum，并核对数据库业务内容。没有重跑五日 simulation、重建 Universe 或默认读取 2025-06-30 G3 seed。

最终两次保存 manifest：
- 60d1ec0d-8a9f-4bd0-8968-6930c05c7101；业务子运行 c589a9df-a980-44c9-8c55-50ab07921334
- 7550ba84-cbfd-43fa-9da7-91b17b862b75；业务子运行 bb37a4d2-a823-4de5-967a-3e5af7102081

两次均 idempotent / business partial：
`270a7373b1d4e854e7e4ccc7f1d774ecf85f8783d975636c4243da8426a52f05`

全库业务记录数量前后相同：snapshot 385，checkpoint 310，lifecycle 1351，rule evidence 16430。checkpoint 整表校验为 bc5fe2dce6503acf509c7ea64ef0a3bd；lifecycle 整表校验为 eadf1a8424d5330b42e1b473e46ddfff。状态天数和连续计数位于 checkpoint 中，整体校验相同证明没有重复累计。幂等验证保留原 snapshot run_id 4ce52a35-d7a8-4a81-af5e-29e47b5f8c6d，通过日期、profile、checksum 和 manifest 关联，不为制造关联重写业务记录。

真实失败恢复使用同一个父级任务：36988916142 因数字表示校验停止；修正后 36989296127 成功；36989524355 同日复跑成功；36989952264 完成 SHA 追踪复查；36990266271 暴露既有步骤状态约束冲突，事务完整回滚；修复后 36990602935 成功。失败记录和 Git 历史保留。原子保存步骤使用合法 succeeded 表示保存成功，metadata 及业务运行/父级使用 partial 表示业务部分完成。

隔离 SQL 验收全部在事务回滚中完成，证明故障后的写入不泄漏、历史日期不选择未来 checkpoint、running/failed/partial 回调真实、迟到 dispatch 不覆盖完成回调、partial 不提升正式 latest success。验收 SQL 随包保存。

调度仍只有原有日终入口：cron job 1，v43-daily-research-pipeline，0 9 * * * UTC = 每天 17:00 Asia/Shanghai。既有每15分钟 stale cleanup 保留，不是第二个生产 scheduler。数据库日历确认下一自然交易日是 2026-10-08；调度每天触发，非交易日跳过。

自动检查：Daily Pipeline 16 项、生产成功边界 4 项、真实 DB 续跑/兼容性 9 项、前端入口 3 项通过；另有真实 Workflow、原子幂等提交与回滚式 SQL 验收。未重跑 G1/G2/G3 Gate。

## 正式关闭状态

G1 = PASS；G2 = PASS；G3 = PASS；G4 = PASS。
MILESTONE A = CLOSED；MILESTONE B = CLOSED；MILESTONE C = CLOSED。
PRODUCTION_MAINLINE_ENABLED = true。
MAINLINE_LIVE = READY_WAITING_FIRST_PRODUCTION_RUN。
Blocking Issues = 0。

## MILESTONE D — HISTORICAL VALIDATION / BLIND TEST 开工清单

- [ ] 冻结 V2.2.1 参数、规则、taxonomy、指标可用性版本及运行代码基线。
- [ ] 预先划定历史验证区间和完全未用于调整规则的盲测区间。
- [ ] 明确观察日、信息可得时间、标签判定日、缺失与 Freeze 处理，禁止未来信息泄漏。
- [ ] 预先登记评价指标、样本分组、比较基线和通过标准。
- [ ] 使用隔离 run_type / manifest / 报告，不覆盖正式 latest success、checkpoint 或 lifecycle。
- [ ] 结果保留数据来源、参数与代码版本，能复算；盲测结果出齐前不改规则。
- [ ] 开始前确认范围与交付要求。

MILESTONE D 本轮未启动。
