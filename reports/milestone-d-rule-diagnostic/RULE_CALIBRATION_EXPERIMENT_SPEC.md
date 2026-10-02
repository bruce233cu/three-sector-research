# A股主线识别系统 V2.2.1 — RULE CALIBRATION EXPERIMENT SPEC

> **状态：SPECIFICATION_ONLY / NOT_EXECUTED**
> 本文冻结下一轮规则校准实验的版本、指标、顺序、成功门槛、失败护栏和Holdout隔离原则。它不修改正式规则，不生成新`rule_version`，不授权生产发布，也不把现有25例重新包装成独立准确率。

## 1. Executive Summary

当前问题不是“系统完全找不到主线”，而是三件事同时存在：

1. **S1→S2升级受单项硬否决。** 正例10/10曾到S1，但事件期S2只有5/10；B在7个正例中出现25个唯一阻塞日，其中8日、4例具备合法S1升级资格。
2. **短期共振和中期持续性没有充分分开。** 负例事件期出现S2的4例中，只有N10是事件期新确认，其余3例是旧S2延续；当天同时很强不等于可持续。
3. **候选状态过于敏感。** 已有117次`S0→S1→S0`，说明单日跌破候选标准容易反复开关生命周期。

本轮固定五个层级：`BASELINE → V1 → V2 → V3 → V4`。每一级只研究一个机制；先通过预设护栏，才能作为下一级唯一父版本。禁止把各层候选全部交叉、禁止网格搜索、禁止按P10/N10或单个行业挑参数。

**开发集晋级的硬目标：** 正例事件期S2召回至少从5/10提高到6/10；负例事件期新误确认不超过1例、S2暴露不超过11日；不丢失任何基线事件期正例；NULL/Freeze语义不变；改善至少涉及2个正例且来自2个episode。V3开始还必须让候选往返明显下降。

即使全部达到，也只能称为 **CALIBRATION CANDIDATE**。正式泛化结论必须来自全新、按episode隔离、完全不参与设计的Holdout。

## 2. 为什么现在不能直接改规则

- 25例已经被阅读、诊断并用于提出候选，永久属于`DEVELOPMENT / DIAGNOSTIC SET`。
- B既制造漏报风险，也确实过滤负例；直接删除或统一降阈值可能把误报一起放大。
- 13项warmup请求未认证只是局部缺口；更大的限制是完整84日初始化仍未认证。规则问题与数据资格问题不能混为一谈。
- D.newhigh与E3在450个事件案例日完全一致，说明当前“五组”并非五份独立信息。
- 当前没有独立、冻结的结构转弱/退潮参考日，不能凭事后走势重写S3/S4。
- 开发集样本小、episode相关且存在跨标签重叠；任何单一总分都很容易隐藏召回、误报和滞后之间的交换。

因此，本规格只允许**有限、可解释、逐层归因**的结构实验。不得把开发集最优值直接写入正式profile。

## 3. BASELINE：当前冻结表现

基线必须使用现有归档输入、现有正式规则、现有profile和相同case窗口。执行阶段先重放BASELINE，只有与下表及既有checksum一致时才能继续；这属于实验工具验收，不是重跑G1–G4。

| 维度 | BASELINE |
| --- | ---: |
| 正样本事件期至少一次有效S2 | 5/10 |
| 正样本全窗口至少一次有效S2 | 6/10 |
| 负样本事件期新进入S2 | 1/10（N10） |
| 负样本事件期S2暴露 | 11案例行业日 |
| 负样本稳定S2暴露（连续≥3交易日） | 2/10 |
| 正例事件期S2案例首次确认滞后 | `[-12,-4,-1,3,14]`交易日；中位数-1，均值0.0 |
| 正例全窗口S2案例首次确认滞后 | `[-12,-4,-1,3,14,37]`；中位数1，均值6.17 |
| `S0→S1→S0` | 117 |
| `S1→S2→S1/S0` | 0；正式状态合同不允许直接路径 |
| `S2→S3→S2`恢复转移 | 4 |
| 总transition / reversal / 短周期reversal | 341 / 276 / 174 |
| Freeze日 | 63 |
| warmup请求认证 | 5369/5382 = 99.758454% |
| 数据资格 | G5=FAIL；effective PIT；knowledge-time未验证；完整84日warmup未认证 |

负滞后表示事件开始前已经进入S2，不代表预测准确。所有滞后同时保留case级分布；不得只展示中位数掩盖漏报或晚确认。

