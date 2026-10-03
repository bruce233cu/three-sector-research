# A股主线识别系统 V2.2.1 — G5 Warmup Qualification Report

> **最终状态：G5 = FAIL**
>
> **13项缺口：0/13解决**
>
> **Holdout：当前不允许开始设计或执行**

## 1. 一句话结论

5369/5382（99.758454%）只代表证券请求通过原认证响应校验，不代表84日状态路径已经完整初始化。13项当前响应与原认证字节不同，而原字节和成功价格缓存均未归档；无法可靠补齐，所以完整板块预热、S0—S4重放及四类计数器前置历史仍未认证，G5必须保持FAIL。

## 2. G5正式验收合同

G5通过要求不是“覆盖率够高”，而是每个用于验证的case同时满足：

1. 84个预热交易日及前驱日输入完整且可追溯；
2. 历史行业成员按日期生效，不使用当前或未来成员倒灌；
3. 个股行情窗口足够计算MA20、MA60、NEW_HIGH60及冻结指标；
4. NULL保持NULL，Freeze按原合同执行；
5. 从合法初始化状态重放S0/S1/S2/S3/S4；
6. confirm/recover/weaken/retire计数器拥有完整前置历史；
7. 相同输入至少两次重放结果完全一致；
8. PIT、来源、checksum和数据版本可审计。

任何用于Holdout的case只要缺少上述一项，就不能标记warmup-qualified。

## 3. 原始失败原因与13项缺口

13项均不是HTTP失败：诊断请求全部返回200。失败类型统一为`certified_payload_mismatch`：当前响应的原始字节checksum与原认证值不同。由于原认证原始字节和成功价格缓存没有持久化，无法判断差异位于哪一行，也不能证明当前响应与当时认证数据等价。

| 类型 | 数量 | 能否现有artifact补齐 | 本轮处理 |
| --- | ---: | --- | --- |
| 当前响应≠原认证字节 | 13 | 否 | 保持未解决，不用当前响应静默替换 |
| 行情HTTP不可达 | 0 | 不适用 | 无 |
| 合法停牌/未上市 | 0个请求级终态 | 不适用 | 不伪造为NULL |
| 历史成员缺失 | 0项已证明 | 不适用 | 沿用effective-PIT成员证据 |

13项证券及行业/case映射详见`warmup_gap_inventory.csv`。直接涉及：P01、P06、P07、N05、N06、A01；其余证券还进入全市场基准或广度输入。无论是否直接命中行业，25例均没有生成合格的完整84日板块面板和状态重放，因此不能把其余19例标成已认证。

## 4. 状态路径与计数器影响

完整预热未生成，现有开发集轨迹仍是冷启动诊断路径。潜在影响不能量化为“无影响”：

- S0/S1/S2/S3/S4首日状态可能被左截断；
- confirm/recover/weaken/retire可能缺少窗口前累计值；
- 可能出现错误继承、提前或延迟确认、以及Freeze时点偏差；
- RS、breadth、turnover及MA20/MA60/NEW_HIGH60可能受缺口影响；
- 当前没有合格输入可做最小状态重放，强行运行只会把未认证数据包装成结果。

这并不证明13项一定会实质改变每个case，只证明目前没有足够证据排除影响。

## 5. 正式验收表

| 验收项 | 结果 | 证据/说明 |
| --- | --- | --- |
| A. warmup窗口完整 | **FAIL** | 5382中13项未获认证终态 |
| B. 历史成员按日期有效 | PASS（既有证据） | effective-PIT成员checksum保持 |
| C. 个股行情窗口满足 | **FAIL** | 13项不能可靠恢复 |
| D. MA20/MA60/NEW_HIGH60真实可得 | **FAIL** | 完整84日板块面板未生成 |
| E. NULL保持NULL | PASS（合同） | 未填0、未把失败伪装成停牌 |
| F. Freeze逻辑正确 | 未完成 | 未在完整warmup路径验证 |
| G. state replay合法初始化 | **FAIL** | 完整重放未执行 |
| H. 四类计数器前置历史完整 | **FAIL** | 完整重放未执行 |
| I. membership effective-PIT | PASS | 沿用已认证成员证据 |
| J. knowledge-time | **FAIL / 未验证** | `knowledge_time_unverified=true` |
| K. deterministic rerun | **FAIL / 未执行** | 无合格完整输入 |
| L. 未来成分未倒灌 | PASS（本轮） | 本轮未回填、未重建Universe |
| M. Holdout案例全部具备资格 | **FAIL** | 当前无可认证资格范围 |

## 6. Case资格边界

### 当前25例

- warmup-qualified：**无**。
- 直接受13项行业成员缺口影响：P01、P06、P07、N05、N06、A01。
- 其余19例：虽无直接行业映射，但完整84日状态初始化仍未生成，因此同样未认证。
- 此外，25例已经永久属于Development / Diagnostic Set，即使未来补齐warmup，也不能成为独立Holdout。

逐case结论见`warmup_case_eligibility.csv`。

### 未来Holdout

本报告没有形成可接受的Conditional Pass，因此现在不能建立或运行Holdout。未来每个新case必须在入选前证明其完整84日数据、历史成员、指标窗口、状态初始化和确定性重放均合格；不能仅避开上述6个直接case就视为通过。

## 7. 为什么本轮不补数据、不重放

现有当前响应可以下载，但与原认证版本不同；直接采用会变成未经授权的数据重新认证，而不是补齐旧版本。原字节不存在，现有artifact也不能恢复。填0、用未来数据、用当前成员、近似值或静默换版本均违反合同。

因此本轮没有重建全A历史库、没有重跑G1—G4、没有重跑Calibration，也没有执行无合法输入的“最小重放”。这是数据资格阻塞，不是工具重试不足。

## 8. 最终决定与下一步

**G5 = FAIL。** V4-A可以被冻结为`CALIBRATION_CANDIDATE`，但Holdout仍为`NOT_AUTHORIZED_PENDING_G5`。

下一阶段应进入**Warmup Data Version Re-certification设计**：明确授权以当前历史响应建立新的不可变数据版本，保存原始字节、标准化行、来源时间、checksum和成功缓存；完成13项差异审计后，只重建84日板块面板并最小重放状态路径。通过G5后再进入独立Holdout Design。不得通过继续调规则掩盖该缺口。

## 9. Evidence Index

- `../milestone-d-warmup-resume/warmup_audit.json`
- `../milestone-d-warmup-resume/evidence/failed_items_classified.json`
- `../milestone-d-baseline-v1/warmup-recovery/recovery_attempt_audit.json`
- `../milestone-d-warmup-resume/G5_FINAL_GATE.json`
- `../milestone-d-rule-diagnostic/warmup_security_membership_impact.csv`
- `warmup_gap_inventory.csv`
- `warmup_case_eligibility.csv`
- `g5_qualification.json`
