# A股主线识别系统 V2.2.1 — G5 Warmup Data Version Recertification

## 结论

**G5 = CONDITIONAL PASS。** 已建立新的不可变 Warmup 数据版本 `warmup_data_version_v2_1b7b20d9f8470f29`。这不是旧响应恢复：它使用同一 Provider 合同重新取得当前响应，生成新的 raw/normalized checksum、source snapshot、fetch run 与 manifest。旧 13 项 checksum 缺口已 **13/13 通过新版本重认证解决**；84 日 × 31 行业共 2,604 行 Warmup Panel 已生成；25/25 个 Development / Diagnostic cases 的状态及 confirm/recover/weaken/retire 计数器初始化通过，两次重放 checksum 一致。

条件性而非无条件 PASS 的原因是：历史成员达到 `effective_pit`，没有未来成员倒灌，但 strict knowledge-time 仍未验证。可进入独立 Holdout Design，不得直接执行 Holdout 或发布规则；每个新 Holdout case 必须位于下述资格边界内并再次做 case-level warmup qualification。

## 新数据版本

| 项目 | 结果 |
|---|---|
| version_id | `warmup_data_version_v2_1b7b20d9f8470f29` |
| 与旧版本关系 | `NEW_VERSION_NOT_ORIGINAL_RECOVERY` |
| Provider | Sina，经锁定的 AKShare 1.18.97 raw decode 路径 |
| 请求窗口 | 2024-04-30 前驱日 + 2024-05-06 至 2024-08-30 共 84 个交易日 |
| Taxonomy / membership | SW2021 / 冻结的日有效成员历史 |
| PIT | `effective_pit` |
| strict knowledge-time | 未验证 |
| 请求证券 | 5,384 |
| 有标准化行情 | 5,382 |
| 明确保留 NULL | 2（000416.SZ、002699.SZ，均为冻结 G3 合同中的既有 Provider 不可用项） |
| Panel | 84 × 31 = 2,604 行 |
| Panel checksum | `be151d081e670ea85b5e2bfc5c82f83385b74deb6bb7dd2749e9efe55302630e` |

原认证 checksum 中 5,368 项与当前响应相同，14 项不同。14 项包括旧 13 个未恢复缺口及 688500.SH；它们均被明确归入新版本，未写成“旧响应已恢复”。2 个既有 Provider 不可用证券没有生成假行情、没有填 0，继续作为 NULL 进入冻结覆盖率合同。

## 13 项旧缺口

旧缺口全部取得当前有效响应并生成新的 normalized checksum，状态均为 `success`。详细逐项映射见 `warmup_gap_recertification.csv`。这些项目是 **resolved_by_recertification=true**，不是 recovered_original=true。

## 84 日合同与 Panel

84 日范围沿用冻结历史盲测合同，不重新定义。它为 60 日 MA60 / NEW_HIGH60 / turnover 历史、20 日相对强势与状态计数器提供前置路径。2024-05-06 至 2024-07-25 的 58 个早期交易日因滚动窗口尚未形成，31 个行业全部合法 Freeze；隔离 G5 重放仍逐日推进 S0、Freeze 与计数器语义。只有“整组全部 Freeze”的低排名截面可继续，任何非冻结且有效排名行业少于 10 个的日期仍会失败。

验证结果：

- 历史成员逐日有效，31 个 SW1 行业齐全；未发现未来成员倒灌。
- NULL 保持 NULL，没有填 0；2 个既有 Provider 缺口通过覆盖率合同处理。
- Freeze 日状态转移数为 0。
- 84 日 Panel 完整，必要指标在初始化锚点均可得。
- 状态从合法 S0 开始，经连续冻结规则重放至各 case 初始化日。
- confirm、recover、weaken、retire 四类计数器均存在、为非负整数且具备完整前置路径。

## 最小状态重放

重放范围为 2024-05-06 至 2025-03-18，只用于状态与计数器初始化，不评估案例结果，也不重新运行 V4 Calibration。

| 验收项 | 结果 |
|---|---:|
| Development cases | 25 |
| Warmup qualified | 25 |
| Unqualified | 0 |
| 状态行 | 6,572 |
| Freeze 日非法转移 | 0 |
| 非法状态转移 | 0 |
| deterministic rerun | PASS |
| 两次 checksum | `a6c8c793f07f8f8af725a5f99cd8c8360e804e02832115df94f8508cc87721fd` |

25 个 case 仅证明 warmup 初始化资格，仍永久属于 Development / Diagnostic Set，不能转用为独立 Holdout。

## Holdout 资格边界

允许下一阶段进入 **Holdout Design**，但不允许直接执行。新 Holdout case 必须同时满足：

1. 对象属于 SW2021 的 31 个一级行业，并使用逐日 effective-PIT 成员；
2. 所需状态路径完全落在当前已认证数据范围内：Warmup 从 2024-05-06 起，正式板块数据最晚至 2025-06-30；
3. case 的初始化锚点至少拥有完整 84 个有效交易日，且事件/后置窗口不越过已认证数据终点；
4. 每个新 case 在执行前重新验证 membership、market data、indicator windows、Freeze、四类计数器与 deterministic replay；
5. 与当前 25 个 Development cases 按 episode 隔离；当前 25 例不得进入 Holdout；
6. 若使用范围外日期、其他 taxonomy、其他 Provider 或要求 strict knowledge-time PIT，必须先建立新的数据版本并重新认证 G5。

## 隔离与限制

- V4-A 仍冻结为 `v4a_calibration_candidate_v1`，本轮未修改候选逻辑、阈值或成功标准。
- `PRODUCTION_MAINLINE_ENABLED=false`，`MAINLINE_LIVE=false`；无 Production 写入。
- 未运行 Holdout、V4 Calibration、G1–G4，也未建立长期全 A 历史库。
- 本结论仍是 `CALIBRATION_ONLY / DIAGNOSTIC_ONLY`，不代表生产准确率。

## Evidence Index

- 数据版本原始证据：`reports/milestone-d-warmup/recertification-37100031176/`
- 状态重放证据：`reports/milestone-d-warmup/recertification-37100723220/`
- 新版 manifest：`recertification-37100031176/warmup_data_version_manifest.json`
- Provider audit：`recertification-37100031176/provider_fetch_audit.json.gz`
- Panel：`recertification-37100031176/warmup_board_inputs.json.gz`
- 状态资格：`recertification-37100723220/warmup_state_replay_verification_v2.json`
- 确定性：`recertification-37100723220/g5_deterministic_rerun_v2.json`
