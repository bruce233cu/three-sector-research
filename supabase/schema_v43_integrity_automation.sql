begin;

-- V4.3: immutable model snapshots. Current rows remain the working copy;
-- every completed version is frozen here before it can be used by valuation.
create table if not exists public.profit_model_versions (
  id uuid primary key default gen_random_uuid(),
  profit_model_id uuid not null references public.profit_models(id) on delete restrict,
  company_id uuid not null references public.companies(id) on delete restrict,
  scenario text not null,
  model_version integer not null,
  model_date date not null,
  fiscal_year integer not null,
  model_type text,
  target_date date,
  revenue numeric,
  incremental_net_profit numeric,
  total_profit numeric,
  target_market_cap numeric,
  profit_confidence text,
  assumptions text,
  evidence text,
  parameters jsonb not null default '{}'::jsonb,
  calculation_trace jsonb not null default '{}'::jsonb,
  source_status text not null default 'verified_current_state',
  frozen_at timestamptz not null default now(),
  unique(profit_model_id, model_version)
);

create table if not exists public.model_parameter_history (
  id uuid primary key default gen_random_uuid(),
  profit_model_id uuid not null references public.profit_models(id) on delete restrict,
  company_id uuid not null references public.companies(id) on delete restrict,
  model_version integer not null,
  parameter_key text not null,
  operation text not null check(operation in ('insert','update','delete')),
  previous_value jsonb,
  new_value jsonb,
  changed_at timestamptz not null default now()
);

alter table public.expected_return_snapshots
  add column if not exists price_snapshot_id uuid references public.price_snapshots(id) on delete restrict,
  add column if not exists model_version integer,
  add column if not exists model_snapshot_ids uuid[] not null default '{}',
  add column if not exists probability_assessment_ids uuid[] not null default '{}';

alter table public.daily_reports
  add column if not exists freeze_integrity_status text,
  add column if not exists freeze_integrity_note text;

create table if not exists public.daily_report_versions (
  id uuid primary key default gen_random_uuid(),
  report_id uuid references public.daily_reports(id) on delete restrict,
  report_date date not null,
  report_version text not null,
  version_number integer not null,
  frozen_snapshot jsonb not null,
  integrity_status text not null,
  integrity_note text,
  generated_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique(report_date, version_number)
);

create table if not exists public.automation_jobs (
  job_code text primary key,
  job_name text not null,
  schedule_text text not null,
  is_scheduled boolean not null default false,
  scheduler_kind text,
  external_dependency text,
  last_run_at timestamptz,
  last_success_at timestamptz,
  last_status text,
  last_error text,
  updated_at timestamptz not null default now()
);

