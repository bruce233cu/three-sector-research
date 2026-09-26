begin;

create index if not exists idx_mainline_adjustment_source on mainline.adjustment_factors(source_snapshot_id);
create index if not exists idx_mainline_benchmark_source on mainline.benchmark_daily(source_snapshot_id);
create index if not exists idx_mainline_benchmark_run on mainline.benchmark_daily(run_id);
create index if not exists idx_mainline_corporate_action_source on mainline.corporate_actions(source_snapshot_id);
create index if not exists idx_mainline_daily_snapshot_lifecycle on mainline.daily_mainline_snapshot(lifecycle_id);
create index if not exists idx_mainline_daily_snapshot_profile on mainline.daily_mainline_snapshot(profile_id);
create index if not exists idx_mainline_daily_snapshot_source on mainline.daily_mainline_snapshot(source_snapshot_id);
create index if not exists idx_mainline_daily_snapshot_run on mainline.daily_mainline_snapshot(run_id);
create index if not exists idx_mainline_quality_run on mainline.data_quality_daily(run_id);
create index if not exists idx_mainline_valuation_source on mainline.float_market_cap_daily(source_snapshot_id);
create index if not exists idx_mainline_valuation_run on mainline.float_market_cap_daily(run_id);
create index if not exists idx_mainline_lifecycle_profile on mainline.mainline_lifecycles(profile_id);
create index if not exists idx_mainline_lifecycle_prior on mainline.mainline_lifecycles(prior_lifecycle_id);
create index if not exists idx_mainline_membership_source on mainline.membership_history(source_snapshot_id);
create index if not exists idx_mainline_manifest_parent on mainline.run_manifests(parent_run_id);
create index if not exists idx_mainline_security_source on mainline.security_master(source_snapshot_id);
create index if not exists idx_mainline_stock_source on mainline.stock_daily(source_snapshot_id);
create index if not exists idx_mainline_stock_run on mainline.stock_daily(run_id);
create index if not exists idx_mainline_taxonomy_source on mainline.taxonomy_definitions(source_snapshot_id);
create index if not exists idx_mainline_calendar_source on mainline.trading_calendar(source_snapshot_id);

commit;
