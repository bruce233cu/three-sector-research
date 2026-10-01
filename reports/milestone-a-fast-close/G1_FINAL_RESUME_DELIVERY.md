# A股主线识别系统 V2.2.1 — MILESTONE A FAST-CLOSE 断点续跑最终验收

**G1 = FAIL**  
**READY_FOR_PRODUCTION_ENABLEMENT = false**  
MILESTONE A 未关闭；未进入 Phase 2。

本次从 GitHub 和 Supabase 真实状态续跑，只核验 benchmark、source lineage 和最终数据 Gate。没有重跑已有研究、Provider测试、日历构建或source恢复。最终验收为证据审计，不冒充15样本计算重跑。

## 已落地工作

|事项|本轮核验结果|
|---|---|
|起始 HEAD|ce3c57d8b5a4f6864239683dd4eeac75b6a0bb28|
|政策/计算入口提交|942e71c2139b9de8ff34781af802c3ea24a98fb7|
|前轮交付与恢复记录提交|ce3c57d8b5a4f6864239683dd4eeac75b6a0bb28|
|V2.2.1 独立profile|数据库与代码均存在；原V2.2 profile保留|
|circ_mv延期|两个依赖指标 g1_required=false、NULL_ONLY、inactive_when_unavailable|
|SSE交易日历|2018-09-01～2026-12-31，3044行，2020开市日；日历source引用完整|
|旧source登记恢复|前轮恢复4条，9处引用，涉及6样本；本轮未重复恢复|
|空/悬空source引用|当前数组NULL元素0，悬空UUID 0；这不等于三类输入均齐全|
|15固定样本|5 SUCCESS、10 PARTIAL，全部mainline_v2.2.0|
|V2.2.1正式快照|0|
|前轮验收manifest|07209fc5-9cc4-46bf-a82a-5a2d5568886a，failed|

前轮实际修改文件：
- 942e71c：config/parameter_profile_industry_trend_v221_fast_close.json；docs/V2_2_1_CIRC_MV_DEFERRED_AMENDMENT.md；src/mainline/metrics/availability.py；scripts/mainline/build_fast_close_calendar.py；tests/mainline/test_v221_availability.py；calendar_manifest.json、sina_calendar.raw、trading_calendar.csv。
- ce3c57d：reports/milestone-a-fast-close/ 下的15_samples_baseline_audit.csv、FAST_CLOSE_DELIVERY.md、MILESTONE_B_START_CHECKLIST.md、artifact_checksums.json、baseline_db_read.json、g1_gate_result.json、source_registry_restoration.json、supabase_final_verification.json、verification.json。

## A — benchmark冻结口径

1. 冻结值仍为 ALL_A_EQUAL_WEIGHT。等权的数学核心：每个市场交易日对当日历史A股Universe中按冻结合同有效的证券收益率等权平均，B(t)=sum(r_i(t))/N_valid(t)。每只有效证券权重相同，不按市值、股本或成交额加权。Universe必须按当时日期成立，不得使用今天的全A名单倒灌。证券缺失仍降低coverage，不能默认为0。现有工程合同对停牌无有效行情规定从有效分母排除并降低coverage。
2. 当前可读冻结profile只写了基准名称，未提供完整可执行的benchmark合同。ST、新股纳入日、沪深北交所适用边界、公司行动收益口径等，不能仅凭英文名称擅自补成“原冻结规则”。SecurityRepository只提供上市/退市日期过滤，不能证明以上全部边界已落实。
3. 801003是申万A指，来源是申万指数行情API，不能因为名字含A股就当成全A等权。申万公开股价系列编制说明采用流通股本加权；该旧说明不能冒充2019～2025所有801003版本的完整方法文档。本轮未取得足以证明目标日期801003与冻结等权定义完全一致的方法证据，验收不得把二者视为等价。
4. 代码证据：src/mainline/poc/run_phase1d.py、run_phase1e.py直接get_sw_index("801003")，以pct_chg/100作为benchmark_returns，以该指数amount作为all_a_amount。phase1f_c.py继续采用同一路径。sector.py只消费外部benchmark_returns，没有构造全A等权序列；availability.py只处理延期指标，不校验输入基准身份。
5. 直接受影响：benchmark_return、rs_5/10/20。同一路径的成交额Universe另未认证，影响turnover_share、turnover_intensity。后续RS排名、WIN或状态引擎若使用这些输入同样受影响，但本轮未开发这些功能。sector_return与广度不因基准身份直接改变。
6. 当前没有已验收正确实现。最小修复必须让输入满足原ALL_A_EQUAL_WEIGHT合同，并独立证明历史全A成交额分母；仅改名、贴标或改profile无法修复。数据库security_master与stock_daily均为0行，这不意味着必须建立全A长期库，但现有临时证据也没有提供完整全A基准输入。需要历史Universe与其窗口临时数据或可靠的同口径基准来源。当前任务禁止Provider大规模测试，且缺少这些已验证输入，不能在本次凭空完成真实15样本修复。未修改冻结定义、计算器或生产链路。

