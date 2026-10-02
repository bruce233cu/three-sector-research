# A股主线识别系统 V2.2.1 — MILESTONE D WARMUP RECOVERY RESUME REPORT

**G5 = FAIL；MILESTONE D = OPEN；不能进入 Rule Calibration。**

13项未通过原认证响应校验。当前逐项HTTP均为200，但返回字节校验和均不等于原认证值；继续网络重试不能证明已恢复原字节。未生成完整预热Baseline，无法判断原来的误报、漏报和滞后中有多少来自预热不足。

G1 = PASS / G2 = PASS / G3 = PASS / G4 = PASS（沿用，不重验）；G5 = FAIL。

## 交付27项

| 项目 | 结果 |
|---|---|
| 1. 起始SHA | f9ddd0e92885173db55ef405e6dfa545cd0da950；读取后远端新增9d75a24ab5d1d1eb4a5ccbec1faf51a6287eba40，已以新HEAD为准。 |
| 2. 最终SHA | 最终代码SHA 1585a1a20a69a86aa81c465504f0811425bb9001；恢复逻辑提交18623b689fdfe8efa3b14f50a89a10c180db9345；运行证据合并3dc03367ae10a0bf7a9be502db1fc2b540069bf5；本报告最终归档SHA见交付消息和本文件Git提交。 |
| 3. 前一轮Action | 37004800566，failure；本轮承接已启动的37008036477，failure。未再启动重复全量抓取。 |
| 4. 原失败项数量 | 13；前轮逐项清单未上传。本轮复现13项，见下表，不能伪称已找到前轮遗失清单。 |
| 5. 原失败原因分类 | 前轮逐项原因遗失；本轮复现13项均J：原认证响应字节校验不一致。A/B/C/D/E/F/G/H/I无本轮失败证据。 |
| 6. 本轮重试数量 | 活动Run做3轮、共39次缓存复核；本Work另对13项各做1次HTTP诊断。 |
| 7. 同provider重试数量 | 0次真正网络重试；39次读取同缓存，均仍不一致。13次诊断请求使用原Sina。 |
| 8. fallback数量 | 0；未引入任何新数据源。 |
| 9. valid_no_trade数量 | 请求级0；日级无交易统计未完成，不能把校验不一致的13项标成停牌或NULL。 |
| 10. 最终failure数量 | 13；分类原因明确，但没有合格认证终态，不能宣布恢复完成。 |
| 11. warmup coverage | 请求认证覆盖5369/5382 = 99.758454%；完整板块预热覆盖未生成。 |
| 12. warmup checksum | NULL：完整认证预热未生成。失败证据校验 ac87180155834153a31bf9169921a4a6e274f7de5564b7813906e8730925c792，不能冒充warmup校验。 |
| 13. cache复用 | 旧Run无artifact，现有工作区无缓存。G3/Production/Universe artifact已复用；Universe价格Parquet所需区间行数为0。活动Run三轮复用自己的13项缓存，但未上传价格缓存；未来缓存持久化已修复。 |
| 14. 是否重新下载全量 | 既有活动Run重新请求原5382证券的必要84日窗口，因为旧成功缓存未保存；授权依据用户第29–30条。没有扩大Universe、字段或日期，也未重新抓完整历史库。 |
| 15. production_writes | 0。正式快照、checkpoint、lifecycle、manifest数量和整表校验前后一致；latest_success保持NULL。系统优化留痕为独立public记录。 |
| 16. 25个case完整warmup结果 | NOT_RUN；原25个冷启动case全部保留，完整预热列为NULL。 |
| 17. cold-start vs full-warmup | NOT_RUN；同名DIFF文件明确未执行，逐case差异为NULL，不能报告为“没有变化”。 |
| 18. miss变化 | NULL；原冷启动全窗漏报4/10，仍DIAGNOSTIC_ONLY。 |
| 19. false positive变化 | NULL；原冷启动负例事件期S2为4/10、11案例行业日。 |
| 20. lag变化 | NULL；原冷启动已确认正例首次观察S2滞后中位数1交易日，不代表完整预热。 |
| 21. churn变化 | NULL；原归档转换335、反复270、短反复169。新评估器补计窗口首日转换，旧case同口径重统计为341/276/174；此口径变化不归因于warmup。 |
| 22. lifecycle变化 | NULL；完整预热未运行。 |
| 23. deterministic rerun | 完整预热NOT_RUN；原冷启动5例一致不能替代。恢复7项针对性测试、最新Baseline合同17项通过。 |
| 24. PIT状态 | effective_pit；knowledge_time_unverified=true；不宣称strict knowledge PIT。 |
| 25. G5最终状态 | FAIL；G1–G4不重开。 |
| 26. Blocking Issues | 仅下列2项。 |
| 27. 是否可以进入Rule Calibration | 否。不改规则、阈值、状态机、profile、rule_version、标签、窗口或expected_behavior。 |

