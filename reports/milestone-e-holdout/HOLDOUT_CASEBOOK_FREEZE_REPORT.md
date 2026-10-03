# A股主线识别系统 V2.2.1 — Holdout Casebook Freeze Report

> **结论：HOLDOUT CASEBOOK NOT FROZEN — BLOCKED BY INDEPENDENCE BOUNDARY**
>
> 本轮没有运行BASELINE或V4-A，没有查看任何Holdout状态结果，也没有生成伪正式`holdout_casebook_v1`。

## Executive Summary

- **冻结失败的直接原因是候选池为空。** 当前认证板块数据共197个交易日，范围为2024-09-02至2025-06-30；Development 25例的case窗口联合覆盖同样的197个交易日，独立干净交易日为0。
- **换行业不能消除污染。** 冻结合同按episode和行情阶段隔离，而不是只按行业或日期行隔离；同一认证日期已经进入Development选择、诊断或校准观察范围。
- **流程在Step 1合法停止。** 没有候选能够通过最先执行的Development窗口排除，因此不能继续伪造标签双审、contamination CLEAN或逐例Warmup QUALIFIED。
- **下一步需要扩展并重新认证数据范围。** 新范围应优先覆盖Development之后的完整新历史区间，并为每个候选保留84个交易日前置路径；完成新G5边界后，才能重新开始Casebook Freeze。

## 1. 输入与不可变合同

| 项目 | 值 |
|---|---|
| repository branch | `mainline-phase1e` |
| design source commit | `ad3cbb0b3e654a548b0ef9e14c9c4737c2c858f8` |
| candidate | `v4a_calibration_candidate_v1`，FROZEN |
| Development casebook | `casebook_v1_20261002_25` |
| Development casebook file checksum | `6d29aef9b1ae82b1c72061d065ac6aaf736d0aa729f0e6e200e04049febb44b9` |
| Warmup data version | `warmup_data_version_v2_1b7b20d9f8470f29` |
| certified board input checksum | `c350662efb5ef5c8a7a4defcf5fe4b10511356d2532b720bc777acd7dc9e90f6` |
| success criteria checksum | `f142e79f1241df5c6e51a89bb49d5baca45996caae2abe8b1af15da8a78293f2` |
| Production | `PRODUCTION_MAINLINE_ENABLED=false`; `MAINLINE_LIVE=false` |

`holdout_success_criteria.json`未修改。V4-A逻辑、正式rule/profile、Production、scheduler和Sites均未修改。

## 2. 候选池审计

| 指标 | 结果 |
|---|---:|
| 认证板块日期范围 | 2024-09-02 至 2025-06-30 |
| 认证交易日 | 197 |
| 被Development case窗口覆盖 | 197 |
| 独立干净交易日 | **0** |
| 可进入标签审查的候选episode | **0** |

Development窗口形成连续覆盖：

| Development episode cluster | 覆盖范围 | Cases |
|---|---|---|
| 秋季政策行情 | 2024-09-02—2024-12-10 | P01/P02/N01/N02/N03/A03 |
| 秋季及消费红利 | 2024-09-13—2025-02-06 | P03/P04/P05/N10 |
| 消费退潮及年末调整 | 2024-10-29—2025-02-17 | N04/N06/N07/N08/N09 |
| 春节AI与机器人 | 2024-12-16—2025-05-07 | P06/P07/P08/N05/A01/A04 |
| 关税冲击后轮动 | 2025-02-24—2025-06-30 | A02/A05 |
| 二季度轮动 | 2025-03-19—2025-06-30 | P09/P10 |

这些区间互相衔接并覆盖全部认证板块日。按照预注册合同，窗口重叠已是硬FAIL；无需、也不允许先运行V4-A再挑选“表现合适”的日期。

## 3. 冻结步骤完成情况

| Step | 状态 | 证据/原因 |
|---|---|---|
| 1. 建立候选池 | BLOCKED | 31个SW1行业均只有0个独立认证交易日 |
| 2. 独立标签 | NOT STARTED | 无通过Step 1的case |
| 3. 双审/adjudication | NOT STARTED | 无合法标签对象 |
| 4. Episode隔离 | FAIL AT SCOPE | 197/197日期与Development窗口重叠 |
| 5. Contamination Audit | BLOCKED | scope级污染已成立，无法产生CLEAN case |
| 6. Warmup Qualification | NOT STARTED | 合同禁止对污染case赋予Holdout资格 |
| 7–11. 固窗/固标/冻结/checksum/manifest | NOT AUTHORIZED | 前置门未通过 |

## 4. 标签、污染和Warmup结论

- 正例：0/10；负例：0/10；模糊例：0/5。
- 标签双审未完成，原因不是审查遗漏，而是没有合法候选可交付Reviewer A/B。
- Episode隔离未通过；contamination audit没有任何`CLEAN`正式case。
- 没有对污染候选运行逐例状态重放，因此Warmup资格为`NOT_EVALUATED`，不能写成PASS。
- G5仍为`CONDITIONAL PASS`；其边界只证明数据可用于合格范围，不消除Development污染。

## 5. 数据质量判断

**Finding：当前数据范围不适合独立Holdout选样。** 完整性本身没有失败，但可用范围与开发集100%时间重叠，形成Critical级分析污染风险。若强行从该区间挑25例，任何准确率都只能继续算Development结果，不能证明泛化。

最小补救不是降低20日隔离规则，而是新增一个与Development episodes隔离的认证历史范围。优先方案：

1. 扩展到2025-07-01之后的完整新历史区间；若样本形态不足，再补充Development之前且从未用于设计的更早年份。
2. 新范围为每个event保留至少84个有效交易日前置路径，并重新认证membership、PIT、指标窗口、NULL/Freeze、四类counter与deterministic replay。
3. 建立新`warmup_data_version`或明确继承合同的扩展版本；不要覆盖现有版本。
4. 数据边界通过后，从Step 1重新建立候选池；仍禁止查看V4-A输出。

## 6. 审计声明

- `holdout_casebook_v1`未生成、未冻结、未消费。
- 没有正式casebook checksum；仅为draft文件生成审计checksum。
- 没有运行V4-A或BASELINE Holdout comparator，没有计算Recall、误报、S2暴露或状态路径。
- V4-A仍为冻结`CALIBRATION_CANDIDATE`；Production仍关闭。
- `INDEPENDENT HOLDOUT EXECUTION`继续不允许。
