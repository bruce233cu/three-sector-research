# A股主线识别系统 V2.2.1 — RULE CALIBRATION EXECUTION REPORT V3

> **结论：NO CANDIDATE PASSED**
> **资格：CALIBRATION_ONLY / DIAGNOSTIC_ONLY；G5 = FAIL**
> 仅代表25例开发/诊断集，不是Holdout、生产准确率或上线授权。

## 1. Baseline与B3参考复现

BASELINE **PASS**：事件期正例5/10，全窗口6/10；负例新确认1，S2暴露11日；`S0→S1→S0`=117，short reversal=174。逐日状态与归档一致。
V1-B3参考臂 **PASS**：9/10、9/10、1、12日及既有checksum全部一致。

## 2. 三个平行候选

| 候选 | 结论 | 事件期正例 | 全窗正例 | 新增命中 | 负例新确认 | 负例S2日 | S0→S1→S0 | short reversal | transition |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| V3_A_NULL_GATING_ONLY | FAIL | 8/10 | 8/10 | P03、P09、P10 | 1 | 13 | 101 | 160 | 340 |
| V3_B_SAME_BRANCH_ONLY | FAIL | 9/10 | 9/10 | P01、P03、P09、P10 | 1 | 12 | 97 | 154 | 340 |
| V3_C_NULL_GATING_AND_SAME_BRANCH | FAIL | 8/10 | 8/10 | P03、P09、P10 | 1 | 13 | 101 | 160 | 340 |

关键结果不是“NULL门没有生效”，而是**暂停且保留计数**仍不足以封住N02：V3-A/C在C为NULL的日期都没有推进确认，但9月24日C恢复为FALSE时，B-present因Enhancer=TRUE获得第1个有效日；9月25日至27日再次NULL只暂停、不清零；9月30日C再次为FALSE且Enhancer仍为TRUE，于是同一路径取得第2个有效日并确认。该确认晚于B3，反而受既有最短停留/弱化节奏影响，在事件期留下2个S2日，使总负例暴露升至13日。

V3-B则完整复现了B3的N02缺口：`B_PRESENT_ENHANCER`在C=NULL时仍可连续成立，因此9月20日确认并留下1个事件期S2日。由此可见，单独要求“证据已知”或“同一分支持续”都没有形成足够的负例过滤。

## 3. 候选归因

### V3_A_NULL_GATING_ONLY

- 新增正例：P03、P09、P10；丢失原命中：无。
- 事件期确认滞后均值/中位数：1.88/0.0；逐case：`{'P01': None, 'P02': None, 'P03': 1, 'P04': -13, 'P05': 14, 'P06': -1, 'P07': -5, 'P08': -12, 'P09': 27, 'P10': 4}`。
- matched-lag均值/中位变化：-3.40/0。
- 负例新确认：N10；负例S2暴露：13日；负例S1日：21。
- 专项哨兵：`{'p10_event_hit': True, 'p10_lag_max_5': True, 'p10_delay_vs_b3_max_1': True, 'n02_no_confirm_while_c_null': True, 'n02_event_s2_exposure_0': False, 'n04_full_window_no_s2': True, 'n08_event_no_s2': True, 'n08_full_window_no_s2': True}`。
- 失败检查：negative_s2_case_days_max_11、sentinel_n02_event_s2_exposure_0。
- 归因：NULL日期本身没有完成确认，但“暂停保留”把9月24日与9月30日两个相隔的B-present有效日串接起来；N02仍在事件前进入S2。

### V3_B_SAME_BRANCH_ONLY

- 新增正例：P01、P03、P09、P10；丢失原命中：无。
- 事件期确认滞后均值/中位数：1.78/1；逐case：`{'P01': 1, 'P02': None, 'P03': 1, 'P04': -13, 'P05': 14, 'P06': -1, 'P07': -5, 'P08': -12, 'P09': 27, 'P10': 4}`。
- matched-lag均值/中位变化：-3.40/0。
- 负例新确认：N10；负例S2暴露：12日；负例S1日：21。
- 专项哨兵：`{'p10_event_hit': True, 'p10_lag_max_5': True, 'p10_delay_vs_b3_max_1': True, 'n02_no_confirm_while_c_null': False, 'n02_event_s2_exposure_0': False, 'n04_full_window_no_s2': True, 'n08_event_no_s2': True, 'n08_full_window_no_s2': True}`。
- 失败检查：negative_s2_case_days_max_11、sentinel_n02_no_confirm_while_c_null、sentinel_n02_event_s2_exposure_0。
- 归因：N02的Enhancer本身稳定，same-branch并不能阻断`B_PRESENT_ENHANCER`；该候选与B3关键指标一致。

### V3_C_NULL_GATING_AND_SAME_BRANCH

- 新增正例：P03、P09、P10；丢失原命中：无。
- 事件期确认滞后均值/中位数：1.88/0.0；逐case：`{'P01': None, 'P02': None, 'P03': 1, 'P04': -13, 'P05': 14, 'P06': -1, 'P07': -5, 'P08': -12, 'P09': 27, 'P10': 4}`。
- matched-lag均值/中位变化：-3.40/0。
- 负例新确认：N10；负例S2暴露：13日；负例S1日：21。
- 专项哨兵：`{'p10_event_hit': True, 'p10_lag_max_5': True, 'p10_delay_vs_b3_max_1': True, 'n02_no_confirm_while_c_null': True, 'n02_event_s2_exposure_0': False, 'n04_full_window_no_s2': True, 'n08_event_no_s2': True, 'n08_full_window_no_s2': True}`。
- 失败检查：negative_s2_case_days_max_11、sentinel_n02_event_s2_exposure_0。
- 归因：组合候选仍允许同一`B_PRESENT_ENHANCER`签名跨NULL暂停期保留计数，因此结果与V3-A相同；same-branch没有提供额外过滤。

