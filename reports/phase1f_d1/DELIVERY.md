# A股主线识别系统 V2.2 — Phase 1F-D1 在线Provider真POC交付报告

结论：PARTIAL。Sina真实行情窗口与重跑一致性达到要求，但不能宣布完整Provider POC通过，不建议进入Phase 1F-D2。本轮停止，不启用生产、不补历史样本、不进入G1/Phase 2。

## 实际执行

GitHub Actions github-hosted ubuntu-latest，Linux 6.17.0-1022-azure，Python 3.12.14，记录时区UTC。执行branch mainline-phase1e，执行SHA 9c9c7e4d576975573fc5750a9dee426d5d458907。最终Sina任务2026-10-01 10:35—10:54 UTC（北京时间18:35—18:54），约19分钟。只执行189/472/491人的三个历史成员快照，两轮重新抓取；未配置Supabase写权限。

## 健康检查与Provider结论

通达信/pytdx 1.72：首轮8节点4个握手成功；诊断轮8节点2个握手成功。诊断轮使用123.125.108.14:7709与218.6.170.47:7709，握手耗时1.086/1.852秒。5只历史成员：000045.SZ、000049.SZ、000008.SZ、000039.SZ、000020.SZ，各两次调用。10请求、0成功、10失败、0请求超时、0空返回；健康请求阶段14.54秒。两个节点均实际返回到解析流程，但pytdx报底层`unpack requires a buffer of 4 bytes`。当前锁定实现未通过健康检查，未运行板块批次；不等同于所有通达信服务永久失败。节点连接超时另列，不混同股票请求超时。保留原始BLOCKED初判及补充FAIL评审理由，不改写原始证据。

Sina/AKShare 1.18.97：健康检查同5只成员、10请求10成功，0失败/超时/空返回，耗时5.39秒；两次请求窗口一致。使用stock_zh_a_daily同一新浪原始日K URL和JS解码器，跳过其股本合并及ffill；未调用完整函数，也未调用东财。实际URL为https://finance.sina.com.cn/realstock/company/<sz或sh证券代码>/hisdata_klc2/klc_kl.js。不复权；成交量股、成交额人民币元；顺序、单位和>=60条历史窗口检查通过。停牌零量记录剔除且不补值，但未专项确认停牌身份或退市覆盖，不冒充完成这些专项验证。

## 三个样本实测

两轮下列人数、coverage、核心指标、window checksum与错误统计完全一致；时间无需相等。

| sample_id |成员|有效成员|MA20|MA60/NEW_HIGH60/window|OHLCV/amount|circ_mv|单轮错误|耗时两轮(秒)|
|---|---:|---:|---:|---:|---:|---:|---:|---|
|2019-06-28:801080|189|187|97.35%|90.48%|98.94%|0%|1|94.99 / 98.32|
|2021-12-31:801890|472|449|93.43%|89.41%|95.13%|0%|23|230.84 / 228.82|
|2025-06-30:801080|491|463|92.26%|90.84%|94.30%|0%|28|245.37 / 231.64|

单轮失败构成：2019样本1空返回；2021样本15个BJ证券映射不支持、8空返回；2025样本18个BJ映射不支持、10空返回。BJ属于本POC适配能力缺口，不能据此断言新浪底层绝不支持北交所。空返回原因未确证，不能直接归因退市。两个批次合计104错误；无预算耗尽；不使用其他样本。

## 指标、Freeze、NULL与正式验收阻塞

三个板块均生成sector_return、benchmark_return、rs_5/10/20、turnover_share/intensity、up_ratio、above_ma20/60、new_high_60、top3_turnover_share。critical_data_ok均true，stage_frozen均false，freeze_reason均NULL。turnover_cap_deviation和top3_return_contribution依赖历史circ_mv，保持NULL；circ_mv coverage=0%是实测0个有效字段/真实成员数，绝非缺失值填0。