## 4. 固定评价指标

### 4.1 Primary outcome metrics

| ID | 指标 | 固定定义 | 方向 |
| --- | --- | --- | --- |
| M1 | 正样本事件期S2召回 | 10个正例中，在冻结事件窗口内至少1个非Freeze交易日状态为S2的case数/10。继承事件前S2仍算事件期覆盖，但必须另标`inherited` | 越高越好 |
| M2 | 正样本全窗口S2召回 | 10个正例中，在冻结pre/event/post窗口内至少1日有效S2的case数/10 | 越高越好 |
| M3 | 负样本事件期新误确认 | 10个负例中，事件窗口内发生合法`S1→S2`新转移的case数和转移次数；继承S2不计新确认 | 越低越好 |
| M4 | 负样本事件期S2暴露 | 负例事件窗口内state=S2且非Freeze的案例行业日总数；同时报告每例最长连续S2 | 越低越好 |

### 4.2 Latency metrics

对每个正例，`lag = market_session_index(first_valid_S2) - market_session_index(event_start)`。交易日来自冻结日历：事件前为负，事件开始为0，事件后为正。

必须同时报告：

- 事件期命中case的原始case级lag、均值、中位数、最小值、最大值；未命中不进入均值，但单独列为右删失MISS。
- 全窗口命中case的lag分布；事件后确认单独标`late_confirmation`。
- **matched-lag：** 仅对BASELINE已在事件期覆盖的5个正例比较新旧lag，报告每例变化、均值和中位数，防止新增一个晚确认后分母变化造成假象。
- 新恢复case必须给出实际lag，不能只说召回增加。

### 4.3 State stability metrics

| ID | 指标 | 固定定义 |
| --- | --- | --- |
| M5 | 候选往返 | 压缩transition序列中的`S0→S1→S0`模式数，可重叠，沿用现有evaluator口径 |
| M6 | 确认直接回落 | `S1→S2→S1/S0`路径数；按正式合同应始终为0，非0视为非法实现 |
| M7 | 确认后恢复反复 | `S2→S3→S2`次数；另报`S2→S3→S2→S3`模式数 |
| M8 | reversal | 沿用现有evaluator：回到当前观察窗口已出现过的状态；同时报告`short_interval_reversal_count`（≤5交易日） |
| M9 | transition总数 | 全25例完整窗口的合法状态变化总数 |
| M10 | 假候选滞留 | 负例事件窗口S1案例行业日、每例最长连续S1、首次candidate失败到S0的交易日延迟 |

### 4.4 Data qualification metrics

- NULL必须按`TRUE / FALSE / NULL`三态逐规则、逐组统计；NULL不得转0、不得默认TRUE、不得计作满足天数。
- Freeze日、Freeze原因、恢复首日保护和计数暂停/重置策略必须与同一输入下BASELINE合同一致。
- 每个实验输出`warmup_sensitive`、`pit_level`、`knowledge_time_unverified`、有效成员覆盖与关键指标可用率。
- 因候选规则新增历史窗口而不足的数据必须产生NULL/Freeze或“不可判定”，不能缩短窗口冒充满足。

## 5. 固定实验架构

### 5.1 共同规则

- 每个候选使用同一25例、同一日期、同一快照、同一成员历史和同一日历。
- 只替换本节明确列出的实验逻辑；其余正式规则逐字节保持不变。
- 候选只存在于实验命名空间，例如`experiment_id`；不得复用或覆盖正式`rule_version`与`parameter_profile`。
- 每个候选至少确定性重跑2次，输出checksum必须一致。
- 同一层候选并列时不以加权总分选胜者；按硬门槛、再按预设优先顺序选择。仍并列则标`INCONCLUSIVE`，不得临时加指标。

### 5.2 顺序淘汰

```text
BASELINE一致性
  → V1三臂中最多选1个
    → V2三臂中最多选1个
      → V3两臂中最多选1个
        → V4去重验证
          → 冻结唯一Calibration Candidate
            → 新Holdout（另行授权后才执行）
```

不允许V1×V2×V3全组合；最多执行1个BASELINE、3个V1、3个V2、2个V3、1个V4，共10条预注册路径，而且后层只继承前层唯一胜出版本。

## 6. V1 — B HARD-VETO RESTRUCTURE

### 6.1 V1共同边界