create table if not exists public.automation_runs (
  id uuid primary key default gen_random_uuid(),
  job_code text not null references public.automation_jobs(job_code) on delete restrict,
  run_date date not null,
  trigger_type text not null check(trigger_type in ('manual','scheduled','retry')),
  status text not null check(status in ('running','succeeded','partial','failed')),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  processed_count integer not null default 0,
  success_count integer not null default 0,
  failed_count integer not null default 0,
  error_message text,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists public.automation_run_steps (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.automation_runs(id) on delete restrict,
  step_code text not null,
  step_name text not null,
  status text not null check(status in ('succeeded','skipped','failed')),
  processed_count integer not null default 0,
  message text,
  started_at timestamptz not null default now(),
  finished_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  unique(run_id, step_code)
);

create table if not exists public.source_health (
  source_code text primary key,
  source_name text not null,
  source_type text not null,
  status text not null check(status in ('healthy','degraded','failed','not_configured')),
  last_checked_at timestamptz,
  last_success_at timestamptz,
  last_error text,
  consecutive_failures integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.data_consistency_checks (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references public.automation_runs(id) on delete restrict,
  check_date date not null,
  check_code text not null,
  severity text not null check(severity in ('P0','P1','P2')),
  passed boolean not null,
  affected_count integer not null default 0,
  details jsonb not null default '{}'::jsonb,
  checked_at timestamptz not null default now()
);

create index if not exists profit_model_versions_company_idx on public.profit_model_versions(company_id,model_version desc,scenario);
create index if not exists parameter_history_model_idx on public.model_parameter_history(profit_model_id,model_version,changed_at desc);
create index if not exists expected_trace_price_idx on public.expected_return_snapshots(price_snapshot_id);
create index if not exists automation_runs_job_idx on public.automation_runs(job_code,started_at desc);
create index if not exists automation_steps_run_idx on public.automation_run_steps(run_id,step_code);
create index if not exists consistency_checks_date_idx on public.data_consistency_checks(check_date,severity,passed);

-- Existing reports are labelled honestly. Backfilled or edited reports remain
-- preserved, but they are not eligible as original same-day blind-test evidence.
update public.daily_reports
set freeze_integrity_status = case
      when created_at::date > report_date then 'backfilled_not_original'
      when generated_at > created_at + interval '5 minutes' then 'regenerated_after_creation'
      when updated_at > created_at + interval '5 minutes' then 'modified_after_creation'
      else 'original_frozen'
    end,
    freeze_integrity_note = case
      when created_at::date > report_date then '这份日报是在报告日期之后补录的，只能回看，不能作为当日盲测证据。'
      when generated_at > created_at + interval '5 minutes' then '冻结内容在首次建档后重新生成过，不能视为最初版本。'
      when updated_at > created_at + interval '5 minutes' then '这份日报在首次生成后被修改过，不能视为最初版本。'
      else '生成后未发现覆盖，后续禁止修改。'
    end;

insert into public.daily_report_versions(report_id,report_date,report_version,version_number,frozen_snapshot,integrity_status,integrity_note,generated_at)
select id,report_date,report_version,1,frozen_snapshot,freeze_integrity_status,freeze_integrity_note,generated_at
from public.daily_reports
on conflict(report_date,version_number) do nothing;

-- Freeze the model state that currently exists. Older states that were already
-- overwritten are explicitly marked as backfilled, never presented as original.
insert into public.profit_model_versions(
  profit_model_id,company_id,scenario,model_version,model_date,fiscal_year,model_type,target_date,
  revenue,incremental_net_profit,total_profit,target_market_cap,profit_confidence,assumptions,evidence,
  parameters,calculation_trace,source_status,frozen_at
)
select p.id,p.company_id,p.scenario,p.model_version,p.model_date,p.fiscal_year,p.model_type,p.target_date,
  p.revenue,p.net_profit,p.total_profit,p.target_market_cap,p.profit_confidence,p.assumptions,p.evidence,
  coalesce((select jsonb_object_agg(mp.parameter_key,jsonb_build_object(
    'value',mp.parameter_value,'normalized_value',mp.normalized_value,'unit',mp.unit,'data_type',mp.data_type,
    'source_name',mp.source_name,'source_url',mp.source_url,'source_published_at',mp.source_published_at,
    'evidence_grade',mp.evidence_grade,'derivation_logic',mp.derivation_logic,'notes',mp.notes
  )) from public.model_parameters mp where mp.profit_model_id=p.id),'{}'::jsonb),
  p.calculation_trace,'backfilled_current_state',coalesce(p.updated_at,p.created_at)
from public.profit_models p
on conflict(profit_model_id,model_version) do nothing;

-- Link existing valuation snapshots to the exact price, model version and
-- probability rows available at calculation time.
update public.expected_return_snapshots e
set price_snapshot_id = coalesce(e.price_snapshot_id,(select ps.id from public.price_snapshots ps where ps.company_id=e.company_id and ps.trade_date=e.trade_date order by ps.captured_at desc limit 1)),
    model_version = coalesce(e.model_version,(select max(pm.model_version) from public.profit_models pm where pm.company_id=e.company_id)),
    model_snapshot_ids = case when cardinality(e.model_snapshot_ids)=0 then coalesce((select array_agg(pmv.id order by pmv.scenario) from public.profit_model_versions pmv where pmv.company_id=e.company_id and pmv.model_version=(select max(pm2.model_version) from public.profit_models pm2 where pm2.company_id=e.company_id)),'{}'::uuid[]) else e.model_snapshot_ids end,
    probability_assessment_ids = case when cardinality(e.probability_assessment_ids)=0 then coalesce((select array_agg(pa.id order by pa.scenario) from public.probability_assessments pa where pa.company_id=e.company_id and pa.effective_at<=e.calculated_at and (pa.superseded_at is null or pa.superseded_at>e.calculated_at)),'{}'::uuid[]) else e.probability_assessment_ids end;

-- Screening decisions are events, not mutable stage cells.
alter table public.screening_decisions drop constraint if exists screening_decisions_object_type_object_id_stage_rule_versio_key;

create or replace function public.reject_history_mutation()
returns trigger language plpgsql set search_path='' as $$
begin
  raise exception '% is append-only; insert a new history row instead',tg_table_name;
end $$;

create or replace function public.guard_probability_history()
returns trigger language plpgsql set search_path='' as $$
begin
  if tg_op='DELETE' then raise exception 'probability_assessments is append-only'; end if;
  if old.superseded_at is null and new.superseded_at is not null
     and (to_jsonb(new)-'superseded_at')=(to_jsonb(old)-'superseded_at') then return new; end if;
  raise exception 'probability history may only be closed by setting superseded_at';
end $$;

drop trigger if exists screening_decisions_immutable on public.screening_decisions;
create trigger screening_decisions_immutable before update or delete on public.screening_decisions for each row execute function public.reject_history_mutation();
drop trigger if exists state_transitions_immutable on public.company_state_transitions;
create trigger state_transitions_immutable before update or delete on public.company_state_transitions for each row execute function public.reject_history_mutation();
drop trigger if exists expected_returns_immutable on public.expected_return_snapshots;
create trigger expected_returns_immutable before update or delete on public.expected_return_snapshots for each row execute function public.reject_history_mutation();
drop trigger if exists investment_assessments_immutable on public.investment_assessments;
create trigger investment_assessments_immutable before update or delete on public.investment_assessments for each row execute function public.reject_history_mutation();
drop trigger if exists daily_snapshots_immutable on public.company_daily_snapshots;
create trigger daily_snapshots_immutable before update or delete on public.company_daily_snapshots for each row execute function public.reject_history_mutation();
drop trigger if exists timeline_events_immutable on public.company_timeline_events;
create trigger timeline_events_immutable before update or delete on public.company_timeline_events for each row execute function public.reject_history_mutation();
drop trigger if exists report_versions_immutable on public.daily_report_versions;
create trigger report_versions_immutable before update or delete on public.daily_report_versions for each row execute function public.reject_history_mutation();
drop trigger if exists model_versions_immutable on public.profit_model_versions;
create trigger model_versions_immutable before update or delete on public.profit_model_versions for each row execute function public.reject_history_mutation();
drop trigger if exists model_parameter_history_immutable on public.model_parameter_history;
create trigger model_parameter_history_immutable before update or delete on public.model_parameter_history for each row execute function public.reject_history_mutation();
drop trigger if exists probability_history_guard on public.probability_assessments;
create trigger probability_history_guard before update or delete on public.probability_assessments for each row execute function public.guard_probability_history();
drop trigger if exists price_snapshots_immutable on public.price_snapshots;
create trigger price_snapshots_immutable before update or delete on public.price_snapshots for each row execute function public.reject_history_mutation();

create or replace function public.capture_parameter_history()
returns trigger language plpgsql set search_path='' as $$
declare pm public.profit_models%rowtype;
begin
  select * into pm from public.profit_models where id=coalesce(new.profit_model_id,old.profit_model_id);
  if exists(select 1 from public.profit_model_versions v where v.profit_model_id=pm.id and v.model_version=pm.model_version) then
    raise exception 'model version % is frozen; increment model_version and set model_status to draft before changing parameters',pm.model_version;
  end if;
  insert into public.model_parameter_history(profit_model_id,company_id,model_version,parameter_key,operation,previous_value,new_value)
  values(pm.id,pm.company_id,pm.model_version,coalesce(new.parameter_key,old.parameter_key),lower(tg_op),case when tg_op='INSERT' then null else to_jsonb(old) end,case when tg_op='DELETE' then null else to_jsonb(new) end);
  return coalesce(new,old);
end $$;

drop trigger if exists capture_parameter_history_trigger on public.model_parameters;
create trigger capture_parameter_history_trigger before insert or update or delete on public.model_parameters for each row execute function public.capture_parameter_history();

create or replace function public.freeze_completed_profit_model()
returns trigger language plpgsql set search_path='' as $$
begin
  if new.model_status='complete' and (old.model_status is distinct from 'complete' or old.model_version is distinct from new.model_version or old.calculation_trace is distinct from new.calculation_trace) then
    insert into public.profit_model_versions(
      profit_model_id,company_id,scenario,model_version,model_date,fiscal_year,model_type,target_date,
      revenue,incremental_net_profit,total_profit,target_market_cap,profit_confidence,assumptions,evidence,
      parameters,calculation_trace,source_status
    ) values (
      new.id,new.company_id,new.scenario,new.model_version,new.model_date,new.fiscal_year,new.model_type,new.target_date,
      new.revenue,new.net_profit,new.total_profit,new.target_market_cap,new.profit_confidence,new.assumptions,new.evidence,
      coalesce((select jsonb_object_agg(mp.parameter_key,jsonb_build_object('value',mp.parameter_value,'normalized_value',mp.normalized_value,'unit',mp.unit,'data_type',mp.data_type,'source_name',mp.source_name,'source_url',mp.source_url,'source_published_at',mp.source_published_at,'evidence_grade',mp.evidence_grade,'derivation_logic',mp.derivation_logic,'notes',mp.notes)) from public.model_parameters mp where mp.profit_model_id=new.id),'{}'::jsonb),
      new.calculation_trace,'native_version'
    ) on conflict(profit_model_id,model_version) do nothing;
  end if;
  return new;
end $$;

drop trigger if exists freeze_completed_profit_model_trigger on public.profit_models;
create trigger freeze_completed_profit_model_trigger after update on public.profit_models for each row execute function public.freeze_completed_profit_model();

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
  return new;
end $$;

drop trigger if exists populate_expected_return_trace_trigger on public.expected_return_snapshots;
create trigger populate_expected_return_trace_trigger before insert on public.expected_return_snapshots for each row execute function public.populate_expected_return_trace();

-- Existing rows may be backfilled, but all future valuation snapshots must be fully traceable.
alter table public.expected_return_snapshots
  add constraint expected_return_price_trace_required check(price_snapshot_id is not null) not valid,
  add constraint expected_return_model_trace_required check(model_version is not null and cardinality(model_snapshot_ids)=3 and cardinality(probability_assessment_ids)=3) not valid;

insert into public.automation_jobs(job_code,job_name,schedule_text,external_dependency) values
('daily_research_pipeline','每日完整研究流程','每天 08:00（北京时间）','价格接口、外部信号来源、Supabase定时任务'),
('signal_collection','信号采集','由每日完整研究流程调用','外部信息源采集器'),
('opportunity_update','机会更新','由每日完整研究流程调用',null),
('company_mapping_check','公司映射检查','由每日完整研究流程调用',null),
('price_update','价格更新','由每日完整研究流程调用','东方财富行情接口'),
('model_recalculation','模型重算','由每日完整研究流程调用',null),
('investment_recalculation','投资价值重算','由每日完整研究流程调用',null),
('shadow_scan','观察状态扫描','由每日完整研究流程调用',null),
('daily_report_generation','日报生成','由每日完整研究流程调用',null),
('daily_snapshot','每日快照','由投资价值快照触发',null),
('company_timeline','公司时间轴','由关键事件触发',null),
('consistency_check','一致性检查','由每日完整研究流程调用',null),
('source_health_check','数据源健康检查','由每日完整研究流程调用',null)
on conflict(job_code) do update set job_name=excluded.job_name,schedule_text=excluded.schedule_text,external_dependency=excluded.external_dependency,updated_at=now();

insert into public.source_health(source_code,source_name,source_type,status,last_error,metadata) values
('eastmoney_quote','东方财富行情','price','not_configured','尚未部署并验证自动价格采集器','{}'),
('external_signal_sources','外部研究信号来源','signal','not_configured','尚未配置可自动抓取的外部信号源清单和采集器','{}')
on conflict(source_code) do nothing;

alter table public.profit_model_versions enable row level security;
alter table public.model_parameter_history enable row level security;
alter table public.daily_report_versions enable row level security;
alter table public.automation_jobs enable row level security;
alter table public.automation_runs enable row level security;
alter table public.automation_run_steps enable row level security;
alter table public.source_health enable row level security;
alter table public.data_consistency_checks enable row level security;

grant select on public.profit_model_versions,public.model_parameter_history,public.daily_report_versions,public.automation_jobs,public.automation_runs,public.automation_run_steps,public.source_health,public.data_consistency_checks to anon,authenticated;
grant select,insert,update,delete on public.profit_model_versions,public.model_parameter_history,public.daily_report_versions,public.automation_jobs,public.automation_runs,public.automation_run_steps,public.source_health,public.data_consistency_checks to service_role;

do $$ declare t text; begin
  foreach t in array array['profit_model_versions','model_parameter_history','daily_report_versions','automation_jobs','automation_runs','automation_run_steps','source_health','data_consistency_checks'] loop
    execute format('drop policy if exists anon_read_%I on public.%I',t,t);
    execute format('create policy anon_read_%I on public.%I for select to anon using (true)',t,t);
    execute format('drop policy if exists authenticated_read_%I on public.%I',t,t);
    execute format('create policy authenticated_read_%I on public.%I for select to authenticated using (true)',t,t);
  end loop;
end $$;

comment on table public.profit_model_versions is 'Append-only frozen company model versions used by investment valuation';
comment on table public.daily_report_versions is 'Append-only frozen daily report payloads with integrity labels';
comment on table public.automation_runs is 'Actual execution log; code existence alone must never create a success row';

commit;
