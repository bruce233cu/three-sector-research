# V2.2冻结原文摘录 — acceptance_checklist.md

来源：A股主线识别系统_V2.2_施工冻结版_完整规格说明书_2026-09-23.docx；Library ID libfile_09e31bd4124481918c633968098f8b58。
本附件保留对应整页原文（包含相邻章节），不新增业务定义；V2.2.1两项显式修订另见原修订文件。

A 股主线识别系统 · V2.2 施工冻结版
数据 → 证据 → 规则 → 判断 ｜ AI 只解释 ｜ 历史可追溯
第 17 页
验收指标 施工定义
PIT Coverage 严格 PIT 对象-日期数 / 应测试对象-日期总数
反过拟合要求
第一轮校准集与最终 holdout 必须时间分离。任何参数修改必须产生新 profile。禁止为了修复某一年、某行业写日期/名
称特判。
16. 自动测试与验收用例
测试 ID 场景 Expected
T-MET-001 新股上市 15 日参与 ABOVE_MA20 从分母排除；coverage 下降；不得 False
T-MET-002 板块无正贡献 TOP3_RETURN_CONTRIBUTION=null
T-PIT-001 查询 2020 行业成分 只返回 2020 有效成分，不返回后续调入股票
T-DQ-001 日线完整率 94% critical_data_ok=false，stage_frozen=true
T-SM-001 S2 单日大跌但未满足转弱连续条件 仍 S2，不直接 S3/S4
T-SM-002 S4 后再次强势 新 lifecycle，从 S1 开始
T-RULE-001 规则 profile 阈值变化 旧历史快照不被覆盖
T-API-001 指标缺失 JSON 返回 null 并给 coverage/reason，不返
回 0
T-UI-001 候选对象 显示在候选区，不显示为正式主线
T-AI-001 AI 找不到驱动证据 输出‘驱动原因尚未确认’，不得补造
17. 第一阶段具体施工文件清单
阶段 必须新增/完成
Phase 1 数据底座 providers/base.py；至少 1 主 1 备 provider；security/
taxonomy/membership 仓库；质量检查；sql/001-003
Phase 2 指标与状态机 metrics/*.py；rules/*.py；state_machine/*.py；
parameter_profile JSON；unit tests
Phase 3 最小前端/API /api/radar；/api/mainlines；详情页；数据质量页；规则说明页

A 股主线识别系统 · V2.2 施工冻结版
数据 → 证据 → 规则 → 判断 ｜ AI 只解释 ｜ 历史可追溯
第 18 页
阶段 必须新增/完成
Phase 4 历史盲测 backtest/runner.py；evaluator.py；casebook；
run_manifest；盲测报告
Phase 5 增强 M1-M4、结构标签、Watchlist、主线家族
Phase 6 AI 解释 证据检索、驱动归因、反证；严格只读机器结果
18. 阶段 Gate：没有通过就不能进入下一阶段
Gate 必须通过
G1 数据 2019 年至今 SW1 日线/PIT 成分可回放；质量检查可冻结；主备源
实际工作
G2 指标 所有指标有单元测试；边界用例通过；同一输入重复运行结果一致
G3 状态机 S0-S4 合法转移；连续天数、防抖、lifecycle 重入正确
G4 前端 任何状态可追到原始指标、规则、数据质量；无静态假数据
G5 盲测 完成正负样本；输出误报/漏报/滞后/churn/PIT 覆盖；先报告再改
参
G6 增强 仅在核心状态稳定后启用标签、市场环境和 AI 解释
19. 日常运行与故障处理
时间/事件 动作
交易日 15:30 后 等待基础行情就绪
16:00-17:00 采集 Primary；校验；必要时 fallback
数据就绪 计算派生指标→质量判定→状态机→保存不可变快照
快照完成 刷新 API 缓存/前端
解释层 读取已完成快照生成驱动说明，不阻塞硬状态
次日发现数据修订 新增修订记录；默认不覆盖当日原始判断事实，可生成
recomputed 视图

A 股主线识别系统 · V2.2 施工冻结版
数据 → 证据 → 规则 → 判断 ｜ AI 只解释 ｜ 历史可追溯
第 19 页
重跑幂等：同一 as_of_date + rule_version + profile_id 写入必须幂等；如需重新计算，使用明确的 recompute_run_id 并
保留原始 run_manifest。
20. 安全与权限
 Supabase service role 只能存在服务器/后台任务，不进入浏览器。
 匿名/普通用户只读公开派生结果；watchlist 按 auth.uid()做 RLS 隔离。
 所有人工覆盖/备注必须记录 user_id、timestamp、before/after，不影响机器快照。
 第三方 Provider 密钥使用环境变量/GitHub Secrets，不写入仓库。
 日志禁止输出完整密钥和敏感 token。
21. 最终上线验收清单
域 验收项 通过
数据源 Primary/Backup 均实际调用过 □
PIT 抽查至少 5 个历史日期成员正确 □
退市股 历史 Universe 不丢失 □
指标 14 个核心指标均有公式+测试 □
缺失值 null/coverage 处理符合合同 □
候选 S1 证据可展开 □
确认 S2 A/B/C/D 条件可展开 □
转弱 连续恶化与 minimum dwell 有效 □
退潮 S4 关闭生命周期；再起新 lifecycle □
冻结 核心数据异常不会改变状态 □
规则版本 旧历史结果不被新规则覆盖 □
API 响应 Schema 与错误码一致 □
前端 先事实后判断，无总分 □
回测 严格 PIT 模式可复现 □
负样本 无主线窗口不会硬判大量 S2 □
AI 不能修改硬状态，找不到原因可输出未确认 □