**只改：** S1→S2确认中B的角色及补偿路径。
**不改：** A/B/C/D/Enhancer原子定义和阈值、candidate、连续计数的Freeze行为、S2/S3/S4、casebook和数据。

### 6.2 三个有限候选

| 候选 | 可执行定义 | 假设 | 预期收益 | 主要副作用 |
| --- | --- | --- | --- | --- |
| V1-A HARD CONTROL | 完全保留`A AND B AND C AND D AND Enhancer`连续2个有效交易日 | 实验框架应复现BASELINE；B硬门槛也可能是必要过滤 | 无业务改善；验证实验实现 | 若不能逐字节复现，整轮停止 |
| V1-B TIERED EXCEPTION | 标准路径不变；新增例外路径：`A AND D AND C AND Enhancer`为TRUE、B为FALSE，且例外路径连续3个有效交易日才确认。B为NULL时不得走例外 | B不足可由更长的其他四组同步补偿，而不是无条件放行 | 恢复间歇领涨真主线，同时保留B信息与额外时间成本 | 可能让成交/广度短脉冲在第3日误确认；确认更晚 |
| V1-C CORE + SUPPORT | A和D必须TRUE；B/C/Enhancer中至少2组TRUE；连续2个有效交易日。任一核心组NULL则不可判定；辅助组NULL不算票 | 强度+广度是核心，B只是三种支持证据之一 | 降低B绝对否决，保留至少4/5组证据 | 相比V1-B更容易放行B失败的脉冲，误报风险更高 |

这里的3日和2-of-3是**实验结构参数**，不是正式阈值建议。禁止再添加2日、4日、3-of-5等临时候选。

### 6.3 V1晋级/失败

- 必须满足全局硬门槛（第10节）。
- V1-A必须与BASELINE逐case、逐日状态和checksum一致，否则`HARNESS_FAIL`。
- V1-B与V1-C若都过门槛，预设优先V1-B，因为它保留原标准路径、变更面更小；只有V1-C在M1更高至少1例且M3/M4不差于V1-B时，才选择V1-C。
- 若改善只来自P10、或只有1个正例发生任何有利变化，标`OVERFIT_RISK_HIGH`，不晋级V2。

## 7. V2 — V1 + MULTI-DAY PERSISTENCE

### 7.1 V2共同边界

V2只在唯一V1胜出版本上增加时间维度，使用已有A/B/C/D/Enhancer三态序列；不新增行情指标、不改原子阈值、不使用事件后数据。

### 7.2 三个有限候选

| 候选 | 可执行定义 | 主要假设 | 预期收益 | 主要副作用 |
| --- | --- | --- | --- | --- |
| V2-P1 CORE 3/5 | 当日满足V1路径；最近5个有效交易日A≥3日且D≥3日；B/C/Enhancer至少一个组≥3日 | 真主线应有核心强度和广度积累，不只当日共振 | 降低单日爆发误确认 | 快速启动可能被延迟；早期窗口不足产生NULL |
| V2-P2 BALANCED 3/5 | 当日满足V1路径；最近5个有效交易日中，A、D、C三组各≥3日 | 成交持续性必须与强度、广度同时存在 | 专门过滤N10式成交短暂同步 | 慢趋势或成交不连续的真主线可能继续漏报 |
| V2-P3 TWO-STAGE | Stage 1：最近5个有效交易日A和D各≥3日；Stage 2：随后（可含Stage 1最后一日）V1当日确认条件连续2日 | 先形成趋势底座，再确认当前共振 | 逻辑最清晰，可解释“积累→确认” | 等待时间可能最长；Stage边界实现需严格防未来数据 |

有效交易日必须是当日所需证据均可判定且非Freeze的日子；窗口不足不得用较短分母替代。计数只向后看。

### 7.3 V2选择规则

- 三个候选都先过全局硬门槛。
- 首先淘汰M3或M4高于BASELINE者；然后淘汰matched-lag不达标者。
- 仍有多个候选时，优先M4更低；再比较M1；再比较matched-lag；仍并列预设优先P1（限制更少）。
- 不能因为N10被挡住就选择候选；至少需在两个不同负例/模糊例呈现更合理的持续性行为，或保持全部负例护栏并改善两个正例。

## 8. V3 — V2 + S1 HYSTERESIS

### 8.1 V3共同边界

**只改S1退出到S0。** S0→S1进入仍使用正式candidate；S1→S2使用V2胜出逻辑；S2/S3/S4不变。Freeze暂停退出计数，NULL不算失败，恢复首日不硬转移。

