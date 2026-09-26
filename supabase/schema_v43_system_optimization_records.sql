-- V4.3: a plain-language, append-only growth record for the research system.
create table if not exists public.system_optimization_records (
  id uuid primary key default gen_random_uuid(),
  record_key text not null unique,
  version text not null,
  record_date date not null,
  change_types text[] not null default '{}',
  one_line_summary text not null,
  why_changed text not null,
  problems_found jsonb not null default '[]'::jsonb,
  main_changes jsonb not null default '[]'::jsonb,
  expected_result text not null,
  database_changed boolean not null default false,
  database_change_summary text,
  screening_logic_changed boolean not null default false,
  screening_logic_summary text,
  automation_changed boolean not null default false,
  automation_change_summary text,
  old_data_impact text not null default '没有影响旧数据',
  acceptance_result text not null
    check (acceptance_result in ('已通过','部分通过','未通过')),
  unresolved_issues jsonb not null default '[]'::jsonb,
  next_step text not null,
  important_decisions jsonb not null default '[]'::jsonb,
  technical_details jsonb not null default '{}'::jsonb,
  is_version_summary boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists system_optimization_records_version_date_idx
  on public.system_optimization_records(version, record_date desc, created_at desc);
create index if not exists system_optimization_records_change_types_idx
  on public.system_optimization_records using gin(change_types);

alter table public.system_optimization_records enable row level security;
drop policy if exists "system_optimization_records_public_read"
  on public.system_optimization_records;
create policy "system_optimization_records_public_read"
  on public.system_optimization_records
  for select to anon, authenticated using (true);

grant select on public.system_optimization_records to anon, authenticated;
grant insert on public.system_optimization_records to authenticated, service_role;

insert into public.system_optimization_records (
  record_key, version, record_date, change_types, one_line_summary,
  why_changed, problems_found, main_changes, expected_result,
  database_changed, database_change_summary, screening_logic_changed,
  screening_logic_summary, automation_changed, automation_change_summary,
  old_data_impact, acceptance_result, unresolved_issues, next_step,
  important_decisions, technical_details
) values
(
  'v4-0-summary','V4.0','2026-09-18',
  array['逻辑调整','模型调整','公司时间轴','数据修复'],
  '这次把原来偏静态的研究页面，升级成能一步步判断公司、计算赔率并记录公司变化的基础系统。',
  '原来的系统能展示信号和公司，但公司为什么进入下一步、利润怎样变成赔率、状态为什么变化，还没有一套统一规则。',
  jsonb_build_array(
    '公司完成利润核算以后，和是否值得投资混在一起。',
    '价格、利润、概率和期望收益之间缺少统一计算过程。',
    '公司后续发生了什么，缺少连续的历史记录。'
  ),
  jsonb_build_array(
    '建立了从机会、公司、模型到投资价值的基础状态规则。',
    '增加了悲观、中性、乐观三种情况的利润、概率和赔率计算。',
    '增加了公司关键变化记录和投资价值评估。'
  ),
  '以后公司必须先有完整模型，再结合当天价格判断是否值得投资；公司重要变化也可以回看。',
  true,'增加了模型、赔率、状态变化和公司时间记录所需的长期保存能力。',
  true,'把完成模型、完成评估和通过投资筛选分成不同判断。',
  true,'增加了生成投资价值结果后继续评估公司状态的基础机制。',
  '有，但旧数据已经保留，并按新规则重新整理。',
  '部分通过',
  jsonb_build_array(
    '当时还没有完整解决日报、筛选链展示和历史记录冻结。',
    '每日更新仍主要依赖人工写入。'
  ),
  '继续整理前端结构，让用户能看清公司是怎样一步步筛出来的。',
  jsonb_build_array(
    '公司赚多少钱和值多少钱是一层；今天这个价格划不划算是另一层。',
    '完成赔率测算，不代表通过投资筛选。',
    '价格变化只能改变赔率，不能直接改变公司基本面概率。'
  ),
  jsonb_build_object(
    '依据','现有提交和数据库变更',
    '相关提交',jsonb_build_array('23f5228','078f958','3b89eda')
  )
),
(
  'v4-1-summary','V4.1','2026-09-18',array['界面调整'],
  '这次主要把页面重新整理得更舒服，并把不同入口的公司详情统一起来。',
  'V4.0的功能逐渐增多，页面越来越像后台表格，同一家公司还可能从不同入口进入不同的详情页面。',
  jsonb_build_array(
    '页面字段多、层级弱，打开后不容易先看到结论。',
    '同一家公司在不同页面的入口不统一。',
    '界面变清楚以后，一步步筛选的主线反而不够明显。'
  ),
  jsonb_build_array(
    '重新整理了前端信息层级和页面职责。',
    '统一了公司跳转入口。',
    '提高了列表和详情页的阅读效率。'
  ),
  '打开页面后先看到结论、原因和下一步，同一家公司进入同一个详情页。',
  false,null,false,null,false,null,
  '没有影响旧数据。','部分通过',
  jsonb_build_array(
    '页面虽然更舒服了，但信号到机会、公司、模型、投资价值的筛选链不够清楚。',
    '完整日报和公司研究历史没有在新结构里充分表达。'
  ),
  '恢复完整筛选链，同时补回完整日报和公司时间轴。',
  jsonb_build_array(
    '同一家公司无论从哪里点击，都应该进入同一个公司详情页。',
    '详细数据放在第二层，第一屏先说结论、原因、变化和下一步。'
  ),
  jsonb_build_object(
    '依据','现有提交记录',
    '相关提交',jsonb_build_array('639d6eb','a2a0a71')
  )
),
(
  'v4-2-summary','V4.2','2026-09-19',
  array['界面调整','逻辑调整','日报调整','公司时间轴','数据修复'],
  '这次恢复了一步步筛选逻辑，同时补回完整日报、公司时间轴和统一公司详情。',
  'V4.1虽然页面舒服了，但看不出公司是怎样从信号一步步筛到投资价值的，日报也不足以说明当天整个系统发生了什么。',
  jsonb_build_array(
    '筛选链在界面上不够完整。',
    '日报过度浓缩，机会、公司、模型、赔率和风险没有完整放在一起。',
    '观察公司暂停在哪一步、为什么暂停不够清楚。',
    '公司信息分散，缺少从第一次发现到现在的完整研究路径。'
  ),
  jsonb_build_array(
    '恢复了五阶段筛选链，并让每个节点可以进入对应页面。',
    '建立了包含十个部分的每日研究日报。',
    '增加了独立公司时间轴和统一公司详情。',
    '把观察阶段、观察原因和重新激活条件整理清楚。',
    '补充了信号形成机会的长期关系记录。'
  ),
  '用户可以沿着信号、机会、公司、模型和投资价值逐步查看，也能通过日报和时间轴理解当天变化与公司历史。',
  true,'增加了筛选结论、信号与机会关系、日报冻结内容等记录。',
  true,'持续验证不再作为第六步；完成评估和通过高期望收益判断明确分开。',
  false,null,
  '没有删除旧数据；旧数据继续保留，并补充了新的关系和历史记录。',
  '部分通过',
  jsonb_build_array(
    '后来验收发现部分历史记录仍可能被覆盖。',
    '自动化显示完成，但没有真正的每日调度和失败提醒。',
    '部分模型数字在不同页面显示口径不一致。',
    '历史日报中有事后补录内容，不能直接用于严格盲测。'
  ),
  '进入V4.3：先建立系统优化记录，再逐项处理历史留痕、自动化和模型显示问题。',
  jsonb_build_array(
    '持续验证不是最后一步，而是从发现机会开始就一直在做。',
    '公司时间轴单独记录公司从第一次发现到后续验证的完整变化。',
    '完成赔率测算，不代表通过投资筛选。',
    '历史日报生成以后，不应该被后来数据反向改写。'
  ),
  jsonb_build_object(
    '依据','现有提交、数据库变更和V4.2全系统验收',
    '相关提交',jsonb_build_array('8da46d2','40f971d','ba5fc01','a893d2e')
  )
),
(
  'v4-3-system-optimization-log','V4.3','2026-09-19',
  array['界面调整','数据修复','自动化修复'],
  '这次增加了一个给未来自己看的系统成长记录本，以后每次改系统都要说明为什么改、改了什么和还剩什么。',
  '系统已经连续升级多个版本，但以前缺少一处能用大白话回看每次修改原因、结果和遗留问题的地方，时间久了很容易重复推翻已经确定的规则。',
  jsonb_build_array(
    '以前只能从代码提交和数据库变化里猜每个版本做了什么。',
    '没有长期保存“当时为什么要改”。',
    '重要决定分散在不同任务里，几个月后很难快速回忆。',
    '每次Work任务结束后没有固定的系统留痕步骤。'
  ),
  jsonb_build_array(
    '增加“系统优化记录”入口和按版本分组的时间线。',
    '增加按版本和修改类型查看的筛选。',
    '每条记录保存为什么改、发现的问题、主要修改、重要决定和下一步。',
    '技术内容默认收起，需要时再展开。',
    '补录V4.0、V4.1、V4.2，并建立以后每次Work修改完成必须补记录的规则。'
  ),
  '以后只看一句话就能知道每个版本主要做了什么；展开后可以看清当时的问题、修改结果和遗留事项。',
  true,'增加了专门保存系统优化历史的记录，不改动原有研究数据。',
  false,'没有修改信号、机会、公司、模型或投资价值的筛选规则。',
  true,'增加了Work任务完成后必须同步补写系统优化记录的固定规则。',
  '没有影响旧数据，只新增系统优化记录。',
  '已通过',
  jsonb_build_array(
    '这个功能能保证以后Work修改按规则留痕，但系统外部的手工修改仍需要主动补记录。'
  ),
  '下一步按照V4.2验收结果，优先修复模型数字显示、历史记录覆盖和自动化真实运行问题。',
  jsonb_build_array(
    '系统优化记录和公司时间轴是两套记录：前者记系统怎么成长，后者记公司怎么变化。',
    '每次记录最重要的是说明当时为什么要改。',
    '默认给人看大白话，技术内容只在需要时展开。'
  ),
  jsonb_build_object(
    '依据','本次真实功能实现和现有版本记录',
    '相关版本',jsonb_build_array('V4.0','V4.1','V4.2','V4.3')
  )
)
on conflict (record_key) do nothing;
