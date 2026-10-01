# historical circ_mv 专项诊断（Phase 1F-D1.2）

本脚本独立于生产Provider。只取12只证券的Sina原始股本、CNinfo全字段股份变动和Sina原始close，两轮共72次请求。不会实例化生产客户端、使用Token、连接数据库或执行板块批次。

安装：`python -m pip install -r scripts/mainline/phase1f_d12/requirements.txt`

联网执行（仅明确需要新一轮专项时）：
`python scripts/mainline/phase1f_d12/circ_mv_probe.py --out artifacts/phase1f_d12/NEW_RUN`

中断后使用相同输出目录会跳过已经写完的同来源、同证券、同轮次JSON，不重新请求。两轮独立取数仍按repetition分别存放。需要全新取数请使用新目录；不要把旧目录当成新的fresh run。

离线核验已下载证据包（不联网）：
`python scripts/mainline/phase1f_d12/verify_circ_mv.py /PATH/TO/phase1f_d12`

results/中仅提交小型摘要与验证表。完整原始响应/规范化全字段、source_manifest和checksums保存在交付证据ZIP中。离线核验器必须对完整ZIP解压目录执行；不能对GitHub的摘要目录执行。

候选as-of日期筛选仅用于诊断差异，不证明effective PIT。所有accepted float_shares、effective_date、circ_mv保持NULL。源事件日期未通过，脚本不会自动批准；source date/有效日期/公告日期不得混淆。

本次最终PARTIAL / FREE_CIRC_MV_NOT_PROVEN。72次请求成功、36组规范化响应重复一致，不等于历史市值可用。主要阻塞为600183季度统计与逐日转换生效序列、其他公司事件完整性、冻结语义边界及全A分母。

原Sina OHLCV主链、冻结计算器/参数、Workflow、Daily Pipeline和Supabase均未改。按用户禁止生产写入的要求，以DELIVERY.md中文留痕代替共享优化表写入。
