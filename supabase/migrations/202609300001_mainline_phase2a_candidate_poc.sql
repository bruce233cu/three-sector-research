begin;

create table if not exists mainline.phase2a_candidate_checks (
  trade_date date not null,
  object_id text not null,
  taxonomy_code text not null,
  industry_name text not null,
  taxonomy_version text not null,
  window_id text not null,
  window_kind text not null,
  metrics jsonb not null,
  conditions jsonb not null,
  valid_condition_count smallint not null check (valid_condition_count between 0 and 5),
  pass_condition_count smallint not null check (pass_condition_count between 0 and 5),
  final_decision text not null check (final_decision in ('S1','S0','DATA_INSUFFICIENT')),
  decision_reason text not null,
  rule_version text not null,
  parameter_profile text not null,
  run_id uuid not null,
  source_snapshot_ids text[] not null default '{}',
  source_used text not null,
  fetched_at timestamptz not null,
  code_commit text,
  created_at timestamptz not null default now(),
  primary key (trade_date, object_id, rule_version, parameter_profile, run_id)
);

comment on table mainline.phase2a_candidate_checks is 'Phase 2A frozen S0-to-S1 rule evidence; no scores and no S2-S4 state.';
create index if not exists phase2a_candidate_checks_latest_idx on mainline.phase2a_candidate_checks(trade_date desc, final_decision);
alter table mainline.phase2a_candidate_checks enable row level security;
revoke all on table mainline.phase2a_candidate_checks from public, anon, authenticated;

create or replace function public.get_mainline_status_v2()
returns jsonb language sql security definer set search_path = pg_catalog, public, mainline as $$
  select public.get_mainline_phase1d_status() || jsonb_build_object(
    'candidate_poc', coalesce((
      select jsonb_agg(to_jsonb(x) order by x.trade_date desc, x.taxonomy_code)
      from (
        select distinct on (trade_date, object_id) trade_date, industry_name, taxonomy_code,
          conditions, valid_condition_count, pass_condition_count, final_decision
        from mainline.phase2a_candidate_checks
        order by trade_date desc, object_id, created_at desc
        limit 40
      ) x
    ), '[]'::jsonb)
  );
$$;

revoke all on function public.get_mainline_status_v2() from public, anon, authenticated;
grant execute on function public.get_mainline_status_v2() to service_role;

commit;
