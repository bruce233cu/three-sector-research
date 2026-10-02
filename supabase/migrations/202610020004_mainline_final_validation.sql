begin;
create or replace function public.mainline_validation_input(p_date date)
returns jsonb language plpgsql stable set search_path='' as $$
declare rows jsonb; sources jsonb;
begin
 if p_date >= (now() at time zone 'Asia/Shanghai')::date then raise exception 'validation must use completed historical date'; end if;
 select jsonb_agg(decision_reason order by object_id) into rows from mainline.daily_mainline_snapshot
 where as_of_date=p_date and profile_id='industry_trend_v221_state_completion_v1';
 if jsonb_array_length(rows)<>31 or rows is null then raise exception 'validation requires certified full daily panel'; end if;
 select jsonb_agg(to_jsonb(s)) into sources from mainline.source_snapshots s where source_snapshot_id in
 (select distinct jsonb_array_elements_text(x->'snapshot'->'source_snapshot_ids')::uuid from jsonb_array_elements(rows) x);
 return jsonb_build_object('rows',rows,'sources',sources,'source','database_real_historical_panel','trade_date',p_date);
end $$;
revoke all on function public.mainline_validation_input(date) from public,anon,authenticated;
grant execute on function public.mainline_validation_input(date) to service_role;
CREATE OR REPLACE FUNCTION public.mainline_commit_day(p_payload jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
declare
 d date:=(p_payload->>'trade_date')::date;
 rid uuid:=(p_payload->>'run_id')::uuid;
 pid uuid:=coalesce((p_payload->>'pipeline_run_id')::uuid,gen_random_uuid());
 prof text:=p_payload->>'profile_id';
 rv text:=p_payload->>'rule_version';
 typ text:=p_payload->>'run_type';
 cs text:=p_payload->>'checksum';
 row jsonb; s jsonb; m jsonb; lc jsonb; q jsonb; src jsonb;
 n integer; existing text; frozen integer:=0; result text:='committed';
begin
 if typ not in ('production','production_simulation','backfill','production_validation') then raise exception 'invalid run_type'; end if;
 if not exists(select 1 from mainline.trading_calendar where exchange='SSE' and cal_date=d and is_open) then raise exception 'not a verified market day'; end if;
 if prof<>'industry_trend_v221_state_completion_v1' or rv<>'mainline_v2.2.1_state_completion_v1' then raise exception 'unapproved profile'; end if;
 perform pg_advisory_xact_lock(hashtextextended('mainline:'||d||prof,0));
 n:=jsonb_array_length(p_payload->'rows');
 if n<>31 then raise exception 'incomplete daily panel'; end if;
 if n<>(select count(distinct x->'snapshot'->>'object_id') from jsonb_array_elements(p_payload->'rows') x) then raise exception 'duplicate object'; end if;
 select min(business_checksum) into existing from mainline.daily_checkpoints where trade_date=d and profile_id=prof and rule_version=rv;
 if typ='production_validation' and existing is null then raise exception 'validation requires existing certified target'; end if;
 if existing is not null and existing<>cs then raise exception 'conflicting committed input requires separate versioned backfill'; end if;
 if existing is not null then result:='idempotent'; end if;
 insert into public.automation_runs(id,job_code,run_date,trigger_type,status,metadata)
 values(pid,'mainline_job',d,'manual','running',jsonb_build_object('run_type',typ,'run_id',rid,'code_sha',p_payload->>'code_sha','rule_version',rv,'parameter_profile',prof))
 on conflict(id) do nothing;
 insert into mainline.run_manifests(run_id,job_name,as_of_date,code_commit,rule_version,profile_id,parameter_hash,status,provider_versions,row_counts,error_summary)
 values(rid,'mainline_job',d,p_payload->>'code_sha',rv,prof,p_payload->>'parameter_hash','running',
 jsonb_build_object('run_type',typ,'pipeline_run_id',coalesce(p_payload->>'parent_pipeline_run_id',pid::text),'business_run_id',pid,'input_mode',p_payload->>'input_mode','workflow_run_id',p_payload->>'workflow_run_id','business_date',d,'bootstrap_source',p_payload->>'bootstrap_source','seed_date',p_payload->>'seed_date','checkpoint_evidence',p_payload->'checkpoint_evidence','profile_reuse_explicit',true),jsonb_build_object('boards',n),jsonb_build_object('checksum',cs,'result',result))
 on conflict(run_id) do nothing;
 for src in select * from jsonb_array_elements(p_payload->'sources') loop
   insert into mainline.source_snapshots(source_snapshot_id,source_id,dataset_code,source_version,fetched_at,response_checksum,row_count,raw_location,historical_capability,metadata)
   values((src->>'source_snapshot_id')::uuid,src->>'source_id',src->>'dataset_code',src->>'source_version',(src->>'fetched_at')::timestamptz,src->>'response_checksum',(src->>'row_count')::integer,src->>'raw_location','historical_partial',src->'metadata')
   on conflict do nothing;
 end loop;
 if existing is null then
  -- Preserve lifecycle ancestry; these are certified board checkpoints, never synthetic fixtures.
  for lc in select * from jsonb_array_elements(coalesce(p_payload->'lifecycle_ancestry','[]')) loop
   insert into mainline.mainline_lifecycles(lifecycle_id,object_id,object_type,profile_id,candidate_at,confirmed_at,weakened_at,closed_at,close_reason,prior_lifecycle_id,lifecycle_payload,last_state_date)
   values((lc->>'lifecycle_id')::uuid,lc->>'object_id',lc->>'object_type',prof,(lc->>'candidate_at')::date,(lc->>'confirmed_at')::date,(lc->>'weakened_at')::date,(lc->>'closed_at')::date,lc->>'close_reason',(lc->>'prior_lifecycle_id')::uuid,lc,d)
   on conflict(lifecycle_id) do update set confirmed_at=excluded.confirmed_at,weakened_at=excluded.weakened_at,closed_at=excluded.closed_at,close_reason=excluded.close_reason,lifecycle_payload=excluded.lifecycle_payload,last_state_date=excluded.last_state_date
   where mainline.mainline_lifecycles.last_state_date<=excluded.last_state_date;
  end loop;
  for row in select * from jsonb_array_elements(p_payload->'rows') loop
   if row->'snapshot'->>'as_of_date'<>d::text or row->'state'->>'trade_date'<>d::text or row->'state'->'checkpoint'->>'last_date'<>d::text then raise exception 'input date mismatch'; end if;
   if row->'state'->>'rule_version'<>rv or row->'state'->>'parameter_profile'<>prof then raise exception 'checkpoint version mismatch'; end if;
   row:=jsonb_set(jsonb_set(row,'{snapshot,run_id}',to_jsonb(rid)),'{state,run_id}',to_jsonb(rid));
   m:=row->'snapshot';s:=row->'state';lc:=s->'checkpoint'->'lifecycle';
   if jsonb_typeof(lc)='object' then
    insert into mainline.mainline_lifecycles(lifecycle_id,object_id,object_type,profile_id,candidate_at,confirmed_at,weakened_at,closed_at,close_reason,prior_lifecycle_id,lifecycle_payload,last_state_date)
    values((lc->>'lifecycle_id')::uuid,lc->>'object_id',lc->>'object_type',prof,(lc->>'candidate_at')::date,(lc->>'confirmed_at')::date,(lc->>'weakened_at')::date,(lc->>'closed_at')::date,lc->>'close_reason',(lc->>'prior_lifecycle_id')::uuid,lc,d)
    on conflict(lifecycle_id) do update set confirmed_at=excluded.confirmed_at,weakened_at=excluded.weakened_at,closed_at=excluded.closed_at,close_reason=excluded.close_reason,lifecycle_payload=excluded.lifecycle_payload,last_state_date=excluded.last_state_date
    where mainline.mainline_lifecycles.last_state_date<=excluded.last_state_date;
   end if;
   if (s->>'stage_frozen')::boolean then frozen:=frozen+1; end if;
   insert into mainline.daily_checkpoints values(d,m->>'object_id',m->>'taxonomy_version',rv,prof,rid,s->'checkpoint',s,cs);
   insert into mainline.daily_mainline_snapshot(as_of_date,object_id,object_type,lifecycle_id,hard_status,previous_status,rs_5,rs_10,rs_20,rs_5_pct,rs_10_pct,rs_20_pct,win_5,win_10,turnover_share,turnover_pct_60,turnover_intensity,up_ratio,above_ma20,above_ma60,new_high_60,top3_turnover_share,valid_member_count,metric_coverage_json,critical_data_ok,stage_frozen,freeze_reason,decision_reason,rule_version,profile_id,run_id,taxonomy_code,taxonomy_version,member_count,sector_return,benchmark_return,source_snapshot_ids,pit_level,knowledge_time_unverified,cache_checksum)
   values(d,m->>'object_id',m->>'object_type',(s->>'lifecycle_id')::uuid,s->>'state',s->>'previous_state',(m->>'rs_5')::numeric,(m->>'rs_10')::numeric,(m->>'rs_20')::numeric,(m->>'rs_5_pct')::numeric,(m->>'rs_10_pct')::numeric,(m->>'rs_20_pct')::numeric,(m->>'win_5')::numeric,(m->>'win_10')::numeric,(m->>'turnover_share')::numeric,(m->>'turnover_pct_60')::numeric,(m->>'turnover_intensity')::numeric,(m->>'up_ratio')::numeric,(m->>'above_ma20')::numeric,(m->>'above_ma60')::numeric,(m->>'new_high_60')::numeric,(m->>'top3_turnover_share')::numeric,(m->>'valid_member_count')::integer,m->'metric_coverage_json',(s->>'critical_data_ok')::boolean,(s->>'stage_frozen')::boolean,s->>'freeze_reason',row,rv,prof,rid,m->>'taxonomy_code',m->>'taxonomy_version',(m->>'member_count')::integer,(m->>'sector_return')::numeric,(m->>'benchmark_return')::numeric,ARRAY(select jsonb_array_elements_text(m->'source_snapshot_ids'))::uuid[],'effective_pit',true,cs);
   for q in select * from jsonb_array_elements(row->'rules') loop
    insert into mainline.rule_evidence values(d,m->>'object_id',rv,prof,q->>'rule_id',rid,q->'actual_value',q->'threshold',q->>'operator',(q->>'passed')::boolean,case when q->>'passed' is null then 'unavailable' else 'available' end,q->>'reason');
   end loop;
  end loop;
 else
  select count(*) into frozen from mainline.daily_checkpoints where trade_date=d and profile_id=prof and (state_payload->>'stage_frozen')::boolean;
 end if;
 insert into mainline.production_feature_history(trade_date,object_id,taxonomy_version,rule_version,profile_id,metric_availability_version,snapshot,evidence_sha256,evidence_location)
 select d,x->'snapshot'->>'object_id',x->'snapshot'->>'taxonomy_version',rv,prof,x->'snapshot'->>'metric_availability_version',x->'snapshot',cs,'run-manifest:'||rid::text from jsonb_array_elements(p_payload->'rows') x on conflict do nothing;
 if p_payload->>'fault_stage'='db_write' and typ='backfill' then raise exception 'acceptance_injected_db_rollback'; end if;
 insert into mainline.data_quality_daily(as_of_date,dataset_code,run_id,expected_count,actual_count,missing_count,duplicate_count,completeness_ratio,schema_valid,critical_data_ok,stage_frozen,freeze_reason,warnings)
 values(d,'daily_board_state',rid,n,n,0,0,1,true,frozen=0,frozen>0,case when frozen>0 then array['board_rule_or_input_frozen'] else array[]::text[] end,jsonb_build_array(jsonb_build_object('frozen_boards',frozen))) on conflict do nothing;
 update mainline.run_manifests set status='success',critical_data_ok=frozen=0,stage_frozen=frozen>0,finished_at=now(),row_counts=row_counts||jsonb_build_object('frozen',frozen),source_snapshot_ids=ARRAY(select (x->>'source_snapshot_id')::uuid from jsonb_array_elements(p_payload->'sources') x) where run_id=rid;
 insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message,metadata)
 values(pid,'mainline_atomic_commit','板块状态、规则和质量原子保存','succeeded',n,result,jsonb_build_object('checksum',cs,'frozen_boards',frozen)) on conflict(run_id,step_code) do nothing;
 update public.automation_runs set status='succeeded',finished_at=now(),processed_count=n,success_count=n,metadata=metadata||jsonb_build_object('checksum',cs,'result',result) where id=pid;
 update public.automation_jobs set last_run_at=now(),last_status='succeeded',last_success_at=now(),last_error=null where job_code='mainline_job' and typ='production';
 if typ in ('production','production_validation') and p_payload->>'parent_pipeline_run_id' is not null then
 perform public.mainline_parent_result((p_payload->>'parent_pipeline_run_id')::uuid,jsonb_build_object('status',case when frozen>0 then 'partial' else 'succeeded' end,'business_status',case when frozen>0 then 'partial' else 'succeeded' end,'child_run_id',rid,'business_run_id',pid,'workflow_run_id',p_payload->>'workflow_run_id','business_date',d,'run_type',typ,'checkpoint_evidence',p_payload->'checkpoint_evidence','finished_at',now()));
 end if;
 return jsonb_build_object('status','succeeded','result',result,'run_id',rid,'pipeline_run_id',pid,'date',d,'checksum',cs,'boards',n,'frozen',frozen);
