begin;

alter table public.companies add column if not exists company_role text;
alter table public.companies add column if not exists research_pool_status text;
alter table public.companies add column if not exists valuation_status text;
alter table public.companies add column if not exists investment_assessment_status text;
alter table public.companies add column if not exists shadow_reason text;
alter table public.companies add column if not exists reactivation_condition text;
alter table public.companies add column if not exists transition_reason text;
alter table public.companies add column if not exists last_transition_at timestamptz;
alter table public.companies add column if not exists last_validation_at timestamptz;
alter table public.companies add column if not exists next_validation_at timestamptz;

alter table public.opportunities add column if not exists subsector text;
alter table public.opportunities add column if not exists core_change text;
alter table public.opportunities add column if not exists demand_evidence text;
alter table public.opportunities add column if not exists supply_evidence text;
alter table public.opportunities add column if not exists company_evidence text;
alter table public.opportunities add column if not exists consensus_level text;
alter table public.opportunities add column if not exists core_validation text;
alter table public.opportunities add column if not exists counter_evidence text;
alter table public.opportunities add column if not exists opportunity_status text;

alter table public.opportunity_companies add column if not exists company_role text;
alter table public.opportunity_companies add column if not exists research_pool_status text;

create table if not exists public.investment_thresholds (
  id uuid primary key default gen_random_uuid(),
  rule_code text not null unique,
  rule_name text not null,
  min_expected_return numeric not null,
  min_annualized_return numeric not null,
  min_risk_reward numeric not null,
  min_base_return numeric not null,
  min_profit_confidence text not null check (min_profit_confidence in ('low','medium','high')),
  min_probability_confidence text not null check (min_probability_confidence in ('low','medium','high')),
  is_provisional boolean not null default true,
  calibration_status text not null default 'pending_historical_calibration',
  effective_from timestamptz not null default now(),
  effective_to timestamptz,
  is_active boolean not null default true,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.investment_assessments (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  expected_return_snapshot_id uuid not null references public.expected_return_snapshots(id) on delete restrict,
  threshold_id uuid not null references public.investment_thresholds(id) on delete restrict,
  expected_return numeric not null,
  annualized_expected_return numeric,
  base_return numeric,
  max_downside numeric,
  risk_reward numeric,
  profit_confidence text,
  probability_confidence text,
  passed boolean not null,
  classification text not null check (classification in ('high_expected_return','shadow','failed')),
  failure_reasons text[] not null default '{}',
  check_results jsonb not null default '{}'::jsonb,
  assessed_at timestamptz not null default now(),
  unique(expected_return_snapshot_id,threshold_id)
);

create table if not exists public.company_state_transitions (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  from_status text,
  to_status text not null,
  transition_type text not null check (transition_type in ('migration','research_upgrade','shadow_downgrade','reactivation','high_expected_return_upgrade','risk_downgrade','archive','manual_correction')),
  transition_reason text not null,
  trigger_event_id uuid references public.company_timeline_events(id) on delete set null,
  model_version integer,
  migration_key text unique,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.company_validation_events (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  validation_date date not null,
  validation_type text not null check (validation_type in ('order','customer','mass_production','asp','market_share','gross_margin','financial_report','industry_demand','competition','price','valuation','counter_evidence','status_change')),
  title text not null,
  conclusion text not null,
  effect text not null check (effect in ('strengthen','weaken','neutral','revalue','recalculate_profit')),
  return_to_step integer check (return_to_step is null or return_to_step in (4,5)),
  source_url text,
  evidence_grade text check (evidence_grade is null or evidence_grade in ('S','A','B','C','D')),
  is_resolved boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists companies_v4_pool_idx on public.companies(company_role,research_pool_status);
create index if not exists companies_v4_valuation_idx on public.companies(valuation_status,investment_assessment_status);
create index if not exists assessments_company_date_idx on public.investment_assessments(company_id,assessed_at desc);
create index if not exists assessments_snapshot_idx on public.investment_assessments(expected_return_snapshot_id);
create index if not exists assessments_threshold_idx on public.investment_assessments(threshold_id);
create index if not exists transitions_company_date_idx on public.company_state_transitions(company_id,created_at desc);
create index if not exists transitions_trigger_idx on public.company_state_transitions(trigger_event_id);
create index if not exists validation_company_date_idx on public.company_validation_events(company_id,validation_date desc);

alter table public.investment_thresholds enable row level security;
alter table public.investment_assessments enable row level security;
alter table public.company_state_transitions enable row level security;
alter table public.company_validation_events enable row level security;
grant select on public.investment_thresholds,public.investment_assessments,public.company_state_transitions,public.company_validation_events to anon,authenticated;
grant select,insert,update,delete on public.investment_thresholds,public.investment_assessments,public.company_state_transitions,public.company_validation_events to service_role;

drop policy if exists anon_read_investment_thresholds on public.investment_thresholds;
create policy anon_read_investment_thresholds on public.investment_thresholds for select to anon using (true);
drop policy if exists authenticated_read_investment_thresholds on public.investment_thresholds;
create policy authenticated_read_investment_thresholds on public.investment_thresholds for select to authenticated using (true);
drop policy if exists anon_read_investment_assessments on public.investment_assessments;
create policy anon_read_investment_assessments on public.investment_assessments for select to anon using (true);
drop policy if exists authenticated_read_investment_assessments on public.investment_assessments;
create policy authenticated_read_investment_assessments on public.investment_assessments for select to authenticated using (true);
drop policy if exists anon_read_company_state_transitions on public.company_state_transitions;
create policy anon_read_company_state_transitions on public.company_state_transitions for select to anon using (true);
drop policy if exists authenticated_read_company_state_transitions on public.company_state_transitions;
create policy authenticated_read_company_state_transitions on public.company_state_transitions for select to authenticated using (true);
drop policy if exists anon_read_company_validation_events on public.company_validation_events;
create policy anon_read_company_validation_events on public.company_validation_events for select to anon using (true);
drop policy if exists authenticated_read_company_validation_events on public.company_validation_events;
create policy authenticated_read_company_validation_events on public.company_validation_events for select to authenticated using (true);

insert into public.investment_thresholds(rule_code,rule_name,min_expected_return,min_annualized_return,min_risk_reward,min_base_return,min_profit_confidence,min_probability_confidence,is_provisional,notes)
values('V4-TEMP-001','V4临时投资价值门槛',0.30,0.15,1.50,0,'medium','medium',true,'历史盲测完成前的临时规则，仅用于流程分流，不是永久投资标准。')
on conflict(rule_code) do update set rule_name=excluded.rule_name,min_expected_return=excluded.min_expected_return,min_annualized_return=excluded.min_annualized_return,min_risk_reward=excluded.min_risk_reward,min_base_return=excluded.min_base_return,min_profit_confidence=excluded.min_profit_confidence,min_probability_confidence=excluded.min_probability_confidence,is_provisional=true,notes=excluded.notes;

update public.opportunities set
  subsector=coalesce(subsector,name),
  core_change=coalesce(core_change,upgrade_evidence),
  demand_evidence=coalesce(demand_evidence,upgrade_evidence),
  supply_evidence=coalesce(supply_evidence,status_chain),
  company_evidence=coalesce(company_evidence,core_company),
  consensus_level=coalesce(consensus_level,case when cognition_gap_score>=7 then '共识形成早期' else '共识较高' end),
  core_validation=coalesce(core_validation,next_verification),
  counter_evidence=coalesce(counter_evidence,break_condition),
  opportunity_status=case when pass_result like '5/5%' or pass_result like '4/5%' then 'confirmed' else 'pending_confirmation' end,
  stage=case when pass_result like '5/5%' or pass_result like '4/5%' then '机会确认' else '待确认' end;

update public.companies set
 company_role='investable_candidate',research_pool_status='research',valuation_status='insufficient_data',investment_assessment_status='not_evaluated',
 status='研究池',shadow_reason=null,transition_reason='产业机会映射明确，值得继续投入资源完善利润模型',last_transition_at=now(),
 reactivation_condition=accounting_blocker,next_validation_at='2026-09-30 00:00:00+08'
where name in ('三角防务','神剑股份','飞沃科技');

update public.companies set
 company_role='investable_candidate',research_pool_status='shadow',valuation_status='completed',investment_assessment_status='evaluated',status='影子池',
 shadow_reason='赔率不足；中性情景为负；利润与概率可信度均低',
 transition_reason='已完成投资价值评估，但期望收益约2.5%、风险收益比约0.06，不满足V4临时门槛',
 reactivation_condition='ASP或客户批量订单进一步确认；利润模型上修；或股价下降后重新评估达到配置门槛',last_transition_at=now(),last_validation_at=now(),next_validation_at='2026-09-30 00:00:00+08'
where name='柯力传感';

update public.companies set company_role='investable_candidate',research_pool_status='shadow',valuation_status='not_started',investment_assessment_status='not_evaluated',status='影子池',
 shadow_reason='公司体量大且机器人利润映射不清',transition_reason='产业趋势可验证，但暂不能把机会可靠映射为公司利润',
 reactivation_condition='出现可归属的机器人订单、供应份额和利润贡献后重新进入研究池',last_transition_at=now(),next_validation_at='2026-10-15 00:00:00+08' where name='宁德时代';

update public.companies set company_role='investable_candidate',research_pool_status='shadow',valuation_status='not_started',investment_assessment_status='not_evaluated',status='影子池',
 shadow_reason='证据与映射不足，且当前市值超出小市值优先范围',transition_reason='逻辑未失效，但客户、ASP、单机价值量和供货时间未确认',
 reactivation_condition='客户正式确认、批量订单出现、ASP取得，或价格进入可评估区间',last_transition_at=now(),next_validation_at='2026-10-15 00:00:00+08' where name='金力永磁';

update public.companies set company_role='investable_candidate',research_pool_status='shadow',valuation_status='not_started',investment_assessment_status='not_evaluated',status='影子池',
 shadow_reason='产业机会仅通过3/5硬筛，共识较高且赔率尚未核算',transition_reason='保留观察，但暂不投入完整利润估值资源',
 reactivation_condition='完成硬筛、Q3订单继续兑现并出现合理估值空间后重新进入研究池',last_transition_at=now(),next_validation_at='2026-10-27 00:00:00+08' where name='金盘科技';

update public.companies set company_role='industry_validator',research_pool_status='filtered',valuation_status='not_started',investment_assessment_status='not_evaluated',status='产业验证对象',
 transition_reason='海外公司，仅用于验证AI产业需求、技术路线与供给变化，不进入A股赔率核算',reactivation_condition='若未来系统开放对应市场直接投资，再重新评估投资角色',last_transition_at=now(),next_validation_at='2026-10-31 00:00:00+08'
where name in ('GlobalFoundries','Marvell Technology');

update public.companies set company_role='industry_validator',research_pool_status='filtered',valuation_status='not_started',investment_assessment_status='not_evaluated',status='产业验证对象',
 transition_reason='未上市产业主体，用于验证机器人订单、交付与量产，不进入股票赔率核算',reactivation_condition='上市或出现明确可投资供应链映射后重新分类',last_transition_at=now(),next_validation_at='2026-10-15 00:00:00+08' where name='银河通用';

update public.opportunity_companies oc set company_role=c.company_role,research_pool_status=c.research_pool_status,accounting_status=c.accounting_status from public.companies c where c.id=oc.company_id;

insert into public.company_state_transitions(company_id,from_status,to_status,transition_type,transition_reason,model_version,migration_key,metadata)
select id,case name when '柯力传感' then '正式入池→Step 5继续验证' when '三角防务' then '正式入池' when '神剑股份' then '正式入池' when '飞沃科技' then '正式入池' when '宁德时代' then '正式入池/待映射' when '银河通用' then '正式入池/待映射' when '金盘科技' then '待硬筛' when '金力永磁' then '验证→定点→量产准备' else 'watch' end,research_pool_status,'migration',transition_reason,(select max(pm.model_version) from public.profit_models pm where pm.company_id=c.id),'v4-initial-'||id::text,
 jsonb_build_object('company_role',company_role,'valuation_status',valuation_status,'investment_assessment_status',investment_assessment_status,'legacy_status',case name when '柯力传感' then '正式入池→Step 5继续验证' when '三角防务' then '正式入池' when '神剑股份' then '正式入池' when '飞沃科技' then '正式入池' when '宁德时代' then '正式入池/待映射' when '银河通用' then '正式入池/待映射' when '金盘科技' then '待硬筛' when '金力永磁' then '验证→定点→量产准备' else 'watch' end)
from public.companies c on conflict(migration_key) do nothing;

insert into public.investment_assessments(company_id,expected_return_snapshot_id,threshold_id,expected_return,annualized_expected_return,base_return,max_downside,risk_reward,profit_confidence,probability_confidence,passed,classification,failure_reasons,check_results)
select e.company_id,e.id,t.id,e.expected_return,e.annualized_expected_return,(e.scenario_results->'中性'->>'return')::numeric,e.max_assumed_downside,e.risk_reward_ratio,e.profit_confidence,e.probability_confidence,false,'shadow',
 array['期望收益低于临时门槛','年化期望收益低于临时门槛','风险收益比低于临时门槛','中性情景收益为负','利润可信度不足','概率可信度不足'],
 jsonb_build_object('rule_code',t.rule_code,'rule_is_provisional',t.is_provisional,'expected_return_pass',false,'annualized_return_pass',false,'risk_reward_pass',false,'base_return_pass',false,'profit_confidence_pass',false,'probability_confidence_pass',false)
from public.expected_return_snapshots e join public.companies c on c.id=e.company_id and c.name='柯力传感'
join public.investment_thresholds t on t.rule_code='V4-TEMP-001'
on conflict(expected_return_snapshot_id,threshold_id) do nothing;

insert into public.company_validation_events(company_id,validation_date,validation_type,title,conclusion,effect,return_to_step,evidence_grade,is_resolved)
select id,current_date,'status_change','V4投资价值重新分流','完成评估不等于高期望收益；当前转入影子池等待价格或基本面条件改善','revalue',5,'C',false
from public.companies where name='柯力传感' and not exists(select 1 from public.company_validation_events v where v.company_id=companies.id and v.title='V4投资价值重新分流');

alter table public.company_timeline_events drop constraint if exists company_timeline_events_event_type_check;
alter table public.company_timeline_events add constraint company_timeline_events_event_type_check check(event_type in ('first_discovery','focus_research','formal_pool','fundamental_change','price_change','valuation_change','model_revision','validation','result_validation','status_transition','risk_deterioration','downgrade','exit','current'));
alter table public.company_timeline_events drop constraint if exists company_timeline_events_change_driver_check;
alter table public.company_timeline_events add constraint company_timeline_events_change_driver_check check(change_driver in ('initial','price','fundamental','valuation','model_revision','validation','result_validation','status_transition','risk'));

insert into public.company_timeline_events(company_id,event_at,event_type,title,description,evidence_level,data_type,previous_state,current_state,change_driver,change_reason,system_status,model_version,is_key_event,calculation_trace)
select c.id,now(),'status_transition','V4状态机：转入影子池','完成投资价值评估，但未达到临时高期望收益门槛','C','model_inference',
 jsonb_build_object('legacy_status','正式入池→Step 5继续验证'),jsonb_build_object('research_pool_status','shadow','investment_assessment_status','evaluated'),
 'status_transition',c.transition_reason,'影子池',coalesce((select max(model_version) from public.profit_models where company_id=c.id),1),true,
 jsonb_build_object('temporary_threshold','V4-TEMP-001','reactivation_condition',c.reactivation_condition)
from public.companies c where c.name='柯力传感' and not exists(select 1 from public.company_timeline_events e where e.company_id=c.id and e.title='V4状态机：转入影子池');

comment on column public.companies.status is 'V3兼容展示字段；V4逻辑以company_role/research_pool_status/valuation_status/investment_assessment_status为准';
comment on table public.company_state_transitions is 'Append-only V4 company state history';
comment on table public.investment_thresholds is 'Configurable thresholds; provisional until historical calibration';
comment on table public.company_validation_events is 'Step 6 evidence events that may return a company to Step 4 or Step 5';

commit;
