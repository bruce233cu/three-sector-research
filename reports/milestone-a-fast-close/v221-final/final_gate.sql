with samples as (
 select * from mainline.daily_mainline_snapshot where run_id='62c078a6-7033-444b-a868-7f593dc54c3d' and rule_version='mainline_v2.2.1' and profile_id='industry_trend_v2_2_1_fast_close'
), lineage as (
 select d.as_of_date,d.object_id,
  count(*) filter(where s.dataset_code='membership_snapshot' and s.row_count>0) membership_sources,
  count(*) filter(where s.dataset_code='stock_window' and s.row_count>0) stock_sources,
  count(*) filter(where s.dataset_code='all_a_equal_weight_benchmark' and s.row_count>0) equal_weight_sources,
  count(*) filter(where a.id is not null and s.source_snapshot_id is null) dangling
 from samples d left join lateral unnest(d.source_snapshot_ids) a(id) on true left join mainline.source_snapshots s on s.source_snapshot_id=a.id
 group by d.as_of_date,d.object_id
), result as (
 select count(*) formal_count,count(*) filter(where stage_frozen) frozen_count,
 count(*) filter(where critical_data_ok) critical_ok_count,
 count(*) filter(where benchmark_return is not null and (metric_coverage_json->>'benchmark')::numeric >=.95) benchmark_available_count,
 count(*) filter(where benchmark_return is null and rs_5 is null and rs_10 is null and rs_20 is null) null_propagation_count,
 count(*) filter(where turnover_cap_deviation is null and top3_return_contribution is null) deferred_null_count,
 count(*) filter(where decision_reason->>'source_lineage_complete'='true') lineage_claim_count,
 count(*) filter(where decision_reason->>'membership_effective_pit'='true') membership_effective_date_count
 from samples
), source_result as (
 select count(*) filter(where membership_sources>0 and stock_sources>0 and equal_weight_sources>0) complete_chain_count,
 coalesce(sum(dangling),0) dangling_count from lineage
)
select case when formal_count=15 and critical_ok_count=15 and benchmark_available_count=15 and complete_chain_count=15
 and dangling_count=0 and (select error_summary->>'real_data_repeatability_accepted' from mainline.run_manifests where run_id='62c078a6-7033-444b-a868-7f593dc54c3d')='true'
 then 'PASS' else 'FAIL' end as "G1",
 (formal_count=15 and critical_ok_count=15 and benchmark_available_count=15 and complete_chain_count=15
 and dangling_count=0 and (select error_summary->>'real_data_repeatability_accepted' from mainline.run_manifests where run_id='62c078a6-7033-444b-a868-7f593dc54c3d')='true') as "READY_FOR_PRODUCTION_ENABLEMENT",result.*,source_result.*
 from result cross join source_result;
