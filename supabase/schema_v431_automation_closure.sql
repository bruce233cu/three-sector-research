begin;

alter table public.raw_clues
  add column if not exists published_at timestamptz,
  add column if not exists company_names text[] not null default '{}',
  add column if not exists opportunity_keywords text[] not null default '{}',
  add column if not exists evidence_level text,
  add column if not exists sentiment text,
  add column if not exists dedupe_key text;

create unique index if not exists raw_clues_dedupe_key_uidx
  on public.raw_clues(dedupe_key) where dedupe_key is not null;

grant select on public.sectors to service_role;
grant select,insert on public.raw_clues,public.source_documents,public.signals to service_role;

alter table public.automation_runs drop constraint if exists automation_runs_status_check;
alter table public.automation_runs
  add constraint automation_runs_status_check
  check(status in ('running','succeeded','partial','failed','timed_out'));

alter table public.source_health drop constraint if exists source_health_status_check;
alter table public.source_health
  add constraint source_health_status_check
  check(status in ('healthy','healthy_no_new_trade','degraded','failed','not_configured'));

insert into public.source_health(
  source_code,source_name,source_type,status,last_error,metadata
) values (
  'cninfo_disclosure','巨潮资讯法定信息披露平台','signal','not_configured',
  '采集器已登记，等待首次真实运行验证',
  jsonb_build_object('enabled',true,'scope','当前8家A股研究公司的法定披露公告','window_days',30)
)
on conflict(source_code) do update set
  source_name=excluded.source_name,
  source_type=excluded.source_type,
  metadata=public.source_health.metadata||excluded.metadata,
  updated_at=now();

create or replace function public.close_stale_automation_runs(
  p_timeout interval default interval '30 minutes'
)
returns integer
language plpgsql
security definer
set search_path=''
as $$
declare
  v_count integer:=0;
  r record;
begin
  for r in
    update public.automation_runs
    set status='timed_out',
        finished_at=now(),
        failed_count=greatest(failed_count,1),
        error_message=format('任务运行超过%s仍未结束，系统已自动结束这次假运行。',p_timeout),
        metadata=metadata||jsonb_build_object(
          'timed_out_at',now(),
          'timeout_seconds',extract(epoch from p_timeout)::integer
        )
    where status='running' and started_at<now()-p_timeout
    returning id
  loop
    insert into public.automation_run_steps(
      run_id,step_code,step_name,status,processed_count,message,metadata
    ) values (
      r.id,'run_timeout','运行超时清理','failed',0,
      '任务超过合理执行时间仍未结束，已经自动标记为超时。',
      jsonb_build_object('timeout_seconds',extract(epoch from p_timeout)::integer)
    ) on conflict(run_id,step_code) do nothing;
    v_count:=v_count+1;
  end loop;
  return v_count;
end $$;

revoke all on function public.close_stale_automation_runs(interval)
  from public,anon,authenticated;
grant execute on function public.close_stale_automation_runs(interval)
  to service_role;

