-- V4.2: traceable screening decisions and immutable daily-report payloads.
create table if not exists public.screening_decisions (
  id uuid primary key default gen_random_uuid(),
  object_type text not null check (object_type in ('signal','opportunity','company','model','investment')),
  object_id uuid not null,
  object_name text not null,
  stage text not null check (stage in ('change_discovery','opportunity_confirmation','company_mapping','company_modeling','investment_value','high_expected_return')),
  decision text not null check (decision in ('pass','observe','fail','evaluated','validator','pending')),
  reason text not null,
  evidence_ids uuid[] not null default '{}',
  next_step text,
  rule_version text not null default 'V4.2',
  evaluated_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (object_type, object_id, stage, rule_version)
);

create index if not exists screening_decisions_stage_idx
  on public.screening_decisions(stage, decision, evaluated_at desc);
create index if not exists screening_decisions_object_idx
  on public.screening_decisions(object_type, object_id, evaluated_at desc);

alter table public.daily_reports
  add column if not exists frozen_snapshot jsonb not null default '{}'::jsonb,
  add column if not exists report_version text not null default 'V4.2',
  add column if not exists generated_at timestamptz not null default now();

alter table public.screening_decisions enable row level security;
drop policy if exists "screening_decisions_anon_read" on public.screening_decisions;
create policy "screening_decisions_anon_read" on public.screening_decisions
  for select to anon using (true);
drop policy if exists "screening_decisions_authenticated_all" on public.screening_decisions;
create policy "screening_decisions_authenticated_all" on public.screening_decisions
  for all to authenticated using (true) with check (true);
grant select on public.screening_decisions to anon;
grant select, insert, update, delete on public.screening_decisions to authenticated;

insert into public.screening_decisions
  (object_type, object_id, object_name, stage, decision, reason, next_step, evaluated_at, metadata)
select 'signal', s.id, s.title, 'change_discovery',
  case when s.status = 'watch' then 'fail' when coalesce(s.action,'') in ('观察','继续观察') then 'observe' else 'pass' end,
  coalesce(nullif(s.change_description,''), '已形成结构化变化记录'),
  coalesce(nullif(s.verification_needed,''), '等待下一条可验证证据'),
  coalesce(s.updated_at,s.created_at),
  jsonb_build_object('signal_date',s.signal_date,'source_url',s.source_url,'source_grade',s.source_grade)
from public.signals s
on conflict (object_type, object_id, stage, rule_version) do update set
  decision=excluded.decision, reason=excluded.reason, next_step=excluded.next_step,
  evaluated_at=excluded.evaluated_at, metadata=excluded.metadata, updated_at=now();

insert into public.screening_decisions
  (object_type, object_id, object_name, stage, decision, reason, next_step, evaluated_at, metadata)
select 'opportunity', o.id, o.name, 'opportunity_confirmation',
  case when o.opportunity_status='confirmed' then 'pass'
       when coalesce(o.action,'')='观察' then 'observe' else 'pending' end,
  coalesce(nullif(o.core_change,''),nullif(o.upgrade_evidence,''),nullif(o.pool_reason,''),'等待机会证据闭环'),
  coalesce(nullif(o.next_verification,''),nullif(o.next_research,''),'继续验证机会成立条件'),
  coalesce(o.updated_at,o.created_at),
  jsonb_build_object('external_id',o.external_id,'status',o.opportunity_status,'pass_result',o.pass_result)
from public.opportunities o
on conflict (object_type, object_id, stage, rule_version) do update set
  decision=excluded.decision, reason=excluded.reason, next_step=excluded.next_step,
  evaluated_at=excluded.evaluated_at, metadata=excluded.metadata, updated_at=now();

insert into public.screening_decisions
  (object_type, object_id, object_name, stage, decision, reason, next_step, evaluated_at, metadata)
select 'company', c.id, c.name, 'company_mapping',
  case when c.company_role='industry_validator' then 'validator'
       when c.research_pool_status='shadow' and c.shadow_stage='mapping' then 'observe'
       when c.research_pool_status in ('research','shadow') then 'pass' else 'pending' end,
  coalesce(nullif(c.transition_reason,''),nullif(c.pool_reason,''),nullif(c.shadow_reason,''),'已纳入公司映射'),
  coalesce(nullif(c.reactivation_condition,''),nullif(c.key_assumptions,''),'补充公司受益证据'),
  coalesce(c.last_transition_at,c.updated_at,c.created_at),
  jsonb_build_object('role',c.company_role,'pool',c.research_pool_status,'shadow_stage',c.shadow_stage)
from public.companies c
on conflict (object_type, object_id, stage, rule_version) do update set
  decision=excluded.decision, reason=excluded.reason, next_step=excluded.next_step,
  evaluated_at=excluded.evaluated_at, metadata=excluded.metadata, updated_at=now();

