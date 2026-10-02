# MILESTONE B — BUSINESS_RULE_CONFLICT

冻结原文：V2.2施工冻结版（2026-09-23），已完整读取21页；来源ID及摘录见
metric_contract.md、rules.md、state_machine.md、backtest_contract.md、acceptance_checklist.md。
本记录不改阈值、不创造新规则；G1保持PASS，不返回Phase 1。

## 1. 转弱/退潮的可执行定义未闭合（原文第12页）

原文要求“RS_5斜率<0”“RS_10横截面分位连续恶化”“继续下降”
“广度下降”“核心/中军组显著转弱”“核心结构破坏”“活跃子方向明显减少”。
未固定斜率估计方法/窗口、组内连续下降窗口、广度同步改善/下降的聚合判据、
核心/中军证券分组与显著阈值、结构破坏或子方向明显减少的量化定义。
E4“自身90%高分位”也未固定历史窗口/最低样本和“广度同步改善”聚合定义。
这些是业务判据，不能以开发者猜测替代。E1–E3已实现，可独立贡献增强证据，
E4未知不会被当作false；无家族数据的E5不冒充有效增强证据。
所有未闭合的必要组保持NULL，不输出假的S3/S4。

## 2. Freeze恢复与S3恢复S2的计数合同未闭合（原文第10–12页）

原文明确坏数据Frozen(prev)，但没有规定Freeze跨日后连续计数是重置、
暂停保留还是按何种条件恢复；也没有规定recover_to_confirmed的完整判据
与连续天数。冻结期间沿用可信状态已实现。数据恢复后不猜测补写转移，
缺少恢复合同则保持状态并记录resume_policy_unresolved。
单元测试中的显式reset只证明内核支持该策略，是fixture假设，不是新增冻结规则。
S4重入新lifecycle从S1开始，依据原文第10页转移表和第17页T-SM-002；
原伪代码的S4 return S4只作用于已关闭的旧lifecycle，新周期不重开旧记录。

## 3. 真实状态验收输入不足（不是Provider失败）

数据库现有15个SUCCESS指标样本：每个日期仅3个有效SW1对象，合计6个不同对象。
原指标合同要求同日同层级RS横截面有效对象至少10个；不得对3对象重排名后冒充全市场。
旧样本hard_status为空，没有连续可信previous_state或已确认lifecycle的种子。
现有缓存可重用构造真实60日行情/benchmark窗口，但只证明目标5日期membership完整，
不能把目标日期股票集合静态延伸为所有中间日期的完整历史membership。
因此真实连续窗口只作为诊断证据，不能认证历史升级/退潮。
正式引擎输出保持未知状态NULL、stage_frozen=true和明确阻塞原因。

这些缺口不影响已关闭的G1。代码、明确规则、指标测试和离线审计继续完成，
但MILESTONE B不能宣称CLOSED或READY_FOR_DAILY_MAINLINE=true。
