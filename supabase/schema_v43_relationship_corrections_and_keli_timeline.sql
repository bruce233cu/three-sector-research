begin;

create table if not exists public.opportunity_signal_link_corrections (
  id uuid primary key default gen_random_uuid(),
  link_id uuid not null unique references public.opportunity_signal_links(id) on delete restrict,
  is_valid boolean not null default false,
  reason text not null,
  corrected_at timestamptz not null default now(),
  rule_version text not null default 'V4.3.1'
);
alter table public.opportunity_signal_link_corrections enable row level security;
drop policy if exists "opportunity_signal_link_corrections_public_read" on public.opportunity_signal_link_corrections;
create policy "opportunity_signal_link_corrections_public_read" on public.opportunity_signal_link_corrections
for select to anon,authenticated using(true);
grant select on public.opportunity_signal_link_corrections to anon,authenticated;
grant insert on public.opportunity_signal_link_corrections to service_role;
drop trigger if exists opportunity_signal_link_corrections_immutable on public.opportunity_signal_link_corrections;
create trigger opportunity_signal_link_corrections_immutable before update or delete on public.opportunity_signal_link_corrections
for each row execute function public.reject_history_mutation();

insert into public.opportunity_signal_link_corrections(link_id,is_valid,reason)
select l.id,false,'机器人量产信号被错误关联到商业航天机会；保留原关系记录，但从有效研究链排除。'
from public.opportunity_signal_links l
join public.opportunities o on o.id=l.opportunity_id
join public.signals s on s.id=l.signal_id
where o.sector_id<>s.sector_id
on conflict(link_id) do nothing;

create or replace view public.active_opportunity_signal_links with (security_invoker=true) as
select l.* from public.opportunity_signal_links l
left join public.opportunity_signal_link_corrections x on x.link_id=l.id and not x.is_valid
where x.id is null;
grant select on public.active_opportunity_signal_links to anon,authenticated;

alter table public.company_timeline_events drop constraint if exists company_timeline_events_event_type_check;
alter table public.company_timeline_events add constraint company_timeline_events_event_type_check check(event_type in (
  'first_discovery','opportunity_mapping','company_mapping','modeling_started','modeling_complete','investment_evaluation',
  'focus_research','formal_pool','fundamental_change','price_change','valuation_change','model_revision','validation',
  'result_validation','status_transition','risk_deterioration','downgrade','exit','current'
));

insert into public.company_timeline_events(company_id,event_at,event_type,title,description,source_url,source_publish_date,evidence_level,data_type,change_driver,change_reason,system_status,model_version,is_key_event,current_state,calculation_trace)
select c.id,s.signal_date::timestamptz,'first_discovery','首次发现：力学传感器批量信号',s.title,s.source_url,s.signal_date,
  case when s.source_grade in ('S','A','B','C','D') then s.source_grade else 'C' end,'fact','initial','日期和内容直接来自最早有效信号。','变化发现',1,true,
  jsonb_build_object('signal_id',s.id,'external_id',s.external_id),jsonb_build_object('backfill_basis','signals')
from public.companies c
join public.opportunity_companies oc on oc.company_id=c.id
join public.active_opportunity_signal_links l on l.opportunity_id=oc.opportunity_id
join public.signals s on s.id=l.signal_id
where c.name='柯力传感' and s.signal_date=(select min(s2.signal_date) from public.active_opportunity_signal_links l2 join public.signals s2 on s2.id=l2.signal_id where l2.opportunity_id=oc.opportunity_id)
  and not exists(select 1 from public.company_timeline_events t where t.company_id=c.id and t.event_type='first_discovery');

insert into public.company_timeline_events(company_id,event_at,event_type,title,description,evidence_level,data_type,change_driver,change_reason,system_status,model_version,is_key_event,current_state,calculation_trace)
select c.id,o.created_at,'opportunity_mapping','机会形成：机器人/力学传感器',o.pool_reason,'B','fact','initial','事件日期来自机会记录的创建时间。','机会确认',1,true,
  jsonb_build_object('opportunity_id',o.id,'opportunity',o.name),jsonb_build_object('backfill_basis','opportunities.created_at')
