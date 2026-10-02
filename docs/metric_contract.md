# V2.2冻结原文摘录 — metric_contract.md

来源：A股主线识别系统_V2.2_施工冻结版_完整规格说明书_2026-09-23.docx；Library ID libfile_09e31bd4124481918c633968098f8b58。
本附件保留对应整页原文（包含相邻章节），不新增业务定义；V2.2.1两项显式修订另见原修订文件。

A 股主线识别系统 · V2.2 施工冻结版
数据 → 证据 → 规则 → 判断 ｜ AI 只解释 ｜ 历史可追溯
第 8 页
边界情况 冻结口径
退市股 历史日期仍保留；delist_date 之后才退出 Universe
停牌股 仍属于成分，但当日无有效收益/成交时从相应指标有效分母排
除，并记录 coverage
新上市<20 日 ABOVE_MA20 分母排除，不得默认 False
新上市<60 日 ABOVE_MA60/NEW_HIGH_60 按各自历史要求排除并记录
coverage
当日无成交 成交类指标视为无有效观测，不用 0 代替
ST/特别涨跌停规则 若使用涨停类辅助指标，按当日真实规则计算
公司行动/复权 收益序列必须使用不引入未来事件的可审计复权口径；Provider 若
不能证明 PIT，标 data_quality_warning
6. 指标合同：公式、分母、缺失值与权重
指标 施工定义 缺失/边界
板块收益 默认等权成分日收益聚合；同时保留流通市值加
权辅助序列
有效收益成分不足 70%→该日板块收益无效
RS_N prod(1+sector_ret,N)-
prod(1+benchmark_ret,N)
窗口有效率<90%→null
RS 横截面分位 同日同层级有效对象 percent_rank 有效对象<10→null
WIN_5/10 窗口内 sector_ret > benchmark_ret 的有效天数
/ 有效比较天数
有效天数少于 4/8→null
TURNOVER_SHARE sum(member amount)/sum(all-A eligible 
amount)
分母=0→null
TURNOVER_PCTL percent_rank(当前 TURNOVER_SHARE vs 自身
过去窗口有效值)
60 日有效值<40 或 250 日<160→null
TURNOVER_INTENSITY 当前 TURNOVER_SHARE / 60 日中位数 中位数≤0→null
TURNOVER_CAP_DEVIATION (turnover_share - 
freefloat_mv_share)/freefloat_mv_share
市值占比≤0→null
UP_RATIO 上涨有效成分 / 有收益有效成分 覆盖率<70%→null
ABOVE_MA20/60 满足历史长度且 close>MA 的股票 / 满足历史长度
股票
coverage 单独记录

A 股主线识别系统 · V2.2 施工冻结版
数据 → 证据 → 规则 → 判断 ｜ AI 只解释 ｜ 历史可追溯
第 9 页
指标 施工定义 缺失/边界
NEW_HIGH_60 满足 60 日历史且 close>=过去 60 日最高 close 的
股票 / 可计算股票
coverage 单独记录
TOP3_TURNOVER_SHARE 成员成交额 Top3 / 板块成交额 有效成交成员<3→null
TOP3_RETURN_CONTRIBUTION 按前一交易日自由流通市值权重×当日收益形成
贡献；Top3 绝对正贡献/全部正贡献
全部正贡献≤0→null；不与负贡献相除
关键修正：Top3 收益贡献
不再用“Top3 / 板块净涨幅贡献”这种在板块接近 0 或下跌时会失真的分母。统一定义为：Top3 个股的正收益贡献 / 全
部正收益贡献。若当天没有正贡献，则返回 null，不做结构判断。
7. parameter_profile_v1.json 冻结模板
第一版参数配置
{
 "profile_id": "industry_trend_v2_2_1",
 "mainline_type": "B_industry_trend",
 "rule_version": "mainline_v2.2.0",
 "benchmark": {
 "primary": "ALL_A_EQUAL_WEIGHT",
 "secondary": [
 "ALL_A_CAP_WEIGHT"
 ]
 },
 "coverage": {
 "min_sector_return": 0.7,
 "min_breadth": 0.7,
 "min_rs_window": 0.9
 },
 "candidate": {
 "rs5_cross_section_pct_max": 0.2,
 "rs10_min": 0.0,
 "win5_min": 0.6,
 "turnover_intensity_min": 1.0,
 "candidate_min_pass_count": 3
 },
 "confirm": {
 "rs10_cross_section_pct_max": 0.3,
 "rs10_min": 0.0,
 "win5_min": 0.8,
 "win10_min": 0.7,
 "turnover_pct60_min": 0.6,
 "above_ma20_min": 0.6,
 "breadth_min_pass_count": 2,
 "enhancer_min_pass_count": 2,
 "confirm_consecutive_days": 2
 },
 "weaken": {
 "deterioration_group_min": 2,
 "consecutive_days": 2,
 "min_dwell_days_after_confirm": 3
 },
 "retire": {
 "core_deterioration_group_min": 2,
 "consecutive_days": 3,
 "rs10_cross_section_pct_exit": 0.5,
