# RULE DIAGNOSTIC — REPORT CLOSEOUT

**状态：COMPLETE / DIAGNOSTIC_ONLY。** 本页是断点恢复后的交付索引，不是新一轮诊断。主报告、候选清单与证据在恢复前已经提交并推送；本轮只校验文件、补齐文档索引，没有执行诊断、evaluator、warmup、状态重放或规则校准。

## 先读哪份

阅读 [主报告](RULE_DIAGNOSTIC_REPORT.md)；需要页面版时打开 [HTML报告](RULE_DIAGNOSTIC_REPORT.html)。主报告已包括成绩单、逐案例阻塞、判别力、AND结构、滞后、Churn、S3/S4、warmup、规则分级、Top 5候选和独立Holdout设计。

## 核心结论：事实、诊断与待验证分开

| 已核实事实 | 诊断结论 | 尚未证明的部分 |
| --- | --- | --- |
| 正例10/10曾S1、6/10曾S2、5/10事件期处于S2；4例全窗漏报 | 发现环节不是首要瓶颈，升级约束需要研究 | 放松B后究竟能增加几例确认，必须实验；不能把阻塞日当改善天数 |
| B在7正例单独阻塞25个非S2事件日，其中8日、4例具备S1升级资格 | B的一票否决与五组全部AND存在重复结构风险 | B也拦住部分负例，直接删掉可能提高误报 |
| 4负例事件期S2合计11日，仅N10在事件内新确认；其余3例继承旧S2 | 必须同时研究短期共振确认与旧状态退出，不能把4例都当4次错误入场 | 哪种中期持续性过滤真正有效，以及会增加多少滞后 |
| D广度正负通过率差34.7pp；C4.intensity仅1.64pp；D.newhigh与E3为同一证据 | 广度信息值得保留，成交强度单项区分弱，增强证据需要去重 | 去重后的组合、权重与净效果未知 |
| 341次转移、276次反复、174次短反复；117个S0→S1→S0模式 | 候选的单日进出是最大量级的横跳来源，优先研究退出滞回 | 减少横跳是否会使弱候选驻留更久、失效响应变慢 |
| 预热认证5369/5382=99.758454%；完整84日初始化仍未认证，G5=FAIL | 高请求覆盖率不能替代状态路径预热资格 | 13项缺口和完整预热对结果的反事实改变量无法定量确认 |

## 问题优先级与处置边界

| 问题类别 | 下一步 | 当前处理 |
| --- | --- | --- |
| 数据 / warmup | 明确完整预热与PIT资格的验收路径，保留NULL/Freeze | 不用调参填补未知，不认证新版准确率 |
| 阈值 / 组合 | 第一优先：B硬否决与S2分层确认的有限方案 | 需要重新标定与受控实验；不能直接改生产 |
| 持续性 / 指标 | 第二优先：成交与中期证据积累、两阶段确认；去重检查并行作为设计审查 | 只提出方案，净改善需更多样本验证 |
| 状态机 | 第三优先：S1进入/退出滞回；S3/S4另补独立转弱/退潮参考日 | 候选退出和确认后恢复分开测试，不统一延长全部等待 |
| 样本定义 | 25例固定为开发/诊断集；未来新Holdout至少10正、10负、5模糊，按episode隔离 | 不改现有标签，不用这些案例证明新版泛化 |
| 工程 / 正式合同 | 沿用冻结公式、rule_version、profile、casebook、Provider及生产调度 | 当前不应修改；G1–G4不重验、Production不改 |

下一阶段应先形成 **Rule Calibration实验规格**：有限候选、比较口径、成功与失败标准、数据资格处理和Holdout隔离。随后按正式阶段授权与Gate要求进入实验。本轮不执行候选测试、不新建rule_version、不启动Holdout。

## Evidence Index

下列都是已经提交的文件；本页不重新生成底层结果。

