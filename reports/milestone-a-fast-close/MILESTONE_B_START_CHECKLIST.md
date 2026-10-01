# MILESTONE B：Mainline Engine 开工清单

状态：仅为下一阶段准备清单；当前G1=FAIL，不是开工授权或已开发功能。

1. G1核心口径问题解决后，锁定metrics输入合同、可用性版本、横截面rank、win5/win10和60日统计。
2. 按V2.2.1 profile实现rules与S0–S4硬状态门槛；deferred指标不参与判断/计数，不把NULL当false，不降低其他阈值。
3. 实现state machine与合法迁移、consecutive days、confirm/weaken/retire计数。
4. 实现debounce、minimum dwell、lifecycle开始/结束/恢复事件。
5. 实现freeze propagation；冻结不伪造观测日、不累计连续日、不错误推进状态。
6. unit tests覆盖跨状态、缺失、冻结、恢复、边界日、不同profile、不可用增强项。
7. 固定输入、规则、参数、可用性、source manifest和checksum，实现deterministic rerun。
8. 开工仍不等于生产启用；mainline_job保持disabled，生产启用单独执行。
