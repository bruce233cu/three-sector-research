# A股主线识别系统 V2.2.1 — Holdout Data Range Extension Report

> **结论：DATA RANGE QUALIFIED, BUT NOT LARGE ENOUGH FOR THE FROZEN 25-CASE SPACING CONTRACT**
>
> 本轮没有运行BASELINE或V4-A，没有选择、标注或执行任何Holdout case。

## 1. 数据版本

| 项目 | 结果 |
|---|---|
| 新数据版本 | `holdout_data_version_v1_0caf3bfbd06e202b` |
| Development污染截止 | `2022-11-25` |
| 20交易日机械边界 | `2022-12-23` |
| 安全Holdout起点 | `2023-04-03` |
| 新认证范围 | `2022-11-28` 至 `2024-04-30` |
| 安全候选交易日 | 261 |
| SW1覆盖 | 31 / 31 |
| PIT | effective-PIT；knowledge-time未验证 |

安全起点不是简单采用“污染截止+20日”。它要求污染截止后先积累完整84个交易日的状态初始化前缀，故候选期使用第85个post-Development交易日开始；具体case仍须逐例检查催化、政策事件、连续行情和二波延续，不能因日期达标自动判CLEAN。

## 2. 资格验收

| 检查 | 结果 |
|---|---|
| 每日历史成员 | PASS |
| 31行业完整panel | PASS |
| 84交易日warmup | PASS |
| state initialization | PASS |
| confirm/recover/weaken/retire | PASS |
| NULL保留 / Freeze合同 | PASS |
| 无未来成员倒灌 | PASS（逐日effective interval解析） |
| deterministic rerun | PASS |

完整provider响应与标准化结果分别保留checksum；panel、membership及两次state replay均有独立checksum。`knowledge_time_verified=false`，不得写成strict knowledge-time PIT。

## 3. Holdout容量判断

冻结合同要求不同Holdout case窗口不重叠，并原则上至少间隔20个交易日。认证候选期只有261个交易日；即便把每个case乐观地压缩成单日锚点，最多也只有14个20日间隔锚点，仍低于25例。因此数据质量资格已通过，但当前扩展范围仍不足以支持`10正 + 10负 + 5模糊`的冻结规模。

这不是V4-A结果，也不是标签失败。下一步应继续增加从未用于Development的独立历史范围，或由合同所有者正式重新审视全局20日间隔约束；在现合同下，不允许进入正式Casebook Freeze。

## 4. 隔离声明

- `v4a_calibration_candidate_v1`保持冻结，未在新区间执行。
- 未运行Calibration、G1-G4、Holdout或Production。
- 正式rule/profile/state machine和成功标准均未修改。
- `PRODUCTION_MAINLINE_ENABLED=false`，`MAINLINE_LIVE=false`。
