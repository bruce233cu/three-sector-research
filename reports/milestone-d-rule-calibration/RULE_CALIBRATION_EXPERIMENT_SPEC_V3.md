# A股主线识别系统 V2.2.1 — RULE CALIBRATION EXPERIMENT SPEC V3

> **状态：SPECIFICATION_ONLY / NOT_EXECUTED**
>
> **资格：CALIBRATION_ONLY / DIAGNOSTIC_ONLY；G5 = FAIL**
>
> 本规格只冻结三个确认完整性候选。它不修改正式规则、阈值、状态机、profile或Production，不授权运行Holdout。

## 1. Executive Summary

V2已经证明两件事：

1. B不应继续拥有无条件硬否决权。V1-B3把正例事件期S2召回从5/10提高到9/10，原5个命中没有丢失，并挡住了N04的跨分支拼接与N08的低绝对广度脉冲。
2. V1-B3仍会在C为NULL时，用B+Enhancer完成B-present路径，使N02于事件前被确认，给事件窗口增加1个S2暴露日。

因此V3不再调整B阈值，也不碰退出、恢复和S3/S4。本轮只隔离验证两个确认完整性问题：

- **KEY EVIDENCE NULL GATING：** 关键组级证据必须已知；存在NULL时确认计数暂停，不能被其他票补足。
- **SAME-BRANCH PERSISTENCE：** 跨日必须有同一个可审计证据签名持续成立，不允许不同证据组合接力完成确认。

冻结三个平行候选：

| 候选 | 唯一增量 | 主要回答的问题 |
| --- | --- | --- |
| V3-A | V1-B3 + NULL gating | 挡住N02是否只需补齐证据完整性门 |
| V3-B | V1-B3 + same-branch persistence | 证据签名稳定是否能过滤跨日换挡 |
| V3-C | V1-B3 + 两者组合 | 两项约束同时存在时，能否保住召回并通过全部护栏 |

三个候选均独立从V1-B3派生，分别与BASELINE比较；A/B的结果不得改变C的定义。

## 2. 为什么选择V1-B3作为基础候选

V1-B3保留正式五组AND路径，同时把补偿确认拆成两个互斥分支：

- **B-present：** `S1 AND A AND D AND above_ma20>=0.60 AND B AND (C OR Enhancer)`，连续2个有效交易日。
- **B-waived：** `S1 AND A AND D AND above_ma20>=0.60 AND B=FALSE AND C AND Enhancer`，连续3个有效交易日。
- 两个分支拥有独立计数器，不能跨分支累计。

它比B2更适合作为基础，原因不是分数更高，而是结构更可归因：

- P10可通过持续的B-waived路径确认；
- N04从B-present切到B-waived时不能拼接计数，因此未确认；
- N08因`above_ma20<0.60`无法启动补偿路径；
- 唯一已定位缺口是N02在C=NULL时仍能沿B-present确认。

V1-B3仍是实验基础，不是正式规则，也不是Holdout候选。

## 3. 为什么不再调整B

| Case | B表现 | 正确处理 | 说明 |
| --- | --- | --- | --- |
| P10 | B持续FALSE | 应确认 | A/C/D/Enhancer和绝对广度持续共振 |
| N02 | B为TRUE | 应阻断当次确认 | C连续NULL，证据不完整 |
| N04 | B在路径中切换 | 应阻断 | 支撑结构换挡，B3已用分支隔离挡住 |
| N08 | B短暂改善 | 应阻断 | 绝对广度远低于0.60 |

提高B要求会继续漏掉P10；降低B要求会扩大误报。当前分界不在B数值，而在证据是否完整、是否由同一结构持续支持。

## 4. Required-known evidence合同

### 4.1 最终定义

确认S2前，下列**组级输出**必须真实可得：

1. `A`
2. `B`
3. `C`
4. `D`
5. `Enhancer`
6. `above_ma20`

同时沿用输入资格前提：`prior_state=S1`、`critical_data_ok=TRUE`、当前非正式Freeze。

这里要求的是A/B/C/D/Enhancer的组级三态输出已知，不要求每个可选底层原子项都非NULL；只要正式组规则能给出TRUE或FALSE，该组就属于known。`above_ma20`必须是有效数值，不能用0、前值或行业均值填补。

### 4.2 为什么六项都必须known

