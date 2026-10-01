# A股主线识别系统 V2.2.1 — circ_mv延后启用最小修订

本修订新增版本，不改写V2.2冻结定义、公式、旧profile或旧历史判断。

## 版本身份

- rule_version: `mainline_v2.2.1`
- parameter_profile: `industry_trend_v2_2_1_fast_close`
- metric_availability_version: `mainline_metric_availability_v2.2.1_deferred_circ_mv`

原profile虽然名称含v2_2_1，其rule_version实际为mainline_v2.2.0；名称不能作为规则版本证据。
新profile独立保留原全部阈值，仅增加可用性政策。生效日期适用于新版本执行，历史回放使用新的snapshot复合主键；不覆盖旧版本行。

## 延后启用

保留原`turnover_cap_deviation`和`top3_return_contribution`定义；原全A历史流通市值分母和前一观察日流通市值权重不变。
两指标状态为`deferred_due_to_unproven_historical_circ_mv`，角色为`optional_enhancement / deferred_metric`。
当前版本即使输入含未验证市值，也强制两指标为NULL，coverage为0并同时标注deferred；不伪装成普通数据失败。
禁止0填充、代理填充、total_mv替换、自由流通市值替换、当前值填历史或成交额代理。

两项不计入当前G1硬条件，也不因其NULL触发Freeze。S0–S4新版本规则必须`inactive_when_unavailable`：不参与硬门槛、增强项计数或缺失导致的状态降级，不得把NULL当false。不降低其他增强项通过阈值；若其余可用增强项不足，按新版明确规则处理，不能暗改旧规则。
未来恢复必须同时新建rule_version、parameter_profile、metric_availability_version，完成来源/PIT/分母验收，不回写旧版本历史判断。

## 实现核查与入口

当前仓库无已实现S0–S4状态机；15条历史snapshot的hard_status均为空。现有profile没有两指标名直接对应的S1–S4门槛，但confirm/retire保留增强项数量阈值，不能推断未实现增强项定义已通过。
新增`calculate_v221_snapshot`为显式可选计算入口，复用原冻结核心公式；旧计算入口、Sina Provider和现有回填脚本未替换。
新入口输出三个版本标识。已有snapshot用rule_version/profile_id原字段，并在decision_reason中记录metric_availability_version/circ_mv_status；run_manifest在provider_versions中记录同样可用性版本。无需改schema。
未通过当前G1前不得把数值计算结果认证为合格输入。新版入口本身不证明基准、全A成交额、来源质量或PIT。

## G1 V2.2.1最低条件

历史板块定义/日期成员/effective PIT/无当前成员倒灌/按需历史窗口/市场交易日MA20、MA60、NEW_HIGH60/OHLCV/amount/冻结定义benchmark/真实交易日历/coverage/NULL/Freeze/source/manifest/checksum/重跑一致/错误阻断仍是硬条件。
来源级质量阈值与冻结profile的sector_return >=70%、breadth >=70%、RS窗口>=90%均不降低。
`circ_mv_status=deferred`不阻塞G1；这不豁免benchmark或全A成交额分母语义。

本轮检测到原profile的ALL_A_EQUAL_WEIGHT与既有801003申万A指输入尚未证明等价；其成交额也尚未证明为历史全A成交额分母。这属于独立核心口径核验，不能由本修订自动放行。
