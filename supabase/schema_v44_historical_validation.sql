begin;

-- V4.4 lives beside, but never writes into, the real-time research chain.
create table if not exists public.historical_validation_runs (
  id uuid primary key default gen_random_uuid(),
  test_code text not null unique,
  test_name text not null,
  sector text not null check (sector in ('机器人','商业航天','AI')),
  warmup_start_date date not null,
  start_date date not null,
  end_date date not null,
  evaluation_end_date date not null,
  replay_mode text not null check (replay_mode in ('historical_source_reconstruction','true_point_in_time_source')),
  timezone text not null default 'Asia/Shanghai',
  decision_time_rule text not null,
  model_version text not null,
  rule_version text not null,
  threshold_version text not null,
  source_version text not null,
  search_rule_version text not null,
  git_commit_sha text not null,
  database_migration_version text not null,
  version_fingerprint text not null,
  window_selection_reason text not null,
  historical_market_phase text,
  status text not null check (status in ('draft','ready','running','completed','invalid','failed')),
  information_coverage_pct numeric not null default 0,
  stable_available_pct numeric not null default 0,
  collected_record_count integer not null default 0,
  available_record_count integer not null default 0,
  excluded_record_count integer not null default 0,
  signal_count integer not null default 0,
  opportunity_count integer not null default 0,
  company_count integer not null default 0,
  model_count integer not null default 0,
  assessment_count integer not null default 0,
  future_leak_count integer not null default 0,
  model_knowledge_leak_count integer not null default 0,
  hindsight_search_violation_count integer not null default 0,
  availability_high_risk_count integer not null default 0,
  dataset_construction_bias_count integer not null default 0,
  p0_count integer not null default 0,
  p1_count integer not null default 0,
  can_enter_v45 boolean not null default false,
  conclusion text not null,
  created_at timestamptz not null default now(),
  completed_at timestamptz,
  locked_at timestamptz,
  check (warmup_start_date <= start_date and start_date <= end_date and end_date <= evaluation_end_date)
);

create table if not exists public.historical_validation_days (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  simulation_date date not null,
  as_of_time timestamptz not null,
  decision_time timestamptz not null,
  earliest_trade_time timestamptz not null,
  available_raw_record_count integer not null default 0,
  excluded_record_count integer not null default 0,
  signal_count integer not null default 0,
  opportunity_count integer not null default 0,
  company_count integer not null default 0,
  model_count integer not null default 0,
  assessment_count integer not null default 0,
  evidence_bundle jsonb not null default '{}'::jsonb,
  replay_conclusion text not null,
  created_at timestamptz not null default now(),
  unique(test_run_id, simulation_date)
);

create table if not exists public.historical_raw_records (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  original_record_id uuid,
  source_name text not null,
  source_url text,
  source_type text not null,
  title text not null,
  summary text,
  raw_content text,
  sector text not null,
  company_names text[] not null default '{}',
  opportunity_keywords text[] not null default '{}',
  evidence_level text,
  sentiment text not null default 'neutral',
  event_date date,
  published_at timestamptz,
  known_at timestamptz,
  available_at timestamptz,
  ingested_at timestamptz,
  availability_status text not null check (availability_status in ('A','B','C','D')),
  availability_risk text not null,
  source_access_method text not null,
  archive_status text not null,
  search_ranking_bias boolean not null default false,
  strict_eligible boolean not null default false,
  dedupe_key text,
  underlying_event_id text not null,
  original_screening_status text,
  provenance jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(test_run_id, original_record_id)
);

create table if not exists public.historical_available_records (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  validation_day_id uuid not null references public.historical_validation_days(id),
  historical_raw_record_id uuid not null references public.historical_raw_records(id),
  inclusion_status text not null check (inclusion_status in ('available','excluded')),
  exclusion_reason text,
  boundary_check jsonb not null,
  created_at timestamptz not null default now(),
  unique(validation_day_id, historical_raw_record_id)
);