insert into public.screening_decisions
  (object_type, object_id, object_name, stage, decision, reason, next_step, evaluated_at, metadata)
select 'company', c.id, c.name, 'company_modeling',
  case when c.valuation_status='completed' then 'pass'
       when c.shadow_stage='modeling' or c.valuation_status='insufficient_data' then 'observe'
       when c.company_role='industry_validator' then 'validator' else 'pending' end,
  case when c.valuation_status='completed' then '悲观/中性/乐观模型已经完成'
       else coalesce(nullif(c.accounting_blocker,''),nullif(c.shadow_reason,''),'关键输入尚不完整') end,
  coalesce(nullif(c.reactivation_condition,''),nullif(c.key_assumptions,''),'补齐利润模型关键变量'),
  coalesce(c.updated_at,c.created_at),
  jsonb_build_object('valuation_status',c.valuation_status,'accounting_status',c.accounting_status)
from public.companies c
where c.company_role <> 'industry_validator' or c.company_role is null
on conflict (object_type, object_id, stage, rule_version) do update set
  decision=excluded.decision, reason=excluded.reason, next_step=excluded.next_step,
  evaluated_at=excluded.evaluated_at, metadata=excluded.metadata, updated_at=now();

insert into public.screening_decisions
  (object_type, object_id, object_name, stage, decision, reason, next_step, evaluated_at, metadata)
select 'investment', ia.id, c.name, 'investment_value', 'evaluated',
  '已使用公司模型、最新价格与市值完成投资价值评估',
  case when ia.passed then '持续跟踪赔率与风险' else coalesce(array_to_string(ia.failure_reasons,'；'),'等待重新评估') end,
  ia.assessed_at,
  jsonb_build_object('company_id',c.id,'classification',ia.classification,'expected_return',ia.expected_return,'risk_reward',ia.risk_reward)
from public.investment_assessments ia join public.companies c on c.id=ia.company_id
on conflict (object_type, object_id, stage, rule_version) do update set
  decision=excluded.decision, reason=excluded.reason, next_step=excluded.next_step,
  evaluated_at=excluded.evaluated_at, metadata=excluded.metadata, updated_at=now();

insert into public.screening_decisions
  (object_type, object_id, object_name, stage, decision, reason, next_step, evaluated_at, metadata)
select 'investment', ia.id, c.name, 'high_expected_return',
  case when ia.passed and ia.classification='high_expected_return' then 'pass' else 'fail' end,
  case when ia.passed and ia.classification='high_expected_return' then '达到高期望收益规则'
       else coalesce(array_to_string(ia.failure_reasons,'；'),'未达到高期望收益规则') end,
  case when ia.passed then '进入持续验证' else coalesce(c.reactivation_condition,'等待价格或基本面触发重新评估') end,
  ia.assessed_at,
  jsonb_build_object('company_id',c.id,'classification',ia.classification,'expected_return',ia.expected_return,'base_return',ia.base_return,'max_downside',ia.max_downside,'risk_reward',ia.risk_reward)
from public.investment_assessments ia join public.companies c on c.id=ia.company_id
on conflict (object_type, object_id, stage, rule_version) do update set
  decision=excluded.decision, reason=excluded.reason, next_step=excluded.next_step,
  evaluated_at=excluded.evaluated_at, metadata=excluded.metadata, updated_at=now();

