insert into public.system_optimization_records (
  record_key,version,record_date,change_types,one_line_summary,why_changed,
  problems_found,main_changes,expected_result,database_changed,database_change_summary,
  screening_logic_changed,screening_logic_summary,automation_changed,automation_change_summary,
  old_data_impact,acceptance_result,unresolved_issues,next_step,important_decisions,technical_details
) values (
  'v4-4-historical-information-validation','V4.4','2026-09-19',array['历史测试','数据修复'],
  '这次没有检验赚不赚钱，只检验系统回到过去时会不会偷看未来；第一轮查出了历史资料是后来补进来的，而且资料范围只围绕当前研究公司，所以没有通过。',
  '实时研究系统已经能每天运行，但这不代表把它放回过去也可信。最大的风险是今天能查到的资料被误当成当时已经知道，或者先知道研究公司是谁，再围绕这些公司补历史资料。',
  jsonb_build_array(
    '候选历史资料虽然当时已经公开，但系统是在十多天后才采集到，不能放进当时的证据包。',
    '现有公告资料只覆盖当前研究池里的8家公司，不是当时全市场统一扫描出来的公司池。',
    '缺少当时版本的财报、行业数据、证券名单、历史股本和负面信息覆盖。',
    '因此无法从信号一直回放到公司模型和投资价值。'
  ),
  jsonb_build_array(
    '建立了和实时系统完全分开的历史验证记录区。',
    '把事情发生、公开、可获得和系统实际采到的时间分开保存。',
    '每个测试先锁定日期、模型、规则、门槛、数据源、搜索规则和代码版本。',
    '增加了被排除资料、来源覆盖、搜索路径、公司发现路径和未来泄漏检查。',
    '固定并真实运行了机器人、商业航天和AI三个小窗口。',
    '发现资料库偏差后，按规则把三次测试全部标记为无效，没有继续生成公司和模型。'
  ),
  '以后历史资料只有在判断时点前已经公开、可以获得并且系统已经实际采到，才能进入证据包；发现作弊风险就停止，不能拿无效结果评价系统。',
  true,'增加了独立历史验证记录，不改实时信号、机会、公司、模型、日报或当前状态。',
  false,'没有修改实时筛选逻辑；历史回放只是把同一套规则锁定后隔离运行。',
  false,'没有改每日实时自动化，历史验证按独立测试运行。',
  '没有影响旧数据；历史测试只复制来源记录，不向实时研究表写回任何结果。',
  '未通过',
  jsonb_build_array(
    '需要按统一赛道关键词和统一官方来源建立不围绕当前公司名单的历史资料库。',
    '需要补当时完整证券池，包括后来退市、更名和重组的公司。',
    '需要补财报、行业数据、机构预测和股本的当时版本。',
    '需要提高负面信息覆盖后，再重新创建新的测试编号。'
  ),
  '先补齐真正按历史时点建立的数据源和证券池，再新建V4.4测试；在此之前不进入V4.5动态盲测。',
  jsonb_build_array(
    '历史资料当时公开，不等于系统当时已经知道。',
    '证据包以系统实际采到的时间为准，模型不能凭记忆补事实。',
    '无效和运行失败分开：跑完但发现作弊风险叫无效。',
    '历史测试结果永远不写回实时公司状态。',
    '本轮不显示收益、胜率或最佳股票。'
  ),
  jsonb_build_object(
    '三个测试',jsonb_build_array('V44-ROB-20260901','V44-SPACE-20260901','V44-AI-20260901'),
    '共同窗口','预热2026-08-25；正式回放2026-09-01至2026-09-08',
    '候选资料',68,'严格可用资料',0,'未来信息泄漏',0,'模型知识泄漏',0,'后验搜索违规',0,
    '资料库构建偏差',3,'测试状态','INVALID'
  )
)
on conflict (record_key) do nothing;

insert into public.system_optimization_records (
  record_key,version,record_date,change_types,one_line_summary,why_changed,
  problems_found,main_changes,expected_result,database_changed,database_change_summary,
  screening_logic_changed,automation_changed,old_data_impact,acceptance_result,
  unresolved_issues,next_step,important_decisions,technical_details
) values (
  'v4-4-negative-coverage-wording-correction','V4.4','2026-09-20',array['数据修复','历史测试'],
  '这次只更正了一句不准确的话：候选库里有负面公告，但系统当时并没有采到，所以严格可用负面信息仍然是0。',
  '发布后的再次核对发现，原记录把“当时严格可用的负面信息为0”写成了“候选资料没有负面记录”，容易让人误解成资料库完全没有负面内容。',
  jsonb_build_array('三个赛道的预热期资料里各有1条负面公告，但都在历史判断日之后才被系统采集。'),
  jsonb_build_array('保留原检查记录，另外追加一条更正说明；没有覆盖或删除旧记录。'),
  '页面同时显示更正后的准确结论和更正原因，历史审计过程本身也可以追溯。',
  true,'增加了只追加的历史检查更正记录。',false,false,
  '没有影响实时研究数据，也没有改变三次测试的无效结论。','已通过',
  jsonb_build_array('严格历史负面信息覆盖仍然为0，仍需重建。'),
  '继续补齐真正按历史时点采集的统一资料库。',
  jsonb_build_array('审计记录发现写错时不能覆盖原记录，只能追加更正。'),
  jsonb_build_object('更正数量',3,'原结论','负面覆盖不通过','更正后结论','负面覆盖仍不通过')
)
on conflict (record_key) do nothing;
