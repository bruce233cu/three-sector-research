begin;

create table if not exists public.expected_return_corrections (
  id uuid primary key default gen_random_uuid(),
  snapshot_id uuid not null unique references public.expected_return_snapshots(id) on delete restrict,
  corrected_change_driver text not null,
  corrected_change_reason text not null,
  correction_reason text not null,
  corrected_at timestamptz not null default now(),
  rule_version text not null default 'V4.3.1'
);

alter table public.expected_return_corrections enable row level security;
drop policy if exists "expected_return_corrections_public_read" on public.expected_return_corrections;
create policy "expected_return_corrections_public_read" on public.expected_return_corrections
  for select to anon,authenticated using(true);
grant select on public.expected_return_corrections to anon,authenticated;
grant insert on public.expected_return_corrections to service_role;
drop trigger if exists expected_return_corrections_immutable on public.expected_return_corrections;
create trigger expected_return_corrections_immutable before update or delete on public.expected_return_corrections
for each row execute function public.reject_history_mutation();

insert into public.expected_return_corrections(snapshot_id,corrected_change_driver,corrected_change_reason,correction_reason)
select e.id,
  case when c.name='柯力传感' and e.calculated_at='2026-09-19 10:29:13.397151+00'::timestamptz then 'price' else 'no_change' end,
  case when c.name='柯力传感' and e.calculated_at='2026-09-19 10:29:13.397151+00'::timestamptz
       then '模型与概率未变，价格由50.25元降至49.05元，只有赔率发生变化。'
       else '模型、概率和价格均未发生实质变化，本次只是重复重算。' end,
  '旧计算把模型记录的更新时间放进了变化指纹，导致重复重算被误记成基本面变化。原记录保留，本条追加更正。'
from public.expected_return_snapshots e
join public.companies c on c.id=e.company_id
where c.name in ('柯力传感','三角防务','飞沃科技')
  and e.calculated_at between '2026-09-19 10:28:00+00'::timestamptz and '2026-09-19 10:38:00+00'::timestamptz
  and e.change_driver in ('fundamental','dual')
on conflict(snapshot_id) do nothing;

create or replace function public.populate_expected_return_trace()
returns trigger language plpgsql set search_path='' as $$
declare v_version integer;
begin
  select max(model_version) into v_version from public.profit_models where company_id=new.company_id and model_status='complete';
  new.model_version:=v_version;
  select id into new.price_snapshot_id from public.price_snapshots where company_id=new.company_id and trade_date=new.trade_date order by captured_at desc limit 1;
  select coalesce(array_agg(id order by scenario),'{}'::uuid[]) into new.model_snapshot_ids from public.profit_model_versions where company_id=new.company_id and model_version=v_version;
  select coalesce(array_agg(id order by scenario),'{}'::uuid[]) into new.probability_assessment_ids from public.probability_assessments where company_id=new.company_id and superseded_at is null;
  if new.price_snapshot_id is null or cardinality(new.model_snapshot_ids)<>3 or cardinality(new.probability_assessment_ids)<>3 then
    raise exception 'valuation trace incomplete for company %',new.company_id;
  end if;
  new.trace_integrity_status:='complete';
  new.trace_integrity_note:='价格、模型版本和概率记录均可追溯。';
  return new;
end $$;

create or replace view public.latest_expected_returns with (security_invoker=true) as
select distinct on(e.company_id)
  e.id,e.company_id,e.trade_date,e.current_price,e.current_market_cap,e.target_date,e.scenario_results,
  e.expected_return,e.max_assumed_downside,e.risk_reward_ratio,e.years_to_target,e.annualized_expected_return,
  e.profit_confidence,e.probability_confidence,e.research_status,e.change_vs_previous,
  coalesce(x.corrected_change_driver,e.change_driver) change_driver,
  coalesce(x.corrected_change_reason,e.change_reason) change_reason,
  e.model_fingerprint,e.calculation_trace,e.calculated_at,e.created_at,
  c.name company_name,c.stock_code,c.external_code,
  e.price_snapshot_id,e.model_version,e.model_snapshot_ids,e.probability_assessment_ids,
  e.trace_integrity_status,e.trace_integrity_note,x.correction_reason
