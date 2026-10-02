do $audit$
declare p jsonb; out jsonb; before_state text; after_state text; before_count bigint; after_count bigint; idem boolean:=false; conflict_ok boolean:=false; fault_ok boolean:=false;
begin
 select md5(string_agg(to_jsonb(c)::text,'' order by trade_date,object_id)) into before_state from mainline.daily_checkpoints c;
 select count(*) into before_count from mainline.mainline_lifecycles;
 select jsonb_build_object('trade_date','2026-09-30','profile_id','industry_trend_v221_state_completion_v1','rule_version','mainline_v2.2.1_state_completion_v1',
 'parameter_hash','85c701a313b6a59529e7b8a7ea52af64d2e708011f56abf5d82d74580fd2384f',
 'run_type','backfill','code_sha','33e615c39fec195a170b4dbfb932095c47de4824','run_id',gen_random_uuid(),'pipeline_run_id',gen_random_uuid(),
 'checksum',(select min(business_checksum) from mainline.daily_checkpoints where trade_date='2026-09-30' and profile_id='industry_trend_v221_state_completion_v1'),
 'rows',jsonb_agg(decision_reason order by object_id),'sources','[]'::jsonb,'lifecycle_ancestry','[]'::jsonb)
 into p from mainline.daily_mainline_snapshot where as_of_date='2026-09-30' and profile_id='industry_trend_v221_state_completion_v1';
 begin
  out:=public.mainline_commit_day(p);
  idem:=out->>'result'='idempotent';
  raise exception using errcode='Z0001',message='acceptance rollback';
 exception when sqlstate 'Z0001' then null; end;
 begin
  perform public.mainline_commit_day(p||jsonb_build_object('checksum','conflicting_acceptance_checksum'));
 exception when others then
  if sqlerrm like '%conflicting committed input%' then conflict_ok:=true; else raise; end if;
 end;
 begin
  perform public.mainline_commit_day(p||jsonb_build_object('fault_stage','db_write'));
 exception when others then
  if sqlerrm like '%acceptance_injected_db_rollback%' then fault_ok:=true; else raise; end if;
 end;
 select md5(string_agg(to_jsonb(c)::text,'' order by trade_date,object_id)) into after_state from mainline.daily_checkpoints c;
 select count(*) into after_count from mainline.mainline_lifecycles;
 if not(idem and conflict_ok and fault_ok and before_state=after_state and before_count=after_count) then raise exception 'G4 backfill acceptance failed'; end if;
 perform set_config('mainline.g4_acceptance',jsonb_build_object('existing_day_idempotent',idem,'conflicting_backfill_rejected',conflict_ok,'db_write_fault_rolled_back',fault_ok,'checkpoint_payload_unchanged',before_state=after_state,'lifecycle_count_unchanged',before_count=after_count,'lifecycle_count',before_count,'no_persistent_test_writes',true)::text,false);
end $audit$;
select current_setting('mainline.g4_acceptance')::jsonb as acceptance;
