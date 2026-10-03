# A股主线识别系统 V2.2.1 — RULE CALIBRATION EXPERIMENT SPEC V4

> **状态：FINAL_BOUNDED_SPECIFICATION_ONLY / NOT_EXECUTED**
>
> **资格：CALIBRATION_ONLY / DIAGNOSTIC_ONLY；G5 = FAIL**
>
> 这是当前25个Development / Diagnostic cases上的最后一轮有限结构校准规格。本轮只冻结V4-A、V4-B、V4-C，不修改正式规则，不授权运行Holdout。

## 1. Executive Summary

V3已经把剩余确认缺口压缩为两个可验证问题：

1. **NULL后旧计数仍可接续。** V3-A/C在C为NULL时没有推进计数，但保留了9月24日的旧计数；9月30日数据恢复后继续累计，N02仍被确认。说明“暂停但保留”不符合连续证据语义。
2. **B-present仍允许绕过C。** V3-B要求同一证据签名持续，但`B_PRESENT_ENHANCER`可在C=NULL时连续成立，N02仍于9月20日确认。说明B强与Enhancer强不能替代成交确认C。

V4只验证两个有限修正：

- required-known出现NULL时，立即切断本轮确认连续链，恢复后从1重新计数；
- B-present只有在C真实可得且为TRUE时才能计数和确认。

| 候选 | 唯一增量 | 主要回答的问题 |
| --- | --- | --- |
| V4-A | NULL打断确认连续性 | 清除旧计数能否阻止N02跨NULL接续确认 |
| V4-B | B-present强制C=TRUE | 成交确认能否挡住“B强但C不足/未知”的假确认 |
| V4-C | 两项同时启用 | 两个约束是否互补，并在不伤害P10的前提下通过全部护栏 |

三个候选彼此平行，独立从统一基础结构运行，分别与BASELINE比较。不得根据A/B结果修改C。

## 2. V3事实基础与不再讨论的方向

| 版本 | 正例事件期S2 | 正例全窗S2 | 负例新确认 | 负例S2暴露 | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| BASELINE | 5/10 | 6/10 | 1 | 11日 | 对照组 |
| V3-A | 8/10 | 8/10 | 1 | 13日 | NULL旧计数接续导致失败 |
| V3-B | 9/10 | 9/10 | 1 | 12日 | C可被Enhancer绕过导致失败 |
| V3-C | 8/10 | 8/10 | 1 | 13日 | 两个缺口未被同时封住 |

已排除的方向：

- 不继续调整A/B/C/D/Enhancer或above_ma20阈值；
- 不新增指标，不延长机械等待，不修改退出、恢复、S3/S4；
- 不删除B，也不恢复五组全AND硬否决；
- 不使用case、行业、日期或标签作为规则输入；
- 不因只差1—2个负例暴露日而放宽Guardrail。

## 3. 统一基础结构

三个V4候选共同继承以下实验结构：

### 3.1 V1-B3确认路径

- **STANDARD：** `A AND B AND C AND D AND Enhancer`，连续2个有效交易日。
- **B-present：** 共同安全底座为`S1 AND A AND D AND above_ma20>=0.60 AND B=TRUE`，连续2个有效交易日；C的角色由候选定义。
- **B-waived：** `S1 AND A AND D AND above_ma20>=0.60 AND B=FALSE AND C AND Enhancer`，连续3个有效交易日。
- STANDARD、B-present、B-waived计数相互独立，不跨分支借用天数。

### 3.2 Same-branch / evidence-signature

保留V3已经验证合理的证据签名机制：

| evidence_signature | 证据结构 | 所需有效日 |
| --- | --- | ---: |
| `STANDARD_ALL` | 正式五组AND | 2 |
| `B_PRESENT_C` | 安全底座 + B=TRUE + C=TRUE | 2 |
| `B_PRESENT_ENHANCER` | 安全底座 + B=TRUE + Enhancer=TRUE | 2 |
| `B_WAIVED_C_ENHANCER` | 安全底座 + B=FALSE + C=TRUE + Enhancer=TRUE | 3 |

