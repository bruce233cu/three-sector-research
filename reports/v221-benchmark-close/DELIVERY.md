# A股主线识别系统 V2.2.1 — MILESTONE A FINAL CLOSE / G1 FINAL 交付包

**G1 = PASS**  
**READY_FOR_PRODUCTION_ENABLEMENT = true**  
**MILESTONE A = CLOSED**

验收范围为固定5日期×3行业的15条新版审计样本。未启用生产任务，未进入Phase 2。

## ALL_A_EQUAL_WEIGHT 与历史 Universe

目标交易日实际有效上市A股中，使用当天和前一市场交易日的有效close计算单股收益，再对有效收益做简单等权平均。包含当时有效、后来退市的A股；排除未来上市、当时已退市及非A证券。缺失价格不补0、不向前借价；上市首日没有前一上市交易日价格则视为缺失。零成交额停牌记录保持不可用。

benchmark_coverage = valid_return_count / historical_universe_count。覆盖率≥95%才输出收益，否则NULL/Freeze；RS窗口90%、板块内部70%保持不变。全A成交额为同一历史Universe当日有效amount之和，独立记录amount coverage。

轻量解析器以交易所上市/终止上市事件及历史代码区间解析历史集合；没有用当前存续名单直接回填历史。复用既有SSE/SZSE终止上市及上市资料，补齐官方SZSE全部146页（2904条）以及必要BJ代码/退出事件。BJ上市时间不早于2021-11-15，920代码变更按实际生效日期处理。仅5个固定日期及其指标所需300个市场日窗口，没有逐日全历史回填。

| 日期 | Universe | SH | SZ | BJ | 排除未来上市 | 排除已退市 | 包含后来退市 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2019-06-28 | 3631 | 1471 | 2160 | 0 | 2177 | 101 | 227 |
| 2020-06-30 | 3876 | 1637 | 2239 | 0 | 1921 | 112 | 219 |
| 2021-12-31 | 4684 | 2031 | 2571 | 82 | 1080 | 145 | 192 |
| 2023-06-30 | 5222 | 2220 | 2798 | 204 | 479 | 208 | 130 |
| 2025-06-30 | 5419 | 2283 | 2868 | 268 | 188 | 302 | 36 |

样本核验包括688001上市前排除、833994在2021有效而2022退出、835305/839680历史代码与920新代码生效边界。官方翰博退出PDF已解析核验，checksum列于source元数据。CDR九号公司不作为A股，故与包含CDR的沪市总数相差1。

## 801003 与新版实现

801003为申万A指指数点位序列；指数点位收益不是按本项目历史Universe直接计算的单股收益算术平均，其当前完整成分/权重方法版本没有形成等价性证据。不得宣称等价。新版benchmark、RS5/10/20、turnover_share、turnover_intensity全部使用真实全A计算输入。旧801003数据保留。

实现见 `src/mainline/metrics/historical_universe.py`、`benchmark.py`、`scripts/mainline/v221_benchmark_resume.py`；已通过板块输入直接复用，1558支既有行情缓存不重抓，额外4064支仅用于本次临时benchmark窗口。

| 日期 | 有效收益/Universe | benchmark coverage | 等权收益 | amount coverage | 全A成交额（元） |
|---|---:|---:|---:|---:|
| 2019-06-28 | 3607/3631 | 99.3390% | -1.441568% | 99.4767% | 415,313,570,467 |
| 2020-06-30 | 3830/3876 | 98.8132% | 1.468027% | 98.9422% | 746,502,408,890 |
| 2021-12-31 | 4636/4684 | 98.9752% | 0.623648% | 99.0393% | 1,062,451,240,209 |
| 2023-06-30 | 5168/5222 | 98.9659% | 1.094911% | 99.0808% | 919,968,338,346 |
| 2025-06-30 | 5371/5419 | 99.1142% | 1.311822% | 99.1880% | 1,513,654,041,880 |

