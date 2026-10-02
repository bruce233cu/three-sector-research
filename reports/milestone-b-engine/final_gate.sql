with e as(select * from mainline.daily_mainline_snapshot where profile_id='industry_trend_v2_2_1_engine_audit'),g as(select * from mainline.daily_mainline_snapshot where profile_id='industry_trend_v2_2_1_benchmark_close'),refs as(select distinct unnest(source_snapshot_ids) id from e)
select
(select count(*) from e) engine_audit_rows,
(select count(*) from e where hard_status is null and previous_status is null and lifecycle_id is null and stage_frozen) unknown_state_preserved,
(select count(*) from e a join g b using(as_of_date,object_id) where a.sector_return is not distinct from b.sector_return and a.benchmark_return is not distinct from b.benchmark_return and a.rs_5 is not distinct from b.rs_5 and a.rs_10 is not distinct from b.rs_10 and a.rs_20 is not distinct from b.rs_20 and a.turnover_share is not distinct from b.turnover_share and a.turnover_intensity is not distinct from b.turnover_intensity and a.up_ratio is not distinct from b.up_ratio and a.above_ma20 is not distinct from b.above_ma20 and a.above_ma60 is not distinct from b.above_ma60 and a.new_high_60 is not distinct from b.new_high_60 and a.top3_turnover_share is not distinct from b.top3_turnover_share) core_metrics_unchanged,
(select count(*) from e where turnover_cap_deviation is null and top3_return_contribution is null) deferred_null,
(select count(*) from refs r left join mainline.source_snapshots s on s.source_snapshot_id=r.id where s.source_snapshot_id is null) dangling_sources,
(select count(*) from refs r join mainline.source_snapshots s on s.source_snapshot_id=r.id where not exists(select 1 from mainline.source_registry z where z.provider_code=s.source_id and z.dataset_code=s.dataset_code)) unregistered_sources,
(select count(*) from mainline.data_quality_daily where run_id='354edd71-af9e-5d7f-9864-6f54545ddefd' and stage_frozen) state_quality_audits,
(select count(*) from mainline.mainline_lifecycles) lifecycle_rows,
(select count(*) from g where critical_data_ok and not stage_frozen and decision_reason->>'status'='SUCCESS') original_G1_SUCCESS,
(select count(*) from mainline.run_manifests where run_id in ('354edd71-af9e-5d7f-9864-6f54545ddefd','cbbe3b07-dd05-5c69-a105-f05edf7df206')) engine_manifests,
(select count(*) from mainline.stock_daily) persisted_stock_rows,
(select count(*) from mainline.security_master) persisted_security_rows,
(select count(*) from mainline.trading_calendar) calendar_rows,
(select error_summary->'final_gates'->>'G2' from mainline.run_manifests where run_id='354edd71-af9e-5d7f-9864-6f54545ddefd') G2,
(select error_summary->'final_gates'->>'G3' from mainline.run_manifests where run_id='354edd71-af9e-5d7f-9864-6f54545ddefd') G3,
(select error_summary->'optimization_record'->>'summary' from mainline.run_manifests where run_id='354edd71-af9e-5d7f-9864-6f54545ddefd') optimization_summary

