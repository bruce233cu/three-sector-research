with per_sample as (
select d.as_of_date,d.object_id,d.rule_version,d.critical_data_ok,d.stage_frozen,
count(x.sid) ref_count,count(*) filter(where x.sid is not null and s.source_snapshot_id is null) dangling,
count(*) filter(where s.metadata->>'restored_from_immutable_artifact'='true') restored,
coalesce(bool_or(s.dataset_code='membership_snapshot' and s.row_count>0),false) member_ok,
coalesce(bool_or(s.dataset_code='stock_window' and s.row_count>0),false) stock_ok,
coalesce(bool_or(s.dataset_code='benchmark_window' and s.row_count>0),false) benchmark_ref_ok,
m.run_id is not null manifest_ok
from mainline.daily_mainline_snapshot d
left join lateral unnest(d.source_snapshot_ids)x(sid) on true
left join mainline.source_snapshots s on s.source_snapshot_id=x.sid
left join mainline.run_manifests m on m.run_id=d.run_id
group by d.as_of_date,d.object_id,d.rule_version,d.critical_data_ok,d.stage_frozen,m.run_id
), checks as (
select count(*) samples,count(*) filter(where restored>0) samples_with_restored_refs,
sum(restored) restored_ref_occurrences,sum(dangling) dangling_refs,
count(*) filter(where member_ok and stock_ok and benchmark_ref_ok and manifest_ok) complete_nonempty_registered_chains,
count(*) filter(where not(member_ok and stock_ok and benchmark_ref_ok and manifest_ok)) incomplete_or_empty_registered_chains,
count(*) filter(where rule_version='mainline_v2.2.1') v221_snapshots,
count(*) filter(where stage_frozen) frozen_old_snapshots,
count(*) filter(where ref_count=1) benchmark_only_chains from per_sample
)
select now() audited_at,'G1 DATA GATE — V2.2.1 FINAL' gate,
'FAIL' result,false "READY_FOR_PRODUCTION_ENABLEMENT",
'open' milestone_a_status,
checks.*,
(select jsonb_object_agg(status,n) from(select status,count(*) n from mainline.phase1d_sample_runs group by status)x) old_status_counts,
(select params_json->'benchmark' from mainline.parameter_profiles where profile_id='industry_trend_v2_2_1_fast_close') frozen_benchmark,
(select params_json->'metric_availability' from mainline.parameter_profiles where profile_id='industry_trend_v2_2_1_fast_close') deferred_policy,
(select jsonb_build_object('min',min(cal_date),'max',max(cal_date),'rows',count(*),'open_days',count(*) filter(where is_open)) from mainline.trading_calendar where exchange='SSE') calendar,
jsonb_build_object('benchmark_identity','FAIL_NOT_CERTIFIED','all_a_amount_semantics','FAIL_NOT_CERTIFIED','raw_payload_replay','FAIL_NOT_VERIFIED','v221_15_sample_acceptance','FAIL_NO_V221_SNAPSHOTS') evidence_checks
from checks
