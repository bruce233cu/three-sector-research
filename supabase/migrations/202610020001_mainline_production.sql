begin;
-- Only board-level state/evidence are long-lived; no individual price tables.
create table if not exists mainline.daily_checkpoints (
  trade_date date not null,object_id text not null,taxonomy_version text not null,
  rule_version text not null,profile_id text not null,run_id uuid not null references mainline.run_manifests,
  checkpoint jsonb not null,state_payload jsonb not null,business_checksum text not null,
  primary key(trade_date,object_id,taxonomy_version,rule_version,profile_id)
);
create table if not exists mainline.rule_evidence (
  trade_date date not null,object_id text not null,rule_version text not null,
  profile_id text not null,rule_id text not null,run_id uuid not null references mainline.run_manifests,
  actual_value jsonb,threshold jsonb,operator text,passed boolean,availability text not null,reason text,
  primary key(trade_date,object_id,rule_version,profile_id,rule_id)
);
alter table mainline.mainline_lifecycles add column if not exists lifecycle_payload jsonb;
alter table mainline.mainline_lifecycles add column if not exists last_state_date date;
alter table mainline.daily_checkpoints enable row level security;
alter table mainline.rule_evidence enable row level security;
grant all on mainline.daily_checkpoints,mainline.rule_evidence to service_role;
insert into public.automation_jobs(job_code,job_name,is_scheduled,scheduler_kind,schedule_text)
values('mainline_job','A股主线每日任务',false,'现有17:00 Daily Pipeline独立业务任务','待G4通过后启用：每天17:00 Asia/Shanghai')
on conflict(job_code) do nothing;

create or replace function public.mainline_production_context(p_date date)
returns jsonb language sql stable security invoker set search_path='' as $$
select jsonb_build_object(
 'calendar',(select jsonb_agg(cal_date order by cal_date) from mainline.trading_calendar where exchange='SSE' and is_open),
 'is_open',(select is_open from mainline.trading_calendar where exchange='SSE' and cal_date=p_date),
 'latest_success',(select max(as_of_date) from mainline.run_manifests where job_name='mainline_job' and status='success' and provider_versions->>'run_type'='production'),
 'checkpoints',(select jsonb_agg(to_jsonb(c)) from mainline.daily_checkpoints c where trade_date=(select max(trade_date) from mainline.daily_checkpoints where trade_date<p_date and profile_id='industry_trend_v221_state_completion_v1')),
 'enabled',(select is_scheduled from public.automation_jobs where job_code='mainline_job'));
$$;
revoke all on function public.mainline_production_context(date) from public,anon,authenticated;
grant execute on function public.mainline_production_context(date) to service_role;

