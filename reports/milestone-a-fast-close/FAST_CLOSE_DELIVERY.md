# A股主线识别系统 V2.2.1 — MILESTONE A FAST-CLOSE / G1 CLOSED 交付包

验收状态：**G1 = FAIL，G1尚未关闭。**
READY_FOR_PRODUCTION_ENABLEMENT = false。
circ_mv已解除当前G1硬阻塞；剩余阻塞属于核心benchmark / 全A成交额分母口径，不能由本次市值最小修订豁免。

## 1. V2.2.1修订内容

新增正式最小修订说明、独立profile和可选计算入口，原V2.2文件、公式、profile和历史snapshot保留。
rule_version = mainline_v2.2.1
parameter_profile = industry_trend_v2_2_1_fast_close
metric_availability_version = mainline_metric_availability_v2.2.1_deferred_circ_mv
三个标识同时输出；已有数据库使用rule_version/profile_id原字段与decision_reason JSON记录可用性版本，无schema改动。

## 2. 与V2.2差异

仅延后circ_mv及两个依赖指标的G1硬要求与状态规则参与资格。未修改指标公式、benchmark定义、来源级质量要求、核心coverage阈值或旧版本判断。
原profile名称虽然含v2_2_1，但rule_version实际为mainline_v2.2.0；新profile用独立ID，避免混淆。
旧profile和15条旧snapshot逐条核验未改变。

## 3. circ_mv deferred规则

circ_mv_status = deferred。
turnover_cap_deviation / top3_return_contribution状态均为deferred_due_to_unproven_historical_circ_mv，角色optional_enhancement / deferred_metric。
新版入口即使收到市值输入，也保持两项NULL；对应coverage为0并明确标注deferred。
不填0，不用total_mv、自由流通市值、当前值或成交额代理。
两项不参与当前G1硬条件，不因NULL触发Freeze。S0–S4规则要求inactive_when_unavailable：不参与硬门槛、增强项计数或缺失导致的状态降级；其他阈值不降。
恢复必须新建rule_version、parameter_profile和metric availability version，不回写旧历史判断。

## 4. 当前可参与核心计算的指标

sector_return、benchmark_return、rs_5、rs_10、rs_20、turnover_share、turnover_intensity、up_ratio、above_ma20、above_ma60、new_high_60、top3_turnover_share。
这里指新版计算合同允许；不是本轮15样本已全部重新验证合格。benchmark与全A成交额口径未确认前，相关结果不得认证为正式引擎输入。
当前仓库无已实现S0–S4状态机，15条历史snapshot的hard_status为空；本轮未开发Phase 2。

## 5. 当前不参与的指标

turnover_cap_deviation = NULL。
top3_return_contribution = NULL。
原profile没有两字段名直接绑定S1–S4，但保留confirm/retire增强项数量阈值；不能据此宣称未实现的全部增强项规则已验收。新版本明确可用性政策供后续引擎执行。

## 6. 交易日历状态

已真实补齐mainline.trading_calendar的SSE市场参考日历：2018-09-01至2026-12-31，3044个自然日、2020个开市日；2019–2026部分有1941个开市日。
额外2018范围用于2019历史窗口缓冲。使用Sina真实编码交易日序列，未按工作日猜开市；2026全年与上交所正式节假日公告逐日核对，差异0。
2020-01-31为休市，2020-02-03为开市；既有18条日历开闭市标识与新源无冲突。
数据库3044行与artifact逐行相同，包含正确pretrade_date。区间最初几天前一交易日为2018-08-31，不因落在本次写入范围之外而置空。
目前只声明SSE参考日历，不冒充独立验证过的SZSE/BSE日历。发布的未来覆盖至2026年末；2027未知日期不能当成休市，应先刷新来源。
未修改17:00 Daily Pipeline架构，未启用mainline_job。

## 7. PARTIAL处理结果

两次读取真实数据库：SUCCESS=5、PARTIAL=10、FAIL=0，15条均为旧版结果。
由于检测到独立核心口径冲突，本轮停止在新版回填前：PARTIAL重跑0，新V2.2.1 snapshot写入0。
未把旧成功标签复制成新版SUCCESS，未用缺失指标豁免来放行不符合冻结benchmark的计算。
这不是15样本收口成功，也没有宣称Phase 1已结束。

