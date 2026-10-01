# A股主线识别系统 V2.2.1
## MILESTONE A FINAL CLOSE / G1 FINAL 交付包

**G1 = FAIL**  
**READY_FOR_PRODUCTION_ENABLEMENT = false**  
MILESTONE A：未关闭。未进入 Phase 2。

本次是断点续跑。真实输入重算：SUCCESS 0 / PARTIAL 15 / FAIL 0。
不再把上一轮15条纯缺失输入冻结结果当作真实行情POC。

### 1. benchmark 定义与实现

目标日真实历史 A 股 Universe U_t：当时已上市，且未越过退市日；后来退市股保留
历史资格，未来上市股票不倒灌；B/H股、基金、债券等非A股不进入。
ST不因标签而排除。有效当日个股收益集合 V_t 不包含缺失/无有效交易观测。

benchmark_coverage = |V_t| / |U_t|。只有历史分母已验证且覆盖率≥95%，才输出
benchmark_return = sum(return_i for i in V_t) / |V_t|；不足则 NULL / Freeze。
未知分母的coverage也是NULL，不伪报0%。RS窗口90%与板块内部70%保持不变。

实现：src/mainline/metrics/benchmark.py + scripts/mainline/v221_real_close.py。
新版链路不使用801003；所有RS及60日成交窗口按真实市场日历限定，不能以“最近有效
观测”向前拉长。代码测试通过，但真实benchmark验收不能用代码测试代替。

### 2. 801003与冻结benchmark的差异

801003为申万Ａ指，是申万发布的指数点位序列，其日收益来自点位变化，不是本项目
基于历史有效个股直接计算的等权平均。历史公开申万股价系列编制说明采用流通股本
权重及连锁计算。801003当前完整方法版本、成分范围和调整细则尚未形成项目证据，
因此不声称已复现其全部当前定义，更不能宣称与ALL_A_EQUAL_WEIGHT等价。
两者可能方向相近或某日数值偶合，但这不是等价证明。

受影响：benchmark_return、RS5/10/20、RS派生比较；旧801003成交额代理还会影响
turnover_share/turnover_intensity。旧801003数据保留，只移出新版输入。