create table if not exists public.historical_signals (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  validation_day_id uuid not null references public.historical_validation_days(id),
  signal_key text not null,
  title text not null,
  sector text not null,
  change_type text,
  judgment text not null,
  reason text not null,
  evidence_record_ids uuid[] not null default '{}',
  next_step text,
  created_at timestamptz not null default now(),
  unique(test_run_id, signal_key)
);

create table if not exists public.historical_opportunities (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  validation_day_id uuid not null references public.historical_validation_days(id),
  opportunity_key text not null,
  name text not null,
  sector text not null,
  logic text not null,
  status text not null,
  source_signal_ids uuid[] not null default '{}',
  evidence_record_ids uuid[] not null default '{}',
  risk text,
  counter_evidence text,
  next_validation text,
  created_at timestamptz not null default now(),
  unique(test_run_id, opportunity_key)
);

create table if not exists public.historical_companies (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  validation_day_id uuid not null references public.historical_validation_days(id),
  company_key text not null,
  company_name text not null,
  stock_code text,
  listing_status_at_time text,
  company_role text not null,
  opportunity_ids uuid[] not null default '{}',
  first_signal_id uuid,
  discovery_reason text not null,
  business_description_at_time text,
  mapping_evidence_record_ids uuid[] not null default '{}',
  modeling_decision text not null,
  modeling_reason text not null,
  created_at timestamptz not null default now(),
  unique(test_run_id, company_key)
);

create table if not exists public.historical_models (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  validation_day_id uuid not null references public.historical_validation_days(id),
  historical_company_id uuid not null references public.historical_companies(id),
  model_version text not null,
  model_type text not null,
  financial_vintage text,
  forecast_vintage text,
  pessimistic_profit numeric,
  base_profit numeric,
  optimistic_profit numeric,
  pessimistic_target_market_cap numeric,
  base_target_market_cap numeric,
  optimistic_target_market_cap numeric,
  pessimistic_probability numeric,
  base_probability numeric,
  optimistic_probability numeric,
  profit_confidence text,
  probability_confidence text,
  parameter_evidence jsonb not null default '{}'::jsonb,
  calculation_trace jsonb not null default '{}'::jsonb,
  vintage_risk text,
  frozen_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique(test_run_id, historical_company_id, model_version)
);

create table if not exists public.historical_assessments (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  validation_day_id uuid not null references public.historical_validation_days(id),
  historical_company_id uuid not null references public.historical_companies(id),
  historical_model_id uuid not null references public.historical_models(id),
  assessment_version text not null,
  calculation_date date not null,
  decision_time timestamptz not null,
  price_snapshot_time timestamptz not null,
  historical_trade_price numeric not null,
  adjusted_return_price numeric,
  share_count_at_time numeric not null,
  market_cap_at_time numeric not null,
  pessimistic_return numeric,
  base_return numeric,
  optimistic_return numeric,
  expected_return numeric,
  max_downside numeric,
  risk_reward_ratio numeric,
  suspended boolean,
  limit_up boolean,
  limit_down boolean,
  turnover numeric,
  liquidity_status text,
  created_at timestamptz not null default now(),
  unique(test_run_id, historical_company_id, assessment_version)
);

create table if not exists public.historical_decisions (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  validation_day_id uuid not null references public.historical_validation_days(id),
  object_type text not null,
  object_key text not null,
  stage text not null,
  decision text not null,
  reason text not null,
  evidence_record_ids uuid[] not null default '{}',
  rule_version text not null,
  decision_time timestamptz not null,
  created_at timestamptz not null default now()
);