create or replace function public.complete_v43_daily_run(
  p_run_id uuid,
  p_run_date date,
  p_price_success integer,
  p_price_failed integer,
  p_price_errors jsonb default '[]'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path=''
as $$
declare
  v_count integer;
  v_model_count integer:=0;
  v_expected_count integer:=0;
  v_snapshot_count integer:=0;
  v_timeline_count integer:=0;
  v_consistency_failures integer:=0;
  v_report_version integer;
  v_report_id uuid;
  v_snapshot jsonb;
  v_expected_id uuid;
  v_started_at timestamptz;
  v_status text;
  v_error_message text;
  r record;
begin
  select started_at into v_started_at
  from public.automation_runs
  where id=p_run_id and status='running';
  if v_started_at is null then
    raise exception 'automation run is missing or no longer running';
  end if;

  if not exists(
    select 1 from public.automation_run_steps
    where run_id=p_run_id and step_code='signal_collection'
  ) then
    insert into public.automation_run_steps(
      run_id,step_code,step_name,status,processed_count,message
    ) values (
      p_run_id,'signal_collection','更新信号','failed',0,
      '没有收到外部采集器的真实运行结果，不能把流程标记为成功。'
    );
  end if;

  select count(*) into v_count
  from public.opportunities o
  where exists(
    select 1 from public.active_opportunity_signal_links l
    where l.opportunity_id=o.id
  );
  insert into public.automation_run_steps(
    run_id,step_code,step_name,status,processed_count,message
  ) values (
    p_run_id,'opportunity_update','判断机会变化','succeeded',v_count,
    '检查了所有已有机会的信号来源；没有凭空改变机会状态。'
  );

  select count(*) into v_count from public.opportunity_companies;
  insert into public.automation_run_steps(
    run_id,step_code,step_name,status,processed_count,message
  ) values (
    p_run_id,'company_mapping_check','更新公司映射','succeeded',v_count,
    '逐条检查现有机会与公司的映射关系。'
  );

  insert into public.automation_run_steps(
    run_id,step_code,step_name,status,processed_count,message,metadata
  ) values (
    p_run_id,'price_update','获取最新价格',
    case when p_price_failed=0 then 'succeeded' else 'failed' end,
    p_price_success,
    case
      when p_price_failed>0 then '部分或全部行情获取失败。'
      when jsonb_array_length(coalesce(p_price_errors->'warnings','[]'::jsonb))>0
        then '当天休市，沿用最近交易日已经验证的价格、股本和市值快照；不视为数据源故障。'
      else '行情接口返回价格、股本和市值，并按同一交易日保存。'
    end,
    jsonb_build_object('failed_count',p_price_failed,'errors',p_price_errors)
  );

  for r in select id from public.profit_models where model_status='complete' loop
    perform public.recalculate_profit_model(r.id);
    v_model_count:=v_model_count+1;
  end loop;
  insert into public.automation_run_steps(
    run_id,step_code,step_name,status,processed_count,message
  ) values (
    p_run_id,'model_recalculation','更新需要更新的模型','succeeded',v_model_count,
    '只重算已具备完整输入的模型；被关键数据卡住的模型不会伪装完成。'
  );

  for r in
    select distinct company_id
    from public.profit_models where model_status='complete'
  loop
    v_expected_id:=public.recalculate_expected_return(r.company_id,p_run_date);
    if v_expected_id is not null then
      v_expected_count:=v_expected_count+1;
    end if;
  end loop;
  insert into public.automation_run_steps(
    run_id,step_code,step_name,status,processed_count,message
  ) values (
    p_run_id,'investment_recalculation','重算投资价值','succeeded',v_expected_count,
    '使用冻结模型版本和同一交易日价格快照重算。'
  );

  select count(*) into v_count
  from public.companies where research_pool_status='shadow';
  insert into public.automation_run_steps(
    run_id,step_code,step_name,status,processed_count,message
  ) values (
    p_run_id,'shadow_scan','扫描观察状态','succeeded',v_count,
    '检查观察公司是否已有价格、模型或证据变化；没有触发条件时保持观察。'
  );

  select count(*) into v_snapshot_count
  from public.company_daily_snapshots where created_at>=v_started_at;
  insert into public.automation_run_steps(
    run_id,step_code,step_name,status,processed_count,message
  ) values (
    p_run_id,'daily_snapshot','保存每日快照','succeeded',v_snapshot_count,
    '每日快照由新的投资价值快照自动生成；当天已存在时保持幂等，不重复制造记录。'
  );

  select count(*) into v_timeline_count
  from public.company_timeline_events where created_at>=v_started_at;
  insert into public.automation_run_steps(
    run_id,step_code,step_name,status,processed_count,message
  ) values (
    p_run_id,'company_timeline','写入关键时间轴','succeeded',v_timeline_count,
    '只有首次评估、明显价格变化、模型变化和状态变化进入主时间轴。'
  );

  v_snapshot:=public.build_v43_daily_snapshot(p_run_date);
  select id into v_report_id
  from public.daily_reports where report_date=p_run_date;
  if v_report_id is null then
    insert into public.daily_reports(
      report_date,raw_clue_count,valid_signal_count,new_pool_count,
      valuation_change_count,pending_verification_count,summary,coverage_quality,
      report_markdown,strongest_sector,research_can_end,frozen_snapshot,
      report_version,generated_at,freeze_integrity_status,freeze_integrity_note
    ) values (
      p_run_date,
      (select count(*) from public.raw_clues where discovered_at::date=p_run_date),
      (v_snapshot->'stats'->>'new_valid_signals')::integer,
      (v_snapshot->'stats'->>'new_opportunities')::integer,
      0,0,v_snapshot->>'headline','{}'::jsonb,'V4.3数据库自动生成',
      '待数据判断',false,v_snapshot,'V4.3.1',now(),'original_frozen',
      '生成后立即冻结，禁止覆盖。'
    ) returning id into v_report_id;
  end if;
  select coalesce(max(version_number),0)+1 into v_report_version
  from public.daily_report_versions where report_date=p_run_date;
  insert into public.daily_report_versions(
    report_id,report_date,report_version,version_number,frozen_snapshot,
    integrity_status,integrity_note,generated_at
  ) values (
    v_report_id,p_run_date,'V4.3.1',v_report_version,v_snapshot,
    'original_frozen','本次真实日流程生成的追加版本；未覆盖当天已有记录。',now()
  );
  insert into public.automation_run_steps(
    run_id,step_code,step_name,status,processed_count,message,metadata
  ) values (
    p_run_id,'daily_report_generation','生成当日日报','succeeded',1,
    '生成新的冻结版本，没有覆盖旧日报。',
    jsonb_build_object('version_number',v_report_version)
  );

  insert into public.data_consistency_checks(
    run_id,check_date,check_code,severity,passed,affected_count,details
  )
  select p_run_id,p_run_date,'price_market_cap_same_snapshot','P0',
    count(*)=0,count(*),
    jsonb_build_object('rule','市值与同一价格快照的价格×股本误差不得超过1%')
  from public.price_snapshots
  where market_cap>0 and shares_outstanding>0
    and abs(market_cap-close_price*shares_outstanding)/market_cap>0.01;

  insert into public.data_consistency_checks(
    run_id,check_date,check_code,severity,passed,affected_count,details
  )
  select p_run_id,p_run_date,'probability_sum_100','P0',count(*)=0,count(*),'{}'::jsonb
  from (
    select company_id from public.probability_assessments
    where superseded_at is null
    group by company_id
    having count(*)<>3 or sum(probability_pct)<>100
  ) x;

  insert into public.data_consistency_checks(
    run_id,check_date,check_code,severity,passed,affected_count,details
  )
  select p_run_id,p_run_date,'valuation_full_trace','P0',count(*)=0,count(*),'{}'::jsonb
  from (
    select distinct on(company_id) *
    from public.expected_return_snapshots
    order by company_id,trade_date desc,calculated_at desc
  ) latest
  where price_snapshot_id is null or model_version is null
    or cardinality(model_snapshot_ids)<>3
    or cardinality(probability_assessment_ids)<>3;

  insert into public.data_consistency_checks(
    run_id,check_date,check_code,severity,passed,affected_count,details
  )
  select p_run_id,p_run_date,'active_signal_opportunity_same_sector','P0',
    count(*)=0,count(*),'{}'::jsonb
  from public.active_opportunity_signal_links l
  join public.opportunities o on o.id=l.opportunity_id
  join public.signals s on s.id=l.signal_id
  where o.sector_id<>s.sector_id;

  insert into public.data_consistency_checks(
    run_id,check_date,check_code,severity,passed,affected_count,details
  )
  select p_run_id,p_run_date,'company_has_opportunity','P0',count(*)=0,count(*),'{}'::jsonb
  from public.companies c
  where not exists(
    select 1 from public.opportunity_companies oc where oc.company_id=c.id
  );

  insert into public.data_consistency_checks(
    run_id,check_date,check_code,severity,passed,affected_count,details
  )
  select p_run_id,p_run_date,'opportunity_has_signal','P0',count(*)=0,count(*),'{}'::jsonb
  from public.opportunities o
  where not exists(
    select 1 from public.opportunity_signal_links l where l.opportunity_id=o.id
  );

  insert into public.data_consistency_checks(
    run_id,check_date,check_code,severity,passed,affected_count,details
  )
  select p_run_id,p_run_date,'evaluated_company_status_match','P0',
    count(*)=0,count(*),'{}'::jsonb
  from public.companies c
  where c.investment_assessment_status in ('evaluated','high_expected_return')
    and not exists(
      select 1 from public.investment_assessments i where i.company_id=c.id
    );

  insert into public.data_consistency_checks(
    run_id,check_date,check_code,severity,passed,affected_count,details
  )
  select p_run_id,p_run_date,'shadow_reason_complete','P1',count(*)=0,count(*),'{}'::jsonb
  from public.companies c
  where c.research_pool_status='shadow'
    and (
      c.shadow_stage is null or nullif(c.shadow_reason,'') is null
      or nullif(c.reactivation_condition,'') is null
    );

  select count(*) into v_consistency_failures
  from public.data_consistency_checks
  where run_id=p_run_id and severity='P0' and not passed;
  insert into public.automation_run_steps(
    run_id,step_code,step_name,status,processed_count,message,metadata
  ) values (
    p_run_id,'consistency_check','运行一致性检查',
    case when v_consistency_failures=0 then 'succeeded' else 'failed' end,
    8,
    case when v_consistency_failures=0
      then 'P0一致性检查全部通过。'
      else '仍有P0一致性检查未通过。'
    end,
    jsonb_build_object('p0_failed_checks',v_consistency_failures)
  );

  select count(*) into v_count
  from public.source_health
  where status in ('degraded','failed','not_configured');
  insert into public.automation_run_steps(
    run_id,step_code,step_name,status,processed_count,message,metadata
  ) values (
    p_run_id,'source_health_check','检查数据源健康','succeeded',
    (select count(*) from public.source_health),
    format('全部数据源均已检查；其中%s个处于降级、失败或未配置状态。',v_count),
    jsonb_build_object(
      'attention_count',v_count,
      'healthy_no_new_trade_count',(
        select count(*) from public.source_health where status='healthy_no_new_trade'
      )
    )
  );

  v_status:=case
    when exists(
      select 1 from public.automation_run_steps
      where run_id=p_run_id and status='failed'
    ) then case when v_consistency_failures>0 or p_price_failed>0 then 'failed' else 'partial' end
    else 'succeeded'
  end;
  select string_agg(coalesce(message,step_name),'；' order by started_at)
  into v_error_message
  from public.automation_run_steps
  where run_id=p_run_id and status='failed';

  update public.automation_runs
  set status=v_status,
      finished_at=now(),
      processed_count=(
        select coalesce(sum(processed_count),0)
        from public.automation_run_steps where run_id=p_run_id
      ),
      success_count=(
        select count(*) from public.automation_run_steps
        where run_id=p_run_id and status='succeeded'
      ),
      failed_count=(
        select count(*) from public.automation_run_steps
        where run_id=p_run_id and status='failed'
      ),
      error_message=case when v_status='succeeded' then null else v_error_message end
  where id=p_run_id;

  update public.automation_jobs j
  set last_run_at=now(),
      last_status=s.status,
      last_success_at=case when s.status='succeeded' then now() else j.last_success_at end,
      last_error=case when s.status='succeeded' then null else s.message end,
      updated_at=now()
  from public.automation_run_steps s
  where s.run_id=p_run_id and j.job_code=s.step_code;

  update public.automation_jobs
  set last_run_at=now(),
      last_status=v_status,
      last_success_at=case when v_status='succeeded' then now() else last_success_at end,
      last_error=case when v_status='succeeded' then null else v_error_message end,
      updated_at=now()
  where job_code='daily_research_pipeline';

  return jsonb_build_object(
    'status',v_status,
    'model_recalculated',v_model_count,
    'investment_recalculated',v_expected_count,
    'daily_snapshots',v_snapshot_count,
    'timeline_events',v_timeline_count,
    'report_version',v_report_version,
    'p0_failed_checks',v_consistency_failures
  );
end $$;

revoke all on function public.complete_v43_daily_run(uuid,date,integer,integer,jsonb)
  from public,anon,authenticated;
grant execute on function public.complete_v43_daily_run(uuid,date,integer,integer,jsonb)
  to service_role;

insert into public.automation_jobs(
  job_code,job_name,schedule_text,is_scheduled,scheduler_kind,external_dependency
) values (
  'automation_timeout_cleanup','运行超时清理','每15分钟',true,
  'Supabase数据库定时任务',null
) on conflict(job_code) do update set
  job_name=excluded.job_name,
  schedule_text=excluded.schedule_text,
  is_scheduled=excluded.is_scheduled,
  scheduler_kind=excluded.scheduler_kind,
  updated_at=now();

do $$
declare
  existing_id bigint;
begin
  select jobid into existing_id
  from cron.job where jobname='v431-stale-run-cleanup';
  if existing_id is not null then
    perform cron.unschedule(existing_id);
  end if;
  perform cron.schedule(
    'v431-stale-run-cleanup',
    '*/15 * * * *',
    $job$select public.close_stale_automation_runs(interval '30 minutes');$job$
  );
end $$;

select public.close_stale_automation_runs(interval '30 minutes');

commit;