核查来源：[申万官方指数发布页](https://www.swsresearch.com/institute_sw/allIndex/releasedIndex)；
[历史申万股价系列编制说明原文](https://finance.sina.com.cn/roll/20031017/0612478149.shtml)。
后者为2003年历史方法，不能冒充801003最新完整编制附件。

### 3. 15样本总表与coverage

OHLCV与amount当日coverage在本次结果中相同，按历史样本成员数计算。
NULL benchmark coverage表示历史全A分母未被证明，不表示观测收益为零。

| 日期 | 行业代码 | 有效/成员 | OHLCV/amount | MA20 | MA60 | NEW_HIGH60 | benchmark | 状态 | Freeze |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| 2019-06-28 | 801080 | 187/189 | 98.94% | 97.35% | 90.48% | 90.48% | NULL | PARTIAL | 是 |
| 2019-06-28 | 801120 | 32/33 | 96.97% | 93.94% | 87.88% | 87.88% | NULL | PARTIAL | 是 |
| 2019-06-28 | 801790 | 48/50 | 96.00% | 96.00% | 96.00% | 96.00% | NULL | PARTIAL | 是 |
| 2020-06-30 | 801050 | 116/118 | 98.31% | 96.61% | 88.98% | 88.98% | NULL | PARTIAL | 是 |
| 2020-06-30 | 801120 | 38/38 | 100.00% | 100.00% | 97.37% | 97.37% | NULL | PARTIAL | 是 |
| 2020-06-30 | 801790 | 52/53 | 98.11% | 94.34% | 94.34% | 94.34% | NULL | PARTIAL | 是 |
| 2021-12-31 | 801080 | 353/361 | 97.78% | 96.12% | 92.52% | 92.52% | NULL | PARTIAL | 是 |
| 2021-12-31 | 801780 | 41/42 | 97.62% | 97.62% | 95.24% | 95.24% | NULL | PARTIAL | 是 |
| 2021-12-31 | 801890 | 458/472 | 97.03% | 95.34% | 90.25% | 90.25% | NULL | PARTIAL | 是 |
| 2023-06-30 | 801050 | 137/141 | 97.16% | 96.45% | 95.74% | 95.74% | NULL | PARTIAL | 是 |
| 2023-06-30 | 801120 | 121/125 | 96.80% | 96.80% | 96.00% | 96.00% | NULL | PARTIAL | 是 |
| 2023-06-30 | 801890 | 531/550 | 96.55% | 95.27% | 92.00% | 92.00% | NULL | PARTIAL | 是 |
| 2025-06-30 | 801080 | 480/491 | 97.76% | 95.72% | 94.30% | 94.30% | NULL | PARTIAL | 是 |
| 2025-06-30 | 801780 | 42/42 | 100.00% | 100.00% | 100.00% | 100.00% | NULL | PARTIAL | 是 |
| 2025-06-30 | 801890 | 582/600 | 97.00% | 96.17% | 94.00% | 94.00% | NULL | PARTIAL | 是 |

### 4. 核心指标总表

| 日期 / 行业 | sector_return | benchmark_return | RS5 / RS10 / RS20 | turnover_share / intensity | UP_RATIO | MA20 / MA60 / HIGH60 | Top3成交 |
|---|---:|---:|---|---|---:|---|---:|
| 2019-06-28 / 801080 | -1.86% | NULL | NULL / NULL / NULL | NULL / NULL | 13.37% | 53.80% / 22.81% / 2.92% | 12.77% |
| 2019-06-28 / 801120 | -0.57% | NULL | NULL / NULL / NULL | NULL / NULL | 21.88% | 70.97% / 37.93% / 0.00% | 36.43% |
| 2019-06-28 / 801790 | -0.53% | NULL | NULL / NULL / NULL | NULL / NULL | 25.00% | 89.58% / 41.67% / 4.17% | 36.32% |
| 2020-06-30 / 801050 | 1.13% | NULL | NULL / NULL / NULL | NULL / NULL | 78.45% | 42.11% / 53.33% / 7.62% | 21.85% |
| 2020-06-30 / 801120 | 2.45% | NULL | NULL / NULL / NULL | NULL / NULL | 89.47% | 60.53% / 78.38% / 16.22% | 25.55% |
| 2020-06-30 / 801790 | 2.43% | NULL | NULL / NULL / NULL | NULL / NULL | 98.08% | 74.00% / 72.00% / 10.00% | 24.96% |
| 2021-12-31 / 801080 | 0.07% | NULL | NULL / NULL / NULL | NULL / NULL | 49.58% | 53.31% / 65.27% / 4.19% | 8.90% |
| 2021-12-31 / 801780 | 0.12% | NULL | NULL / NULL / NULL | NULL / NULL | 53.66% | 34.15% / 32.50% / 0.00% | 50.07% |
| 2021-12-31 / 801890 | 0.58% | NULL | NULL / NULL / NULL | NULL / NULL | 57.64% | 55.11% / 65.73% / 9.62% | 12.17% |
| 2023-06-30 / 801050 | 1.47% | NULL | NULL / NULL / NULL | NULL / NULL | 86.86% | 56.62% / 34.07% / 5.19% | 14.10% |
| 2023-06-30 / 801120 | 0.48% | NULL | NULL / NULL / NULL | NULL / NULL | 70.25% | 27.27% / 16.67% / 0.00% | 30.59% |
| 2023-06-30 / 801890 | 0.82% | NULL | NULL / NULL / NULL | NULL / NULL | 60.26% | 85.69% / 72.92% / 13.04% | 10.10% |
| 2025-06-30 / 801080 | 1.58% | NULL | NULL / NULL / NULL | NULL / NULL | 86.46% | 92.34% / 84.67% / 20.09% | 6.60% |
| 2025-06-30 / 801780 | -0.72% | NULL | NULL / NULL / NULL | NULL / NULL | 11.90% | 57.14% / 95.24% / 2.38% | 22.72% |
| 2025-06-30 / 801890 | 1.59% | NULL | NULL / NULL / NULL | NULL / NULL | 85.22% | 81.28% / 74.65% / 12.23% | 4.01% |

每条完整字段、deferred原因、source引用、run/version/profile及Freeze原因见
snapshot_export.json。turnover_cap_deviation与top3_return_contribution全部NULL，
原因明确为deferred_due_to_unproven_historical_circ_mv。

### 5. 来源链、PIT与重跑

原15样本：完整非空旧链5/15，恢复涉及6样本；4条真实登记、9个引用已在前轮恢复，
本次未重新恢复旧source。新版真实来源数、悬空引用及完整链数量见database_gate.json。
本次写后验证：新增35条真实source；成员/行情/日历链15/15；四类完整链0/15，
缺口均为真实benchmark来源；悬空引用0，未登记引用0。没有把组件名单冒充benchmark。
没有为缺失benchmark创建占位来源。Sina真实窗口与成员/日历来源能关联到mainline
source_registry、source_snapshots和run_manifests；缺失的benchmark链如实保留缺口。

本次成功Sina证券 1558/1578；
临时行情行数 364775。同输入复算一致 15/15；
比较核心指标、coverage、Freeze、benchmark、同一source引用及parameter hash。
已有真实行情缓存只复用数据，不伪称再次网络获取，保留原fetched_at和响应checksum。
membership有效日期检查 15/15；全Universe和全部输入PIT
不能据此宣称通过。knowledge_time_unverified=true；Level 2缺失不单独阻塞POC。

### 6. Freeze与NULL验收

代码验证：95%边界可用、94%不足、未来上市/非A/退市日期过滤、非有限收益/重复行情拒绝、
精确20日RS窗口缺失不拉长、重复membership在计算前拒绝、NULL保持NULL、
coverage下降触发Freeze，以及circ_mv deferred本身不触发Freeze。
正式结果的每条Freeze原因、真实coverage和完整对照记录见snapshots.json/checks.json。
原冻结日线质量门槛仍保留；未以板块70%取代其95%关键数据门槛。

### 7. source / manifest / checksum

真实计算代码SHA：eed55fc788896f517b70654e10fa0d09c1657154  
run_id：382be957-d400-4d09-b2ac-8507a166a0e8  
recompute_run_id：2a9c9c7c-62e1-485d-baae-4529630deac6  
parameter hash：9197164aa1cf65d56539618a13712cfd982f8e90598ff4b9a2d31bc7fd0ee358  
workflow：36889897269；artifact：11176476748  
artifact SHA256：8b7c002739504be81d7634fce93be68f15c4811fb6034f8a9995786def9c2b0c

最低来源元数据：provider、真实upstream、请求参数及日期、fetched_at、
原始响应checksum（可得时）、标准化checksum、行数、coverage、code SHA、parameter hash、run ID。
证据等级明确。source_snapshots.json保存本轮登记；sina_fetch_audit.json保存逐证券
请求结果；universe_acquisition.json保存真实官方名单请求结果。
原始HTTP响应非永久全量保存不作为自动FAIL理由。

### 8. GitHub与Supabase

仓库：bruce233cu/three-sector-research；分支：mainline-phase1e。
用户给出的52da934是旧检查点；实际起始SHA：25d27a0ff903eee49402832ece6fdad3e121fc89。
本轮提交和最终SHA见delivery_meta.json及GitHub最终提交。报告本身位于交付commit，
避免在报告中伪造自引用commit SHA。

Supabase新增：独立同口径V2.2.1审计profile、15条正式结果、新真实source登记、
原始运行与复算manifest。旧V2.2 15条、前轮冻结15条均不覆盖。证券行情仅临时输入，
不回填全A长期stock_daily库。没有核心schema迁移，没有修改main、Sites、Daily Pipeline、
三大赛道或Phase 2。查询验证与最终数据Gate见database_gate.json/final_gate.sql。

### 9. 最终G1与真正阻塞项

1. 历史全A股Universe尚未完整验证：深圳在市名单未成功取得，北交所当前名单不能独立证明历史完整资格。无法证明benchmark及全A成交分母的历史覆盖率，benchmark / RS / turnover保持NULL；完整benchmark source链及全Universe PIT仍未通过。

G1=FAIL；READY_FOR_PRODUCTION_ENABLEMENT=false。
真实benchmark、RS、turnover或PIT缺口未通过时，不能因15条行数齐全而关闭MILESTONE A。

| 冻结验收项目 | 最终结果 |
|---|---|
| 历史taxonomy / membership回放 | 15/15有效日期与SW版本已核对 |
| 无未来membership倒灌 | 15/15成员有效日期检查通过 |
| 真实交易日历 | 3044行，既有来源；未重建 |
| OHLCV / amount | 15/15当日coverage≥96% |
| MA20 / MA60 / NEW_HIGH60市场窗口 | 真实交易日窗口；逐指标coverage见表 |
| ALL_A_EQUAL_WEIGHT | 计算代码已实现；真实历史分母未通过 |
| RS / turnover | NULL，真实端到端可用性未通过 |
| breadth | 15/15真实计算 |
| coverage / NULL / Freeze | 真实覆盖率与NULL保留；15/15冻结；边界测试通过 |
| source / manifest / checksum | 成员行情日历完整；benchmark缺口未通过 |
| effective PIT | 成员有效日期15/15；全A Universe未通过 |
| deterministic rerun | 同输入15/15一致 |
| 正式V2.2.1 snapshot | 已追加15条；0 SUCCESS / 15 PARTIAL / 0 FAIL |
| circ_mv deferred | 两项指标NULL；不构成本轮阻塞 |

### 10. Technical debt（不追加为新Phase 1研究）

Sina当前收益为未复权相邻真实观测close比率；公司行动口径保存warning，未冒充
严格knowledge PIT或未来复权。临时workflow输入artifact保留30天；本包包含输入与
核验checksum，避免只留下不可复算的登记。801003最新完整方法附件未用于本次计算。
不重新研究circ_mv、Tushare、BJ/停牌/退市专项，不以这些名义新增阶段。

### 11. MILESTONE B开工清单（仅PASS后可开工）

metrics finalization；rules；S0-S4；state machine；consecutive days；debounce；
lifecycle；freeze propagation；unit tests；deterministic rerun。
本轮未开工。FAIL时该清单仅为后续范围，不代表Phase 2授权或MILESTONE A关闭。

### 12. 优化留痕与执行规范

为什么改：前轮仅生成缺失输入结果，未满足真实Sina与来源链验收。改了什么：在既有
主链上获取并缓存真实窗口、重算固定15样本；修复官方SH终止上市名单B股混入风险；
记录完整元数据与同输入复算。版本V2.2.1，业务阈值不变，数据库仅mainline追加，
不改状态筛选/生产自动化，不覆盖旧数据。验收结果以本包G1为准；未解决问题仅限上列。

使用[Supabase技能](skill://supabase@openai-curated-remote/root/.codex/plugins/cache/openai-curated-remote/supabase/1.0.0/skills/supabase/SKILL.md)
完成mainline限定写入和写后验证；遵循[Postgres批量写入规范](https://www.postgresql.org/docs/current/sql-copy.html)
将15条结果和来源批量纳入事务。用户禁止影响三大赛道优先于共享public优化日志默认规则，
优化记录写入mainline manifest与此报告。
