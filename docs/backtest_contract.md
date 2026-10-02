# V2.2冻结原文摘录 — backtest_contract.md

来源：A股主线识别系统_V2.2_施工冻结版_完整规格说明书_2026-09-23.docx；Library ID libfile_09e31bd4124481918c633968098f8b58。
本附件保留对应整页原文（包含相邻章节），不新增业务定义；V2.2.1两项显式修订另见原修订文件。

A 股主线识别系统 · V2.2 施工冻结版
数据 → 证据 → 规则 → 判断 ｜ AI 只解释 ｜ 历史可追溯
第 16 页
页面 首屏必须看到 不得隐藏
时间轴 候选→确认→转弱→退潮事件 旧 rule_version 快照
系统说明 公式、规则、数据源、PIT 解释 不允许“模型自动判断”模糊话术
 空值必须显示“数据不足”，不能显示 0。
 stage_frozen=true 时，状态卡必须显示“数据冻结，沿用上一有效状态”，不得伪装为正常判断。
 AI 解释区与机器事实区视觉分离，并标注“解释，不参与硬状态”。
 默认不展示任何总分、星级、87 分式评分。
15. 历史盲测施工合同
标准运行命令
python -m src.backtest.runner --start 2019-01-01 --end 2025-12-31 --taxonomy sw1 --rule-version 
mainline_v2.2.0 --profile industry_trend_v2_2_1 --mode point_in_time --output runs/2019_2025_v220/
输出文件 内容
daily_snapshot.parquet 每交易日×每行业全部指标与状态
transition_events.csv 所有 S0→S1→S2→S3→S4 事件
quality_events.csv 冻结、缺失、冲突、PIT 覆盖
metrics_summary.json 误报/漏报/滞后/churn 等汇总
case_review.csv 历史 casebook 的人工对照结果
run_manifest.json 代码 commit、rule_version、profile、数据版本、运行时间
验收指标 施工定义
False Breakout 5/10 S2 确认后 5/10 个交易日内进入 S3/S4 且未在窗口末恢复 S2
Confirmation Delay 人工 casebook 参考起点→首次 S2 的交易日数；仅用于 case review
Status Churn 20 日滚动窗口内硬状态变化次数
Retreat Delay 人工 casebook 结构恶化参考点→首次 S4 交易日数
No-mainline Precision 负样本窗口内，没有任何 S2 的交易日占比
Post-Confirm Alpha S2 确认日收盘后第 5/10/20/60 日板块相对基准收益

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
