# A股主线识别系统 V2.2.1
## MILESTONE B / MAINLINE ENGINE LIVE 交付包

| 验收 | 最终结论 |
|---|---|
| G1 数据底座 | PASS，保持 CLOSED |
| G2 指标 Gate | **PASS** |
| G3 完整状态机 Gate | **FAIL** |
| MILESTONE B | **OPEN** |
| READY_FOR_DAILY_MAINLINE | **false** |

**已完成明确指标、独立规则、合法状态控制内核与审计保存；完整业务状态认证被3项真正缺口阻断。未启用生产mainline_job、未修改Sites。**

### 1. Metrics finalization

已保留通过G1的sector_return、benchmark_return、RS5/10/20、turnover_share/intensity、up_ratio、MA20/MA60、NEW_HIGH60、Top3成交占比，15/15核心事实不变。新增纯计算模块覆盖RS3、WIN5/10、RS横截面分位、成交额60/250日分位、20日均值、3市场日滞后及确认用最近3个有效成交日趋势。

公式依V2.2第8–9页：RS为两个复利收益之差；WIN严格大于基准且至少4/8有效比较日；成交分位用SQL percent_rank和40/160最少有效日；RS排名同日/同分类版本/同层级，至少10有效对象，高RS排前。精确日历窗口不延伸到额外有效观测。

历史窗口未完整认证时新增指标保持NULL，诊断数值只进入诊断文件，不作为生产硬状态输入。两个circ_mv指标强制deferred/NULL，未重新启用。

### 2. Metric availability 与规则

可用性明确区分available / unavailable / deferred / frozen。NULL规则结果为passed=null，0仍是有效观测，可真实比较为false；禁止bool(NULL)。

实现C1–C5候选，确认A/B/C/D分组及E1–E3增强条件。每项都有rule_id、版本、对象、交易日、metric、actual_value、threshold、operator、passed、reason、profile和availability版本。15样本共570条独立规则结果，见rule_results.json。

E4未量化部分保持BUSINESS_RULE_CONFLICT；无家族数据的E5不认证通过。未给出可执行定义的转弱/退潮/恢复判据保持未知，不能宣称已完整实现S3/S4业务规则。

### 3. S0–S4 与 state machine

冻结状态保持：S0未形成、S1候选、S2已确认、S3转弱、S4退潮。合法转移内核覆盖S0→S1、S1→S0/S2、S2→S3、S3→S2/S4。非法跳级/直接S2→S4受阻。

S4旧周期关闭后不重开；再次强势只能新建lifecycle并从S1开始（原文转移表及T-SM-002）。confirmed连续2日、weaken连续2日且确认后minimum dwell 3市场日、retire连续3日由内核计数。内核消费显式规则证据，不冒充未定义业务谓词已经完成。

### 4. consecutive days / debounce

Checkpoint持久保存上一日日期、状态、持续日数和确认/转弱/退潮连续计数。已知失败重置计数，已知成功继续。只接受相邻市场交易日，不以相隔数年的单日样本充当连续历史。

输出debounce_status、debounce_days、debounce_reason，解释尚未达到连续天数或minimum dwell。无行业、日期、牛熊市特判；未调参。

### 5. lifecycle

内核记录首次进入、确认、转弱、退出和重入，ID用对象/版本/profile/开始日/前周期确定性生成；保留prior_lifecycle_id和reentry_count。Checkpoint和decision_reason保存start/current/highest/last-transition/end字段，现有生命周期表可保存事件列，无需新增schema。

**本轮真实lifecycle新增0条。** 单元测试里的周期全部是虚构对象fixture，不写数据库，不冒充历史主线。

### 6. Freeze propagation / recovery

坏质量或核心证据不足时沿用可信状态、停止硬转移，NULL不能造成降级。没有可信初始状态时保持state=NULL，不能伪造历史S0。冻结开始/结束和resume_reason保存于checkpoint。

原文没有Freeze恢复连续计数合同，也没有recover_to_confirmed完整执行规则。默认安全阻断；测试中的显式reset仅验证能力，未被设为生产业务定义。

### 7. Versioning 与合同恢复

从用户已有V2.2施工冻结版完整说明书读取21页，恢复仓库缺失的metric_contract、state_machine、rules、backtest_contract、acceptance_checklist附件；附件保留整页原文及出处，不重新设计业务。

所有结果绑定mainline_v2.2.1、industry_trend_v2_2_1_engine_audit、mainline_metric_availability_v2.2.1_deferred_circ_mv。原G1 profile和结果保留；新profile audit_only，不标记生产准备完成。

### 8. Tests

| 测试层 | 结果 | 可证明的范围 |
|---|---:|---|
| 新增单元测试 | 58/58 | 指标公式与边界、三值规则、合法转移内核、连续、防抖、Freeze、重入、版本和幂等 |
| 既有benchmark回归 | 6/6 | 95%边界、缺失不填0、等权收益和Freeze |
| 数据库真实15样本 | 15/15 | 核心指标不变、规则/状态同输入一致 |
| 15段60日真实窗口 | 900/900复算一致 | 真实行情和benchmark派生诊断，不证明完整历史状态 |

GitHub离线CI：https://github.com/bruce233cu/three-sector-research/actions/runs/36946510935 。CODE SHA `ed453deb1aab5cccd0fcfd798f5c8f101645c2c4`。测试fixture标注虚构对象，全部真实provider调用数0。

