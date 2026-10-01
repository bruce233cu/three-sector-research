-- Replaces an existing read-only display RPC; no table, column, constraint or permission changes.
create or replace function public.get_mainline_status_v2()
returns jsonb language sql security definer
set search_path to pg_catalog, public, mainline
as $function$
with latest as (
  select * from public.automation_runs where job_code='daily_research_pipeline'
  order by started_at desc limit 1
), successful as (
  select r.* from public.automation_runs r
  where r.job_code='daily_research_pipeline' and (
    r.metadata->'jobs'->'three_sector_daily_job'->>'status'='succeeded'
    or (not (r.metadata ? 'daily_pipeline_version') and r.status='succeeded')
  ) and (r.metadata ? 'successful_report' or exists (
    select 1 from public.automation_run_steps s join public.daily_report_versions v
      on v.report_date=r.run_date and v.version_number=(s.metadata->>'version_number')::integer
    where s.run_id=r.id and s.step_code='daily_report_generation' and s.status='succeeded'
      and v.generated_at between r.started_at and coalesce(r.finished_at,r.started_at)
  )) order by r.finished_at desc nulls last limit 1
), report as (
  select coalesce(r.metadata->'successful_report',(
    select to_jsonb(d)||jsonb_build_object('frozen_snapshot',v.frozen_snapshot,'generated_at',v.generated_at,'report_version',v.report_version)
    from public.daily_report_versions v join public.daily_reports d on d.id=v.report_id
    join public.automation_run_steps s on s.run_id=r.id and s.step_code='daily_report_generation'
      and s.status='succeeded' and v.version_number=(s.metadata->>'version_number')::integer
    where v.report_date=r.run_date and v.generated_at between r.started_at and r.finished_at
    order by v.generated_at desc limit 1
  )) as body from successful r
), day as (select (now() at time zone 'Asia/Shanghai')::date as business_date), calendar as (
  select case when count(*)=0 or count(distinct is_open)>1 then null else bool_and(is_open) end as is_open
  from mainline.trading_calendar c,day where c.cal_date=day.business_date and c.exchange in ('SSE','SZSE')
), good_samples as (
  select * from mainline.phase1d_sample_runs where status='SUCCESS' and not stage_frozen
  order by trade_date desc,updated_at desc limit 8
)
select (public.get_mainline_phase1d_status()-'phase'-'recent_samples') || jsonb_build_object(
  'phase',jsonb_build_object('version','V2.2','phase','Phase 1F','gate','G1','status','未通过 / pending_provider'),
  'recent_samples',coalesce((select jsonb_agg(jsonb_build_object('trade_date',trade_date,'industry_name',industry_name,'taxonomy_code',taxonomy_code,'status',status,'member_count',member_count,'valid_member_count',valid_member_count,'coverage',coverage,'sector_return',sector_return,'rs_10',rs_10,'stage_frozen',stage_frozen) order by trade_date desc) from good_samples),'[]'::jsonb),
  'daily_pipeline',jsonb_build_object(
    'timezone','Asia/Shanghai','business_date',(select business_date from day),
    'trading_calendar',jsonb_build_object('business_date',(select business_date from day),'is_open',(select is_open from calendar)),
    'latest_run_status',(select status from latest),'latest_run_date',(select run_date from latest),
    'three_sector',jsonb_build_object('latest_success_at',(select finished_at from successful),'latest_success_report',(select body from report),'latest_run_status',coalesce((select metadata->'jobs'->'three_sector_daily_job'->>'status' from latest),(select status from latest)),'latest_run_date',(select run_date from latest)),
    'mainline',jsonb_build_object('status','pending_provider','provider_enabled',false,'gate','G1_NOT_PASSED','latest_success_at',(select max(updated_at) from good_samples),'latest_success_trade_date',(select max(trade_date) from good_samples),'latest_run_status',(select metadata->'jobs'->'mainline_job'->>'status' from latest),'latest_run_date',(select run_date from latest))
  )
);
$function$;