- 每个signature拥有独立计数器；只有同一signature自身达到门槛才可确认。
- 不同signature、不同branch的天数不得相加。
- 同一天可记录多个真实成立的signature，但不能形成重复票数。
- V4-B/C中`B_PRESENT_ENHANCER`只保留为审计证据，不再具有确认计数权；它不能替代`B_PRESENT_C`。
- signature只存在于隔离实验，不新增正式状态字段。

### 3.3 Required-known集合保持冻结

确认前必须真实可得的组级证据仍为：

1. A
2. B
3. C
4. D
5. Enhancer
6. above_ma20

不要求每个可选原子项均非NULL；只要求正式组规则能够给出TRUE或FALSE。`above_ma20`必须是有效数值，禁止填0、沿用前值或用其他行业补值。

## 4. FALSE / NULL / FREEZE语义

| 状态 | 确认计数 | S1状态 | 其他状态机逻辑 |
| --- | --- | --- | --- |
| 所有required-known已知且signature=TRUE | 对相应signature计数器+1 | 保持原合同 | 达到门槛才可确认 |
| 所有required-known已知且signature=FALSE | 清零该signature相关计数 | 不因本条单独退出S1 | 保持原合同 |
| required-known任一项=NULL，V4-A/C | **所有本轮确认signature计数立即清零** | 不退出S1 | 不转成FALSE，不制造全局Freeze |
| required-known任一项=NULL，V4-B | 沿用V3的暂停保留，用于隔离C=TRUE约束的独立作用 | 不退出S1 | 不转成默认通过或全局Freeze |
| 正式Freeze | 按既有Freeze/恢复合同暂停或在不可验证缺口后重置 | 不发生硬转移 | V4不修改正式Freeze合同 |

处理优先级固定为：`正式Freeze → required-known NULL合同 → 全部known后的signature TRUE/FALSE`。

V4-A/C的NULL清零只代表“连续确认链中断”，不代表数据为FALSE，不触发`S1→S0`，也不改变candidate、weaken、retire或recover证据。

## 5. V4-A — NULL BREAKS CONFIRMATION CONTINUITY

| 项目 | 冻结定义 |
| --- | --- |
| 基础 | 统一基础结构，含same-branch和四类signature |
| 唯一新增 | required-known出现NULL时，所有确认signature计数立即清零 |
| 数据恢复 | 下一次全部known且某signature为TRUE时，该signature从`1`重新开始 |
| B-present | 仍允许`C OR Enhancer`，用于隔离NULL连续性修复的独立作用 |
| 不改变 | 阈值、确认天数、candidate、退出、恢复、S3/S4 |
| 主要假设 | N02依赖9月24日旧计数跨NULL接续；清除旧链即可阻断9月30日确认 |
| 主要风险 | 真主线在短暂数据缺失后需重新积累，可能延迟或损失P01等NULL较多案例 |
| 过拟合风险 | 中低；规则是通用连续性语义，不依赖case身份 |

V4-A必须记录每次NULL中断前后的所有signature计数，并证明恢复首日最大计数只能为1。

## 6. V4-B — B-PRESENT PATH REQUIRES C=TRUE

| 项目 | 冻结定义 |
| --- | --- |
| 基础 | 统一基础结构，含same-branch；NULL沿用V3暂停保留以隔离单变量 |
| 唯一新增 | B-present只有`C=TRUE`时才具有确认资格 |
| C=NULL | B-present不得计数、不得确认；由required-known门处理 |
| C=FALSE | B-present相关计数清零，不得由B、Enhancer、A或D补足 |
| eligible signature | `B_PRESENT_C`；`B_PRESENT_ENHANCER`仅审计、不得投票 |
| B-waived | 保持`B=FALSE AND C AND Enhancer`连续3日，不变 |
| 主要假设 | N02属于“B强、Enhancer强，但成交确认C不足或未知”的假确认 |
| 主要风险 | C偏慢或短暂波动的真主线可能延迟确认，需重点检查正例召回与lag |
| 过拟合风险 | 中等；C是通用成交确认组，但其判别力此前有限，必须由多case结果证明 |

V4-B禁止把C=known-but-FALSE解释为可由Enhancer替代；这正是与V3-B的结构差异。

## 7. V4-C — COMBINED