### 9. 15条集成审计结果

原G1指标样本仍15 SUCCESS。新版状态审计不是15个已识别主线；因缺少可信previous_state和必要规则输入，15条均state=NULL、stage_frozen=true。

| 日期 | 对象 | 原核心指标 | RS排名有效对象 | state / previous | Freeze | 复算 |
|---|---|---|---:|---|---|
| 2019-06-28 | sw1_801080 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2019-06-28 | sw1_801120 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2019-06-28 | sw1_801790 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2020-06-30 | sw1_801050 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2020-06-30 | sw1_801120 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2020-06-30 | sw1_801790 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2021-12-31 | sw1_801080 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2021-12-31 | sw1_801780 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2021-12-31 | sw1_801890 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2023-06-30 | sw1_801050 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2023-06-30 | sw1_801120 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2023-06-30 | sw1_801890 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2025-06-30 | sw1_801080 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2025-06-30 | sw1_801780 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |
| 2025-06-30 | sw1_801890 | 保持不变 | 3 / 最低10 | NULL / NULL | 是 | 一致 |

### 10. 真实时间序列边界

重用已通过G1缓存和真实市场日历，15个行业-目标日窗口×60市场日，生成900行板块诊断。每个中间日按已知membership有效区间排除未来成员，但目标日样本不能证明中间日已退出且目标日未出现的成员无遗漏。故membership窗口完整性未认证，不用静态目标集合伪造连续历史。

真实时间序列state仍NULL，certified_transition_events=0。完整状态内核的升级/降级用显式synthetic evidence做单元测试；二者严格分开。正式历史盲测/有效性不在本轮进行。

### 11. 最多3个Blocking Issues

| 编号 | 真正阻塞 | 需要明确的最小内容 |
|---|---|---|
| 1 | BUSINESS_RULE_CONFLICT：转弱/退潮量化定义 | RS斜率方法/窗口、组内连续下降定义、广度/结构/核心/家族恶化判据、E4历史分位窗口 |
| 2 | BUSINESS_RULE_CONFLICT：恢复计数 | Freeze解除后的计数重置/暂停政策；S3恢复S2的确认与防抖规则 |
| 3 | 真实状态输入不足 | 每日≥10同层级有效行业、全A广度参照、完整连续membership/指标及可信状态种子 |

详见docs/BUSINESS_RULE_CONFLICT_MILESTONE_B.md。不得让开发端用自己的阈值补上这些业务口径。没有新增Phase 1研究，没有重取Provider或重建Universe/日历。

### 12. G2 / G3最终执行

G2=PASS：冻结明确指标公式、64项测试、边界、NULL/deferred、Freeze与determinism均通过。

G3=FAIL：合法状态内核和synthetic用例通过，但完整冻结业务谓词、恢复政策及真实连续状态验收不成立。代码运行成功不能替代业务Gate。

### 13. Supabase变化与审计

无DDL、无新增schema、无核心字段修改。新增：1个审计profile、1条真实诊断source_snapshot及禁用registry、2条run_manifest、15条engine审计snapshot、15条状态data_quality记录。新增lifecycle=0。状态checkpoint和解释复用decision_reason JSON。

数据库复查：15核心事实未变；15 unknown/frozen正确保留；0悬空/0未注册source；原G1 15 SUCCESS保留；stock_daily/security_master仍0行；calendar仍3044行。中文优化留痕保存于mainline.run_manifests，并按仓库留痕要求追加1条系统优化记录（部分通过，已查询验证）；未改变三大赛道研究逻辑。

- run_id：`354edd71-af9e-5d7f-9864-6f54545ddefd`
- recompute_run_id：`cbbe3b07-dd05-5c69-a105-f05edf7df206`
- parameter_hash：`3fdcbcdf79090dc640cc0d609aa0e8368e36c34e321e0d5ea4a3060463614b06`
- artifact ID：11202595618，SHA256 `64431427c4744cb5276de3892c861ebc6b1b76aa88962030db0e0394d73ecc83`，临时保留30天。

永久Git只保存代码、合同、板块聚合和审计元数据；没有存入全A个股历史库。原逐股输入复用临时cache，未新增长期原始行情资产。

### 14. GitHub与修改文件

Repository：bruce233cu/three-sector-research；Branch：mainline-phase1e。

起始SHA：`75c595e02ded7f6954cad4477ead9f7789e576b0`。

实现/执行commit：`ed453deb1aab5cccd0fcfd798f5c8f101645c2c4`。最终交付commit为包含本报告的提交，精确SHA写入下载包resolved_commit.json。

修改范围：src/mainline/engine的metrics/rules/state_machine；3个test_engine文件；离线脚本与隔离审计workflow；1个audit profile；冻结合同附件与冲突记录；milestone-b-engine报告。main未改、未force push、未重写历史。Sites、生产Daily Pipeline未修改。

### 15. Technical debt / MILESTONE C

除上面3项阻塞外：strict knowledge PIT仍未认证；circ_mv增强继续deferred；未复权公司行为告警沿用原G1事实。均未重新研究。

**MILESTONE B未关闭，READY_FOR_DAILY_MAINLINE=false。** MILESTONE C尚未开工，不启用每日mainline_job，不做Sites展示。G3通过后再交付正式Daily Mainline + Sites开工清单。