end $function$;

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
 on conflict(run_id) do update set status=excluded.status,provider_versions=excluded.provider_versions,error_summary=excluded.error_summary,finished_at=excluded.finished_at;
 perform public.mainline_parent_result(parent,result);
 update public.automation_jobs set last_run_at=now(),last_status=result->>'status',last_error=case when phase='failed' then p_payload->>'reason' else null end where job_code='mainline_job' and p_payload->>'run_type'='production';
 return result;
end $function$;

CREATE OR REPLACE FUNCTION public.get_mainline_status_v2_legacy()
 RETURNS jsonb
 LANGUAGE sql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public', 'mainline'
AS $function$
with latest as (
  select * from public.automation_runs where job_code='daily_research_pipeline' and coalesce(metadata->>'run_type','')<>'production_validation'
  order by started_at desc limit 1
), successful as (
  select r.* from public.automation_runs r
  where r.job_code='daily_research_pipeline' and coalesce(r.metadata->>'run_type','')<>'production_validation' and (
    r.metadata->'jobs'->'three_sector_daily_job'->>'status'='succeeded'
    or (not (r.metadata ? 'daily_pipeline_version') and r.status='succeeded')
  ) and (r.metadata ? 'successful_report' or exists (
    select 1 from public.automation_run_steps s join public.daily_report_versions v
      on v.report_date=r.run_date and v.version_number=(s.metadata->>'version_number')::integer
    where s.run_id=r.id and s.step_code='daily_report_generation' and s.status='succeeded'
      and v.generated_at between r.started_at and coalesce(r.finished_at,r.started_at)
  )) order by r.finished_at desc nulls last limit 1
), report as (
  select coalesce(r.metadata->'successful_report',(
    select to_jsonb(d)||jsonb_build_object('frozen_snapshot',v.frozen_snapshot,'generated_at',v.generated_at,'report_version',v.report_version)
    from public.daily_report_versions v join public.daily_reports d on d.id=v.report_id
    join public.automation_run_steps s on s.run_id=r.id and s.step_code='daily_report_generation'
      and s.status='succeeded' and v.version_number=(s.metadata->>'version_number')::integer
    where v.report_date=r.run_date and v.generated_at between r.started_at and r.finished_at
    order by v.generated_at desc limit 1
  )) as body from successful r
), day as (select (now() at time zone 'Asia/Shanghai')::date as business_date), calendar as (
  select case when count(*)=0 or count(distinct is_open)>1 then null else bool_and(is_open) end as is_open
  from mainline.trading_calendar c,day where c.cal_date=day.business_date and c.exchange in ('SSE','SZSE')
), good_samples as (
  select * from mainline.phase1d_sample_runs where status='SUCCESS' and not stage_frozen
  order by trade_date desc,updated_at desc limit 8
)
select (public.get_mainline_phase1d_status()-'phase'-'recent_samples') || jsonb_build_object(
  'phase',jsonb_build_object('version','V2.2','phase','Phase 1F','gate','G1','status','未通过 / pending_provider'),
  'recent_samples',coalesce((select jsonb_agg(jsonb_build_object('trade_date',trade_date,'industry_name',industry_name,'taxonomy_code',taxonomy_code,'status',status,'member_count',member_count,'valid_member_count',valid_member_count,'coverage',coverage,'sector_return',sector_return,'rs_10',rs_10,'stage_frozen',stage_frozen) order by trade_date desc) from good_samples),'[]'::jsonb),
  'daily_pipeline',jsonb_build_object(
    'timezone','Asia/Shanghai','business_date',(select business_date from day),
    'trading_calendar',jsonb_build_object('business_date',(select business_date from day),'is_open',(select is_open from calendar)),
    'latest_run_status',(select status from latest),'latest_run_date',(select run_date from latest),
    'three_sector',jsonb_build_object('latest_success_at',(select finished_at from successful),'latest_success_report',(select body from report),'latest_run_status',coalesce((select metadata->'jobs'->'three_sector_daily_job'->>'status' from latest),(select status from latest)),'latest_run_date',(select run_date from latest)),
    'mainline',jsonb_build_object('status','pending_provider','provider_enabled',false,'gate','G1_NOT_PASSED','latest_success_at',(select max(updated_at) from good_samples),'latest_success_trade_date',(select max(trade_date) from good_samples),'latest_run_status',(select metadata->'jobs'->'mainline_job'->>'status' from latest),'latest_run_date',(select run_date from latest))
  )
);
$function$;