update public.daily_reports dr
set frozen_snapshot = jsonb_build_object(
  'report_date', dr.report_date,
  'generated_at', now(),
  'is_frozen', true,
  'headline', dr.summary,
  'stats', jsonb_build_object(
    'new_valid_signals', dr.valid_signal_count,
    'new_opportunities', dr.new_pool_count,
    'opportunity_strengthened', (select count(*) from public.daily_opportunity_reviews dor where dor.report_date=dr.report_date and dor.current_stage is distinct from dor.previous_stage and dor.action in ('研究','重点研究')),
    'opportunity_weakened', (select count(*) from public.daily_opportunity_reviews dor where dor.report_date=dr.report_date and dor.action='观察'),
    'new_mapped_companies', (select count(*) from public.opportunity_companies oc where oc.created_at::date=dr.report_date),
    'entered_modeling', (select count(distinct pm.company_id) from public.profit_models pm where pm.created_at::date=dr.report_date),
    'model_completed', (select count(distinct pm.company_id) from public.profit_models pm where pm.model_status='complete' and pm.updated_at::date=dr.report_date),
    'investment_evaluated', (select count(*) from public.investment_assessments ia where ia.assessed_at::date=dr.report_date),
    'high_expected_return', (select count(*) from public.investment_assessments ia where ia.assessed_at::date=dr.report_date and ia.passed and ia.classification='high_expected_return'),
    'to_observe', (select count(*) from public.company_state_transitions st where st.created_at::date=dr.report_date and st.to_status in ('shadow','watch','影子池')),
    'logic_invalidated', (select count(*) from public.company_validation_events ve where ve.validation_date=dr.report_date and ve.effect in ('invalidated','fail','negative'))
  ),
  'sectors', coalesce((select jsonb_agg(jsonb_build_object(
    'track',s.name,'strength',dsr.strength_score,'demand_change',coalesce(dsr.metadata->>'demand_change',dsr.key_changes),
    'supply_change',coalesce(dsr.metadata->>'supply_change',dsr.evidence_summary),'company_change',dsr.company_mapping,
    'opportunity_change',dsr.opportunity_updates,'risk',coalesce(dsr.metadata->>'risk',dsr.conclusion),
    'counter_evidence',coalesce(dsr.metadata->>'counter_evidence','暂无新增反证记录'),'next_verification',dsr.next_verification,
    'conclusion',dsr.conclusion)) from public.daily_sector_reviews dsr join public.sectors s on s.id=dsr.sector_id where dsr.report_date=dr.report_date),'[]'::jsonb),
  'opportunity_changes', coalesce((select jsonb_agg(to_jsonb(dor) - 'id' - 'created_at' - 'updated_at') from public.daily_opportunity_reviews dor where dor.report_date=dr.report_date),'[]'::jsonb),
  'company_changes', coalesce((select jsonb_agg(jsonb_build_object('company',c.name,'from',st.from_status,'to',st.to_status,'reason',st.transition_reason,'next_step',c.reactivation_condition,'changed_at',st.created_at)) from public.company_state_transitions st join public.companies c on c.id=st.company_id where st.created_at::date=dr.report_date),'[]'::jsonb),
  'focus_companies', coalesce((select jsonb_agg(jsonb_build_object('company',c.name,'code',c.stock_code,'status',c.research_pool_status,'price',cds.close_price,'market_cap',cds.market_cap,'profit_base',cds.profit_base,'probability_base',cds.base_probability,'expected_return',cds.expected_return,'risk_reward',cds.risk_reward,'profit_confidence',ia.profit_confidence,'probability_confidence',ia.probability_confidence,'conclusion',coalesce(c.shadow_reason,c.transition_reason),'next_trigger',c.reactivation_condition)) from public.company_daily_snapshots cds join public.companies c on c.id=cds.company_id left join public.investment_assessments ia on ia.company_id=c.id and ia.assessed_at=(select max(i2.assessed_at) from public.investment_assessments i2 where i2.company_id=c.id) where cds.trade_date=dr.report_date),'[]'::jsonb),
  'model_changes', coalesce((select jsonb_agg(jsonb_build_object('company',c.name,'change_type',mcl.change_type,'before',mcl.previous_state,'after',mcl.new_state,'reason',mcl.change_reason,'changed_at',mcl.changed_at)) from public.model_change_log mcl join public.companies c on c.id=mcl.company_id where mcl.changed_at::date=dr.report_date),'[]'::jsonb),
  'price_odds_changes', coalesce((select jsonb_agg(jsonb_build_object('company',c.name,'price',cds.close_price,'market_cap',cds.market_cap,'expected_return',cds.expected_return,'base_return',cds.base_return,'fundamental_change',case when cds.change_driver='price' then '无基本面变化' else cds.change_driver end,'conclusion',case when cds.change_driver='price' then '价格驱动赔率变化' else '基本面/模型与价格共同变化' end)) from public.company_daily_snapshots cds join public.companies c on c.id=cds.company_id where cds.trade_date=dr.report_date),'[]'::jsonb),
  'watch_changes', coalesce((select jsonb_agg(jsonb_build_object('company',c.name,'stage',c.shadow_stage,'reason',c.shadow_reason,'trigger',c.reactivation_condition,'status',c.research_pool_status)) from public.companies c where c.research_pool_status='shadow' and coalesce(c.last_transition_at,c.updated_at)::date=dr.report_date),'[]'::jsonb),
  'risks', coalesce((select jsonb_agg(jsonb_build_object('company',c.name,'result',ve.effect,'reason',ve.conclusion,'source',ve.source_url)) from public.company_validation_events ve join public.companies c on c.id=ve.company_id where ve.validation_date=dr.report_date and ve.effect not in ('pass','confirmed','positive')),'[]'::jsonb),
  'next_tasks', coalesce((select jsonb_agg(jsonb_build_object('title',rt.title,'company',c.name,'status',rt.status,'priority',rt.priority,'due_date',rt.due_date)) from public.research_tasks rt left join public.companies c on c.id=rt.company_id where rt.status not in ('done','completed')),'[]'::jsonb)
), report_version='V4.2', generated_at=now()
where dr.report_date=(select max(report_date) from public.daily_reports);
