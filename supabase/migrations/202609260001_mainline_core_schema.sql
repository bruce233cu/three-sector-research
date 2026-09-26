begin;

create schema if not exists mainline;
revoke all on schema mainline from public, anon, authenticated;

create table if not exists mainline.source_snapshots (
  source_snapshot_id uuid primary key default gen_random_uuid(),
  source_id text not null,
  dataset_code text not null,
  source_version text not null,
  fetched_at timestamptz not null,
  available_at timestamptz,
  response_checksum text not null,
  row_count integer not null check (row_count >= 0),
  raw_location text,
  historical_capability text not null check (historical_capability in ('realtime_only','historical_partial','historical_full')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(source_id,dataset_code,source_version,response_checksum)
);

create table if not exists mainline.run_manifests (
  run_id uuid primary key default gen_random_uuid(),
  recompute_run_id uuid,
  parent_run_id uuid references mainline.run_manifests(run_id),
  job_name text not null,
  as_of_date date,
  code_commit text not null,
  rule_version text,
  profile_id text,
  provider_versions jsonb not null default '{}'::jsonb,
  source_snapshot_ids uuid[] not null default '{}',
  parameter_hash text,
  status text not null check (status in ('running','success','partial','failed','frozen')),
  critical_data_ok boolean,
  stage_frozen boolean not null default false,
  freeze_reason text[],
  row_counts jsonb not null default '{}'::jsonb,
  error_summary jsonb not null default '{}'::jsonb,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists mainline.source_registry (
  provider_code text not null,
  dataset_code text not null,
  provider_role text not null check (provider_role in ('primary','backup')),
  provider_name text not null,
  interface_name text not null,
  endpoint text,
  field_contract jsonb not null,
  source_grade text not null check (source_grade in ('A','B','C')),
  historical_capability text not null check (historical_capability in ('realtime_only','historical_partial','historical_full')),
  backup_unavailable boolean not null default false,
  is_enabled boolean not null default true,
  priority integer not null check (priority > 0),
  source_version text not null,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key(provider_code,dataset_code),
  unique(dataset_code,provider_role,priority)
);

create table if not exists mainline.provider_fetch_runs (
  fetch_run_id uuid primary key default gen_random_uuid(),
  run_id uuid references mainline.run_manifests(run_id),
  dataset_code text not null,
  provider_code text not null,
  source_used text,
  attempt_no integer not null check (attempt_no > 0),
  status text not null check (status in ('started','success','failed','unavailable')),
  source_version text,
  fetched_at timestamptz,
  available_at timestamptz,
  row_count integer check (row_count is null or row_count >= 0),
  request_fingerprint text,
  response_checksum text,
  error_code text,
  error_message text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  metadata jsonb not null default '{}'::jsonb
);

create table if not exists mainline.security_master (
  security_id text primary key,
  ts_code text unique,
  symbol text,
  name text not null,
  exchange text not null,
  list_date date not null,
  delist_date date,
  is_st boolean not null default false,
  security_type text not null default 'stock',
  listing_status text not null default 'listed',
  source_snapshot_id uuid references mainline.source_snapshots(source_snapshot_id),
  source_version text not null,
  fetched_at timestamptz not null,
  available_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (delist_date is null or delist_date >= list_date)
);

create table if not exists mainline.trading_calendar (
  exchange text not null,
  cal_date date not null,
  is_open boolean not null,
  pretrade_date date,
  source_snapshot_id uuid references mainline.source_snapshots(source_snapshot_id),
  source_version text not null,
  fetched_at timestamptz not null,
  available_at timestamptz,
  primary key(exchange,cal_date)
);

create table if not exists mainline.taxonomy_definitions (
  taxonomy_id uuid primary key default gen_random_uuid(),
  taxonomy_type text not null,
  taxonomy_code text not null,
  taxonomy_name text not null,
  taxonomy_version text not null,
  object_id text not null,
  effective_from date not null,
  effective_to date,
  source_id text not null,
  source_snapshot_id uuid references mainline.source_snapshots(source_snapshot_id),
  source_version text not null,
  fetched_at timestamptz not null,
  available_at timestamptz,
  created_at timestamptz not null default now(),
  unique(taxonomy_type,taxonomy_code,taxonomy_version),
  unique(object_id,taxonomy_version),
  check (effective_to is null or effective_to >= effective_from)
);

create table if not exists mainline.membership_history (
  membership_id bigserial primary key,
  security_id text not null references mainline.security_master(security_id),
  taxonomy_id uuid not null references mainline.taxonomy_definitions(taxonomy_id),
  effective_from date not null,
  effective_to date,
  announced_at timestamptz,
  available_at timestamptz not null,
  source_id text not null,
  source_version text not null,
  source_snapshot_id uuid not null references mainline.source_snapshots(source_snapshot_id),
  historical_capability text not null check (historical_capability in ('historical_partial','historical_full')),
  fetched_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique(security_id,taxonomy_id,effective_from,source_id,source_version),
  check (effective_to is null or effective_to >= effective_from)
);

create table if not exists mainline.stock_daily (
  security_id text not null references mainline.security_master(security_id),
  trade_date date not null,
  open numeric, high numeric, low numeric, close numeric,
  pre_close numeric, pct_chg numeric, volume numeric, amount numeric,
  source_id text not null,
  source_version text not null,
  source_snapshot_id uuid not null references mainline.source_snapshots(source_snapshot_id),
  fetched_at timestamptz not null,
  available_at timestamptz,
  run_id uuid references mainline.run_manifests(run_id),
  recompute_run_id uuid,
  created_at timestamptz not null default now(),
  primary key(security_id,trade_date,source_id,source_version),
  check (open is null or open >= 0),
  check (high is null or high >= 0),
  check (low is null or low >= 0),
  check (close is null or close >= 0),
  check (volume is null or volume >= 0),
  check (amount is null or amount >= 0)
);

create table if not exists mainline.float_market_cap_daily (
  security_id text not null references mainline.security_master(security_id),
  trade_date date not null,
  circ_mv numeric, total_mv numeric, turnover_rate numeric,
  source_id text not null,
  source_version text not null,
  source_snapshot_id uuid not null references mainline.source_snapshots(source_snapshot_id),
  fetched_at timestamptz not null,
  available_at timestamptz,
  run_id uuid references mainline.run_manifests(run_id),
  recompute_run_id uuid,
  created_at timestamptz not null default now(),
  primary key(security_id,trade_date,source_id,source_version),
  check (circ_mv is null or circ_mv >= 0),
  check (total_mv is null or total_mv >= 0)
);

create table if not exists mainline.benchmark_daily (
  index_id text not null,
  trade_date date not null,
  open numeric, high numeric, low numeric, close numeric,
  volume numeric, amount numeric,
  source_id text not null,
  source_version text not null,
  source_snapshot_id uuid not null references mainline.source_snapshots(source_snapshot_id),
  fetched_at timestamptz not null,
  available_at timestamptz,
  run_id uuid references mainline.run_manifests(run_id),
  created_at timestamptz not null default now(),
  primary key(index_id,trade_date,source_id,source_version)
);

create table if not exists mainline.adjustment_factors (
  security_id text not null references mainline.security_master(security_id),
  trade_date date not null,
  adj_factor numeric,
  source_id text not null,
  source_version text not null,
  source_snapshot_id uuid not null references mainline.source_snapshots(source_snapshot_id),
  announced_at timestamptz,
  available_at timestamptz,
  fetched_at timestamptz not null,
  data_quality_warning text,
  primary key(security_id,trade_date,source_id,source_version)
);

create table if not exists mainline.corporate_actions (
  action_id uuid primary key default gen_random_uuid(),
  security_id text not null references mainline.security_master(security_id),
  action_type text not null,
  announced_at timestamptz,
  effective_date date,
  available_at timestamptz,
  payload jsonb not null,
  source_id text not null,
  source_version text not null,
  source_snapshot_id uuid not null references mainline.source_snapshots(source_snapshot_id),
  created_at timestamptz not null default now(),
  unique(security_id,action_type,effective_date,source_id,source_version)
);

create table if not exists mainline.parameter_profiles (
  profile_id text primary key,
  mainline_type text not null,
  rule_version text not null,
  params_json jsonb not null,
  effective_from date not null,
  effective_to date,
  validation_report_id text,
  created_at timestamptz not null default now(),
  check (effective_to is null or effective_to >= effective_from)
);

create table if not exists mainline.data_quality_daily (
  quality_id uuid primary key default gen_random_uuid(),
  as_of_date date not null,
  dataset_code text not null,
  run_id uuid references mainline.run_manifests(run_id),
  expected_count integer not null check (expected_count >= 0),
  actual_count integer not null check (actual_count >= 0),
  missing_count integer not null check (missing_count >= 0),
  duplicate_count integer not null check (duplicate_count >= 0),
  completeness_ratio numeric not null check (completeness_ratio between 0 and 1),
  stale_days integer not null default 0 check (stale_days >= 0),
  schema_valid boolean not null,
  source_conflict_flag boolean not null default false,
  pit_violation_count integer not null default 0 check (pit_violation_count >= 0),
  critical_data_ok boolean not null,
  stage_frozen boolean not null,
  freeze_reason text[],
  warnings jsonb not null default '[]'::jsonb,
  source_used text,
  source_version text,
  fetched_at timestamptz,
  available_at timestamptz,
  created_at timestamptz not null default now(),
  unique(as_of_date,dataset_code,run_id)
);

create table if not exists mainline.mainline_lifecycles (
  lifecycle_id uuid primary key default gen_random_uuid(),
  object_id text not null,
  object_type text not null,
  profile_id text not null references mainline.parameter_profiles(profile_id),
  candidate_at date, confirmed_at date, weakened_at date, closed_at date,
  close_reason text,
  prior_lifecycle_id uuid references mainline.mainline_lifecycles(lifecycle_id),
  created_at timestamptz not null default now()
);

create table if not exists mainline.daily_mainline_snapshot (
  as_of_date date not null,
  object_id text not null,
  object_type text not null,
  lifecycle_id uuid references mainline.mainline_lifecycles(lifecycle_id),
  hard_status text not null check (hard_status in ('S0','S1','S2','S3','S4')),
  previous_status text,
  rs_3 numeric, rs_5 numeric, rs_10 numeric, rs_20 numeric,
  rs_5_pct numeric, rs_10_pct numeric, rs_20_pct numeric,
  win_5 numeric, win_10 numeric, turnover_share numeric,
  turnover_pct_60 numeric, turnover_pct_250 numeric,
  turnover_intensity numeric, turnover_cap_deviation numeric,
  up_ratio numeric, above_ma20 numeric, above_ma60 numeric, new_high_60 numeric,
  top3_turnover_share numeric, top3_return_contribution numeric,
  active_subtheme_count integer, valid_member_count integer,
  metric_coverage_json jsonb,
  candidate_flag boolean not null default false,
  confirmed_flag boolean not null default false,
  critical_data_ok boolean not null default true,
  stage_frozen boolean not null default false,
  freeze_reason text,
  decision_confidence text,
  decision_reason jsonb,
  rule_version text not null,
  profile_id text not null references mainline.parameter_profiles(profile_id),
  source_snapshot_id uuid references mainline.source_snapshots(source_snapshot_id),
  run_id uuid references mainline.run_manifests(run_id),
  recompute_run_id uuid,
  created_at timestamptz not null default now(),
  primary key(as_of_date,object_id,rule_version,profile_id)
);

commit;
