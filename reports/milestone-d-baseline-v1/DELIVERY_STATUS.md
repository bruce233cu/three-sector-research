# MILESTONE D 交付状态

G5 = FAIL；MILESTONE D = OPEN。完整 Baseline 没有完成，规则没有优化。

## 唯一根本阻塞：完整认证预热未恢复

原认证的2024-05-06至2024-08-30共84日预热板块输入没有归档。隔离恢复作业37008036477请求5382个原成功来源，其中5369个通过原始响应校验和一致性检查，13个响应与原认证校验和不同，因此没有生成可被接纳的完整预热板块，也没有继续完整预热运行。原价格临时缓存没有上传，现有归档无法补齐。没有用缺失、零值或其他来源替代。

13项为：001367.SZ、002484.SZ、002780.SZ、300099.SZ、300190.SZ、300218.SZ、300285.SZ、300364.SZ、300872.SZ、301220.SZ、600583.SH、603966.SH、688372.SH。

恢复审计见 warmup-recovery/recovery_attempt_audit.json。仓库同期归档的 ../milestone-d-warmup-resume/ 证据已保留：13项独立诊断HTTP为200、校验不一致，不代表可以推断指定历史窗口的价格已经变化。旧恢复实现的三轮重试复查了缓存，不能声称进行了三轮新网络重试。

恢复分类、成功缓存复用、临时缓存artifact和run目录隔离代码已保留；7项恢复合同测试通过，但没有额外启动新补数作业，不声称本轮旧缓存已被找回。

## 已完成隔离诊断证据

25例Casebook先冻结，10正、10负、5模糊；标签不进入引擎。
最新版本为 runs/historical-blind-v1-20261002-diagnostic-v2，仅为冷启动诊断。

25例业务轨迹与5例完整确定性重跑由隔离作业37009367622完成；该作业后续检查因运行标识关联错误失败。
修正检查器输入的运行标识后，作业37010023384复用上述不可变业务artifact，24项隔离测试和执行层时点检查通过。
9类未来扰动均不影响历史结果；历史RS重算17329次，差异0。

原冷启动-01文件保留。新版341次转换、276次状态重访、174次5日内重访，包括窗口首日已知转换；统计变化不能归因为预热或规则改进。

主报告先于候选清单生成；候选清单仅是初步研究假设，因G5失败暂不进入校准。
完整预热与冷启动的差异比较没有执行，结果为NULL，不是零变化。

## 生产保护

详见 production_protection_after.json。本轮前后：snapshot=385、checkpoint=310、lifecycle=1351、rule evidence=16430；checkpoint和lifecycle整体校验和均未变。
相对于起始SHA，现有基线文件没有修改。生产业务、参数、状态规则、Freeze、circ_mv、Provider、Universe、three-sector、production workflow和Sites保持原状。
mainline_job仍为is_scheduled=true；原Daily Pipeline保持0 9 * * * UTC，即北京时间17:00；没有新增cron。
Sites保持v41；MAINLINE_LIVE保持READY_WAITING_FIRST_PRODUCTION_RUN；MANUAL_UI_CHECK_REQUIRED保留。

## 下一步边界

先找回原认证预热输入、13个差异来源的原响应及成功缓存。
如这些输入不可恢复，当前任务停止；是否以当前历史响应重新认证并冻结另一数据版本，需要另行明确授权，不能静默替换。
完整预热通过后，使用相同冻结Casebook与规则重放，至少5例完整重跑，采用同一评估器比较cold/full，再验收G5。
在此之前不改变标签、阈值、状态规则、Provider、Universe或生产入口；不开始规则校准或MILESTONE E。