from public.expected_return_snapshots e
join public.companies c on c.id=e.company_id
left join public.expected_return_corrections x on x.snapshot_id=e.id
order by e.company_id,e.trade_date desc,e.calculated_at desc;

insert into public.opportunity_companies(opportunity_id,company_id,role,mapping_status,accounting_status,rationale,company_role,research_pool_status)
select o.id,c.id,
  case c.name when '东风汽车集团' then '需求验证对象' when 'Oracle' then '需求与资本开支验证对象' else '产业验证对象' end,
  'validated',c.accounting_status,
  case c.name
    when 'GlobalFoundries' then '用于验证AI数据中心相关芯片供给和特色工艺产能，不进入A股赔率模型。'
    when 'Marvell Technology' then '用于验证AI数据中心高速互联芯片需求，不进入A股赔率模型。'
    when 'Oracle' then '用于验证AI数据中心资本开支、云需求与融资约束，不进入A股赔率模型。'
    when '东方空间' then '用于验证星箭批量制造和发射进度，未上市，不进入股票赔率模型。'
    when '星际荣耀' then '用于验证可重复使用液体火箭进展，未上市，不进入股票赔率模型。'
    when '东风汽车集团' then '用于验证工业机器人真实需求和应用进度，不作为机器人零部件投资标的。'
  end,
  c.company_role,c.research_pool_status
from public.companies c
join public.opportunities o on o.name=case
  when c.name in ('GlobalFoundries','Marvell Technology','Oracle') then 'AI数据中心电力设备订单兑现'
  when c.name='东方空间' then '星箭批量制造/西部航天超级工厂'
  when c.name='星际荣耀' then '可重复使用液体火箭产业化'
  when c.name='东风汽车集团' then '人形机器人工业规模化' end
where c.name in ('GlobalFoundries','Marvell Technology','Oracle','东方空间','星际荣耀','东风汽车集团')
on conflict(opportunity_id,company_id) do nothing;

insert into public.screening_decisions(object_type,object_id,object_name,stage,decision,reason,next_step,rule_version,evaluated_at,metadata)
select 'company',c.id,c.name,'company_mapping','validator',oc.rationale,
  c.reactivation_condition,'V4.3.1',now(),jsonb_build_object('company_role','industry_validator','opportunity_id',oc.opportunity_id)
from public.companies c join public.opportunity_companies oc on oc.company_id=c.id
where c.name in ('GlobalFoundries','Marvell Technology','Oracle','东方空间','星际荣耀','东风汽车集团');

insert into public.company_timeline_events(
 company_id,event_at,event_type,title,description,evidence_level,data_type,change_driver,change_reason,
 system_status,model_version,is_key_event,calculation_trace
)
select c.id,now(),'validation','系统更正：重复重算不是基本面变化',
 '保留原始记录，同时明确标记：此前若干“基本面变化”由系统把更新时间误算进变化指纹造成，不代表公司利润、概率或估值发生变化。',
 'A','fact','validation','原错误记录没有删除；更正关系已单独追加并在页面聚合时优先采用。',
 c.status,coalesce((select max(model_version) from public.profit_models p where p.company_id=c.id),1),true,
 jsonb_build_object('rule_version','V4.3.1','corrected_snapshot_ids',(select jsonb_agg(x.snapshot_id) from public.expected_return_corrections x join public.expected_return_snapshots e on e.id=x.snapshot_id where e.company_id=c.id))
from public.companies c
where c.name in ('柯力传感','三角防务','飞沃科技')
  and not exists(select 1 from public.company_timeline_events t where t.company_id=c.id and t.title='系统更正：重复重算不是基本面变化');

commit;
