do $audit$
declare pid uuid:=gen_random_uuid(); rid uuid:=gen_random_uuid(); v jsonb; sector jsonb; ok1 boolean; ok2 boolean; ok3 boolean; ok4 boolean;
begin
 select coalesce(metadata->'jobs'->'three_sector_daily_job',jsonb_build_object('status',status,'source_run_id',id)) into sector from public.automation_runs where job_code='daily_research_pipeline' and status='succeeded' order by started_at desc limit 1;
 begin
 insert into public.automation_runs(id,job_code,run_date,trigger_type,status,metadata) values(pid,'daily_research_pipeline','2026-09-30','manual','running',jsonb_build_object('acceptance_rollback_only',true,'jobs',jsonb_build_object('mainline_job',jsonb_build_object('status','dispatched','business_status','dispatched','pipeline_run_id',pid),'three_sector_daily_job',sector)));
 insert into public.automation_run_steps(run_id,step_code,step_name,status,metadata) values(pid,'mainline_job','回滚范围内的合同检查','running',jsonb_build_object('pipeline_run_id',pid,'business_status','dispatched'));
 select status='running' into ok1 from public.automation_run_steps where run_id=pid and step_code='mainline_job';
 v:=public.mainline_attempt_trace(jsonb_build_object('phase','running','trade_date','2026-09-30','run_type','production','pipeline_run_id',pid,'run_id',rid,'code_sha','33e615c39fec195a170b4dbfb932095c47de4824','workflow_run_id','acceptance_rollback_only'));
 if v->>'business_status'<>'running' or v->>'pipeline_run_id'<>pid::text then raise exception 'running trace broken'; end if;
 v:=public.mainline_attempt_trace(jsonb_build_object('phase','succeeded','trade_date','2026-09-30','run_type','production','pipeline_run_id',pid,'run_id',rid,'code_sha','33e615c39fec195a170b4dbfb932095c47de4824','result','already_committed','workflow_run_id','acceptance_rollback_only'));
 ok2:=v->>'business_status'='partial' and v->>'pipeline_run_id'=pid::text and v->>'child_run_id'=rid::text;
 perform public.mainline_pipeline_finish(pid,'partial',jsonb_build_object('jobs',jsonb_build_object('mainline_job',jsonb_build_object('status','dispatched'),'three_sector_daily_job',sector)),null);
 select metadata->'jobs'->'mainline_job'->>'business_status'='partial',metadata->'jobs'->'three_sector_daily_job'=sector into ok3,ok4 from public.automation_runs where id=pid;
 if not(ok1 and ok2 and ok3 and ok4) then raise exception 'pipeline trace acceptance failed'; end if;
 raise exception using errcode='Z0001',message='rollback acceptance only';
 exception when sqlstate 'Z0001' then null; end;
 if exists(select 1 from public.automation_runs where id=pid) or exists(select 1 from mainline.run_manifests where run_id=rid) then raise exception 'acceptance write leaked'; end if;
 perform set_config('mainline.g4_trace',jsonb_build_object('dispatch_is_not_success',ok1,'parent_child_trace',ok2,'late_pipeline_finish_preserves_business_result',ok3,'three_sector_metadata_preserved',ok4,'test_writes_rolled_back',true,'live_dispatch_tested',false)::text,false);
end $audit$;
select current_setting('mainline.g4_trace')::jsonb as acceptance;