严格最后20个市场交易日coverage分别97.35%、93.43%、92.26%；原计算器above_ma20 coverage分别98.94%、94.49%、93.89%。原计算器在60日窗口内取最近20个有效观测收盘，不检查是否恰好最后20个市场交易日，分别多计3/5/8个成员。因此执行包`frozen_coverage_agrees_with_exact_window=false`，`market_window_pass=false`，整体PARTIAL。MA60/NEW_HIGH60口径一致。此问题属于已有计算器与严格窗口验收口径差异，不能误判Sina行情覆盖失败。本轮不改公式、Freeze或验收阈值。

原计算器SHA256 de70271459a5c98e3649a379910062c4730b4e313312c2c3a74ed79c2eb8b775，未修改。原25项离线测试通过。真实POC不能用离线测试代替。

## PIT、来源及结果包

沿用既有历史成员快照，pit_level=effective_pit、knowledge_time_unverified=true。输入检查验证人数、成员有效起止日期与唯一性；代码强制只用样本日期之前、且属于历史成员的行情，不使用当前成员、未来行情或填补。ZIP无股票明细缓存，Work未做逐行价格重放，因此PIT证据是快照/代码/manifest链，不宣称严格knowledge-time已通过。

11个标准文件全部生成：summary.json、provider_health.json、samples.csv、coverage_report.json、metrics_output.json、run_manifest.json、source_manifest.json、checksums.json、errors.json、environment.json、repeatability_report.json。所有声明的文件checksum已逐一核验。source_manifest记录每证券响应checksum与获取时间，run_manifest保存输入/code/参数哈希与样本run_id。指标仅直接关联价格source ID；成员/基准可由输入完整性与source checksum追溯，但未在每指标行补齐关联ID。manifest沿用C阶段job_name标签，实际D1身份由summary/Git SHA确定。这些追溯元数据缺口列为未完成项，本轮未重写原始结果。

SWS基准沿用原适配器，未执行东财个股接口。基准全量响应含其它日期，但计算严格截断到各样本日期；该原始板块级响应保留在证据中。既有适配器verify=False，传输真实性未强验证，不擅自改变数据源口径。

GitHub run https://github.com/bruce233cu/three-sector-research/actions/runs/36850082132
Artifact 11155722709，SHA256 f50d0b018e331728076207e296ebe4af36cea852f3671e2ecb2fb78676bcf8fe，GitHub保留到2026-10-08。ZIP无个股缓存；runner临时缓存随任务销毁，不建长期数据库。Provider无账号/token、未购买付费数据；runner计费按仓库自身额度，本轮未核验账单。

## GitHub及边界

只写mainline-phase1e。代码提交167ffc5a70a538e547ffc335ea35ca534bbfd0f8（独立POC入口）、141d88413ccc81fec2c908328a61927ebeaab758（底层异常及节点切换）、9c9c7e4d576975573fc5750a9dee426d5d458907（依据通达信证据测试Sina）。最终证据说明提交见交付回复。

修改文件：.github/workflows/mainline-phase1fd1-poc.yml；scripts/mainline/phase1f_d1_run.py；scripts/mainline/phase1f_c/build.py；scripts/mainline/phase1f_c/integrity.json；src/mainline/providers/phase1f_free.py；reports/phase1f_d1/tdx_health_evidence.json；reports/phase1f_d1/acceptance_review.json；reports/phase1f_d1/DELIVERY.md。

是否修改main：否（仍为938fa5b8e4ed6ea7336617b1067ab2e5a9876743）。是否修改Supabase schema/写生产数据/启用mainline_job/补剩余PARTIAL/进入G1/进入Phase2/改UI/改三大赛道或Daily Pipeline：全部否。未建长期个股库。历史样本仍SUCCESS5/PARTIAL10/FAIL0，mainline_job仍pending_provider，G1状态不变。

后续结论：Sina值得保留为行情窗口候选，但本轮不建议进入D2；须先明确既有MA20覆盖口径差异的处理授权、完善所需证据与历史circ_mv独立方案，再考虑重新验收。此次停止，不自动补数或接入生产。