- A、D和above_ma20是所有补偿路径的核心资格。
- B决定进入B-present还是B-waived，未知时不能选择分支。
- C与Enhancer决定支持证据构成。即使其中另一项已为TRUE，也不能用它掩盖关键组未知；这正是N02漏洞。
- P10确认段六项均已知：B明确为FALSE，A/C/D/Enhancer为TRUE，above_ma20约0.917–0.955，因此不会因为本合同被误伤。

### 4.3 TRUE / FALSE / NULL / Freeze语义

| 输入状态 | confirm_counter | branch/signature | 状态机其他逻辑 |
| --- | --- | --- | --- |
| 所有required-known均已知，分支条件TRUE | 对相应计数器+1 | 记录当日branch/signature | 保持原合同 |
| 所有required-known均已知，分支条件FALSE | 对相应计数器清零 | 该签名失效 | 保持原合同 |
| 任一required-known为NULL | **暂停：不+1、不清零** | 保留暂停前分支/签名，不允许新签名接力 | 不把NULL变成TRUE/FALSE，不自动制造全局Freeze |
| 正式Freeze | 不推进 | 按既有Freeze/恢复合同处理 | 禁止硬转移；V3不改变`reset_after_unverifiable_gap` |

处理优先级固定为：`正式Freeze → required-known NULL gate → 全部known后的TRUE/FALSE分支判定`。如果required-known中同时出现NULL与其他FALSE，本日仍按NULL暂停；只有六项全部known时，FALSE才执行清零。

NULL暂停不增加允许确认所需的有效交易日，也不把两个相隔日期伪装成当天连续；执行报告必须同时输出日历跨度和有效计数日。V3不新增暂停超时参数。

## 5. Same-branch persistence合同

### 5.1 Branch ID

| branch_id | 条件 | 所需有效日 |
| --- | --- | ---: |
| `STANDARD` | 正式`A AND B AND C AND D AND Enhancer` | 2 |
| `B_PRESENT` | 共同安全底座 + B=TRUE +（C或Enhancer） | 2 |
| `B_WAIVED` | 共同安全底座 + B=FALSE + C + Enhancer | 3 |

branch_id之间永不共享confirm_counter。

### 5.2 Evidence signature

仅有branch_id还不够：B-present内部可能第一天靠C、第二天靠Enhancer。V3定义四个可审计签名：

| evidence_signature | 当日可计数条件 |
| --- | --- |
| `STANDARD_ALL` | 正式五组AND为TRUE |
| `B_PRESENT_C` | 共同安全底座、B=TRUE、C=TRUE |
| `B_PRESENT_ENHANCER` | 共同安全底座、B=TRUE、Enhancer=TRUE |
| `B_WAIVED_C_ENHANCER` | 共同安全底座、B=FALSE、C=TRUE、Enhancer=TRUE |

同一天可以有多个签名成立，例如C和Enhancer均为TRUE时，两个B-present签名可分别计数。确认只能由**同一个signature自己的连续计数器**达到门槛；不同signature的天数不得相加。

这样既能阻断“第1天仅靠C、第2天仅靠Enhancer”的拼接，也不会惩罚证据增强：如果第1天C和Enhancer都成立、第2天仅Enhancer成立，`B_PRESENT_ENHANCER`仍是连续稳定证据。

### 5.3 计数规则

- 当日某signature为TRUE：只推进该signature计数器。
- 当日某signature为FALSE且所需证据全部known：该signature计数器清零。
- 当日某signature因required-known为NULL：按候选合同暂停或沿用B3原三态行为，不能从其他signature借天数。
- 状态离开S1、正式生命周期重置或既有恢复合同要求重置时，所有确认signature计数器按原合同清零。
- signature只存在于隔离实验，不新增正式状态字段。

## 6. V3-A — NULL GATING ONLY

| 项目 | 冻结定义 |
| --- | --- |
| 基础 | V1-B3完整结构 |
| 唯一新增 | 六项required-known gating |
| 计数结构 | 仍使用V1-B3的STANDARD、B-present、B-waived独立计数器 |
| NULL | 任一required-known为NULL时，三个确认计数器暂停，不推进、不清零 |
| 不新增 | evidence_signature细分、阈值、确认天数、退出或恢复变化 |
| 主要假设 | N02的失败来自C=NULL被绕过；完整性门足以恢复负例暴露护栏 |
| 预期收益 | N02不再于9月20日确认，同时保留P10的B-waived路径 |
| 主要风险 | NULL较多时确认日历时间变长；暂停后恢复可能保留较旧计数 |
| 过拟合风险 | 中低；规则针对一般证据完整性，不使用case身份 |

V3-A是最值得先测的候选，因为它只改变已证实的N02根因，变更面最小、归因最清楚。