| 项目 | 冻结定义 |
| --- | --- |
| 基础 | 统一基础结构 |
| 新增一 | 任一required-known为NULL时，所有确认signature计数清零 |
| 新增二 | B-present必须C=TRUE，`B_PRESENT_ENHANCER`不得投票 |
| 数据恢复 | 全部known且合格的同一signature从1重新计数 |
| 不新增 | 任何阈值、指标、分支、状态、等待天数或例外 |
| 主要假设 | N02同时利用旧计数接续与C绕过；两道约束共同封闭确认漏洞 |
| 主要风险 | 三者中最严格，可能损失NULL敏感正例或增加确认滞后 |
| 过拟合风险 | 中等；组合复杂度最高，必须由A/B独立臂解释增量价值 |

V4-C必须独立从统一基础结构运行，不能继承V4-A/B的运行状态或临时补丁。

## 8. 四个哨兵case的预期行为

哨兵只用于验收和解释，不得作为规则输入。

| Case | 已知结构 | V4预期 | 硬验收 |
| --- | --- | --- | --- |
| P10 | B持续FALSE；A/C/D/Enhancer和绝对广度持续为真；走B-waived固定签名 | V4-A不遇关键NULL链；V4-B不修改B-waived；V4-C同理 | 事件期继续HIT，lag≤+5且较B3最多晚1个交易日 |
| N02 | B与Enhancer强；C在多日为NULL，恢复日为FALSE；V3曾跨NULL接续 | V4-A在9月25日NULL时清除9月24日旧计数；V4-B因C不为TRUE拒绝B-present；V4-C同时阻断 | C=NULL或FALSE期间不得完成B-present；事件期S2暴露=0 |
| N04 | B-present/B-waived与证据构成发生切换 | same-branch继续阻断跨分支/跨signature拼接 | 全窗口无S2 |
| N08 | above_ma20显著低于0.60 | 共同安全底座继续阻断 | 事件期和全窗口均无S2 |

执行报告必须逐日输出四例在BASELINE、B3参考、V4-A/B/C下的A/B/C/D/Enhancer、above_ma20、required-known、signature、计数器前后、NULL中断、确认与状态路径。

## 9. 固定评价指标与成功标准

以下标准原样继承，不得在执行中或看到结果后降低：

| 维度 | 硬标准 |
| --- | --- |
| 正例事件期S2召回 | ≥6/10；期望7/10–8/10 |
| 正例全窗口S2召回 | ≥7/10 |
| 负例事件期新误确认 | ≤1个case且≤1次转移 |
| 负例事件期S2暴露 | ≤11案例行业日；稳定暴露case≤2 |
| 原BASELINE正例命中 | 原5个事件期HIT全部保留 |
| 多case改善 | ≥2个正例、≥2个独立episode有利变化，且≥1个MISS→HIT |
| matched-lag | 原命中中位变化≤+1日、均值≤+2日、单例最晚≤+5日 |
| Churn | `S0→S1→S0`≤117；short reversal≤174；reversal≤276；transition≤341 |
| 负例S1滞留 | 总量不得明显增加；单例最长连续S1较BASELINE增加≤3日 |
| NULL / Freeze | NULL填0=0、NULL默认通过=0、Freeze硬转移=0、输入Freeze掩码不变 |
| 合法性 / 确定性 | 非法转移=0、未来读取=0；每臂至少2次重跑且checksum完全一致 |
| 数据资格 | G5继续FAIL；warmup敏感性必须单列 |

V4专项成功标准：

1. N02不得通过NULL前旧计数完成确认；V4-A/C每次required-known NULL后所有确认计数必须为0。
2. C=NULL不得通过B-present；V4-B/C中C=FALSE也不得通过B-present。
3. 跨branch、跨evidence_signature累计次数必须为0。
4. P10事件期继续HIT且不突破lag护栏。
5. N04全窗口无S2。
6. N08事件期和全窗口无S2。

任一专项标准失败，即使总召回提高，该候选仍为FAIL。

## 10. Guardrails

以下任一情况直接判FAIL：

