# A股主线识别系统 V2.2.1 — G3 FINAL 断点续跑验收
验收日期：2026-10-02。Repository：bruce233cu/three-sector-research；Branch：mainline-phase1e。
验收代码：962a70d72c01bb2c9b5963bbf94dba6e2b213263。
本轮只读已有结果，未下载SWS/Sina，未重建Universe，未重跑900行，未修改Clarification或G1/G2。

## 最终结果
G1 = PASS（既有验收保持关闭）
G2 = PASS（既有验收保持关闭）
G3 = PASS
MILESTONE B = CLOSED
READY_FOR_DAILY_MAINLINE = true
production_mainline_job_enabled = false
MILESTONE C = NOT STARTED

## 可核查证据
Actions：https://github.com/bruce233cu/three-sector-research/actions/runs/36961627493
Artifact：11207954126，mainline-state-completion-acquisition。
ZIP SHA256：1af05b8228128a6895ce361fa13f82df71ab82fc007b55b1700baec1c9eae519，与GitHub artifact digest一致。
真实运行ID：20a64df1-656b-5be0-8753-10ccb604d0c3。
七份real JSON均已读取。Actions成功；112项引擎测试与6项benchmark测试通过。测试样例不计真实事件。
规则：mainline_v2.2.1_state_completion_v1。
Profile：industry_trend_v221_state_completion_v1。
参数hash：85c701a313b6a59529e7b8a7ea52af64d2e708011f56abf5d82d74580fd2384f。

## 真实窗口
2024-09-02—2025-06-30，197市场交易日，84日预热。
每天SW1行业31；每天有效横截面31；每日membership解析197次，每次全31行业，并由resolver再次按目标日解析检查。
S0真实seed，未植入S2/S3；状态6107行，均为real_historical_board。
deterministic rerun一致；独立对已有rows/cross_sections/events重算规范JSON摘要，匹配repeat_checksum：
46bf1f1fd0e45e68e7644c7bb18091bc9f1b570114c0c523802ecd3ccf8b017e。
Provider 5476请求、2失败：000416.SZ和002699.SZ，amount_unit_check_failed。失败未填0；全窗口benchmark最低覆盖98.299445%，高于95%。
PIT=effective_pit；knowledge_time_unverified=true；不宣称Level 2。membership来源TLS未验证，沿用既有证据边界。
临时个股输入1512029行；未建立长期个股库。真实窗口脚本无数据库写入，个股缓存为临时Parquet；本artifact保留板块级证据及抓取manifest。

## 真实状态事件
|转移|真实次数|一个真实例子|
|---|---:|---|
|S0→S1|499|公用事业，2024-09-02|
|S1→S2|59|电力设备，2024-09-04|
|S2→S3|65|电力设备，2024-09-09|
|S3→S2|12|计算机，2024-11-11|
|S3→S4|50|商贸零售，2024-10-10|
|S4→新lifecycle S1|44|商贸零售，2024-10-15|
另有S1→S0 481次。以上直接统计real_events.json，并与board_states中的transition逐项一致；synthetic fixture不混入。

## Clarification核验
真实运行链replay→completion_features→evaluate_rules→advance已采用新版本。
- RS5：5市场日OLS，至少4有效值；独立核对5983个完整可检窗口，零差异。
- RS10：pct_t > pct_t-1 > pct_t-2；6045次可检比较，零差异。
- breadth 3-of-4、WEAKEN 2-of-3、RETIRE 2-of-3：每项6107条规则输出，三值逻辑独立复核零差异。
- breadth自身median20：22072项可独立检查比较，零差异。
- S2→S3两日且确认后至少3市场日；S3→S4三日；S3→S2两日：真实全部转移检查符合连续计数。
- Freeze pause：真实21行冻结，保持状态；未补证时reset及恢复首日禁止转移，真实21次resume_reason记录（其中7次当日规则仍未知而再次冻结），全部无硬转移。
- Freeze resumed：代码链存在完整补证校验；真实窗口没有freeze_gap_evidence补证输入，没有resumed历史实例。本分支由明确标记synthetic的短缺口/校验/连续关系测试证明，不能报告为真实历史事件。
- E4：6107行诊断均为250市场日窗口、160有效值门槛；SQL percent_rank、NULL保留、0.90边界已核对源码与测试。没有宣称整个历史窗口均拥有250有效观测。
- lifecycle：真实50次S4关闭日期一致；44次重入更换ID且prior指向旧周期。
- 行业首日seed、前后状态连续性、Freeze期间无转移、恢复首日无转移、真实转移及规则门槛检查零违规。
审核结论：没有Blocking Issues。短缺口resumed无历史触发属于测试覆盖边界，不伪造补证或人为制造历史事件。

## Supabase审计
本次读取最新manifest，仍为旧G3 FAIL记录（ed453deb...），不是新窗口失败；当前Actions脚本本身不写数据库。
追加本次FINAL独立审计manifest，保留所有旧记录，引用真实artifact、运行ID、代码、参数和checksum。仅追加审计，不入库长期股票行情，不启用生产任务。

## 系统优化记录（普通中文）
为什么：前台断流导致用户无法确认后台已完成的真实验收，数据库仍展示旧失败结论。
改了什么：读取已完成窗口并独立核验，将最终通过结论追加为新审计记录；保留旧结果。
预期：可从代码、Actions、artifact、数据库审计定位同一次验收。
版本：V2.2.1；数据库：仅追加审计；筛选逻辑：未改；自动化：未改；旧数据：不覆盖。
验收：通过。未解决：严格知识时间PIT未证明，Freeze补证resumed没有真实触发实例；均明确标注。
重要决定：G1/G2关闭；B关闭；C仅列开工清单，不启动。

## MILESTONE C — DAILY MAINLINE + SITES 开工清单
1. 在现有版本建立每日板块作业：交易日识别→当日membership/Universe→按需窗口→指标→纯函数状态引擎→审计及板块结果。
2. 明确生产profile从audit_only迁移的版本与参数映射，不静默修改本次审计profile；不调参。
3. 持久化板块快照、checkpoint、规则判定和lifecycle；以日期/对象/分类/规则/profile保证幂等；补跑与生产隔离。
4. 建立Freeze质量报告、来源及checksum、补证流程；满足条件才resumed，否则reset，恢复首日仍禁止转移。
5. 日报展示市场日期、候选S1/确认S2/转弱S3/退潮S4、真实变化与原因；NULL和冻结直观显示。
6. Sites沿用/mainline与现有导航，清晰展示板块榜单、详情/时间轴、覆盖率、数据日期和来源；不冒充收益预测。
7. 验收至少连续5个真实市场日；检查断点续跑、重复运行幂等、Freeze、补跑、结果与页面一致。
8. 验收与上线批准后才启用生产调度；本轮未部署、未开启mainline_job。