create or replace function public.mainline_commit_day(p_payload jsonb)
returns jsonb language plpgsql security invoker set search_path='' as $$
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
 if typ not in ('production','production_simulation','backfill') then raise exception 'invalid run_type'; end if;
 if not exists(select 1 from mainline.trading_calendar where exchange='SSE' and cal_date=d and is_open) then raise exception 'not a verified market day'; end if;
 if prof<>'industry_trend_v221_state_completion_v1' or rv<>'mainline_v2.2.1_state_completion_v1' then raise exception 'unapproved profile'; end if;
 perform pg_advisory_xact_lock(hashtextextended('mainline:'||d||prof,0));
 n:=jsonb_array_length(p_payload->'rows');
 if n<10 then raise exception 'incomplete daily panel'; end if;
 if n<>(select count(distinct x->'snapshot'->>'object_id') from jsonb_array_elements(p_payload->'rows') x) then raise exception 'duplicate object'; end if;
 select min(business_checksum) into existing from mainline.daily_checkpoints where trade_date=d and profile_id=prof and rule_version=rv;
 if existing is not null and existing<>cs then raise exception 'conflicting committed input requires separate versioned backfill'; end if;
 if existing is not null then result:='idempotent'; end if;
 insert into public.automation_runs(id,job_code,run_date,trigger_type,status,metadata)
 values(pid,'mainline_job',d,'manual','running',jsonb_build_object('run_type',typ,'run_id',rid,'code_sha',p_payload->>'code_sha','rule_version',rv,'parameter_profile',prof))
 on conflict(id) do nothing;
 insert into mainline.run_manifests(run_id,job_name,as_of_date,code_commit,rule_version,profile_id,parameter_hash,status,provider_versions,row_counts,error_summary)
 values(rid,'mainline_job',d,p_payload->>'code_sha',rv,prof,p_payload->>'parameter_hash','running',
 jsonb_build_object('run_type',typ,'pipeline_run_id',pid,'profile_reuse_explicit',true),jsonb_build_object('boards',n),jsonb_build_object('checksum',cs,'result',result))
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
   values((lc->>'lifecycle_id')::uuid,lc->>'object_id',lc->>'object_type',prof,(lc->>'candidate_at')::date,(lc->>'confirmed_at')::date,(lc->>'weakened_at')::date,(lc->>'closed_at')::date,lc->>'close_reason',(lc->>'prior_lifecycle_id')::uuid,lc,(lc->>'last_transition_date')::date)
   on conflict(lifecycle_id) do nothing;
  end loop;
  for row in select * from jsonb_array_elements(p_payload->'rows') loop
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
 insert into mainline.data_quality_daily(as_of_date,dataset_code,run_id,expected_count,actual_count,missing_count,duplicate_count,completeness_ratio,schema_valid,critical_data_ok,stage_frozen,freeze_reason,warnings)
 values(d,'daily_board_state',rid,n,n,0,0,1,true,frozen=0,frozen>0,case when frozen>0 then array['board_rule_or_input_frozen'] else array[]::text[] end,jsonb_build_array(jsonb_build_object('frozen_boards',frozen))) on conflict do nothing;
 update mainline.run_manifests set status='success',critical_data_ok=frozen=0,stage_frozen=frozen>0,finished_at=now(),row_counts=row_counts||jsonb_build_object('frozen',frozen),source_snapshot_ids=ARRAY(select (x->>'source_snapshot_id')::uuid from jsonb_array_elements(p_payload->'sources') x) where run_id=rid;
 insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message,metadata)
 values(pid,'mainline_atomic_commit','板块状态、规则和质量原子保存','succeeded',n,result,jsonb_build_object('checksum',cs,'frozen_boards',frozen)) on conflict(run_id,step_code) do nothing;
 update public.automation_runs set status='succeeded',finished_at=now(),processed_count=n,success_count=n,metadata=metadata||jsonb_build_object('checksum',cs,'result',result) where id=pid;
 update public.automation_jobs set last_run_at=now(),last_status='succeeded',last_success_at=now(),last_error=null where job_code='mainline_job' and typ='production';
 return jsonb_build_object('status','succeeded','result',result,'run_id',rid,'pipeline_run_id',pid,'date',d,'checksum',cs,'boards',n,'frozen',frozen);
end $$;
revoke all on function public.mainline_commit_day(jsonb) from public,anon,authenticated;
grant execute on function public.mainline_commit_day(jsonb) to service_role;

create or replace function public.mainline_live_read(p_kind text default 'summary',p_object text default null,p_date date default null)
returns jsonb language plpgsql stable security invoker set search_path='' as $$
declare d date; prod date; sim date; rows jsonb; attempt jsonb; kind text;
begin
 select max(as_of_date) into prod from mainline.run_manifests where job_name='mainline_job' and status='success' and provider_versions->>'run_type'='production';
 select max(as_of_date) into sim from mainline.run_manifests where job_name='mainline_job' and status='success' and provider_versions->>'run_type'='production_simulation';
 d:=coalesce(p_date,prod,sim);kind:=case when prod is not null then 'production' else 'production_simulation' end;
 select to_jsonb(r) into attempt from mainline.run_manifests r where job_name='mainline_job' order by started_at desc limit 1;
 if p_kind='timeline' then
  select jsonb_agg(jsonb_build_object('date',c.trade_date,'state',c.state_payload,'metrics',s.decision_reason->'snapshot') order by c.trade_date)
  into rows from mainline.daily_checkpoints c join mainline.daily_mainline_snapshot s on s.as_of_date=c.trade_date and s.object_id=c.object_id and s.rule_version=c.rule_version and s.profile_id=c.profile_id
  where c.object_id=p_object and c.trade_date<=d;
 else
  select jsonb_agg(s.decision_reason order by case s.hard_status when 'S2' then 0 when 'S1' then 1 when 'S3' then 2 when 'S4' then 3 else 4 end,s.rs_10_pct nulls last,s.object_id)
  into rows from mainline.daily_mainline_snapshot s where s.as_of_date=d and s.profile_id='industry_trend_v221_state_completion_v1' and (p_object is null or s.object_id=p_object);
 end if;
 return jsonb_build_object('data_date',d,'latest_success_date',prod,'latest_simulation_date',sim,'display_run_type',kind,'latest_attempt',attempt,'rows',coalesce(rows,'[]'::jsonb),'production_enabled',(select is_scheduled from public.automation_jobs where job_code='mainline_job'),'rule_version','mainline_v2.2.1_state_completion_v1','profile_id','industry_trend_v221_state_completion_v1');
end $$;
revoke all on function public.mainline_live_read(text,text,date) from public,anon,authenticated;
grant execute on function public.mainline_live_read(text,text,date) to service_role;
commit;