来源：
- https://www.swsresearch.com/institute_sw/allIndex/releasedIndex （801003名称）
- https://finance.sina.com.cn/roll/20031017/0612478149.shtml （原申银万国编制说明公开转载，历史方法证据；不代表目标日期完整新方法）

## B — source lineage最终核验

以下分开统计登记引用与原文可复核性，不把元数据恢复当成原始数据恢复。

|口径|数量|含义|
|---|---:|---|
|样本已有引用UUID均可解析|15/15|悬空引用已归零|
|前轮恢复影响样本|6/15|4个source记录、9处引用|
|成员+非空行情+benchmark登记链齐全，且manifest存在|5/15|仅登记结构完整，仍未认证benchmark口径及raw payload|
|只剩benchmark引用|4/15|3条旧SUCCESS、1条旧PARTIAL|
|其余引用齐全但行情source为空|6/15|row_count=0，不能算有效行情链|
|完整raw payload/checksum回放本轮获认证|0/15|不是永久丢失结论；本轮没有可认证的全链重放|
|全部样本run_manifest可解析|15/15|其中共享旧manifest的source_snapshot_ids仍为空数组|

四个只剩benchmark的样本：
2019-06-28/801120、2021-12-31/801780、2025-06-30/801780、2025-06-30/801890。
按cache_checksum反查source_snapshots，前3个样本成员和行情checksum均无登记匹配；第4个成员checksum可找到0652adf2-42d1-50cb-a308-6b559c34068b，但行情checksum无匹配。7个输入checksum仍无法在当前登记中解析。原始checksum字符串不能替代source记录或原文，未捏造UUID、来源时间或新source。

已只读下载既有Phase1F-D1.1 workflow artifact：
run=36857658882，artifact=11161435899，
SHA256=afcdbcf3297ed434fe8d2b730c6751f1d09ee6642b1b5944ff2c16f68a2b7825，实际ZIP哈希匹配。
它只有3个样本的指标/来源manifest/校验声明，无Sina行情原始rows。可佐证之前已完成POC，不足以恢复15条旧快照原始输入；未重新执行POC。

结论：悬空引用修复本身不再阻塞；缺少成员/有效行情链、原文及可重放校验仍真正阻塞G1。对未能追溯的输入保留失败，不伪造source，不把缺失引用清除后的空数组认作完整链。

## C — G1 DATA GATE — V2.2.1 FINAL

最终证据查询已在真实数据库执行；SQL中FAIL是以上代码/来源审计的明确裁决，不是SQL重新计算行情。明细见g1_final_resume_result.json与g1_final_resume_audit.sql。

最多三项Blocking Issues：

1. **FROZEN_BENCHMARK_AND_ALL_A_AMOUNT_NOT_IMPLEMENTED_OR_CERTIFIED**：801003路径未满足冻结全A等权及全A成交额合同；相关核心指标不能认证。
2. **SOURCE_LINEAGE_RAW_REPLAY_INCOMPLETE**：4条快照缺输入引用，6条行情输入为空，旧raw缓存未完成可重放认证；恢复登记不等于恢复原文。
3. **V221_15_SAMPLE_ACCEPTANCE_ABSENT**：正式新版快照0/15；旧10条仍PARTIAL/Freeze，3样本POC不足以证明15样本新版coverage、NULL/Freeze、PIT和一致性。

circ_mv不在Blocking Issues内。没有新增Phase1研究，没有购买、Token请求、Provider测试、日历重建、source恢复、Sites/Daily Pipeline/三大赛道修改。只新增mainline审计manifest和本报告文件；旧结果/旧manifest均保留。

新验收run_id=ba5a33ff-aae7-4052-b430-b8af9b8f2872；parent_run_id=07209fc5-9cc4-46bf-a82a-5a2d5568886a；status=failed。
规则mainline_v2.2.1；profile=industry_trend_v2_2_1_fast_close。
验收输入代码SHA=ce3c57d8b5a4f6864239683dd4eeac75b6a0bb28；审计时间UTC=2026-10-01 15:02:41.360856+00。
本次依用户限定只在mainline留痕，没有写共享三大赛道优化表。

G1 = FAIL；READY_FOR_PRODUCTION_ENABLEMENT = false。
MILESTONE A保持未关闭。按用户FAIL停止条件，本轮到此结束，不输出已准予开工的MILESTONE B清单，不启动Phase2。
