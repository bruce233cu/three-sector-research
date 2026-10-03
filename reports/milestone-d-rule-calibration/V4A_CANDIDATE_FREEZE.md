# A股主线识别系统 V2.2.1 — V4-A Candidate Freeze

> **冻结状态：CALIBRATION_CANDIDATE**
>
> **冻结标识：`v4a_calibration_candidate_v1`**
>
> **用途边界：仅允许在G5通过后进入独立Holdout；不是正式规则，不得上线。**

## 1. 冻结对象

| 项目 | 冻结值 |
| --- | --- |
| candidate_name | `V4_A_NULL_BREAKS_CONFIRMATION_CONTINUITY` |
| candidate_status | `CALIBRATION_CANDIDATE` |
| candidate_id | `v4a_calibration_candidate_v1` |
| source_commit | `7386d04e666ba2ba34d235ec5025ef7bd0466417` |
| experiment_start_commit | `58217cdfc4f802db503692b98081445c0f7d1ea0` |
| baseline_rule_version | `mainline_v2.2.1_state_completion_v1` |
| baseline_parameter_profile | `industry_trend_v221_state_completion_v1` |
| development_casebook | `casebook_v1_20261002_25` |
| development_casebook_checksum | `249799d4c82ee067c4450e58d3409c661e2afb0dc7ff0339ae277f0f6d69c47d` |
| data_snapshot_version | `board-archive-3ff7ae0a56ab0c65` |
| PIT | `effective_pit`；`knowledge_time_unverified=true` |
| G5 | `FAIL` |
| Holdout | `NOT_AUTHORIZED_PENDING_G5` |
| Production | `PRODUCTION_MAINLINE_ENABLED=false`；`MAINLINE_LIVE=false` |

## 2. 候选逻辑

V4-A继承V1-B3确认结构和same-branch / evidence-signature合同，只增加一条确认连续性约束：

1. required-known集合固定为`A、B、C、D、Enhancer、above_ma20`。
2. 任一required-known为NULL时，当天不得累计确认计数，也不得完成S2确认。
3. NULL立即使本轮连续确认链失效，所有确认signature的旧`confirm_counter`清零。
4. 数据恢复后，第一个全部known且满足同一signature的有效日从`confirm_counter=1`重新开始。
5. 这不是FALSE、全局Freeze或退出S1，不修改candidate、weaken、recover、retire及S3/S4。
6. 各evidence signature独立计数；不同分支或不同signature不得跨日拼接。

冻结后的V4-A不得再针对当前25个Development / Diagnostic cases修改。若未来Holdout失败，必须建立新的开发版本和实验边界，不得返回本开发集继续追调。

## 3. 开发集结果

| 指标 | BASELINE | V4-A | 变化 |
| --- | ---: | ---: | ---: |
| 正例事件期S2召回 | 5/10 | 8/10 | +3 |
| 正例全窗口S2召回 | 6/10 | 8/10 | +2 |
| 负例事件期新误确认 | 1 | 1 | 0 |
| 负例事件期S2暴露 | 11日 | 11日 | 0 |
| S0→S1→S0 | 117 | 106 | -11 |
| short reversal | 174 | 166 | -8 |
| reversal | 276 | 267 | -9 |
| transition | 341 | 340 | -1 |

- 新增事件期命中：P03、P09、P10；原有5个事件期命中全部保留。
- N02事件期S2暴露为0；N04全窗口无S2；N08事件期及全窗口无S2。
- 两次确定性重跑checksum均为`2e3c8e9319657300feb9c67058a789463e400aa78ab658b86218319505dd099f`。
- 全部预注册业务护栏、NULL连续性护栏、signature护栏和Freeze护栏通过。

## 4. 已知限制与准入结论

- 结果来自已被使用过的25例开发/诊断集，不是泛化准确率。
- 25例完整84日warmup状态路径未认证；G5仍为FAIL。
- 13个证券的当前响应与原认证字节不一致，原认证字节及成功价格缓存未归档，不能可靠补造。
- strict knowledge-time PIT仍未验证。
- P01、P06、P07、N05、N06、A01与13项缺口存在直接行业成员关联；其余案例也没有完整状态初始化证明。

因此，V4-A已经正式冻结为候选，但**当前不允许运行独立Holdout，也不允许发布正式rule_version或修改Production**。准入前置条件是G5通过，或另行形成有证据支持且边界明确的Conditional Pass；本次验收没有形成该条件。

## 5. Evidence Index

- `RULE_CALIBRATION_EXPERIMENT_SPEC_V4.md`
- `CALIBRATION_EXECUTION_REPORT_V4.md`
- `calibration_results_v4.json`
- `deterministic_rerun_v4.json`
- `experiment_manifest_v4.json`
- `final_bounded_calibration_decision.json`
- `../milestone-d-warmup/G5_WARMUP_QUALIFICATION_REPORT.md`