## 15条正式新增结果

新增profile：`industry_trend_v2_2_1_benchmark_close`；rule_version：`mainline_v2.2.1`。原V2.2和旧V2.2.1事实不覆盖。完整字段、来源引用、coverage JSON见 `snapshots.json`。

**15 SUCCESS / 0 PARTIAL / 0 FAIL；15 critical_data_ok=true；0 Freeze。**

| 日期 | 行业代码 | 成员/有效 | sector return | benchmark | RS5 | RS10 | RS20 | turnover share | intensity | OHLCV/amount coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019-06-28 | 801080 | 189/187 | -1.8610% | -1.4416% | 0.4376% | 0.7064% | -0.0331% | 7.2905% | 1.2516 | 98.94%/98.94% |
| 2019-06-28 | 801120 | 33/32 | -0.5671% | -1.4416% | 1.8823% | 1.5558% | 0.7875% | 0.8614% | 1.0384 | 96.97%/96.97% |
| 2019-06-28 | 801790 | 50/48 | -0.5254% | -1.4416% | 0.0470% | 4.7629% | 8.0545% | 6.5650% | 1.1623 | 96.00%/96.00% |
| 2020-06-30 | 801050 | 118/116 | 1.1265% | 1.4680% | -1.1493% | -2.1850% | -4.5980% | 2.5459% | 0.8197 | 98.31%/98.31% |
| 2020-06-30 | 801120 | 38/38 | 2.4530% | 1.4680% | 1.7750% | 2.7104% | -0.8836% | 1.0678% | 0.8228 | 100.00%/100.00% |
| 2020-06-30 | 801790 | 53/52 | 2.4301% | 1.4680% | 0.3406% | 2.6983% | 3.2031% | 5.5588% | 1.5118 | 98.11%/98.11% |
| 2021-12-31 | 801080 | 361/353 | 0.0681% | 0.6236% | -0.8236% | -0.7778% | -4.9223% | 8.0355% | 0.8068 | 97.78%/97.78% |
| 2021-12-31 | 801780 | 42/41 | 0.1161% | 0.6236% | -2.9799% | -1.9230% | -3.1681% | 1.1946% | 0.9528 | 97.62%/97.62% |
| 2021-12-31 | 801890 | 472/458 | 0.5841% | 0.6236% | 1.1388% | -0.7424% | -1.9280% | 5.7048% | 1.0163 | 97.03%/97.03% |
| 2023-06-30 | 801050 | 141/137 | 1.4697% | 1.0949% | 1.6192% | 0.0711% | -0.3882% | 3.2111% | 1.0897 | 97.16%/97.16% |
| 2023-06-30 | 801120 | 125/121 | 0.4796% | 1.0949% | -2.3153% | -5.6139% | -1.3321% | 2.3701% | 0.9126 | 96.80%/96.80% |
| 2023-06-30 | 801890 | 550/531 | 0.8222% | 1.0949% | 1.9211% | 6.7347% | 4.9285% | 9.1580% | 1.7028 | 96.55%/96.55% |
| 2025-06-30 | 801080 | 491/480 | 1.5827% | 1.3118% | 0.8764% | 4.6903% | 4.6124% | 13.6108% | 1.1768 | 97.76%/97.76% |
| 2025-06-30 | 801780 | 42/42 | -0.7226% | 1.3118% | -6.3685% | -2.2204% | -1.8655% | 2.1755% | 1.0021 | 100.00%/100.00% |
| 2025-06-30 | 801890 | 600/582 | 1.5937% | 1.3118% | 0.7524% | 0.0798% | -1.1139% | 6.5511% | 0.8205 | 97.00%/97.00% |

RS5/10/20窗口有效率全部100%。板块sector_return、up_ratio、MA20、MA60、NEW_HIGH60、top3_turnover_share与前轮已通过结果15/15逐项一致。两个circ_mv指标仍NULL，并明确标记deferred_due_to_unproven_historical_circ_mv。