为避免无限滞留，两臂共享硬退出：当5个candidate组中≤1组TRUE、其余均为FALSE且无NULL时，可当日退出；这是实验安全阀，必须单列触发次数。

| 候选 | 普通退出定义 | 假设 | 预期收益 | 主要副作用 |
| --- | --- | --- | --- | --- |
| V3-H1 CONSECUTIVE-2 | candidate明确FALSE连续2个有效交易日后S1→S0 | 一日跌破多为噪声，两日确认仍保持响应 | 减少117次候选往返，保留确认观察窗口 | 假候选多停留1日或更久 |
| V3-H2 ROLLING-2/3 | 最近3个有效交易日中candidate明确FALSE至少2日后退出 | 对“失败—恢复—失败”也能退出，比纯连续更稳 | 兼顾去抖与退出速度 | 三日窗口不足/Freeze会延后决定 |

### 8.2 V3专属成功标准

除全局门槛外：

- M5 `S0→S1→S0`必须≤99（相对117至少下降15%）。
- 短周期reversal必须≤157（相对174至少下降约10%）。
- 负例事件期S1案例行业日不得比同父V2增加超过10%；每个负例最长连续S1不得增加超过3个有效交易日。
- 对明确硬失败（≤1票、无NULL）的退出延迟必须为0；其他负例从首次candidate FALSE到S0的中位延迟不得超过2个有效交易日。
- M1/M2不得低于父V2，M3/M4不得高于BASELINE。

若H1与H2都过门槛，优先选择负例S1滞留更少者；再比较M5；仍并列预设优先H1，因逻辑更简单。

## 9. V4 — V3 + EVIDENCE DEDUP

### 9.1 证据家族

| 家族 | 现有证据 | 去重约束 |
| --- | --- | --- |
| Relative strength | A.return、A.rank、B.win5、B.win10、E1 | 各自窗口不同，暂不合并票；记录相关性 |
| Breadth level | D.up、D.ma20、E2 | 比较口径不同，暂不强制合并 |
| Turnover | C.percentile、C.trend；candidate C4 | 确认与候选用途分开，不重复新增同义票 |
| New-high expansion | D.newhigh、E3 | 同一metric、同一lag3比较，必须视为一份证据 |
| Persistence | V2选择的历史条件 | 只能作为时间资格，不再同时复制成多个增强票 |

### 9.2 唯一V4候选

`V4-D1 NEW-HIGH SINGLE-VOTE`：保留D.newhigh在D组中的原作用；Enhancer计算时移除E3这一重复票。Enhancer仍按原阈值从E1/E2/E4中计票，E4为NULL时保持NULL语义，不补TRUE。其余逻辑继承V3。

这是保守去重压力测试，不代表最终一定选择“优先给D”。若因E4数据不足导致大面积不可判定，结果应为`DATA_LIMITED`，不能把E3加回去伪造通过。

### 9.3 V4晋级条件

- 事件案例日中`D.newhigh`与`E3`重复计票数必须从450降为0。
- 全局成功门槛全部通过；M1/M2不得低于父V3，M3/M4不得高于父V3，M5/短反复不得恶化超过5%。
- 因E4历史不足产生的新增NULL必须完整披露。若新增不可判定影响≥2个正例或使M1下降，V4不晋级，但“需要独立增强证据或补齐E4资格”作为明确结论保留。

## 10. 预先冻结的成功标准与Guardrails

### 10.1 全局硬门槛（任一失败即不晋级）

| 维度 | 晋级标准 | 失败示例 |
| --- | --- | --- |
| 正例事件期召回M1 | ≥6/10，且BASELINE已命中的5例无一丢失 | 仍为5/10；或新增1例但丢掉原有1例 |
| 正例全窗口召回M2 | ≥7/10 | 只把事件期外的P10挪早，却仍无新增全窗确认 |
| 负例新误确认M3 | ≤1个case且≤1次转移 | 从1增至2即失败；不等待“总分抵消” |
| 负例S2暴露M4 | ≤11案例行业日；稳定暴露case≤2 | 召回提高但暴露变成12日或稳定误报变3例 |
| 多case改善 | ≥2个正例、来自≥2个episode出现有利变化；其中≥1例由事件期MISS变HIT | 只有P10提前，其他全不变 |
| matched-lag | 原5个事件期HIT无丢失；其中位变化≤+1日、均值变化≤+2日；任一case不得晚>5日 | 用普遍延迟换召回 |
| NULL / Freeze | 不得把NULL当FALSE/0/TRUE；相同输入的数据Freeze掩码与原因合同一致；Freeze期0硬转移 | 缺数据默认通过或跨Freeze累计 |
| 合法性 / 确定性 | 非法transition=0；重复运行checksum一致；未来数据读取=0 | 出现`S2→S1`或同输入不同输出 |
| 单案例依赖 | 去掉任一“改善case”后，仍至少有另一个正例发生独立有利变化；报告leave-one-case结果 | 所有改善都由单一case贡献 |

