# A股主线识别系统 V2.2.1 — Independent Holdout Design

> **状态：DESIGN COMPLETE / CASEBOOK NOT FROZEN / HOLDOUT NOT EXECUTED**
>
> 候选：`v4a_calibration_candidate_v1`（`CALIBRATION_CANDIDATE / FROZEN`）
>
> 数据资格：G5 `CONDITIONAL PASS`，仅在认证边界内允许设计与逐例资格复核。

## 1. 一句话结论

本轮已经冻结一套“一次性、按episode隔离、先标签后运行”的独立Holdout合同，目标样本为10个正例、10个负例、5个模糊例；由于尚未完成独立标签双审、Development episode registry和逐例warmup资格审查，`holdout_casebook_v1`本轮不冻结，也没有运行BASELINE或V4-A。

## 2. 验证对象与不可变边界

| 项目 | 冻结值 |
|---|---|
| candidate | `v4a_calibration_candidate_v1` |
| candidate status | `CALIBRATION_CANDIDATE / FROZEN` |
| baseline rule | `mainline_v2.2.1_state_completion_v1` |
| baseline profile | `industry_trend_v221_state_completion_v1` |
| Development set | `casebook_v1_20261002_25`，永久禁止进入Holdout |
| Development checksum | `249799d4c82ee067c4450e58d3409c661e2afb0dc7ff0339ae277f0f6d69c47d` |
| warmup data version | `warmup_data_version_v2_1b7b20d9f8470f29` |
| PIT | `effective_pit`；`knowledge_time_verified=false` |
| Production | `PRODUCTION_MAINLINE_ENABLED=false`；`MAINLINE_LIVE=false` |

Holdout只验证已冻结候选，不允许改变NULL、confirm counter、same-branch、A/B/C/D/Enhancer、阈值、退出/恢复或S3/S4。任何候选代码、依赖、数据版本或成功标准变化，都使尚未执行的casebook需要重新审计；执行后则必须启用全新的Holdout。

## 3. 样本规模与覆盖

最终可执行casebook最低为25个合格新case：

| 标签 | 最低数量 | 主要用途 |
|---|---:|---|
| positive | 10 | 事件期/全窗口S2召回、确认滞后 |
| negative | 10 | 新误确认、S2暴露、假主线类型 |
| ambiguous | 5 | 边界路径、稳定性和可解释性；不进入主Recall/FP分母 |

不为凑数降低标签、独立性或数据资格。冻结前可增加样本；一旦冻结不得删除、替换或改窗。样本覆盖至少包括科技成长、制造、消费、金融、周期五类中的四类，且正例必须覆盖至少四类主线形态、三个市场环境；负例尽量覆盖八类预注册假主线。

## 4. 独立性单位：episode而不是日期行

`episode_id`由`taxonomy_code + causal_cluster + uninterrupted_market_regime`构成。满足任一条件即视为同一episode，不得拆分：

1. 事件窗或case窗重叠；
2. 同一行业、同一催化/叙事，两个窗口间隔少于20个交易日且没有明确趋势断裂；
3. 虽为不同行业，但属于同一政策冲击或同一跨行业行情，且价格与市场复盘指向同一轮共识形成；
4. 只是提前、延后、缩短或扩展Development窗口。

Holdout episode与任何Development/Diagnostic/Calibration episode之间必须留出至少20个交易日缓冲，并通过语义催化审查。20日缓冲不是充分条件；相同叙事和连续行情即使超过20日仍判同episode。二波只有在中间存在至少20个交易日、相对趋势与成交均显著退潮，并有独立新催化时，才可作为新episode候选。

## 5. 盲态选择与冻结顺序

严格顺序如下，任何越序都构成污染：

1. 建立Development episode registry，登记25例及所有P10/N02/N04/N08等校准引用。
2. 仅依据独立历史事实生成候选池；禁止读取任何V4-A状态、counter或命中结果。
3. 两名独立复核者按标签合同分别给出标签、窗口、理由和证据；冲突交第三人裁决。
4. 执行episode隔离和历史报告引用扫描；污染case永久剔除并保留剔除记录。
5. 对拟入选case逐例执行G5资格预检；不合格case在冻结前替换，替换者重新走完整流程。
6. 固定标签、窗口、episode、样本名单、Warmup资格、成功标准和全部checksum。
7. 生成`holdout_casebook_v1.json/.csv`及manifest，提交到独立commit并签署`FROZEN_NOT_EXECUTED`。
8. 另起执行阶段，一次性运行同一输入上的BASELINE与V4-A；不得预览中间case结果后停止或换样本。

## 6. 标签、数据与防污染合同

- 标签标准见`holdout_labeling_contract.md`；不使用V4-A内部组规则或状态输出定义标签。
- 选择步骤见`holdout_selection_protocol.md`。
- 污染审计见`holdout_contamination_audit_spec.md`。
- Warmup准入见`holdout_warmup_eligibility_contract.md`。
- Casebook字段和不可变约束见`holdout_casebook_schema.json`。
- PASS/FAIL精确门槛见`holdout_success_criteria.json`。

## 7. 一次性执行与结果解释

同一casebook只能正式执行一次。开始执行的定义是：任一正式case的BASELINE或V4-A状态结果被计算或查看。此后casebook标记`CONSUMED`，无论PASS、FAIL、INCONCLUSIVE都不得再次作为纯Holdout。

执行必须同时输出绝对表现和同一Holdout上的BASELINE对照，包括：事件期/全窗召回、新误确认、负例S2暴露、逐例lag、原始路径、四类churn、NULL/Freeze、资格和确定性。模糊样本单列，不进入主要分母。

最终结论只能是：

- `HOLDOUT PASS`：所有最低业务标准、增量价值和合同护栏均通过；可另行讨论候选晋级，但不自动上线。
- `HOLDOUT FAIL`：数据与独立性有效，但任一最低业务标准或候选合同失败。表现不好不得写成INCONCLUSIVE。
- `HOLDOUT INCONCLUSIVE`：仅限执行前/执行中发现不可修复的数据版本、资格、标签冲突、外部数据不可用或独立性破坏；不得调整分母后继续。

## 8. 冻结门（下一阶段）

只有下列项目全部完成，才允许`HOLDOUT CASEBOOK FREEZE`：

- 至少10/10/5个case全部通过独立双审；
- Development episode registry完成；
- contamination audit为0个未解决问题；
- 每例G5资格为`QUALIFIED`；
- 市场风格与形态覆盖达到预注册下限；
- casebook、证据索引、数据版本、候选commit和成功标准checksum已锁定；
- 审计确认未运行或查看V4-A Holdout输出。

当前只满足设计前置条件，因此下一步是`HOLDOUT CASEBOOK FREEZE`，不是`HOLDOUT EXECUTION`。

## 9. 审计声明

本轮没有运行Holdout、BASELINE Holdout comparator或V4-A；没有选择最终case、修改V4-A、正式rule version、parameter profile、Production、scheduler或Sites生产逻辑。