## Freeze / PIT / repeatability

10项测试通过：95%边界可用、94%不可用；未知Universe拒绝；NULL不填0；缺少精确前市场日价格不借旧价；重复membership拒绝；未来上市/已退市/非A排除；BJ成立与历史代码边界；不足benchmark不产生假RS并Freeze；circ_mv deferred本身不Freeze。

同输入双计算15/15核心结果、coverage、Freeze、benchmark、source引用与parameter hash一致，计算checksum和复算checksum逐条相等，见checks.json。新snapshot的repeat_checksum引用本轮校验，原轮checksum保留于parent_repeat_checksum。

effective PIT成立：以生效上市/退出/代码区间和历史membership计算，没有未来成员倒灌。knowledge PIT仍未证明（knowledge_time_unverified=true），没有伪称公告当时可见。所有市场日窗口复用已完成真实日历3044行。

## Source / manifest / checksum

每条都有membership、sector price/amount、calendar、historical Universe、全Aprice/amount、计算benchmark六类真实来源。15/15完整；无悬空或未登记引用；Universe再关联5条原有真实master来源，均注册且checksum有效。

新增3条source_snapshot与对应禁用审计registry、1个审计parameter_profile、2个run_manifest、15条snapshot。没有写security_master或stock_daily（均仍0行），没有建立长期全A库。

- run_id：`7fe5ad62-ab71-4759-a334-08dffe980d97`
- recompute_run_id：`ae8d6541-5a8f-4797-9542-80cc1917fc20`
- parameter_hash：`a602e915961235a8ab5cc678548bf5a249f5197707d18d8b32a518af78c5f21b`
- 计算Actions：https://github.com/bruce233cu/three-sector-research/actions/runs/36942748135
- 临时输入artifact：11201276345；SHA256 `0bbeef90e64d24979ccebc6a20f8567e5326d8ac76ee9dac0e2a4975a9cc32ca`；保留30天。

Source元数据包含provider/upstream、请求参数/日期、fetched_at、row_count、coverage、checksum、代码SHA、parameter hash、run_id。完整原HTTP逐股payload不永久保存，证据等级明确为request checksums plus normalized temporary Parquet；不冒充完整raw archive。300条benchmark聚合结果长期保存于本报告附件；1366323条临时行情不进入长期数据库或Git。

## G1 FINAL 与技术债

数据库final_gate.sql实查15样本完整、来源0悬空/0未注册、两manifest、旧15保留、复用指标不变。G1_FINAL.json由真实计算和数据库核验共同判定PASS。

剩余非阻塞技术债：circ_mv增强指标deferred；历史knowledge publication time未证明；既有未复权行情存在corporate-action警告（沿用前轮验证输入）；临时raw/cache有30天保留期，长期保留聚合结果、checksum和来源登记。本次不新增研究阶段。

## GitHub范围与提交

仓库：bruce233cu/three-sector-research；分支：mainline-phase1e。起始SHA `196285581feb9818dfaf48f4aa2aceba7a7030ef`；实际计算SHA `46e581fa7649134fdf2a879090a715f414b386ca`。最终交付SHA见delivery_meta.json或交付提交链接。仅mainline实现、测试、隔离审计workflow和报告；main、三大赛道、Daily Pipeline、Sites未修改。

提交包含：9baeb7ec（有限字段探针）、7424c907/ca72540b/5984e0ae（官方接口字段补齐）、8cf385a5（resolver与计算）、46e581fa（官方PDF读取）、b7b862e3（仅导出聚合审计证据）、最终交付提交。没有force push。

## MILESTONE B — MAINLINE ENGINE 开工清单

- metrics finalization
- rules
- S0-S4
- state machine
- consecutive days
- debounce
- lifecycle
- freeze propagation
- unit tests
- deterministic rerun