create or replace function public.mainline_parent_result(p_parent uuid,p_result jsonb)
returns void language plpgsql set search_path='' as $$
declare jobs jsonb; next_status text;
begin
 if p_parent is null then return; end if;
 select coalesce(metadata->'jobs','{}') into jobs from public.automation_runs where id=p_parent and job_code='daily_research_pipeline' for update;
 if jobs is null then return; end if;
 jobs:=jobs||jsonb_build_object('mainline_job',coalesce(jobs->'mainline_job','{}')||p_result);
 next_status:=case when not(jobs ? 'three_sector_daily_job') or not(jobs ? 'publish_job')
 or exists(select 1 from jsonb_each(jobs) x where x.value->>'status' in ('running','dispatched')) then 'running'
 when not exists(select 1 from jsonb_each(jobs) x where x.value->>'status' not in ('succeeded','skipped')) then 'succeeded'
 when exists(select 1 from jsonb_each(jobs) x where x.value->>'status'='succeeded') then 'partial'
 when jobs->'mainline_job'->>'status'='partial' then 'partial' else 'failed' end;
 update public.automation_runs set metadata=jsonb_set(coalesce(metadata,'{}'),'{jobs}',jobs,true),status=next_status,
 finished_at=case when next_status='running' then null else now() end where id=p_parent;
 update public.automation_run_steps set status=case when p_result->>'status' in ('succeeded','partial','failed') then p_result->>'status' else 'running' end,
 metadata=coalesce(metadata,'{}')||p_result,message=p_result->>'business_status',
 finished_at=case when p_result->>'status' in ('succeeded','partial','failed') then now() else null end where run_id=p_parent and step_code='mainline_job';
end $$;
create or replace function public.mainline_pipeline_finish(p_parent uuid,p_status text,p_metadata jsonb,p_error text)
returns boolean language plpgsql set search_path='' as $$
declare old jsonb; merged jsonb;
begin
 select metadata into old from public.automation_runs where id=p_parent for update;
 merged:=coalesce(p_metadata->'jobs','{}');
 if old->'jobs'->'mainline_job'->>'business_status' in ('running','succeeded','partial','failed') then
 merged:=merged||jsonb_build_object('mainline_job',old->'jobs'->'mainline_job'); end if;
 update public.automation_runs set metadata=p_metadata||jsonb_build_object('jobs',merged),error_message=p_error where id=p_parent;
 perform public.mainline_parent_result(p_parent,merged->'mainline_job');
 return true;
end $$;
commit;