## 13项失败证据

全部使用原Sina、窗口2024-04-30至2024-08-30（84个预热交易日另含前驱日）；无fallback。表中校验和只是响应字节，不能推断指定历史窗口的价格本身已经变化。原认证原始字节未归档，无法比较哪些行改变。

| security_id | symbol | HTTP | 类别/原因 | Run网络请求 | 缓存复核 | 额外诊断 | 部分缓存/现有artifact |
|---|---|---:|---|---:|---:|---:|---|
| 001367.SZ | sz001367 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |
| 002484.SZ | sz002484 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |
| 002780.SZ | sz002780 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |
| 300099.SZ | sz300099 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |
| 300190.SZ | sz300190 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |
| 300218.SZ | sz300218 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |
| 300285.SZ | sz300285 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |
| 300364.SZ | sz300364 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |
| 300872.SZ | sz300872 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |
| 301220.SZ | sz301220 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |
| 600583.SH | sh600583 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |
| 603966.SH | sh603966 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |
| 688372.SH | sh688372 | 200 | J / certified_payload_mismatch | 1 | 3 | 1 | runner有；未上传；artifact不可补 |

每项原校验和、当前校验和、来源、抓取时间和HTTP证据在 `evidence/failed_items_classified.json`。未把任何不一致响应当作success，也未伪造停牌、上市前或退市后状态。

## 两个Blocking Issues

1. 13项响应与原认证字节不一致；原字节未归档，当前可用artifact没有该区间的个股输入，无法恢复原认证版本。
2. 两个既有Run均未上传成功价格缓存和逐次原响应证据，不能继续仅靠原临时缓存完成认证与完整重放。后续保存路径已修好，但不能追溯补造旧缓存。

完整预热未合格，所以25例完整重放、真实diff及其5例重跑均没有合法输入。上述任务未执行是同一认证缺口的结果，不另堆人为阻塞项。

## 已提交的恢复补强

成功缓存跳过网络请求；每项保留来源、认证校验、请求/重试次数、错误分类、HTTP状态和缓存状态。仅临时网络、限流、服务器错误及无证明的空响应有限重试，最多3次并指数退避；认证字节不一致、单位异常不重复请求。成功和失败均上传缓存；可用resume_run_id恢复现有artifact。

差异脚本对双方使用同一版评估器，保留原冷启动文件，以免统计口径变化被错算成预热收益。以上代码通过测试但没有另触发全量恢复；本轮实际结果来自37008036477，不能把新逻辑测试结果写成该Run已经采用新逻辑。

## 下一步边界

先找回13项原认证字节和成功缓存。如原字节确实不存在，需要另外明确授权“重新认证当前历史窗口、建立新的数据版本”，并检查历史字段差异；当前任务不允许静默以新响应替代原认证数据。恢复认证前不进入规则校准。

Casebook：casebook_v1_20261002_25；checksum：249799d4c82ee067c4450e58d3409c661e2afb0dc7ff0339ae277f0f6d69c47d。
规则：mainline_v2.2.1_state_completion_v1；profile：industry_trend_v221_state_completion_v1。

未修改main、未force push、未重写历史、未运行Production或G1–G4、未新建长期个股资产。

项目修改留痕已追加并查询验证：记录bc18da02-2776-4c69-bee9-654d318bf252，验收状态“未通过”。
