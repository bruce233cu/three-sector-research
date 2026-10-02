begin;
CREATE OR REPLACE FUNCTION public.mainline_attempt_trace(p_payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
declare parent uuid:=(p_payload->>'pipeline_run_id')::uuid; phase text:=p_payload->>'phase'; existing_count integer; frozen integer; last_run uuid; result jsonb;
 rid uuid:=coalesce((p_payload->>'run_id')::uuid,gen_random_uuid());
begin
 if phase not in ('running','succeeded','failed') then raise exception 'invalid attempt phase'; end if;
 select count(*),count(*) filter(where stage_frozen),min(run_id::text)::uuid into existing_count,frozen,last_run from mainline.daily_mainline_snapshot where as_of_date=(p_payload->>'trade_date')::date and profile_id='industry_trend_v221_state_completion_v1';
 if phase='succeeded' and existing_count<>31 then raise exception 'business completion requires 31 persisted snapshots'; end if;
 result:=p_payload||jsonb_build_object('status',case when phase='succeeded' and frozen>0 then 'partial' else phase end,'business_status',case when phase='succeeded' and frozen>0 then 'partial' else phase end,'child_run_id',rid,'snapshot_run_id',last_run);
 insert into mainline.run_manifests(run_id,job_name,as_of_date,code_commit,rule_version,profile_id,status,provider_versions,error_summary,finished_at)
 values(rid,'mainline_job',(p_payload->>'trade_date')::date,p_payload->>'code_sha','mainline_v2.2.1_state_completion_v1','industry_trend_v221_state_completion_v1',case when phase='succeeded' then 'success' else phase end,p_payload||jsonb_build_object('attempt_trace',true,'business_status',result->>'business_status'),jsonb_build_object('reason',p_payload->>'reason','result',p_payload->>'result'),case when phase='running' then null else now() end)
 on conflict(run_id) do update set code_commit=excluded.code_commit,status=excluded.status,provider_versions=excluded.provider_versions,error_summary=excluded.error_summary,finished_at=excluded.finished_at;
 perform public.mainline_parent_result(parent,result);
 update public.automation_jobs set last_run_at=now(),last_status=result->>'status',last_error=case when phase='failed' then p_payload->>'reason' else null end where job_code='mainline_job' and p_payload->>'run_type'='production';
 return result;
end $function$;
commit;

