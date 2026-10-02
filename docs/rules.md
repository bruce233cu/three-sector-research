# V2.2冻结原文摘录 — rules.md

来源：A股主线识别系统_V2.2_施工冻结版_完整规格说明书_2026-09-23.docx；Library ID libfile_09e31bd4124481918c633968098f8b58。
本附件保留对应整页原文（包含相邻章节），不新增业务定义；V2.2.1两项显式修订另见原修订文件。

A 股主线识别系统 · V2.2 施工冻结版
数据 → 证据 → 规则 → 判断 ｜ AI 只解释 ｜ 历史可追溯
第 11 页
fast-track：V2.2 默认关闭。任何未来 fast-track 必须单独新增 profile 字段、历史验证报告和 rule_version，不允许
LLM 临时决定。
9. 硬状态规则的可执行判定
9.1 S1 候选
条件 ID 判定 结果
C1 RS_5 横截面分位≤20% pass/fail/null
C2 RS_10>0 pass/fail/null
C3 WIN_5≥60% pass/fail/null
C4 TURNOVER_SHARE>自身 20 日均值 或 
TURNOVER_INTENSITY>1
pass/fail/null
C5 UP_RATIO>全 A_UP_RATIO 或 
ABOVE_MA20>全 A_ABOVE_MA20
pass/fail/null
规则：有效条件数量必须≥4；在有效条件中通过≥3 项才进入 S1。若有效条件<4，则不判候选并记录
insufficient_evidence。
9.2 S2 已确认
组 必要条件
A 相对强度 RS_10>0 且横截面分位≤30%
B 持续性 WIN_5≥80% 或 WIN_10≥70%
C 成交 TURNOVER_PCTL_60≥60%，且最近 3 个有效交易日
TURNOVER_SHARE 不是连续下降
D 广度 UP_RATIO>全 A、ABOVE_MA20≥60%、NEW_HIGH_60 较 3 日
前改善；3 项至少 2 项
确认前必须同时满足：A/B/C/D 全通过；增强证据至少 2 项；连续 2 个交易日；critical_data_ok=true；当前状态必
须为 S1。
增强证据 定义
E1 RS_20>0

A 股主线识别系统 · V2.2 施工冻结版
数据 → 证据 → 规则 → 判断 ｜ AI 只解释 ｜ 历史可追溯
第 12 页
增强证据 定义
E2 ABOVE_MA60 > 3 日前
E3 NEW_HIGH_60 > 3 日前
E4 TOP3_TURNOVER_SHARE 不处于自身 90%高分位，或广度同步
改善（排除极端单股拉动）
E5 若有家族数据：active_subtheme_count 增加；无家族数据时本
项不计入有效增强条件
9.3 S3 转弱
恶化组 组内触发
RS RS_5 斜率<0 且 RS_10 横截面分位连续恶化
成交 TURNOVER_SHARE 连续下降，或 TURNOVER_INTENSITY 跌破 1
且继续下降
广度 ABOVE_MA20 与 NEW_HIGH_60 中至少一项连续下降，且
UP_RATIO 弱于全 A
结构 Top3 集中度上升且广度下降，或核心/中军组显著转弱
至少 2 组连续 2 日恶化，且 confirmed 后已满足 minimum_dwell=3 日 → S3。
9.4 S4 退潮
核心恶化组：RS、成交、广度三类中至少 2 类连续 3 日恶化；同时至少 1 个增强退潮信号：RS_10 横截面跌出前
50%、核心结构破坏、活跃子方向明显减少。确认 S4 后关闭 lifecycle。
10. 结构标签合同（硬状态之外）
标签 机器触发条件 结束条件
扩散 UP_RATIO/ABOVE_MA20/NEW_HIGH_60/
Top3 贡献四项中≥3 改善，且
TURNOVER_SHARE 不下降
连续 2 日不满足
抱团 Top3 正收益贡献或成交贡献处历史高位，同
时广度弱于板块价格表现
集中度回落且广度恢复
拥挤 成交/换手/RS 高分位中≥2 项 + 边际恶化≥1 拥挤条件或恶化条件消失
