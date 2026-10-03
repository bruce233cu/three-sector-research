# Holdout Warmup Eligibility Contract

## 1. 数据版本与边界

每个case必须使用`warmup_data_version_v2_1b7b20d9f8470f29`，或未来明确继承同一合同且单独通过G5的新版本。当前边界：

- taxonomy：SW2021 31个一级行业；
- membership：逐日`effective_pit`；strict knowledge-time未验证；
- Provider：Sina，经锁定AKShare 1.18.97 raw decode；
- 可认证warmup起点：2024-05-06；
- 已认证板块数据终点：2025-06-30；
- 初始化锚点前至少84个有效交易日；
- 范围外日期、taxonomy、Provider或strict knowledge-time要求必须新建数据版本并重认证G5。

## 2. 逐例资格字段

每例冻结前必须记录：

`warmup_start_date, initialization_anchor_date, required_sessions, available_sessions, membership_ok, market_data_ok, indicator_window_ok, null_semantics_ok, freeze_ok, state_initialization_ok, confirm_counter_ok, recover_counter_ok, weaken_counter_ok, retire_counter_ok, deterministic_ok, future_membership_backfill_detected, knowledge_time_verified, qualification_status, qualification_reason, evidence_checksum`。

## 3. QUALIFIED条件

同时满足才可进入正式分母：

1. case窗口及84日初始化路径完全落入认证范围；
2. 每日使用当日有效成员，无未来成员倒灌；
3. 所需行情与MA20/MA60/NEW_HIGH60、相对强势、成交、广度窗口真实可得；
4. 缺失保持NULL，不填0、不前向填充、不以指数或其他行业代替；
5. Freeze掩码及语义正确，Freeze日无非法状态迁移；
6. 从合法S0开始重放至初始化锚点；
7. confirm/recover/weaken/retire均有完整前置路径且为合法非负整数；
8. 同一输入至少两次重放checksum一致；
9. source snapshot、fetch run、manifest与checksum可追溯；
10. case不要求strict knowledge-time证明。

## 4. 失败处理

- 冻结前不合格：不得进入casebook；可由同分层候补重新走完整选择、标签、污染与资格流程。
- 冻结后、执行前发现不合格：废止整个casebook版本，不得只换该case。
- 执行中发现数据损坏或资格判断错误：结论为`HOLDOUT INCONCLUSIVE`，casebook标记`CONSUMED`，不得调整分母续跑。
- 禁止用覆盖率百分比代替状态初始化资格；禁止降低84日或计数器合同。

## 5. G5条件性边界

G5为`CONDITIONAL PASS`不是全局数据通行证。每个Holdout case仍必须逐例重资格；Holdout Design获准不等于Holdout Execution获准。只有冻结清单全部`QUALIFIED`且deterministic，casebook manifest才可将`execution_authorized`设为true。