| 复核内容 | 对应现有证据 | 读取重点 |
| --- | --- | --- |
| 成绩单、版本、资格 | [diagnostic_summary.json](diagnostic_summary.json) | aggregate.overall；G5；warmup_coverage；rule_version；parameter_profile |
| 每条规则判别力 | [rule_discrimination_matrix.csv](rule_discrimination_matrix.csv) | 案例等权TRUE/总事件日；NULL；正负差；唯一阻塞 |
| 重叠敏感性 | [rule_matrix_overlap_sensitivity.csv](rule_matrix_overlap_sensitivity.csv) | 去掉跨标签行业日后，主要结论是否翻转 |
| 4/5与唯一阻塞 | [event_blockers.csv](event_blockers.csv) | case_id、eligible_S1、last_blocker、atomic_false、frozen；不能把所有非S2日当可升级日 |
| 案例与滞后 / S3/S4路径 | [case_diagnostics.json.gz](case_diagnostics.json.gz) | groups、atomic_blockers、transition_evidence、persistence_at_S2；原确认与继承状态分开 |
| 原子实际值和阈值 | [atomic_daily_evidence.csv.gz](atomic_daily_evidence.csv.gz) | passed、actual_value、threshold、signed_margin、event；FALSE与NULL分开 |
| 确认前持续性 | [persistence_summary.json](persistence_summary.json) | 确认前窗口，不能把事后表现写进当日过滤条件 |
| 横跳归因 | [churn_attribution.json](churn_attribution.json) | 候选票数、退出切换、路径计数；相关case不是独立样本 |
| 13项历史行业映射 | [warmup_security_membership_impact.csv](warmup_security_membership_impact.csv) | related_cases；成员计数占比不是收益/成交影响上限 |
| 规则诊断分级 | [rule_classification.json](rule_classification.json) | 诊断建议，不是已执行规则调整 |
| Top 5候选 | [calibration_candidates.json](calibration_candidates.json) | case、证据、方向、副作用、过拟合风险 |
| 已有校验与确定性记录 | [validation_checks.json](validation_checks.json)、[deterministic_analysis_rerun.json](deterministic_analysis_rerun.json) | 上一轮已保存的校验结果；本轮未重跑 |
| 文件完整性 | [delivery_file_checksums.json](delivery_file_checksums.json) | 本轮核对其中24个文件SHA256全部一致；本页不在原清单内 |
| 生产隔离与项目留痕 | [production_isolation.json](production_isolation.json)、[project_log_verified.json](project_log_verified.json) | 上一轮保存的隔离与记录；本轮未写生产数据库 |
| 原交付回执 | [FINAL_DELIVERY.json](FINAL_DELIVERY.json) | 原最终报告提交定位与尚未执行的HTML视觉验证 |

## 断点与提交留痕

- 用户提供的起点：`cc8f9aa61626a627e202088ac748ea1a75012268`。
- 恢复时核实远端已推进至：`4c24f9ed85cc30562f815759c9bdc0157d006166`。
- 已有证据归档提交：`4e96dcc8eeb3038d41cd89783eb93d9950b0b966`。
- 已有最终报告提交：`4c24f9ed85cc30562f815759c9bdc0157d006166`，已在远端。
- 恢复前本地存在另一份未提交报告草稿；同步时保留在仓库外，不覆盖已提交主报告。
- 本次唯一新增文件：`reports/milestone-d-rule-diagnostic/REPORT_CLOSEOUT.md`；无代码、参数、规则、样本或生产修改。
- 本页最终提交SHA由交付回复及Git记录提供，避免把commit自身SHA写入自身内容。

**报告收口无阻塞。独立验真仍有阻塞：G5=FAIL、完整warmup资格不足；当前仍DIAGNOSTIC_ONLY。** HTML浏览器视觉/交互验证尚未完成，是页面版交付限制；Markdown正文与现有证据可以直接阅读复核。下一步不应宣称规则已优化或准确率已达标。