from public.companies c join public.opportunity_companies oc on oc.company_id=c.id join public.opportunities o on o.id=oc.opportunity_id
where c.name='柯力传感' and not exists(select 1 from public.company_timeline_events t where t.company_id=c.id and t.event_type='opportunity_mapping');

insert into public.company_timeline_events(company_id,event_at,event_type,title,description,evidence_level,data_type,change_driver,change_reason,system_status,model_version,is_key_event,current_state,calculation_trace)
select c.id,oc.created_at,'company_mapping','公司映射：柯力传感',oc.rationale,'B','fact','initial','事件日期和原因来自机会—公司映射记录。','公司映射',1,true,
  jsonb_build_object('opportunity_id',oc.opportunity_id,'mapping_status',oc.mapping_status),jsonb_build_object('backfill_basis','opportunity_companies.created_at')
from public.companies c join public.opportunity_companies oc on oc.company_id=c.id
where c.name='柯力传感' and not exists(select 1 from public.company_timeline_events t where t.company_id=c.id and t.event_type='company_mapping');

insert into public.company_timeline_events(company_id,event_at,event_type,title,description,evidence_level,data_type,change_driver,change_reason,system_status,model_version,is_key_event,current_state,calculation_trace)
select c.id,min(p.created_at),'modeling_started','开始公司建模','建立悲观、中性、乐观三情景利润模型。','C','model_inference','model_revision','事件日期来自最早模型记录。','公司建模',min(p.model_version),true,
  jsonb_build_object('model_count',count(*)),jsonb_build_object('backfill_basis','profit_models.created_at')
from public.companies c join public.profit_models p on p.company_id=c.id where c.name='柯力传感'
group by c.id
having not exists(select 1 from public.company_timeline_events t where t.company_id=c.id and t.event_type='modeling_started');

insert into public.company_timeline_events(company_id,event_at,event_type,title,description,evidence_level,data_type,change_driver,change_reason,system_status,model_version,is_key_event,current_state,calculation_trace)
select c.id,min(v.frozen_at),'modeling_complete','公司模型完成并冻结','三情景利润、估值和模型依据已冻结保存。','C','model_inference','model_revision','事件日期来自模型版本冻结时间。','模型完成',max(v.model_version),true,
  jsonb_build_object('frozen_model_rows',count(*),'scenarios',jsonb_agg(distinct v.scenario)),jsonb_build_object('backfill_basis','profit_model_versions.frozen_at')
from public.companies c join public.profit_model_versions v on v.company_id=c.id where c.name='柯力传感'
group by c.id
having not exists(select 1 from public.company_timeline_events t where t.company_id=c.id and t.event_type='modeling_complete');

insert into public.company_timeline_events(company_id,event_at,event_type,title,description,evidence_level,data_type,price,market_cap,profit_bear,profit_base,profit_bull,probability_bear,probability_base,probability_bull,expected_return,risk_reward,profit_confidence,probability_confidence,change_driver,change_reason,system_status,model_version,is_key_event,current_state,calculation_trace)
select c.id,e.calculated_at,'investment_evaluation','首次投资价值评估','首次生成价格、三情景模型与概率共同形成的投资价值结果。','C','model_inference',e.current_price,e.current_market_cap,
  (e.scenario_results->'悲观'->>'net_profit')::numeric,(e.scenario_results->'中性'->>'net_profit')::numeric,(e.scenario_results->'乐观'->>'net_profit')::numeric,
  (e.scenario_results->'悲观'->>'probability_pct')::integer,(e.scenario_results->'中性'->>'probability_pct')::integer,(e.scenario_results->'乐观'->>'probability_pct')::integer,
  e.expected_return,e.risk_reward_ratio,e.profit_confidence,e.probability_confidence,'valuation','事件日期和数值来自最早投资价值快照。','投资价值评估',coalesce(e.model_version,2),true,
  jsonb_build_object('expected_return_snapshot_id',e.id,'research_status',e.research_status),jsonb_build_object('backfill_basis','expected_return_snapshots.calculated_at','trace_integrity_status',e.trace_integrity_status)
from public.companies c join lateral(select * from public.expected_return_snapshots x where x.company_id=c.id order by x.calculated_at limit 1)e on true
where c.name='柯力传感' and not exists(select 1 from public.company_timeline_events t where t.company_id=c.id and t.event_type='investment_evaluation');

commit;
