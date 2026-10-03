# A股主线识别系统 V2.2.1 — Holdout Clean Range Expansion Report

> **结论：CLEAN DATA SPACE CAPACITY REACHED — CASEBOOK FREEZE MAY RESUME**
>
> 本轮没有运行BASELINE或V4-A，没有给候选episode贴标签，也没有执行Holdout。

## 1. 扩展结果

| 项目 | 结果 |
|---|---|
| 新数据版本 | `holdout_data_version_v2_e3e1ab3c8a78a26d` |
| Pre clean区间 | `2023-04-03` 至 `2024-04-30`（261日） |
| Pre 84日warmup | `2022-11-28` 至 `2023-03-31` |
| Development污染区间 | `2024-09-02` 至 `2025-06-30` |
| Development前隔离带 | 84个交易日；`2024-05-06` 至 `2024-08-30` |
| Post clean区间 | `2025-11-04` 至 `2026-09-30`（223日） |
| 总候选交易日 | 484 |
| SW1覆盖 | 31 / 31 |
| PIT | effective-PIT PASS；knowledge-time未验证 |

选择Pre而非继续向后扩展：截至本次运行，现有Post父版本已经覆盖到其认证终点；向前只补足使冻结容量达到目标并保留1个槽位余量的最小区间。Pre候选区间与Development起点之间另留完整84个交易日隔离带，强于20日机械下限；逐case的催化、政策、连续行情和二波语义仍必须在Casebook Freeze阶段审计。

## 2. 数据与状态资格

| 检查 | Pre | Post父版本 | 合并结论 |
|---|---:|---:|---:|
| 31行业逐日panel | PASS | PASS | PASS |
| 历史成员/effective-PIT | PASS | PASS | PASS |
| 84日warmup | PASS | PASS | PASS |
| state initialization | PASS | PASS | PASS |
| confirm/recover/weaken/retire | PASS | PASS | PASS |
| NULL / Freeze | PASS | PASS | PASS |
| 无未来成员倒灌 | PASS | PASS | PASS |
| deterministic rerun | PASS | PASS | PASS |

`knowledge_time_verified=false`，所以不得把本版本写成strict knowledge-time PIT。原始响应、标准化panel、membership及两次replay均由checksum和source snapshot追溯。

## 3. 独立episode容量

冻结合同下，Pre区间提供14个、Post区间提供12个20交易日隔离锚点，合计26个，超过25例最低规模1个槽位。该数字是时间隔离容量，不是已经选出的episode，也不是10/10/5标签保证；下一轮必须继续盲态选样、双审标签、窗口不重叠与同催化/同连续行情合并审计。若语义去重或类别配额后不足，应如实停止冻结，不得降低标准。

## 4. 隔离声明

- `v4a_calibration_candidate_v1`保持冻结，未在Pre或Post区间执行。
- 未运行Calibration、G1-G4或Holdout。
- 正式rule/profile/state machine及Holdout成功标准未修改。
- `PRODUCTION_MAINLINE_ENABLED=false`，`MAINLINE_LIVE=false`。