create table if not exists public.historical_leak_checks (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  validation_day_id uuid references public.historical_validation_days(id),
  check_code text not null,
  check_name text not null,
  severity text not null check (severity in ('P0','P1','P2')),
  result text not null check (result in ('passed','failed','not_verifiable')),
  violation_count integer not null default 0,
  detail text not null,
  affected_record_ids uuid[] not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists public.historical_source_coverage (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  source_type text not null,
  collected_count integer not null default 0,
  available_count integer not null default 0,
  excluded_count integer not null default 0,
  availability_risk_count integer not null default 0,
  negative_record_count integer not null default 0,
  coverage_pct numeric not null default 0,
  conclusion text not null,
  created_at timestamptz not null default now(),
  unique(test_run_id, source_type)
);

create table if not exists public.historical_search_logs (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  simulation_date date not null,
  query text not null,
  query_origin text not null,
  source_signal_id uuid,
  reason text not null,
  returned_entities text[] not null default '{}',
  selected_entities text[] not null default '{}',
  search_ranking_bias boolean not null default false,
  hindsight_risk text,
  created_at timestamptz not null default now()
);

create index if not exists historical_days_run_date_idx on public.historical_validation_days(test_run_id,simulation_date);
create index if not exists historical_raw_run_time_idx on public.historical_raw_records(test_run_id,published_at,ingested_at);
create index if not exists historical_available_day_status_idx on public.historical_available_records(validation_day_id,inclusion_status);
create index if not exists historical_leak_run_result_idx on public.historical_leak_checks(test_run_id,severity,result);
create index if not exists historical_decisions_run_time_idx on public.historical_decisions(test_run_id,decision_time);

create or replace function public.protect_historical_validation_run()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'historical validation runs are append-only';
  end if;
  if old.locked_at is not null then
    raise exception 'locked historical validation runs cannot be changed';
  end if;
  if row(old.model_version,old.rule_version,old.threshold_version,old.source_version,
         old.search_rule_version,old.git_commit_sha,old.database_migration_version,
         old.warmup_start_date,old.start_date,old.end_date,old.evaluation_end_date)
     is distinct from
     row(new.model_version,new.rule_version,new.threshold_version,new.source_version,
         new.search_rule_version,new.git_commit_sha,new.database_migration_version,
         new.warmup_start_date,new.start_date,new.end_date,new.evaluation_end_date)
  then
    raise exception 'version or date boundary changed; create a new test run';
  end if;
  return new;
end;
$$;

drop trigger if exists historical_validation_runs_guard on public.historical_validation_runs;
create trigger historical_validation_runs_guard
before update or delete on public.historical_validation_runs
for each row execute function public.protect_historical_validation_run();

do $$
declare t text;
begin
  foreach t in array array[
    'historical_validation_days','historical_raw_records','historical_available_records',
    'historical_signals','historical_opportunities','historical_companies','historical_models',
    'historical_assessments','historical_decisions','historical_leak_checks',
    'historical_source_coverage','historical_search_logs'
  ] loop
    execute format('drop trigger if exists %I on public.%I',t||'_immutable',t);
    execute format('create trigger %I before update or delete on public.%I for each row execute function public.reject_history_mutation()',t||'_immutable',t);
  end loop;
end $$;

do $$
declare t text;
begin
  foreach t in array array[
    'historical_validation_runs','historical_validation_days','historical_raw_records',
    'historical_available_records','historical_signals','historical_opportunities',
    'historical_companies','historical_models','historical_assessments','historical_decisions',
    'historical_leak_checks','historical_source_coverage','historical_search_logs'
  ] loop
    execute format('alter table public.%I enable row level security',t);
    execute format('drop policy if exists %I on public.%I',t||'_public_read',t);
    execute format('create policy %I on public.%I for select to anon, authenticated using (true)',t||'_public_read',t);
    execute format('grant select on public.%I to anon, authenticated',t);
    execute format('grant all on public.%I to service_role',t);
  end loop;
end $$;

revoke execute on function public.protect_historical_validation_run() from public, anon, authenticated;
grant execute on function public.protect_historical_validation_run() to service_role;

commit;
