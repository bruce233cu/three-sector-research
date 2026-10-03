# A股主线识别系统 V2.2.1 — RULE CALIBRATION EXECUTION REPORT V4

## Technical Summary

**最终结论：CALIBRATION CANDIDATE FOUND — HOLDOUT REQUIRED。**

至少一个预注册V4候选通过全部业务与专项护栏；候选仅可进入独立Holdout，不能发布正式规则。

本轮严格执行最终有限规格；结果仅适用于25例Development / Diagnostic Set。G5仍为FAIL，资格保持`CALIBRATION_ONLY / DIAGNOSTIC_ONLY`，不构成生产准确率、正式规则优化或上线授权。

## Baseline与执行边界均未漂移

BASELINE **PASS**：事件期正例5/10，全窗口6/10；负例新确认1，负例S2暴露11日；`S0→S1→S0`=117，short reversal=174。
V1-B3参考臂 **PASS**：9/10、9/10、1、12日及既有checksum全部一致。既有V3归档校验=PASS，未重跑V3。

## 三个平行候选的结果

| 候选 | 结论 | 事件期正例 | 全窗正例 | 新增命中 | 丢失命中 | 负例新确认 | 负例S2日 | S0→S1→S0 | short reversal | transition |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| V4_A_NULL_BREAKS_CONFIRMATION_CONTINUITY | PASS | 8/10 | 8/10 | P03、P09、P10 | 无 | 1 | 11 | 106 | 166 | 340 |
| V4_B_B_PRESENT_REQUIRES_C_TRUE | FAIL | 6/10 | 6/10 | P10 | 无 | 1 | 11 | 113 | 170 | 339 |
| V4_C_COMBINED | FAIL | 6/10 | 6/10 | P10 | 无 | 1 | 11 | 113 | 170 | 339 |

以上候选均独立从同一V1-B3 + same-branch基础运行，并分别与BASELINE比较；不存在A叠加B或根据中间结果修改C。

## 每个候选为何通过或失败

### V4_A_NULL_BREAKS_CONFIRMATION_CONTINUITY

- **业务结果：** 事件期/全窗正例=8/10、8/10；新增命中=P03、P09、P10；丢失=无。
- **负例变化：** 新增误确认=无；减少误确认=无；总新确认=1；S2暴露=11日。
- **确认滞后：** 均值/中位数=1.88/0.0；matched变化=-3.40/0；逐case=`{'P01': None, 'P02': None, 'P03': 1, 'P04': -13, 'P05': 14, 'P06': -1, 'P07': -5, 'P08': -12, 'P09': 27, 'P10': 4}`。
- **Churn：** `S0→S1→S0`=106；short reversal=166；reversal=267；transition=340；负例S1日=22。
- **确认完整性：** NULL日=257；断链日=257；旧计数残留违规=0；恢复首日违规=0；C完整性违规=0；跨signature累计=0。
- **专项哨兵：** `{'p10_event_hit': True, 'p10_lag_max_5': True, 'p10_delay_vs_b3_max_1': True, 'n02_no_confirm_when_c_null': True, 'n02_no_confirm_when_c_false_if_required': True, 'n02_event_s2_exposure_0': True, 'null_resets_all_counters_if_required': True, 'recovery_first_eligible_day_max_1_if_required': True, 'n04_full_window_no_s2': True, 'n08_event_no_s2': True, 'n08_full_window_no_s2': True}`。
- **失败检查：** 无。

### V4_B_B_PRESENT_REQUIRES_C_TRUE

