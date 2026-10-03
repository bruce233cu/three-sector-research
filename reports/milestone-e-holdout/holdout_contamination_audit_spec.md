# Holdout Contamination Audit Specification

## 1. 审计输入

- `casebook_v1_20261002_25`及其所有case窗口、行业、催化簇；
- `reports/milestone-d-*`全部报告、CSV/JSON中的case、日期和episode引用；
- Calibration V1—V4与失败归因中使用的P10/N02/N04/N08等哨兵逻辑；
- 拟冻结Holdout候选池、证据包、review记录和访问日志；
- 冻结候选`v4a_calibration_candidate_v1`的source commit与checksum。

## 2. 每例必查项

| 检查 | PASS条件 | FAIL处理 |
|---|---|---|
| exact window overlap | 与Development事件窗/case窗无重叠 | 永久剔除 |
| episode identity | 不共享行业连续行情、催化簇或跨行业政策episode | 永久剔除 |
| 20-session buffer | 最近Development episode边界外至少20个交易日 | 不足则剔除；满足仍需语义审查 |
| report-history scan | 未在诊断、校准、失败归因或候选设计中用于推导规则 | 命中即剔除 |
| sentinel-inspired selection | 不是因类似P10/N02/N04/N08的已知规则结构而入选 | 命中即剔除 |
| result blindness | 选样、标签、窗口冻结前无人运行/查看V4-A或BASELINE结果 | 证据不足即剔除或废止整本 |
| label independence | 标签未使用S1/S2、规则组、counter或candidate输出 | 命中即剔除 |
| duplicate/related episode | casebook内部不重复同一episode或高度相关切片 | 只保留预先排序最高者 |
| temporal evidence | 标签来源日期与用途明确，无未来材料冒充当时共识 | 修正证据；无法修正则剔除 |

## 3. 自动与人工审计

自动检查：日期区间交集、同taxonomy code缓冲、case/date文本扫描、重复URL、相同source snapshot、casebook checksum、git历史、执行产物是否已存在。

人工检查：同政策冲击的跨行业episode、行情是否真正断裂、二波是否独立、选择理由是否受到已知V4-A缺陷启发、公开来源是否代表独立共识。

## 4. 输出合同

冻结前必须生成逐例`holdout_contamination_audit.json`，至少包含：

`case_id, episode_id, overlap_days, nearest_development_episode, buffer_sessions, shared_catalyst, historical_report_hits, sentinel_inspiration_check, v4a_result_accessed, reviewer, status, reason, evidence_checksum`。

只有全部正式case均为`PASS`且未解决问题数为0，才允许冻结。审计日志保留所有被拒case，禁止删除以掩盖筛选路径。

## 5. 执行后污染

任一正式case结果被计算或查看后，manifest立即写入`consumed_at`与执行commit，casebook状态变为`CONSUMED`。此后修改规则或成功标准不得重用该casebook；失败case只能转入新的Development evidence。
