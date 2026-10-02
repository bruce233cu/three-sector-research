-- One parent UUID traces dispatch, business children, checkpoint lineage and immutable snapshots.
with manifests as (
 select * from mainline.run_manifests
 where provider_versions->>'pipeline_run_id'='69ba9ab1-5b05-44f3-aab2-5d3d325fe872'
), business_children as (
 select r.* from public.automation_runs r join manifests m
 on r.id::text=m.provider_versions->>'business_run_id'
)
select jsonb_build_object(
 'parent',(select to_jsonb(r) from public.automation_runs r where id='69ba9ab1-5b05-44f3-aab2-5d3d325fe872'),
 'steps',(select jsonb_agg(to_jsonb(s)) from public.automation_run_steps s where run_id='69ba9ab1-5b05-44f3-aab2-5d3d325fe872'),
 'manifests',(select jsonb_agg(to_jsonb(m)) from manifests m),
 'business_children',(select jsonb_agg(to_jsonb(r)) from business_children r),
 'input_checkpoints',(select jsonb_agg(to_jsonb(c)) from mainline.daily_checkpoints c where run_id='21a8f577-5de8-46d4-8e1a-5b30e7fd0a5a'),
 'target_checkpoints',(select jsonb_agg(jsonb_build_object('trade_date',trade_date,'object_id',object_id,'run_id',run_id,'checksum',business_checksum)) from mainline.daily_checkpoints where trade_date='2026-09-30'),
 'target_snapshots',(select jsonb_agg(jsonb_build_object('date',as_of_date,'object_id',object_id,'run_id',run_id,'state',hard_status,'frozen',stage_frozen)) from mainline.daily_mainline_snapshot where as_of_date='2026-09-30' and profile_id='industry_trend_v221_state_completion_v1')
);