“有利变化”只允许：MISS→事件期HIT、matched-lag提前≥2交易日且不丢失HIT、或该case短反复减少≥2次且召回/误报状态不恶化。不得把无关状态变化计作改善。

### 10.2 任何情况下直接失败

- 负样本事件期新误确认从1增至2或以上。
- 负样本事件期S2暴露超过11日，即使M1从5提升至7也失败。
- 任一BASELINE事件期正例HIT变MISS。
- 任何NULL默认通过、填0、缩短历史窗口或Freeze期间推进硬状态。
- 使用事件终点、未来收益、事后最高点、case标签或case_id作为规则输入。
- 新增行业/日期特例、P10/N10特例、按开发集结果继续追加候选。
- 为降低Churn让负例候选无限滞留，或让确认滞后突破matched-lag护栏。
- 改动正式rule/profile/阈值/状态机、Production、scheduler、Supabase正式状态或Sites。

### 10.3 不使用综合分

不建立“召回×权重−误报×权重”的单一分数。评价顺序固定为：

1. 数据/合法性/确定性；
2. 负例误确认与暴露护栏；
3. 正例召回；
4. matched-lag；
5. 状态稳定性与负例候选滞留；
6. 简单性和变更面。

前一层不过，后一层再好也不能抵消。

## 11. Warmup隔离原则

Rule Calibration回答“同一份合格输入下，规则结构如何反应”；Warmup Qualification回答“输入与初始化是否足以支持可信状态”。二者使用不同状态字段、不同Gate，不互相替代。

- 所有本轮候选结果标`DIAGNOSTIC / CALIBRATION ONLY`、`G5=FAIL`、`warmup_qualified=false`。
- 直接涉及13项未认证证券的P01、P06、P07、N05、N06、A01单列`direct_warmup_sensitive=true`；其余case仍继承`missing_84_day_initialization=true`。
- 主结果给全25例；同时给“直接13项敏感case剔除”的敏感性表，但不得把后者冒充正式准确率。
- P01/P02早期C分位NULL、E4长窗口NULL等必须归入数据资格，不得用规则放宽修复。
- 完整warmup未来补齐后，应以固定候选重跑资格对照；如果结果变化，先归因数据资格，再决定是否继续校准。

## 12. Holdout隔离设计

本轮只冻结设计，不选择最终case、不运行。

### 12.1 规模与覆盖

- 至少10正、10负、5模糊。
- 覆盖科技成长、制造、消费、金融、周期；覆盖上涨、震荡、回撤市场环境。
- 正例覆盖快速启动、慢趋势、二波、高波动和持续强势；负例覆盖单日脉冲、2–3日冲高、宽幅反弹、龙头独涨、轮动与成交退热。

### 12.2 Episode隔离

- 与开发集的行业、主线episode以及pre/event/post窗口不重叠。
- 同产业链、同政策催化、同一轮市场行情视作同一episode；换行业代理名称不能绕过隔离。
- 按episode先分组，再分配开发/Holdout，禁止逐case随机切分。
- 建立排除清单，记录与现有25例的相似episode及排除理由。

### 12.3 盲法与冻结

- 独立标注只看同期公开证据和预先允许的数据，不看S0–S4输出。
- 在揭封前冻结：case标签、event/pre/post窗口、预期行为、数据版本、PIT等级、warmup资格、结构转弱/退潮参考日、唯一候选代码hash和评价脚本hash。
- 模糊样本只用于鲁棒性描述，不并入二分类准确率。
- Holdout揭封只运行一次；至少5例做确定性重跑。看过结果后再调，当前Holdout立即降级为开发集，必须另建新Holdout。

### 12.4 Holdout晋级门槛

由于Holdout尚未选择，禁止预填基线数字。揭封前必须用冻结BASELINE和唯一候选同时运行，并使用同一指标。最低要求：

