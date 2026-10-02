with s as(select * from mainline.daily_mainline_snapshot where profile_id='industry_trend_v2_2_1_benchmark_close'),
refs as(select distinct unnest(source_snapshot_ids) id from s),
src as(select ss.* from refs r left join mainline.source_snapshots ss on ss.source_snapshot_id=r.id),
old as(select * from mainline.daily_mainline_snapshot where profile_id='industry_trend_v2_2_1_final_close')
select
(select count(*) from s) sample_count,
(select count(*) from s where critical_data_ok and not stage_frozen and freeze_reason is null) healthy_unfrozen,
(select count(*) from s where benchmark_return is not null and rs_5 is not null and rs_10 is not null and rs_20 is not null and turnover_share is not null and turnover_intensity is not null) dependent_metrics_available,
(select min((metric_coverage_json->>'benchmark')::numeric) from s) min_benchmark_coverage,
(select min(least((metric_coverage_json->>'rs_5')::numeric,(metric_coverage_json->>'rs_10')::numeric,(metric_coverage_json->>'rs_20')::numeric)) from s) min_rs_coverage,
(select count(*) from s where turnover_cap_deviation is null and top3_return_contribution is null and decision_reason->>'circ_mv_status'='deferred') deferred_correct,
(select count(*) from s where pit_level='effective_pit' and (decision_reason->>'effective_membership_pit')::boolean) effective_pit,
(select count(*) from src where source_snapshot_id is null) dangling_sources,
(select count(*) from src ss where not exists(select 1 from mainline.source_registry r where r.provider_code=ss.source_id and r.dataset_code=ss.dataset_code)) unregistered_sources,
(select jsonb_agg(distinct dataset_code) from src) lineage_datasets,
(select count(*) from s a join old b using(as_of_date,object_id) where a.sector_return is not distinct from b.sector_return and a.up_ratio is not distinct from b.up_ratio and a.above_ma20 is not distinct from b.above_ma20 and a.above_ma60 is not distinct from b.above_ma60 and a.new_high_60 is not distinct from b.new_high_60 and a.top3_turnover_share is not distinct from b.top3_turnover_share) reused_metrics_unchanged,
(select count(*) from old) old_snapshots_preserved,
(select count(*) from mainline.run_manifests where run_id in ('7fe5ad62-ab71-4759-a334-08dffe980d97','ae8d6541-5a8f-4797-9542-80cc1917fc20') and status='success' and parameter_hash='a602e915961235a8ab5cc678548bf5a249f5197707d18d8b32a518af78c5f21b') valid_manifests,
(select count(*) from mainline.stock_daily) persisted_stock_rows,
(select count(*) from mainline.security_master) persisted_security_rows,
(select count(*) from mainline.trading_calendar) calendar_rows,
(select count(*) from s where (select count(distinct ss.dataset_code) from unnest(s.source_snapshot_ids) r(id) join mainline.source_snapshots ss on ss.source_snapshot_id=r.id)>=6) complete_six_source_chains

