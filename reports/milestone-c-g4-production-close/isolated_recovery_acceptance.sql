begin;
do $$
declare rid uuid:=gen_random_uuid(); n bigint; payload jsonb; ctx jsonb;
begin
 select count(*) into n from mainline.run_manifests;
 payload:=public.mainline_validation_input('2026-09-30');
 payload:=payload||jsonb_build_object('trade_date','2026-09-30','run_type','backfill','run_id',gen_random_uuid(),'pipeline_run_id',gen_random_uuid(),
 'profile_id','industry_trend_v221_state_completion_v1','rule_version','mainline_v2.2.1_state_completion_v1',
 'code_sha','g4_isolated_rollback_test','checksum',(select min(business_checksum) from mainline.daily_checkpoints where trade_date='2026-09-30'),'fault_stage','db_write');
 begin
  perform public.mainline_commit_day(payload);
  raise exception 'expected injected rollback did not occur';
 exception when others then
  if sqlerrm <> 'acceptance_injected_db_rollback' then raise; end if;
 end;
 if (select count(*) from mainline.run_manifests)<>n then raise exception 'failed commit leaked manifest'; end if;
 ctx:=public.mainline_production_context('2026-09-30');
 if ctx->>'seed_date'<>'2026-09-29' then raise exception 'backfill selected future checkpoint'; end if;
 insert into public.automation_runs(id,job_code,run_date,trigger_type,status,metadata)
 values(rid,'daily_research_pipeline','2026-09-30','manual','running',jsonb_build_object('run_type','production_validation','jobs',jsonb_build_object('mainline_job',jsonb_build_object('status','dispatched'),'three_sector_daily_job',jsonb_build_object('status','skipped'),'publish_job',jsonb_build_object('status','skipped'))));
 insert into public.automation_run_steps(run_id,step_code,step_name,status,finished_at) values(rid,'mainline_job','隔离回调验收','running',null);
 perform public.mainline_parent_result(rid,'{"status":"failed","business_status":"failed"}');
 if (select status from public.automation_runs where id=rid)<>'failed' then raise exception 'failure callback not persisted'; end if;
 perform public.mainline_parent_result(rid,'{"status":"running","business_status":"running"}');
 if (select finished_at from public.automation_runs where id=rid) is not null then raise exception 'retry still terminal'; end if;
 perform public.mainline_pipeline_finish(rid,'running','{"jobs":{"mainline_job":{"status":"dispatched"},"three_sector_daily_job":{"status":"skipped"},"publish_job":{"status":"skipped"}}}',null);
 perform public.mainline_parent_result(rid,'{"status":"partial","business_status":"partial"}');
 if (select status from public.automation_runs where id=rid)<>'partial' then raise exception 'partial completion lost'; end if;
 perform public.mainline_pipeline_finish(rid,'running','{"jobs":{"mainline_job":{"status":"dispatched"},"three_sector_daily_job":{"status":"skipped"},"publish_job":{"status":"skipped"}}}',null);
 if (select status from public.automation_runs where id=rid)<>'partial' then raise exception 'late dispatch overwrote completion'; end if;
end $$;
rollback;