- 候选正例事件期S2召回高于Holdout BASELINE，且至少改善2个不同episode。
- 负例新误确认不高于Holdout BASELINE，且绝对不超过2/10；S2暴露不高于BASELINE。
- matched-lag中位不晚于BASELINE超过1日、均值不晚超过2日。
- M5和短周期reversal不高于BASELINE；若候选包含V3，M5至少下降10%。
- NULL/Freeze、合法状态、未来数据与确定性护栏全部为0违规。

小样本下不宣称统计显著性或泛化准确率；报告case级结果与episode分布。如果正负权衡冲突，结论为`INCONCLUSIVE`，不得上线。

## 13. 实验执行顺序与停止规则

1. **Preflight：** 核对分支、输入checksum、正式代码hash、casebook、日历和生产隔离；为实验创建独立输出目录/运行ID。
2. **BASELINE harness：** 复现第3节全部数字与逐日状态checksum；失败即停止。
3. **V1：** 只运行A/B/C三臂；按第6节选择最多1个。无候选过硬门槛即停止并保留BASELINE。
4. **V2：** 只在唯一V1父版本运行P1/P2/P3；选择最多1个。无候选过门槛即回退到V1结论，不执行V3/V4。
5. **V3：** 只在唯一V2父版本运行H1/H2；必须达到专属Churn改善与滞留护栏。
6. **V4：** 只运行D1去重压力测试；若因E4资格导致`DATA_LIMITED`，不得偷偷恢复重复票。
7. **开发集结论：** 最多保留1个`CALIBRATION_CANDIDATE`，生成逐case差分、指标表、Guardrail判定和过拟合审计。
8. **停止。** 不生成正式rule_version、不部署、不自动进入Holdout。Holdout选择、冻结与执行需要单独授权。

任何层没有胜出版本，后续层不执行。禁止回头改变上一层候选定义来“救”结果。

## 14. 最终晋级标准

### 14.1 从规格进入Calibration Execution

满足以下条件即可进入下一轮受控执行：

- 本规格已提交并保持不变；
- 实验实现只新增隔离代码/manifest/报告，不触碰正式规则；
- BASELINE一致性、生产隔离、未来泄漏、三态NULL与Freeze测试可执行；
- 每个候选与停止规则由manifest固定，运行时不能动态新增。

### 14.2 从开发集候选进入Holdout准备

- 唯一候选通过第10节所有硬门槛和所属版本专属门槛；
- 改善覆盖至少2个正例、2个episode，且不依赖单一case；
- 负例M3/M4、matched-lag、Churn、NULL/Freeze全部合格；
- 输出确定性一致，代码审查确认无标签/未来数据输入；
- 候选定义、代码hash、评价脚本和数据资格状态冻结。

### 14.3 从Holdout进入正式新规则评审

- Holdout达到第12.4节门槛且无Guardrail违规；
- 完整warmup资格单独通过，或决策层明确接受`warmup_unqualified`而只做继续研究，不得发布生产；
- 通过后也只是进入“新rule_version/profile评审”，不能直接覆盖当前正式版本。

## 15. 本轮变更边界与Evidence Index

本规格依据既有只读证据：

- `RULE_DIAGNOSTIC_REPORT.md`：成绩单、阻塞、误报路径、滞后、Churn、S3/S4、Top 5候选。
- `REPORT_CLOSEOUT.md`：问题分类、处置边界与完整Evidence Index。
- `diagnostic_summary.json`：BASELINE总指标、版本、Gate与warmup覆盖。
- `rule_discrimination_matrix.csv`：规则通过率、NULL与唯一阻塞。
- `event_blockers.csv`、`case_diagnostics.json.gz`、`atomic_daily_evidence.csv.gz`：案例、状态资格与原子阈值证据。
- `churn_attribution.json`、`persistence_summary.json`、`warmup_security_membership_impact.csv`：横跳、持续性和13项影响。

本轮只允许新增：

- `reports/milestone-d-rule-diagnostic/RULE_CALIBRATION_EXPERIMENT_SPEC.md`
- `reports/milestone-d-rule-diagnostic/rule_calibration_experiment_spec.json`

没有修改正式rule、profile、阈值、状态机、casebook、标签、Production、scheduler、Supabase正式状态、Sites或G1–G4。`RULE CALIBRATION EXECUTION`尚未启动。