- **业务结果：** 事件期/全窗正例=6/10、6/10；新增命中=P10；丢失=无。
- **负例变化：** 新增误确认=无；减少误确认=无；总新确认=1；S2暴露=11日。
- **确认滞后：** 均值/中位数=0.50/0.5；matched变化=-0.20/0；逐case=`{'P01': None, 'P02': None, 'P03': None, 'P04': 2, 'P05': 14, 'P06': -1, 'P07': -4, 'P08': -12, 'P09': None, 'P10': 4}`。
- **Churn：** `S0→S1→S0`=113；short reversal=170；reversal=274；transition=339；负例S1日=23。
- **确认完整性：** NULL日=272；断链日=0；旧计数残留违规=0；恢复首日违规=0；C完整性违规=0；跨signature累计=0。
- **专项哨兵：** `{'p10_event_hit': True, 'p10_lag_max_5': True, 'p10_delay_vs_b3_max_1': True, 'n02_no_confirm_when_c_null': True, 'n02_no_confirm_when_c_false_if_required': True, 'n02_event_s2_exposure_0': True, 'null_resets_all_counters_if_required': True, 'recovery_first_eligible_day_max_1_if_required': True, 'n04_full_window_no_s2': True, 'n08_event_no_s2': True, 'n08_full_window_no_s2': True}`。
- **失败检查：** positive_full_window_s2_cases_min_7、favorable_positive_cases_min_2、favorable_episodes_min_2。

### V4_C_COMBINED

- **业务结果：** 事件期/全窗正例=6/10、6/10；新增命中=P10；丢失=无。
- **负例变化：** 新增误确认=无；减少误确认=无；总新确认=1；S2暴露=11日。
- **确认滞后：** 均值/中位数=0.67/1.0；matched变化=0.00/0；逐case=`{'P01': None, 'P02': None, 'P03': None, 'P04': 3, 'P05': 14, 'P06': -1, 'P07': -4, 'P08': -12, 'P09': None, 'P10': 4}`。
- **Churn：** `S0→S1→S0`=113；short reversal=170；reversal=274；transition=339；负例S1日=23。
- **确认完整性：** NULL日=272；断链日=272；旧计数残留违规=0；恢复首日违规=0；C完整性违规=0；跨signature累计=0。
- **专项哨兵：** `{'p10_event_hit': True, 'p10_lag_max_5': True, 'p10_delay_vs_b3_max_1': True, 'n02_no_confirm_when_c_null': True, 'n02_no_confirm_when_c_false_if_required': True, 'n02_event_s2_exposure_0': True, 'null_resets_all_counters_if_required': True, 'recovery_first_eligible_day_max_1_if_required': True, 'n04_full_window_no_s2': True, 'n08_event_no_s2': True, 'n08_full_window_no_s2': True}`。
- **失败检查：** positive_full_window_s2_cases_min_7、favorable_positive_cases_min_2、favorable_episodes_min_2。

## P10、N02、N04、N08关键路径

### P10

| Arm | 确认日 | 事件期S2 | 全窗口S2 | 解释 |
| --- | --- | --- | --- | --- |
| BASELINE | 2025-06-27 | False | True | 正式五组AND未在事件期确认 |
| V4_A_NULL_BREAKS_CONFIRMATION_CONTINUITY | 2025-05-12、2025-06-27 | True | True | B-waived路径未改变，持续证据完成确认 |
| V4_B_B_PRESENT_REQUIRES_C_TRUE | 2025-05-12、2025-06-27 | True | True | B-waived路径未改变，持续证据完成确认 |
| V4_C_COMBINED | 2025-05-12、2025-06-27 | True | True | B-waived路径未改变，持续证据完成确认 |

逐日A/B/C/D/Enhancer、above_ma20、required-known、signature、计数器、断链、确认、Freeze与NULL原因保存在`calibration_results_v4.json`的`focus_case_paths.P10`。

### N02

| Arm | 确认日 | 事件期S2 | 全窗口S2 | 解释 |
| --- | --- | --- | --- | --- |
| BASELINE | 2024-11-07 | False | True | 事件期无S2，事件后11月7日才由正式路径确认 |
| V4_A_NULL_BREAKS_CONFIRMATION_CONTINUITY | 2024-11-06 | False | True | NULL清除旧链，但C=FALSE时仍允许Enhancer补偿 |
| V4_B_B_PRESENT_REQUIRES_C_TRUE | 2024-11-07 | False | True | C=NULL/FALSE均不能获得B-present确认资格 |
| V4_C_COMBINED | 2024-11-07 | False | True | NULL断链且B-present强制C=TRUE |

