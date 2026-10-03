# A股主线识别系统 V2.2.1 — Independent Holdout Casebook Freeze V2

> **结论：HOLDOUT CASEBOOK NOT FROZEN — POSITIVE QUOTA SHORTFALL**
>
> 本轮完成盲态候选筛选、A/B双审、冲突裁决、episode去重、污染审计和Warmup资格核对；但合规留存池只有 **8 positive / 10 negative / 5 ambiguous**。未生成或冒充`holdout_casebook_v1`，未运行或查看V4-A在任何候选上的结果。

## 1. 一句话结论

Clean数据空间足够，不等于标签结构必然足够。30个候选经合同审查后，两个正例因独立公开证据不足被拒绝，另一个电子正例与前一电子行情属于同一连续AI/半导体episode而被合并排除，最终正例只剩8个；硬凑25例会同时违反标签硬门槛和episode独立性。

## 2. 输入与冻结合同

| 项目 | 值 |
|---|---|
| branch / source HEAD | `mainline-phase1e` / `c615784783d52a739a8b83f16360b3dbc2dc31cb` |
| 数据版本 | `holdout_data_version_v2_e3e1ab3c8a78a26d` |
| Clean范围 | Pre `2023-04-03—2024-04-30`; Post `2025-11-04—2026-09-30` |
| 候选规则 | `v4a_calibration_candidate_v1`，FROZEN CALIBRATION_CANDIDATE |
| 目标配额 | 10 positive / 10 negative / 5 ambiguous |
| Holdout成功标准 | 沿用`holdout_success_criteria.json`，未修改 |
| Production | `PRODUCTION_MAINLINE_ENABLED=false`; `MAINLINE_LIVE=false` |

事实：本轮只使用独立行业面板统计、公开历史资料、冻结的Clean区间与Warmup资格文件。没有读取候选规则输出、状态路径、Recall、误报、S2暴露、lag或Churn。

## 3. 流程完成情况

| Step | 状态 | 结果 |
|---|---|---|
| 1. 建立候选池 | COMPLETE | 25个首选 + 5个同时间槽替补，共30个 |
| 2. 盲态选样 | COMPLETE | 未使用V4-A或BASELINE输出 |
| 3. 独立标签 | COMPLETE | Reviewer A/B分别封存意见 |
| 4. 双审 | COMPLETE | 两位Reviewer互不可见；均声明未查看V4-A |
| 5. Adjudication | COMPLETE | 冲突只按已封存证据裁决；配额不参与改标 |
| 6. Episode去重 | COMPLETE | `HB_POST_07`与`HB_POST_06`合并为同一连续AI/电子episode，排除`HB_POST_07` |
| 7. Contamination Audit | COMPLETE | 留存23例全部CLEAN；7例为标签/episode排除 |
| 8. Warmup Qualification | COMPLETE | 30/30候选起点均为QUALIFIED；留存23/23全部通过 |
| 9–10. 固定窗口/标签 | COMPLETE FOR DRAFT | 只形成不可执行draft |
| 11–13. 正式casebook/checksum/manifest | BLOCKED | 10/10/5未满足；正式v1不得生成 |

## 4. 双审与裁决结果

Reviewer A通过原始候选13例、替补2例；Reviewer B通过原始候选20例、替补4例。差异主要来自Post区间公开来源检索覆盖，而非V4-A结果。裁决规则如下：

- 双方同意且标签一致：通过标签门；
- A因“未找到来源”拒绝、B提供至少两条独立且及时的可核验来源：按证据包裁决通过；
- B提出标签本质不成立（如过易负例、非阶段主线）或双方均拒绝：拒绝；
- 配额不足不能推翻证据门槛。

关键正例缺口：

1. `HB_POST_01`（综合，2025-11-04—11-17）：两位Reviewer均无法确认两条独立、及时且能证明“综合行业为持续板块主线”的公开来源，拒绝。
2. `HB_R1`（石油石化，同一时间槽替补）：两位Reviewer均认为量化形态较强，但只有一条及时资料且未证明持续板块主线，拒绝。
3. `HB_POST_07`（电子，2026-05-07—05-20）：标签证据本身通过，但资料明确描述半导体强势“延续”，与`HB_POST_06`（2026-04-03—04-17）的AI/电子主升属于同一连续episode；按冻结合同只能保留一个代表case。

## 5. 配额与Pre/Post结构

| 类别 | 目标 | 合规draft | 缺口 |
|---|---:|---:|---:|
| Positive | 10 | **8** | **2** |
| Negative | 10 | 10 | 0 |
| Ambiguous | 5 | 5 | 0 |
| 合计 | 25 | **23** | **2** |

留存draft中Pre为13例、Post为10例，三类均横跨Pre/Post；但正例配额是硬条件，不能以负例或模糊例替换。

## 6. Episode、污染与Warmup

- Episode审计：23个留存case窗口不重叠，满足候选池20交易日锚点约束，且没有发现同催化、同政策冲击或同连续行情；`HB_POST_07`因与`HB_POST_06`同一连续AI/电子episode被排除。
- Contamination：23/23留存case为`CLEAN`；均位于已认证Pre/Post Clean范围，不与Development/Calibration窗口重叠，没有历史诊断直接引用，也没有查看V4-A结果。
- Warmup：30/30候选起点均具备84个交易日前置窗口；历史成员、行情、指标窗口、state/counter初始化、NULL/Freeze与deterministic字段均为QUALIFIED。留存23/23全部通过。
- PIT边界：沿用数据版本的`effective_pit`；`knowledge_time_unverified=true`保持不变，未冒充strict knowledge-time PIT。

## 7. 被排除候选

共排除7例：

- 标签证据不合格6例：`HB_POST_01`、`HB_POST_05`、`HB_POST_10`、`HB_PRE_02`、`HB_PRE_09`、`HB_R1`；
- 同一连续episode去重1例：`HB_POST_07`。

完整A/B意见、来源、裁决、episode原因和资格字段见附件CSV。所有排除均发生在正式冻结前；没有用规则表现决定去留。

## 8. 冻结决定与下一步

**事实：** `holdout_casebook_v1`未生成，正式`casebook_checksum`和正式manifest均不存在；仅生成`holdout_casebook_draft_v2`及draft审计checksum。

**诊断结论：** 当前阻塞不再是数据覆盖、Warmup或污染，而是独立正例episode不足。现有Clean区间的时间容量26只是上界，经真实标签和语义episode审查后不能支持10个合格正例。

**下一步：** 不允许进入`INDEPENDENT HOLDOUT EXECUTION`。应只扩展/补充至少2个全新、独立、满足Positive合同且有两条及时独立来源的episode；新增episode必须完成相同双审、污染和Warmup流程。不得回填被拒案例、不得拆分同一行情、不得运行V4-A预看。

## 9. 审计声明

- 未运行V4-A或BASELINE Holdout replay；未计算任何Holdout业务结果。
- V4-A仍为冻结候选，未修改规则、阈值、状态机、profile或casebook成功标准。
- Production、scheduler、Sites生产逻辑均未修改，Production仍关闭。
- 本报告是`DRAFT_ONLY`收口，不授权Holdout Execution。