## 8. 15样本真实状态总表

以下为当前数据库旧版基线，**不是本轮V2.2.1重算结果**。

|日期|行业|旧状态|成员|旧有效成员|旧return coverage|旧Freeze|
|---|---|---|---:|---:|---:|---|
|2019-06-28|801080|PARTIAL|189|12|6.35%|是|
|2019-06-28|801120|SUCCESS|33|32|96.97%|否|
|2019-06-28|801790|PARTIAL|50|0|0%|是|
|2020-06-30|801050|PARTIAL|118|0|0%|是|
|2020-06-30|801120|PARTIAL|38|0|0%|是|
|2020-06-30|801790|SUCCESS|53|40|73.58%|否|
|2021-12-31|801080|PARTIAL|361|0|0%|是|
|2021-12-31|801780|SUCCESS|42|41|97.62%|否|
|2021-12-31|801890|PARTIAL|472|43|9.11%|是|
|2023-06-30|801050|PARTIAL|141|39|27.66%|是|
|2023-06-30|801120|SUCCESS|125|99|79.20%|否|
|2023-06-30|801890|PARTIAL|550|0|0%|是|
|2025-06-30|801080|PARTIAL|491|0|0%|是|
|2025-06-30|801780|SUCCESS|42|42|100%|否|
|2025-06-30|801890|PARTIAL|600|226|37.67%|是|

## 9. coverage

15_samples_baseline_audit.csv逐样本保留实际数据库指标、MA20/MA60/NEW_HIGH60 coverage、metric_coverage_json、Freeze、run/source IDs、旧规则/profile、PIT及新版本身份。
旧数据未单独记录的OHLCV/amount coverage标为NOT_SEPARATELY_RECORDED，不拿return coverage代替。
旧样本存在市值相关历史值时原样保留在old_*列，不删改；新版本列明确写NULL政策与未重算状态，不能把政策当作新计算结果。
sector_return >=70%、breadth >=70%、RS窗口>=90%及既有来源级阈值全部保留；无coverage门槛降低。

## 10. Freeze

测试证明circ_mv deferred本身不触发Freeze；核心return/breadth不足仍Freeze，指标仍NULL。
当前G1审计manifest：critical_data_ok=false、stage_frozen=true。
freeze_reason = CORE_BENCHMARK_AND_ALL_A_AMOUNT_SEMANTICS_UNPROVEN。
这是验收运行冻结，不是新生成15条日级Freeze判断。原15条snapshot的Freeze值未改变。

## 11. PIT

新版政策不使用当前股本填历史、不改历史成员、不引入未来值。
日历声明effective_pit、knowledge_time_unverified=true；未冒充strict knowledge-time PIT。
本轮未进行15样本新版回放，不能把既有PIT标记升级为本轮全量复验结论。

## 12. repeatability

新策略回归测试2/2通过：旧版隔离、deferred NULL、核心Freeze和同输入确定性。
测试用合成fixture，不是实际行情Provider重跑。
日历两次真实HTTP获取原始字节相同；数据库3044行与解码artifact完全一致。
15样本新版真实回放一致性：未执行，因核心口径冲突停止；不宣称通过。

## 13. source / manifest / checksum

日历source_snapshot_id = 243f49a9-32cb-4b72-8205-d91b03498625。
验收run_id = 07209fc5-9cc4-46bf-a82a-5a2d5568886a，数据库status=failed。
日历原始SHA256 = d5112e08726ecc435092fb63547a34fc514b071b1a4a84f9e2c29fb9023726a9。
日历CSV SHA256 = 1ccb62c28b7f66df11ec117ff7ebd11e2a3b0636ccbda132995af74cf35180b6。
parameter_hash = 4ced6ee56df791bdbb893634cfbcb64de104a155466af30ca8ecdbca0681722d。
发现旧snapshot有9处悬空source引用，对应4个缺失source ID；已从起始SHA下不可变的reports/phase1d/final-v2/source_snapshots.json恢复4条登记，悬空引用降为0。
恢复仅是元数据与原声明checksum，不是原始payload重验；metadata明确raw_payload_reverified=false，available_at保持NULL，不推断当时knowledge-time可得。
完整manifest与写后检查见supabase_final_verification.json；文件SHA256见artifact_checksums.json。