## 7. V3-B — SAME-BRANCH PERSISTENCE ONLY

| 项目 | 冻结定义 |
| --- | --- |
| 基础 | V1-B3完整结构 |
| 唯一新增 | 四个evidence_signature独立计数 |
| NULL | 不增加六项required-known总门；沿用V1-B3三态判定，NULL不计TRUE |
| 主要假设 | 即使branch_id相同，支持项换挡也可能制造伪持续性 |
| 预期收益 | 阻断跨日由不同支持证据接力完成确认 |
| 主要风险 | P10以外的真实主线若支持项频繁轮换，确认可能延迟或丢失 |
| N02预期 | C=NULL但Enhancer持续TRUE时，`B_PRESENT_ENHANCER`仍可能确认，因此V3-B可能触发N02专项失败 |
| 过拟合风险 | 中低；signature是通用证明结构，不依赖case或行业 |

V3-B必须执行以隔离same-branch的独立作用，但不能因为总体指标好就豁免N02专项护栏。

## 8. V3-C — NULL GATING + SAME-BRANCH PERSISTENCE

| 项目 | 冻结定义 |
| --- | --- |
| 基础 | V1-B3完整结构 |
| 新增 | 六项required-known gating + 四个signature独立计数 |
| NULL | 任一required-known为NULL时，全部signature计数器暂停 |
| TRUE/FALSE | 只在六项全部known后生成signature并推进或清零对应计数器 |
| 主要假设 | 证据完整性与结构稳定性是互补护栏 |
| 预期收益 | 同时挡住N02式缺失证据确认与跨日证据换挡 |
| 主要风险 | 三者中确认延迟风险最高，可能降低新增正例召回 |
| 过拟合风险 | 中等；组合复杂度更高，必须由A/B独立臂解释结果 |

V3-C必须独立从V1-B3运行，不得把V3-A或V3-B的运行状态、计数器或临时修补带入。

## 9. 四个哨兵case的预期行为

哨兵case只用于验收和解释，`case_id`、行业、日期、标签不得进入规则输入。

| Case | 结构事实 | V3预期 | 硬验收 |
| --- | --- | --- | --- |
| P10 | B=FALSE；A/C/D/Enhancer与高绝对广度连续成立，required-known完整，固定B-waived签名 | 应继续确认 | 事件期必须HIT；首次事件期S2不得晚于B3参考超过1个交易日，即lag≤+5 |
| N02 | B=TRUE、Enhancer=TRUE，但C连续NULL | NULL gating候选必须暂停，不得确认 | C=NULL期间confirm_counter增量=0、不得`S1→S2`；事件期S2暴露回到BASELINE的0日 |
| N04 | 支持结构发生B-present/B-waived切换，B3已阻断 | 不得重新进入 | 全窗口保持无S2；不同signature不得拼接 |
| N08 | above_ma20仅约0.114–0.143 | 继续由绝对广度底座阻断 | 事件期和全窗口均无S2 |

若总体指标通过但任一哨兵硬验收失败，该候选仍为FAIL。哨兵约束不得通过case特调实现。

## 10. 固定评价指标与成功标准

以下标准原样继承V2，不降低、不事后重定义：

| 维度 | 硬标准 |
| --- | --- |
| 正例事件期S2召回 | ≥6/10；期望7/10–8/10 |
| 正例全窗口S2召回 | ≥7/10 |
| 负例事件期新误确认 | ≤1个case且≤1次转移 |
| 负例事件期S2暴露 | ≤11案例行业日；稳定暴露case≤2 |
| 原BASELINE正例命中 | 原5个事件期HIT全部保留 |
| 多case改善 | ≥2个正例、≥2个episode有利变化，且≥1个MISS→HIT |
| matched-lag | 原命中中位变化≤+1日、均值≤+2日、单例最晚≤+5日 |
| Churn | `S0→S1→S0`≤117；short reversal≤174；reversal≤276；transition≤341 |
| 负例S1滞留 | 总量不得明显增加；单例最长连续S1较BASELINE增加≤3日 |
| NULL / Freeze | NULL填0=0、NULL默认通过=0、Freeze硬转移=0、输入Freeze掩码不变 |
| 合法性 / 确定性 | 非法转移=0、未来读取=0；每臂至少2次重跑且checksum完全一致 |
| 数据资格 | G5继续FAIL；warmup敏感性单列，不得冒充规则改善 |

V3新增且不可替代的专项验收：