- 负例新误确认>1或负例S2暴露>11日；
- 原5个事件期正例丢失任意1个；
- 改善少于2个正例或少于2个episode；
- P10丢失或晚于B3超过1个交易日；
- N02在C=NULL/FALSE期间通过B-present，或事件期仍有候选新增S2暴露；
- V4-A/C在NULL后保留任何确认计数，或恢复首个合格日计数不从1开始；
- N04/N08重新出现全窗口S2；
- 不同branch/signature天数相加；
- NULL被填0、转TRUE/FALSE或自动制造全局Freeze；
- candidate、退出、恢复、S3/S4或正式Freeze合同发生变化；
- Churn、S1滞留或确认滞后突破第9节上限；
- 确定性、PIT、输入资格、未来数据读取或非法转移合同失败；
- 改善主要依赖单一case、单一episode或仅来自warmup敏感case。

## 11. 执行顺序与候选选择

下一轮只能按以下顺序执行：

```text
BASELINE等价复现
  → V1-B3参考臂等价复现
  → 校验既有V3归档与checksum（不重跑V3）
  → V4-A（独立运行，对比BASELINE）
  → V4-B（独立运行，对比BASELINE）
  → V4-C（独立运行，对比BASELINE）
  → 固定顺序选择最多1个候选
  → FINAL STOP
```

单个候选失败不阻止其他平行候选，但禁止现场修改后重跑，禁止追加V4-D/E。

若多个候选通过，固定选择顺序为：

1. 所有专项验收通过；
2. 更少负例新确认；
3. 更少负例S2暴露；
4. 更高事件期召回，再看全窗口召回；
5. 更早确认、更低Churn、更少负例S1滞留；
6. 完全并列时按更小变更面优先：`V4-A → V4-B → V4-C`。

## 12. FINAL BOUNDED CALIBRATION Stop Rule

本节为硬合同，不得在执行后改写：

### 12.1 至少一个候选完整PASS

- 最终结论：`CALIBRATION CANDIDATE FOUND — HOLDOUT REQUIRED`；
- 只允许选择最多一个PRIMARY和一个BACKUP；
- 停止开发集调参，不得发布正式规则；
- G5仍为FAIL，只有在独立Holdout设计与数据资格边界明确后，才允许讨论下一步验证。

### 12.2 三个候选全部FAIL

- 最终结论：`NO CANDIDATE PASSED — DEVELOPMENT SET CALIBRATION CLOSED`；
- **永久停止围绕当前25例新增V5/V6、阈值微调、结构补丁或case定制；**
- 当前25例继续保留为Development / Diagnostic Set，不得再用于证明新版本准确；
- 下一阶段只能转向以下三类工作之一：
  1. 数据资格：完成84日warmup认证，区分数据未知与规则失败；
  2. 样本扩充：增加新episode和不同市场风格，但不得把新增样本立即变成新的追调集；
  3. 规则框架重审：重新检验S2确认目标、证据家族与标签定义，而不是继续修补当前结构。
- 禁止自动运行Holdout，因为没有可送检候选。

### 12.3 Baseline、B3参考或数据合同漂移

- 立即停止所有V4候选；
- 标记`BLOCKED BY DATA / BASELINE DRIFT`；
- 只修复数据、归档或运行等价问题，不得带着漂移继续校准。

## 13. Warmup与Holdout隔离

- G5继续FAIL，全部结果必须标记`CALIBRATION_ONLY / DIAGNOSTIC_ONLY`。
- P01、P06、P07、N05、N06、A01继续作为直接warmup敏感case单列。
- 若改善只来自warmup敏感case，候选不得晋级。
- 当前25例永久属于Development / Diagnostic Set。
- V4执行不等于Holdout；即使候选通过，也只能进入“独立Holdout待设计/待执行”。
- 禁止宣称生产准确率提高、正式规则优化完成或可以上线。

## 14. 变更边界与Evidence Index

本规格依据：

- `RULE_CALIBRATION_EXPERIMENT_SPEC_V3.md`
- `CALIBRATION_EXECUTION_REPORT_V3.md`
- `calibration_results_v3.json`
- `version_comparison_v3.csv`
- `case_level_delta_v3.csv`
- `state_transition_delta_v3.csv`
- `experiment_manifest_v3.json`
- `deterministic_rerun_v3.json`
- `V2_FAILURE_ATTRIBUTION_REPORT.md`

本轮只新增V4规格及机器可读合同。没有执行V4，没有修改正式rule_version、parameter_profile、任何阈值、状态机、casebook、Production、scheduler、Sites、Supabase正式业务状态或G1–G4。
