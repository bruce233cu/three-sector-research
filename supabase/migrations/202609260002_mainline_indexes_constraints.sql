begin;

create index if not exists idx_mainline_membership_asof
  on mainline.membership_history(taxonomy_id,effective_from,effective_to);
create index if not exists idx_mainline_membership_security
  on mainline.membership_history(security_id,effective_from,effective_to);
create index if not exists idx_mainline_membership_available
  on mainline.membership_history(available_at);
create index if not exists idx_mainline_security_universe
  on mainline.security_master(list_date,delist_date);
create index if not exists idx_mainline_stock_daily_date
  on mainline.stock_daily(trade_date,security_id);
create index if not exists idx_mainline_valuation_date
  on mainline.float_market_cap_daily(trade_date,security_id);
create index if not exists idx_mainline_benchmark_date
  on mainline.benchmark_daily(index_id,trade_date);
create index if not exists idx_mainline_fetch_run
  on mainline.provider_fetch_runs(run_id,dataset_code,provider_code,attempt_no);
create index if not exists idx_mainline_quality_date
  on mainline.data_quality_daily(as_of_date,dataset_code);
create index if not exists idx_mainline_snapshot_date_status
  on mainline.daily_mainline_snapshot(as_of_date,hard_status);
create index if not exists idx_mainline_manifest_date
  on mainline.run_manifests(as_of_date,job_name,created_at desc);
create index if not exists idx_mainline_source_snapshot
  on mainline.source_snapshots(dataset_code,source_id,fetched_at desc);

create or replace function mainline.reject_snapshot_mutation()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  raise exception 'append-only table: historical rows cannot be updated or deleted';
end;
$$;

drop trigger if exists source_snapshots_append_only on mainline.source_snapshots;
create trigger source_snapshots_append_only
before update or delete on mainline.source_snapshots
for each row execute function mainline.reject_snapshot_mutation();

drop trigger if exists run_manifests_no_delete on mainline.run_manifests;
create trigger run_manifests_no_delete
before delete on mainline.run_manifests
for each row execute function mainline.reject_snapshot_mutation();

revoke all on function mainline.reject_snapshot_mutation() from public,anon,authenticated;

commit;
