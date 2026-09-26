insert into public.system_optimization_records (
  record_key,version,record_date,change_types,one_line_summary,why_changed,problems_found,main_changes,
  expected_result,database_changed,database_change_summary,screening_logic_changed,screening_logic_summary,
  automation_changed,automation_change_summary,old_data_impact,acceptance_result,unresolved_issues,next_step,
  important_decisions,technical_details
) values (
  'v4-3-2-relationship-correction','V4.3.2','2026-09-19',
  array['数据修复','逻辑调整','公司时间轴'],
  '这次纠正了两条串错赛道的证据关系，并用真实记录补齐了柯力传感的关键研究路径。',
  '最终验收时发现，商业航天机会误挂了两条机器人信号；柯力传感虽然有模型和赔率记录，但时间轴缺少首次发现、机会形成和开始建模等关键节点。',
  jsonb_build_array(
    '两条机器人量产信号被错误算进商业航天机会证据。',
    '金力永磁在公司表里存在，但没有挂到任何机会。',
    '柯力传感时间轴能看到当前结果，却不能完整还原从首次发现到首次评估的过程。'
  ),
  jsonb_build_array(
    '保留原始错误关系，另外追加更正并从有效筛选链排除。',
    '增加跨赛道关系一致性检查，以后同类错误会直接判为严重问题。',
    '补齐金力永磁与人形机器人工业规模化机会的观察关系。',
    '根据已有信号、机会、映射、模型和赔率记录补齐柯力传感关键时间轴节点。'
  ),
  '每个公司都能追到机会，每个有效机会证据都属于同一赛道，柯力传感的研究路径可以按时间完整回看。',
  true,'增加只追加的关系更正记录，并补齐真实存在但缺少的关系与时间轴节点。',
  true,'有效筛选链会自动排除已经确认错误的证据关系，但原始记录仍保留。',
  true,'每日一致性检查新增跨赛道关系和公司缺少机会两项检查。',
  '没有删除或覆盖旧数据；错误关系通过追加更正失效。',
  '部分通过',
  jsonb_build_array('外部信号采集器仍未配置，完整日流程仍会如实显示部分完成。','可用于正式历史验真的原始样本仍然不足。'),
  '接入外部信号来源并持续积累原始冻结记录。',
  jsonb_build_array('发现历史关系错误时不删除原记录，而是追加更正并让有效链路自动排除。','时间轴补录只能使用已有记录中的真实日期和内容，不能猜测。'),
  jsonb_build_object('最终验收运行','775f8a67-cd79-4191-94e9-0380b19f2bd4','排除错误关系',2,'有效跨赛道关系',0,'无机会公司',0)
)
on conflict(record_key) do nothing;
