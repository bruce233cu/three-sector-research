# A股主线识别系统 V2.2.1 — RULE CALIBRATION EXECUTION REPORT V2

> **结论：NO CANDIDATE PASSED**
> **资格：CALIBRATION_ONLY / DIAGNOSTIC_ONLY；G5 = FAIL**
> 本报告仅代表25例开发/诊断集，不是Holdout、生产准确率或上线授权。

## 1. Baseline复现

BASELINE **PASS**：事件期正例S2 5/10，全窗口 6/10；负例新误确认 1，负例S2暴露 11日；`S0→S1→S0`=117，short reversal=174。逐日状态与归档完全一致。

## 2. 三个平行候选结果

| 候选 | 结论 | 事件期正例 | 全窗正例 | 新增正例 | 负例新确认 | 负例S2日 | S0→S1→S0 | short reversal | transition | 负例S1日 |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V1_B2_BREADTH_QUALIFIED_WEIGHTED | FAIL | 9/10 | 10/10 | P01、P03、P09、P10 | 1 | 12 | 79 | 135 | 337 | 10 |
| V1_B3_ASYMMETRIC_B_ROLE | FAIL | 9/10 | 9/10 | P01、P03、P09、P10 | 1 | 12 | 97 | 154 | 340 | 21 |
| V1_B4_THREE_DAY_STAGED_CONFIRMATION | FAIL | 7/10 | 7/10 | P09、P10 | 2 | 14 | 101 | 156 | 336 | 14 |

## 3. Case级召回、误报与滞后

### V1_B2_BREADTH_QUALIFIED_WEIGHTED

- 新增事件期正例：P01、P03、P09、P10；丢失原命中：无。
- 新增负例误确认：无；全部负例新确认：N10。
- 事件期正例确认滞后：均值 1.56，中位数 1；逐case：{'P01': 1, 'P02': 19, 'P03': 1, 'P04': -13, 'P05': 14, 'P06': -1, 'P07': -5, 'P08': -12, 'P09': 26, 'P10': 3}。
- 原5例matched-lag变化：均值 -3.40，中位数 0；逐case：{'P04': -16, 'P05': 0, 'P06': 0, 'P07': -1, 'P08': 0}。
- 有利变化case：P01、P03、P04、P09、P10；episode：二季度轮动、秋季及消费红利、秋季政策行情。
- 失败检查：negative_s2_case_days_max_11。

### V1_B3_ASYMMETRIC_B_ROLE

- 新增事件期正例：P01、P03、P09、P10；丢失原命中：无。
- 新增负例误确认：无；全部负例新确认：N10。
- 事件期正例确认滞后：均值 1.78，中位数 1；逐case：{'P01': 1, 'P02': None, 'P03': 1, 'P04': -13, 'P05': 14, 'P06': -1, 'P07': -5, 'P08': -12, 'P09': 27, 'P10': 4}。
- 原5例matched-lag变化：均值 -3.40，中位数 0；逐case：{'P04': -16, 'P05': 0, 'P06': 0, 'P07': -1, 'P08': 0}。
- 有利变化case：P01、P03、P04、P09、P10；episode：二季度轮动、秋季及消费红利、秋季政策行情。
- 失败检查：negative_s2_case_days_max_11。

### V1_B4_THREE_DAY_STAGED_CONFIRMATION

- 新增事件期正例：P09、P10；丢失原命中：无。
- 新增负例误确认：N04；全部负例新确认：N04、N10。
- 事件期正例确认滞后：均值 2.29，中位数 -1；逐case：{'P01': None, 'P02': None, 'P03': None, 'P04': -12, 'P05': 14, 'P06': -1, 'P07': -4, 'P08': -12, 'P09': 27, 'P10': 4}。
- 原5例matched-lag变化：均值 -3.00，中位数 0；逐case：{'P04': -15, 'P05': 0, 'P06': 0, 'P07': 0, 'P08': 0}。
- 有利变化case：P04、P09、P10；episode：二季度轮动、秋季及消费红利。
- 失败检查：negative_new_s2_cases_max_1、negative_new_s2_transitions_max_1、negative_s2_case_days_max_11、negative_stable_s2_cases_max_2。

## 4. P10 与 N08 完整路径差异

### P10

| Arm | 确认日 | 事件期结论 | 关键路径 |
| --- | --- | --- | --- |
| BASELINE | 2025-06-27 | 未确认 | 正式五组AND未连续满足，事件期未确认 |
| V1_B2_BREADTH_QUALIFIED_WEIGHTED | 2025-05-09、2025-06-26 | S2 | 高绝对广度下A/C/D/Enhancer持续成立，按预注册补偿路径完成确认 |
| V1_B3_ASYMMETRIC_B_ROLE | 2025-05-12、2025-06-27 | S2 | 高绝对广度下A/C/D/Enhancer持续成立，按预注册补偿路径完成确认 |
| V1_B4_THREE_DAY_STAGED_CONFIRMATION | 2025-05-12、2025-06-27 | S2 | 高绝对广度下A/C/D/Enhancer持续成立，按预注册补偿路径完成确认 |

### N08

| Arm | 确认日 | 事件期结论 | 关键路径 |
| --- | --- | --- | --- |
| BASELINE | 无 | 未确认 | 正式路径未连续满足 |
| V1_B2_BREADTH_QUALIFIED_WEIGHTED | 无 | 未确认 | above_ma20未达到0.60，补偿路径不启动；随后A/D失效 |
| V1_B3_ASYMMETRIC_B_ROLE | 无 | 未确认 | above_ma20未达到0.60，补偿路径不启动；随后A/D失效 |
| V1_B4_THREE_DAY_STAGED_CONFIRMATION | 无 | 未确认 | above_ma20未达到0.60，补偿路径不启动；随后A/D失效 |

P10在事件启动阶段的above_ma20约为0.917–0.955，并且A/C/D/Enhancer连续成立；N08同期above_ma20仅约0.114–0.143，即使相对扩张D短暂为TRUE，也没有通过绝对广度底座。详细逐日A/B/C/D/Enhancer、above_ma20、S1、计数器、pending及状态转移保存在`calibration_results_v2.json`的`focus_case_paths`。

## 5. NULL、Freeze、Warmup与确定性

- **V1_B2_BREADTH_QUALIFIED_WEIGHTED：** NULL观察56次，NULL推进违规0；Freeze转移违规0；输入Freeze掩码不变；两次checksum一致=True。
- **V1_B3_ASYMMETRIC_B_ROLE：** NULL观察68次，NULL推进违规0；Freeze转移违规0；输入Freeze掩码不变；两次checksum一致=True。
- **V1_B4_THREE_DAY_STAGED_CONFIRMATION：** NULL观察77次，NULL推进违规0；Freeze转移违规0；输入Freeze掩码不变；两次checksum一致=True。
- P01、P06、P07、N05、N06、A01继续标记为直接warmup敏感；完整84日warmup资格仍未通过。
- 候选改善不能被解释为生产准确率，且不得用规则变化掩盖G5失败。

## 6. 候选选择

- **PRIMARY CALIBRATION CANDIDATE：** 无。
- **BACKUP CANDIDATE：** 无。
- 选择顺序严格按冻结合同：负例新确认 → S2暴露 → 召回 → 滞后 → Churn/滞留 → 复杂度。

## 7. 最终判定

BASELINE已复现，但三个预注册候选均未通过全部硬门槛；没有Holdout候选。

本轮没有修改正式rule_version、parameter_profile、阈值、状态机、casebook、Production、scheduler、Supabase正式状态或Sites；没有运行Holdout。