## 4. P10 / N02 / N04 / N08逐日路径

### P10

| Arm | 确认日 | 事件期S2 | 全窗口S2 | 关键解释 |
| --- | --- | --- | --- | --- |
| BASELINE | 2025-06-27 | False | True | 正式五组AND未在事件期确认 |
| V3_A_NULL_GATING_ONLY | 2025-05-12、2025-06-27 | True | True | required-known完整，B-waived持续路径可计数 |
| V3_B_SAME_BRANCH_ONLY | 2025-05-12、2025-06-27 | True | True | required-known完整，B-waived持续路径可计数 |
| V3_C_NULL_GATING_AND_SAME_BRANCH | 2025-05-12、2025-06-27 | True | True | required-known完整，B-waived持续路径可计数 |

完整逐日字段保存在`calibration_results_v3.json`的`focus_case_paths.P10`，包括状态前后、五组证据、above_ma20、required-known、signature、计数器、确认、Freeze和NULL原因。

### N02

| Arm | 确认日 | 事件期S2 | 全窗口S2 | 关键解释 |
| --- | --- | --- | --- | --- |
| BASELINE | 2024-11-07 | False | True | 正式五组AND未在事件前确认；事件后才进入S2 |
| V3_A_NULL_GATING_ONLY | 2024-09-30、2024-11-06 | True | True | NULL日暂停，但两个known日仍可累计并在事件前确认 |
| V3_B_SAME_BRANCH_ONLY | 2024-09-20、2024-11-06 | True | True | 无required-known总门，稳定Enhancer签名仍可能确认 |
| V3_C_NULL_GATING_AND_SAME_BRANCH | 2024-09-30、2024-11-06 | True | True | NULL日暂停，但两个known日仍可累计并在事件前确认 |

完整逐日字段保存在`calibration_results_v3.json`的`focus_case_paths.N02`，包括状态前后、五组证据、above_ma20、required-known、signature、计数器、确认、Freeze和NULL原因。

### N04

| Arm | 确认日 | 事件期S2 | 全窗口S2 | 关键解释 |
| --- | --- | --- | --- | --- |
| BASELINE | 无 | False | False | B3分支隔离继续阻断 |
| V3_A_NULL_GATING_ONLY | 无 | False | False | B3分支隔离继续阻断 |
| V3_B_SAME_BRANCH_ONLY | 无 | False | False | B3分支隔离继续阻断 |
| V3_C_NULL_GATING_AND_SAME_BRANCH | 无 | False | False | B3分支隔离继续阻断 |

完整逐日字段保存在`calibration_results_v3.json`的`focus_case_paths.N04`，包括状态前后、五组证据、above_ma20、required-known、signature、计数器、确认、Freeze和NULL原因。

### N08

| Arm | 确认日 | 事件期S2 | 全窗口S2 | 关键解释 |
| --- | --- | --- | --- | --- |
| BASELINE | 无 | False | False | above_ma20<0.60，安全底座阻断 |
| V3_A_NULL_GATING_ONLY | 无 | False | False | above_ma20<0.60，安全底座阻断 |
| V3_B_SAME_BRANCH_ONLY | 无 | False | False | above_ma20<0.60，安全底座阻断 |
| V3_C_NULL_GATING_AND_SAME_BRANCH | 无 | False | False | above_ma20<0.60，安全底座阻断 |

完整逐日字段保存在`calibration_results_v3.json`的`focus_case_paths.N08`，包括状态前后、五组证据、above_ma20、required-known、signature、计数器、确认、Freeze和NULL原因。

## 5. NULL、signature、Freeze、Warmup与确定性

- **V3_A_NULL_GATING_ONLY：** required-known NULL日249；NULL计数违规0；跨signature累计0；Freeze转移违规0；两次重跑一致=True。
- **V3_B_SAME_BRANCH_ONLY：** required-known NULL日0；NULL计数违规0；跨signature累计0；Freeze转移违规0；两次重跑一致=True。
- **V3_C_NULL_GATING_AND_SAME_BRANCH：** required-known NULL日249；NULL计数违规0；跨signature累计0；Freeze转移违规0；两次重跑一致=True。
- P01、P06、P07、N05、N06、A01继续单列为直接warmup敏感；G5仍为FAIL。

## 6. 候选选择

- **PRIMARY CALIBRATION CANDIDATE：** 无。
- **BACKUP CANDIDATE：** 无。

## 7. 最终判定

三个预注册V3候选均未通过全部硬门槛；没有可进入Holdout的候选。

下一步不应发布规则或进入Holdout。若继续校准，需要先冻结新的有限规格，专门回答“NULL暂停后的旧计数何时失效”以及“B-present补偿路径是否必须要求C为TRUE，而不是仅要求C已知”两个结构问题；不得在本轮事后修改V3。

本轮未修改正式rule_version、parameter_profile、阈值、状态机、退出、恢复、S3/S4、casebook、Production、scheduler、Sites或G1–G4；未运行Holdout。