## 14. technical debt

- circ_mv及两个增强指标延后，未来按新版本恢复。
- BJ、停牌/退市、代码变更边缘证据仍需分类，不得伪造或补当前值。
- 2027交易日历待官方发布后刷新；未知区间必须阻止计算。
- 旧原始缓存payload可用性及checksum需在新版回放时确认；本轮登记修复不替代原始核验。

## 15. G1最终判定与Blocking Issues

G1 DATA GATE — V2.2.1 = FAIL。
只有一个根阻塞项：CORE_BENCHMARK_AND_ALL_A_AMOUNT_SEMANTICS_UNPROVEN。

为什么阻塞：冻结profile指定ALL_A_EQUAL_WEIGHT，而现有POC使用801003申万A指；缺乏两者等价的编制口径证明。其成交额也未证明包含正确历史全A Universe，不能直接认证为turnover_share/intensity分母。这会系统性影响RS与成交额份额，而非少量边缘证券债务。
最小修复：提供现有801003与冻结基准/全A成交额的正式等价性证据；若不等价，依原冻结口径取得基准和全A成交额。然后继续现有10个PARTIAL回放、新版15样本coverage/Freeze/source/checksum/一致性验收，无需恢复circ_mv硬门槛或新开D1.x。
是否需用户操作：若保留原口径，不要求Token/购买；若希望改用801003，需要另行明确授权基准口径版本修订，当前只授权circ_mv最小修订，不能代替该授权。

未完成的15样本新版回放是此阻塞项的后续工作，不是独立凭空新增的优化要求。

## 16. READY_FOR_PRODUCTION_ENABLEMENT

false。mainline_job未启用；未进入Phase 2，不能宣称G1 CLOSED。

## 17. GitHub

Repository: bruce233cu/three-sector-research。
Branch: mainline-phase1e。
起始SHA: 0336635ca36657e7c3420a6b30b0c55bf24a87be。
代码/政策/日历commit: 942e71c2139b9de8ff34781af802c3ea24a98fb7。
最终审计commit为本报告所在提交；完整最终SHA在交付响应和下载版本中列出。
提交均为fast-forward；未修改main、未force push、未重写历史。提交使用skip ci，未手动触发Workflow；无新增Provider测试Workflow run。
修改文件：新增config/parameter_profile_industry_trend_v221_fast_close.json、docs/V2_2_1_CIRC_MV_DEFERRED_AMENDMENT.md、src/mainline/metrics/availability.py、scripts/mainline/build_fast_close_calendar.py、tests/mainline/test_v221_availability.py；新增reports/milestone-a-fast-close目录下审计与calendar artifacts。旧业务文件未改。

## 18. Supabase变化与边界

仅现有mainline结构DML：新增1条独立parameter_profile；日历由18条扩至3044条；新增1条日历source、恢复4条旧source登记；新增1条failed G1审计manifest。
daily_mainline_snapshot仍15条；新V2.2.1 snapshot=0；phase1d_sample_runs状态未改。
schema未改；未写三大赛道业务表；未启用生产mainline_job；未修改Daily Pipeline、Sites UI、Sina OHLCV链。
未研究Tushare/JoinQuant、未索取Token、未购买/充值、未调用付费API。
仓库AGENTS要求共享优化表记录；本轮用户明确禁止影响非mainline模块，因此留痕放在mainline审计manifest与本交付包，未写共享业务表。

## 19. MILESTONE B开工清单

仅准备清单，当前G1未通过，不开始Phase 2代码开发。
G1解决后依次做：metrics合同与统计窗口、rules、S0–S4 state machine、consecutive days、debounce/minimum dwell、lifecycle、freeze propagation、unit tests、固定版本及来源的deterministic rerun。
deferred指标不参与硬状态/增强项计数；生产启用另行执行。

最终边界：是否购买/充值/使用用户Token/调用付费API/修改Sina主链/启用mainline_job/改核心schema/修改Daily Pipeline/影响三大赛道/进入Phase 2：全部否。
