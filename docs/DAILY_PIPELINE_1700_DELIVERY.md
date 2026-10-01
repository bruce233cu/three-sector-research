# Daily Pipeline 17:00 最小改造交付报告

2026-10-01。实施与静态验证完成；首次真实17:00运行待2026-10-02验证。没有手动触发采集、Provider POC、历史补数或Phase 2。

## 职责对比与最小方案

原Supabase cron每天UTC00:00（北京时间08:00）调用v43-daily-pipeline。ChatGPT完整研究日报也在08:00独立写生产表；另有工作日16:30收盘重算任务。

两日报链部分重复。Supabase负责固定来源采集、来源健康与既有数据库研究流程；ChatGPT独有逐条证据判断、存量机会复核、正反证据、3/7/14日回看及完整研究正文。没有简单删除ChatGPT任务，也没有将研究算法移植到Edge Function。

保留：现有Supabase cron、业务计算、冻结日报版本、日志表、每15分钟超时清理、代码备份。

修改：主cron至UTC09:00；显式Asia/Shanghai业务日期；外层模块隔离；最近成功日报读取；既有mainline状态读取RPC的静态阶段标签。

新增：薄调度策略模块、mainline禁用占位、既有metadata中的模块manifest、离线测试。

废弃角色：ChatGPT08:00独立生产写入。该任务改为17:10只读补充研究，保留全部原研究标准但不执行写入；输出仅在任务对话中，生产日报正文不会自动包含这些补充结论。

16:30任务保留原时间及核验/演算能力，改为只读核验和重算建议，禁止写日报、价格/模型/快照及主流水线日志。原因：与17:00流程原有价格/重算职责重叠，异步执行有延迟重叠风险。生产写入由主Pipeline负责；没有修改研究公式、概率、筛选或状态机。这两项任务职责修改是调度权限边界，不是业务算法迁移。

## 新每日结构

唯一正式生产触发器：v43-daily-research-pipeline，jobid=1，active=true，cron=0 9 * * *，cron时区GMT。命令保持既有Vault凭据读取，仅业务日期替换为北京时间日期。回查下一次计划：2026-10-02 17:00 Asia/Shanghai。jobid=3的15分钟清理未变。

现有v43-daily-pipeline部署版本17。依次执行mainline占位、three_sector_daily_job、publish_job；每模块独立捕获异常，没有跨模块事务，前一模块失败不会阻止后一模块调用。三大赛道既有完成RPC的局部事务不变。

mainline_job永远不调用Provider、不写行情或板块快照。已有日历明确非交易日→skipped/non_trading_day；未知→skipped/trading_calendar_unknown；明确交易日→skipped/pending_provider。均记录provider_enabled=false、G1_NOT_PASSED；未知日历同时记录provider_status=pending_provider。当前18条日历截至09-24，10-01回查为unknown，不补日历、不用星期几猜测。

三大赛道日终任务enabled，不因休市跳过信息采集；研究、公司价格、模型和业务RPC保持原逻辑。模块status可为succeeded/partial/failed；步骤表只有succeeded/skipped/failed，所以模块partial在步骤metadata保存。

单次来源请求最多20秒，mainline状态查询10秒，三大赛道模块90秒，publish10秒。没有新增自动业务重试；原源内最多3次重试保留。步骤日志写失败不会中断另一个模块；最终manifest标partial并保存日志错误。调度重复调用检查已有运行/已成功运行，拒绝重复启动；这不是数据库唯一锁，未宣称能阻止任意并发手动请求。

## 时间与manifest

业务日期以Asia/Shanghai计算；信息窗口为00:00～17:00，执行后新增信息标after_cutoff，历史回看标historical_lookback。raw_clues沿用published_at/discovered_at，metadata增加source_time、实际fetched_at、cutoff_at、information_window、pipeline_run_id。次日来源记录拒绝归入前日。缺source_time保留NULL及未验证标记；不修改证据筛选规则。

既有automation_runs/automation_run_steps保存pipeline_run_id、business_date、timezone、各job开始结束、状态、原因、error_summary、source_health_summary、latest_success_at。成功发布时额外保存成功冻结日报副本及report/version身份；仅板块层或既有研究汇总，未建个股明细资产。

## 最近成功结果与状态修复

Sites日报API按模块成功运行选择冻结日报版本，成功副本优先；新任务失败不能把新失败日报放到列表首位。兼容旧成功运行时，用daily_report_generation步骤对应version_number及生成时间范围校验冻结版本。无可证明成功结果时返回空，不伪造成功。

日报API只读原研究表及共享日志，不依赖mainline业务表。返回daily_pipeline，包含latest_success_at、latest_run_status、latest_run_date；保留历史日报布局，不改UI。

mainline-status线上原本调用get_mainline_status_v2；“Phase 2A / S1 POC”来自该RPC静态覆盖及旧POC读取。仅替换既有只读RPC实现：展示Phase 1F/G1未通过/pending_provider，不再读取Phase2A候选；近期样本只展示SUCCESS且未冻结的结果。未删除旧POC表或修改其业务数据。

## 测试与部署

18项离线测试通过：17:00映射、UTC跨日、日期合法性、success+skipped、两方向失败隔离、超时、非交易日、unknown、禁用Provider、时间标记、NULL、失败后最近成功结果、读取层不依赖mainline。

TypeScript语法检查通过；Sites构建通过；Site版本38部署成功。Sites源提交：6d145d475c2be1d208ec76724d9893376ebe8208（Sites托管源仓库，与GitHub仓库分开）。

数据库只读回查：cron=0 9 * * *、enabled=true；phase=Phase1F、gate=G1、Provider=false；成功旧日报仍可读取。匿名角色可读原日志/日报版本/日报；只读RPC权限保持原样，仅service_role调用。

没有用真实生产采集运行冒充测试。完整新manifest及日终新日报需下一次正式17:00执行后核对。独立失败验证为合成测试，没有故意制造生产失败。ChatGPT只读约束是自动任务提示词边界，不是数据库级专用只读凭据；不得宣称已实现凭据级隔离。

## GitHub与边界

仅提交mainline-phase1e，以远端9f77d7b4f2d2fc12fe8759d532747b7a16a665d0为父提交。main不变，不创建业务分支，不包含既有两个未提交Phase1E修改。

修改文件：

- supabase/functions/v43-daily-pipeline/index.ts
- supabase/functions/v43-daily-pipeline/policy.mjs
- supabase/daily_pipeline_schedule_1700.sql
- supabase/daily_pipeline_status_reader.sql
- app/api/research/route.ts
- lib/daily-result.ts
- tests/daily-pipeline.test.mjs
- tests/daily-result.test.mjs
- docs/DAILY_PIPELINE_1700_DELIVERY.md

Supabase核心业务schema：未修改表/字段/约束/权限；替换现有只读状态RPC函数实现。运行配置与优化日志发生写入。UI：未修改。非日报/非mainline研究逻辑：未修改。没有长期个股库、Provider启用或Phase2进入。

下一步启用mainline需要Phase1F真实Provider POC与G1验收、完整可靠交易日日历及独立生产写入验收，并明确授权；不能靠调度接入绕过。本轮交付后停止。