1. **NULL gate integrity：** required-known存在NULL时，相关confirm_counter增量必须为0；N02不得因C=NULL完成确认。
2. **Signature integrity：** 任何确认计数均必须由同一`evidence_signature`独立累计；跨signature累计次数必须为0。
3. **P10 retention：** P10事件期继续HIT且较B3确认最多延迟1个交易日。
4. **N04/N08 containment：** 两例不得重新产生全窗口S2。

## 11. Guardrails

以下任一成立，即使召回提高也判该候选FAIL：

- 负例新误确认>1或负例S2暴露>11日；
- 原5个事件期正例丢失任意1个；
- 改善少于2个正例或少于2个episode；
- P10丢失或晚于B3超过1个交易日；
- N02在C=NULL期间推进确认或事件期仍出现候选新增的S2暴露；
- N04/N08重新出现全窗口S2；
- 不同branch/signature天数被相加；
- NULL被转为0、FALSE或TRUE；NULL暂停时计数被无合同依据地清零；
- Freeze、退出、恢复、S3/S4行为发生变化；
- Churn、负例S1滞留或确认滞后突破第10节上限；
- 确定性、PIT、数据资格或未来数据读取合同失败；
- 改善主要依赖单一case、单一episode或直接warmup敏感case。

## 12. Stop Rule与选择顺序

### 12.1 执行级停止

1. BASELINE不能精确复现`5/10、6/10、1、11日、117、174、276、341`：停止全部V3实验。
2. V1-B3参考臂不能精确复现`9/10事件期、9/10全窗口、1个新误确认、12日暴露`及既有checksum：停止全部V3实验。
3. 输入、casebook、profile、日历、warmup资格或冻结代码hash漂移：停止并标记`BLOCKED BY DATA / BASELINE DRIFT`。
4. 单个V3候选失败：记录失败原因，继续下一个平行候选；不得现场修补。
5. 三个候选均失败：`NO CANDIDATE PASSED`。
6. 至少一个通过：`CALIBRATION CANDIDATE FOUND — HOLDOUT REQUIRED`，停止，不自动运行Holdout。

### 12.2 多候选通过时的固定选择顺序

依次比较：

1. 专项验收全部通过；
2. 更少负例新确认；
3. 更少负例S2暴露；
4. 更高事件期召回，再看全窗口召回；
5. 更早确认、更低Churn和更少负例S1滞留；
6. 完全并列时选择变更面更小者：`V3-A → V3-B → V3-C`。

不使用事后综合分，不因只差1日而放宽Guardrail。

## 13. 下一轮执行顺序

```text
BASELINE一致性复现
  → V1-B3参考臂复现
  → V3-A（独立从B3定义运行，与BASELINE比较）
  → V3-B（独立从B3定义运行，与BASELINE比较）
  → V3-C（独立从B3定义运行，与BASELINE比较）
  → 固定顺序选最多1个候选
  → STOP
```

V3-A最值得先测，因为它是针对N02已验证根因的最小单变量修改；V3-B负责隔离结构稳定性的独立价值；V3-C验证组合副作用。执行顺序不代表预设胜者。

每个臂必须输出：总体指标、逐case变化、逐日branch/signature、required-known NULL、各signature计数器、确认滞后、负例暴露、S1滞留、Churn、Freeze、warmup敏感性及两次确定性checksum。

## 14. Warmup隔离

- G5继续FAIL，全部结果标记`CALIBRATION_ONLY / DIAGNOSTIC_ONLY`。
- P01、P06、P07、N05、N06、A01继续作为直接warmup敏感case单列。
- 主结果仍使用25例开发/诊断集；敏感性结果不能替代主结果。
- 若改善只来自warmup敏感case，候选不得晋级。
- V3不得用规则变化掩盖84日warmup资格缺口。

## 15. 变更边界与Evidence Index

本规格依据：

- `V2_FAILURE_ATTRIBUTION_REPORT.md`
- `CALIBRATION_EXECUTION_REPORT_V2.md`
- `calibration_results_v2.json`
- `version_comparison_v2.csv`
- `case_level_delta_v2.csv`
- `state_transition_delta_v2.csv`
- `experiment_manifest_v2.json`
- `deterministic_rerun_v2.json`
- `RULE_CALIBRATION_EXPERIMENT_SPEC_V2.md`及其JSON合同

本轮只新增本规格及机器可读JSON。没有运行实验，没有修改正式rule_version、parameter_profile、阈值、状态机、weaken、retire、recover、S2→S3、S3→S2、S4、casebook、Production、scheduler、Sites或G1–G4。