逐日A/B/C/D/Enhancer、above_ma20、required-known、signature、计数器、断链、确认、Freeze与NULL原因保存在`calibration_results_v4.json`的`focus_case_paths.N02`。

### N04

| Arm | 确认日 | 事件期S2 | 全窗口S2 | 解释 |
| --- | --- | --- | --- | --- |
| BASELINE | 无 | False | False | 正式五组AND未完成确认 |
| V4_A_NULL_BREAKS_CONFIRMATION_CONTINUITY | 无 | False | False | same-branch继续阻断跨分支拼接 |
| V4_B_B_PRESENT_REQUIRES_C_TRUE | 无 | False | False | same-branch继续阻断跨分支拼接 |
| V4_C_COMBINED | 无 | False | False | same-branch继续阻断跨分支拼接 |

逐日A/B/C/D/Enhancer、above_ma20、required-known、signature、计数器、断链、确认、Freeze与NULL原因保存在`calibration_results_v4.json`的`focus_case_paths.N04`。

### N08

| Arm | 确认日 | 事件期S2 | 全窗口S2 | 解释 |
| --- | --- | --- | --- | --- |
| BASELINE | 无 | False | False | 正式五组AND未完成确认 |
| V4_A_NULL_BREAKS_CONFIRMATION_CONTINUITY | 无 | False | False | above_ma20<0.60，绝对广度底座继续阻断 |
| V4_B_B_PRESENT_REQUIRES_C_TRUE | 无 | False | False | above_ma20<0.60，绝对广度底座继续阻断 |
| V4_C_COMBINED | 无 | False | False | above_ma20<0.60，绝对广度底座继续阻断 |

逐日A/B/C/D/Enhancer、above_ma20、required-known、signature、计数器、断链、确认、Freeze与NULL原因保存在`calibration_results_v4.json`的`focus_case_paths.N08`。

## NULL、Freeze、Warmup与确定性

- **V4_A_NULL_BREAKS_CONFIRMATION_CONTINUITY：** NULL旧计数残留违规=0；恢复首日违规=0；C完整性违规=0；Freeze转移违规=0；两次重跑一致=True。
- **V4_B_B_PRESENT_REQUIRES_C_TRUE：** NULL旧计数残留违规=0；恢复首日违规=0；C完整性违规=0；Freeze转移违规=0；两次重跑一致=True。
- **V4_C_COMBINED：** NULL旧计数残留违规=0；恢复首日违规=0；C完整性违规=0；Freeze转移违规=0；两次重跑一致=True。
- P01、P06、P07、N05、N06、A01仍为直接warmup-sensitive cases；G5继续FAIL。
- NULL没有填0、默认通过或自动制造全局Freeze；正式Freeze输入掩码与BASELINE一致。

## 最终选择与停止规则

- **PRIMARY CALIBRATION CANDIDATE：** V4_A_NULL_BREAKS_CONFIRMATION_CONTINUITY。
- **BACKUP CANDIDATE：** 无。
- **FINAL BOUNDED CALIBRATION Stop Rule：** DEVELOPMENT_SET_TUNING_STOPPED_HOLDOUT_REQUIRED。
- **下一步：** 停止开发集调参，先完成数据资格边界并设计独立Holdout。

本轮未修改正式rule_version、parameter_profile、阈值、状态机、退出、恢复、S3/S4、casebook、Production、scheduler、Sites或G1–G4；未运行Holdout。

## 方法与限制

本次只重放冻结归档中的25个开发/诊断案例，使用预注册规则和固定硬门槛；每臂执行两次并比对checksum。它能判断候选是否满足当前开发集合同，不能证明泛化能力。完整84日warmup仍未认证，因此所有结论必须与G5=FAIL共同阅读。
