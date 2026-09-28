begin;

create table if not exists mainline.phase1d_sample_runs (
  trade_date date not null,
  taxonomy_code text not null,
  industry_name text not null,
  taxonomy_version text,
  status text not null check (status in ('SUCCESS','PARTIAL','FAIL','RUNNING')),
  member_count integer check (member_count is null or member_count >= 0),
  valid_member_count integer check (valid_member_count is null or valid_member_count >= 0),
  coverage numeric check (coverage is null or (coverage >= 0 and coverage <= 1)),
  sector_return numeric,
  benchmark_return numeric,
  rs_5 numeric,
  rs_10 numeric,
  rs_20 numeric,
  turnover_share numeric,
  turnover_intensity numeric,
  turnover_cap_deviation numeric,
  up_ratio numeric,
  above_ma20 numeric,
  above_ma60 numeric,
  new_high_60 numeric,
  top3_turnover_share numeric,
  top3_return_contribution numeric,
  metric_coverage_json jsonb not null default '{}'::jsonb,
  critical_data_ok boolean,
  stage_frozen boolean,
  freeze_reason text,
  run_id uuid,
  source_snapshot_ids uuid[] not null default '{}',
  membership_source text,
  market_data_source text,
  data_source jsonb not null default '{}'::jsonb,
  cache_status text,
  error_detail jsonb not null default '{}'::jsonb,
  pit_level text check (pit_level is null or pit_level in ('effective_pit','strict_knowledge_pit')),
  knowledge_time_unverified boolean not null default true,
  code_commit text,
  test_derived_from_real_data boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (trade_date, taxonomy_code)
);

comment on table mainline.phase1d_sample_runs is
  'Phase 1D objective sector POC status and audit evidence. Contains no S1-S4 state and no company investment output.';

create index if not exists phase1d_sample_runs_status_date_idx
  on mainline.phase1d_sample_runs(status, trade_date desc);

alter table mainline.phase1d_sample_runs enable row level security;
revoke all on table mainline.phase1d_sample_runs from public, anon, authenticated;

create or replace function public.get_mainline_phase1d_status()
returns jsonb
language sql
security definer
set search_path = pg_catalog, public, mainline
as $$
  with samples as (
    select * from mainline.phase1d_sample_runs
  ), latest as (
    select * from samples where run_id is not null order by updated_at desc limit 1
  ), counts as (
    select count(*) total,
      count(*) filter (where status='SUCCESS') success,
      count(*) filter (where status='PARTIAL') partial,
      count(*) filter (where status='FAIL') fail,
      count(*) filter (where status='RUNNING') running,
      count(*) filter (where stage_frozen) frozen,
      count(*) filter (where member_count is not null) membership_ready,
      count(*) filter (where valid_member_count > 0) market_ready,
      count(*) filter (where market_data_source like '%circ_mv%') cap_ready
    from samples
  )
  select jsonb_build_object(
    'phase', jsonb_build_object('version','V2.2','phase','Phase 1D','gate','G1','status',
      case when counts.success >= 12 then '基本通过' else '部分通过 / 建设中' end),
    'counts', jsonb_build_object('total',coalesce(nullif(counts.total,0),15),'success',counts.success,
      'partial',counts.partial,'fail',counts.fail,'running',counts.running),
    'health', jsonb_build_object(
      'taxonomy',case when counts.total>0 then '已取得真实分类版本' end,
      'membership',case when counts.membership_ready>0 then counts.membership_ready||'/'||counts.total||' 样本可追溯' end,
      'market_data',case when counts.market_ready>0 then counts.market_ready||'/'||counts.total||' 样本有有效行情' end,
      'market_cap',case when counts.cap_ready>0 then counts.cap_ready||'/'||counts.total||' 样本可用' else '数据不足' end,
      'cache',(select cache_status from latest),'freeze',counts.frozen||' 个样本冻结',
      'latest_run_id',(select run_id from latest),'latest_run_at',(select updated_at from latest)),
    'recent_samples',(select coalesce(jsonb_agg(to_jsonb(r) order by r.trade_date desc,r.taxonomy_code),'[]'::jsonb)
      from (select trade_date,industry_name,taxonomy_code,status,member_count,valid_member_count,coverage,
        sector_return,rs_10,stage_frozen from samples where status<>'FAIL' order by trade_date desc,taxonomy_code limit 8) r),
    'updated_at',(select updated_at from latest)
  ) from counts;
$$;

revoke all on function public.get_mainline_phase1d_status() from public, anon, authenticated;
grant execute on function public.get_mainline_phase1d_status() to service_role;

commit;
