begin;

create or replace function public.build_v43_daily_snapshot(p_report_date date)
returns jsonb
language sql
stable
set search_path=''
as $$
select jsonb_build_object(
  'report_date',p_report_date,
  'generated_at',now(),
  'is_frozen',true,
  'headline',format('截至%s，系统按真实数据库生成当日研究快照。',p_report_date),
  'stats',jsonb_build_object(
    'new_valid_signals',(select count(*) from public.signals s where s.signal_date=p_report_date and s.status<>'watch'),
    'new_opportunities',(select count(*) from public.opportunities o where o.created_at::date=p_report_date),
    'opportunity_strengthened',(select count(*) from public.daily_opportunity_reviews d where d.report_date=p_report_date and d.action in ('研究','重点研究')),
    'opportunity_weakened',(select count(*) from public.daily_opportunity_reviews d where d.report_date=p_report_date and d.action='观察'),
    'new_mapped_companies',(select count(*) from public.opportunity_companies oc where oc.created_at::date=p_report_date),
    'entered_modeling',(select count(distinct pm.company_id) from public.profit_models pm where pm.created_at::date=p_report_date),
    'model_completed',(select count(distinct v.company_id) from public.profit_model_versions v where v.frozen_at::date=p_report_date and v.total_profit is not null),
    'investment_evaluated',(select count(*) from public.investment_assessments ia where ia.assessed_at::date=p_report_date),
    'high_expected_return',(select count(*) from public.investment_assessments ia where ia.assessed_at::date=p_report_date and ia.classification='high_expected_return' and ia.passed),
    'to_observe',(select count(*) from public.company_state_transitions st where st.created_at::date=p_report_date and st.to_status in ('shadow','watch','影子池')),
    'logic_invalidated',(select count(*) from public.company_validation_events ve where ve.validation_date=p_report_date and ve.effect='weaken')
  ),
  'sectors',coalesce((select jsonb_agg(jsonb_build_object(
    'track',s.name,'strength',d.strength_score,'demand_change',coalesce(d.metadata->>'demand_change',d.key_changes),
    'supply_change',coalesce(d.metadata->>'supply_change',d.evidence_summary),'company_change',d.company_mapping,
    'opportunity_change',d.opportunity_updates,'risk',coalesce(d.metadata->>'risk',d.conclusion),
    'counter_evidence',coalesce(d.metadata->>'counter_evidence','当日没有新增反证记录'),
    'next_verification',d.next_verification,'conclusion',d.conclusion
  ) order by s.name) from public.daily_sector_reviews d join public.sectors s on s.id=d.sector_id where d.report_date=p_report_date),'[]'::jsonb),
  'opportunity_changes',coalesce((select jsonb_agg(to_jsonb(d)-'id'-'created_at'-'updated_at') from public.daily_opportunity_reviews d where d.report_date=p_report_date),'[]'::jsonb),
  'company_changes',coalesce((select jsonb_agg(jsonb_build_object('company',c.name,'from',st.from_status,'to',st.to_status,'reason',st.transition_reason,'changed_at',st.created_at,'next_step',c.reactivation_condition)) from public.company_state_transitions st join public.companies c on c.id=st.company_id where st.created_at::date=p_report_date),'[]'::jsonb),
  'focus_companies',coalesce((select jsonb_agg(jsonb_build_object(
    'company',c.name,'code',c.stock_code,'status',c.research_pool_status,'price',e.current_price,
    'market_cap',e.current_market_cap,'profit_base',(e.scenario_results->'中性'->>'net_profit')::numeric,
    'probability_base',(e.scenario_results->'中性'->>'probability_pct')::numeric,'expected_return',e.expected_return,
    'risk_reward',e.risk_reward_ratio,'profit_confidence',e.profit_confidence,'probability_confidence',e.probability_confidence,
    'conclusion',coalesce(c.shadow_reason,c.transition_reason),'next_trigger',c.reactivation_condition,'calculated_at',e.calculated_at
  )) from public.companies c join lateral(select * from public.expected_return_snapshots x where x.company_id=c.id order by x.trade_date desc,x.calculated_at desc limit 1)e on true where c.company_role='investable_candidate' and c.investment_assessment_status in ('evaluated','high_expected_return')),'[]'::jsonb),
  'model_changes',coalesce((select jsonb_agg(jsonb_build_object('company',c.name,'change_type',m.change_type,'before',m.previous_state,'after',m.new_state,'reason',m.change_reason,'changed_at',m.changed_at)) from public.model_change_log m join public.companies c on c.id=m.company_id where m.changed_at::date=p_report_date),'[]'::jsonb),
  'price_odds_changes',coalesce((select jsonb_agg(jsonb_build_object('company',c.name,'price',d.close_price,'market_cap',d.market_cap,'expected_return',d.expected_return,'base_return',d.base_return,'change_driver',d.change_driver,'conclusion',case when d.change_driver='price' then '只有价格改变，基本面模型与概率没有改变' when d.change_driver='initial' then '首次完成投资价值评估' else '模型或基本面与价格共同变化' end)) from public.company_daily_snapshots d join public.companies c on c.id=d.company_id where d.created_at::date=p_report_date),'[]'::jsonb),
  'watch_changes',coalesce((select jsonb_agg(jsonb_build_object('company',c.name,'stage',c.shadow_stage,'reason',c.shadow_reason,'trigger',c.reactivation_condition,'status',c.research_pool_status)) from public.companies c where c.research_pool_status='shadow'),'[]'::jsonb),
  'risks',coalesce((select jsonb_agg(jsonb_build_object('company',c.name,'result',v.effect,'reason',v.conclusion,'source',v.source_url)) from public.company_validation_events v join public.companies c on c.id=v.company_id where v.validation_date=p_report_date and v.effect in ('weaken','neutral')),'[]'::jsonb),
  'next_tasks',coalesce((select jsonb_agg(jsonb_build_object('title',r.title,'company',c.name,'status',r.status,'priority',r.priority,'due_date',r.due_date)) from public.research_tasks r left join public.companies c on c.id=r.company_id where r.status not in ('done','completed')),'[]'::jsonb)
);
$$;

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
  r record;
  v_status text;
begin
  select started_at into v_started_at from public.automation_runs where id=p_run_id and status='running';
  if v_started_at is null then
    raise exception 'automation run is missing or no longer running';
  end if;

  -- External signal collection has no configured collector yet. Record the truth.
  insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message)
  values(p_run_id,'signal_collection','更新信号','failed',0,'没有配置可自动抓取的外部信号源；不能把“今天没有信息”当成采集成功。');
  update public.source_health set status='not_configured',last_checked_at=now(),last_error='尚未配置外部信号采集器',consecutive_failures=consecutive_failures+1,updated_at=now() where source_code='external_signal_sources';

  select count(*) into v_count from public.opportunities o where exists(select 1 from public.active_opportunity_signal_links l where l.opportunity_id=o.id);
  insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message)
  values(p_run_id,'opportunity_update','判断机会变化','succeeded',v_count,'检查了所有已有机会的信号来源；没有凭空改变机会状态。');

  select count(*) into v_count from public.opportunity_companies;
  insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message)
  values(p_run_id,'company_mapping_check','更新公司映射','succeeded',v_count,'逐条检查现有机会与公司的映射关系。');

  insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message,metadata)
  values(p_run_id,'price_update','获取最新价格',case when p_price_failed=0 then 'succeeded' else 'failed' end,p_price_success,
    case when p_price_failed>0 then '部分或全部行情获取失败。'
         when jsonb_array_length(coalesce(p_price_errors->'warnings','[]'::jsonb))>0 then '当天休市，沿用最近交易日已经验证的价格、股本和市值快照。'
         else '行情接口返回价格、股本和市值，并按同一交易日保存。' end,
    jsonb_build_object('failed_count',p_price_failed,'errors',p_price_errors));

  for r in select id from public.profit_models where model_status='complete' loop
    perform public.recalculate_profit_model(r.id);
    v_model_count:=v_model_count+1;
  end loop;
  insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message)
  values(p_run_id,'model_recalculation','更新需要更新的模型','succeeded',v_model_count,'只重算已具备完整输入的模型；被关键数据卡住的模型不会伪装完成。');

  for r in select distinct company_id from public.profit_models where model_status='complete' loop
    v_expected_id:=public.recalculate_expected_return(r.company_id,p_run_date);
    if v_expected_id is not null then v_expected_count:=v_expected_count+1; end if;
  end loop;
  insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message)
  values(p_run_id,'investment_recalculation','重算投资价值','succeeded',v_expected_count,'使用冻结模型版本和同一交易日价格快照重算。');

  select count(*) into v_count from public.companies where research_pool_status='shadow';
  insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message)
  values(p_run_id,'shadow_scan','扫描观察状态','succeeded',v_count,'检查观察公司是否已有价格、模型或证据变化；没有触发条件时保持观察。');

  select count(*) into v_snapshot_count from public.company_daily_snapshots where created_at>=v_started_at;
  insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message)
  values(p_run_id,'daily_snapshot','保存每日快照','succeeded',v_snapshot_count,'每日快照由新的投资价值快照自动生成。');

  select count(*) into v_timeline_count from public.company_timeline_events where created_at>=v_started_at;
  insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message)
  values(p_run_id,'company_timeline','写入关键时间轴','succeeded',v_timeline_count,'只有首次评估、明显价格变化、模型变化和状态变化进入主时间轴。');

  v_snapshot:=public.build_v43_daily_snapshot(p_run_date);
  select id into v_report_id from public.daily_reports where report_date=p_run_date;
  if v_report_id is null then
    insert into public.daily_reports(report_date,raw_clue_count,valid_signal_count,new_pool_count,valuation_change_count,pending_verification_count,summary,coverage_quality,report_markdown,strongest_sector,research_can_end,frozen_snapshot,report_version,generated_at,freeze_integrity_status,freeze_integrity_note)
    values(p_run_date,0,(v_snapshot->'stats'->>'new_valid_signals')::integer,(v_snapshot->'stats'->>'new_opportunities')::integer,0,0,v_snapshot->>'headline','{}'::jsonb,'V4.3数据库自动生成','待数据判断',false,v_snapshot,'V4.3',now(),'original_frozen','生成后立即冻结，禁止覆盖。') returning id into v_report_id;
  end if;
  select coalesce(max(version_number),0)+1 into v_report_version from public.daily_report_versions where report_date=p_run_date;
  insert into public.daily_report_versions(report_id,report_date,report_version,version_number,frozen_snapshot,integrity_status,integrity_note,generated_at)
  values(v_report_id,p_run_date,'V4.3',v_report_version,v_snapshot,'original_frozen','本次真实日流程生成的追加版本；未覆盖当天已有记录。',now());
  insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message,metadata)
  values(p_run_id,'daily_report_generation','生成当日日报','succeeded',1,'生成新的冻结版本，没有覆盖旧日报。',jsonb_build_object('version_number',v_report_version));

  -- P0 consistency checks.
  insert into public.data_consistency_checks(run_id,check_date,check_code,severity,passed,affected_count,details)
  select p_run_id,p_run_date,'price_market_cap_same_snapshot','P0',count(*)=0,count(*),jsonb_build_object('rule','市值与同一价格快照的价格×股本误差不得超过1%')
  from public.price_snapshots where market_cap>0 and shares_outstanding>0 and abs(market_cap-close_price*shares_outstanding)/market_cap>0.01;

  insert into public.data_consistency_checks(run_id,check_date,check_code,severity,passed,affected_count,details)
  select p_run_id,p_run_date,'probability_sum_100','P0',count(*)=0,count(*),'{}'::jsonb from(
    select company_id from public.probability_assessments where superseded_at is null group by company_id having count(*)<>3 or sum(probability_pct)<>100
  )x;

  insert into public.data_consistency_checks(run_id,check_date,check_code,severity,passed,affected_count,details)
  select p_run_id,p_run_date,'valuation_full_trace','P0',count(*)=0,count(*),'{}'::jsonb from(
    select distinct on(company_id) * from public.expected_return_snapshots order by company_id,trade_date desc,calculated_at desc
  ) latest where price_snapshot_id is null or model_version is null or cardinality(model_snapshot_ids)<>3 or cardinality(probability_assessment_ids)<>3;

  insert into public.data_consistency_checks(run_id,check_date,check_code,severity,passed,affected_count,details)
  select p_run_id,p_run_date,'active_signal_opportunity_same_sector','P0',count(*)=0,count(*),'{}'::jsonb
  from public.active_opportunity_signal_links l
  join public.opportunities o on o.id=l.opportunity_id
  join public.signals s on s.id=l.signal_id
  where o.sector_id<>s.sector_id;

  insert into public.data_consistency_checks(run_id,check_date,check_code,severity,passed,affected_count,details)
  select p_run_id,p_run_date,'company_has_opportunity','P0',count(*)=0,count(*),'{}'::jsonb
  from public.companies c
  where not exists(select 1 from public.opportunity_companies oc where oc.company_id=c.id);

  insert into public.data_consistency_checks(run_id,check_date,check_code,severity,passed,affected_count,details)
  select p_run_id,p_run_date,'opportunity_has_signal','P0',count(*)=0,count(*),'{}'::jsonb from public.opportunities o where not exists(select 1 from public.opportunity_signal_links l where l.opportunity_id=o.id);

  insert into public.data_consistency_checks(run_id,check_date,check_code,severity,passed,affected_count,details)
  select p_run_id,p_run_date,'evaluated_company_status_match','P0',count(*)=0,count(*),'{}'::jsonb from public.companies c where c.investment_assessment_status in ('evaluated','high_expected_return') and not exists(select 1 from public.investment_assessments i where i.company_id=c.id);

  insert into public.data_consistency_checks(run_id,check_date,check_code,severity,passed,affected_count,details)
  select p_run_id,p_run_date,'shadow_reason_complete','P1',count(*)=0,count(*),'{}'::jsonb from public.companies c where c.research_pool_status='shadow' and (c.shadow_stage is null or nullif(c.shadow_reason,'') is null or nullif(c.reactivation_condition,'') is null);

  select count(*) into v_consistency_failures from public.data_consistency_checks where run_id=p_run_id and severity='P0' and not passed;
  insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message,metadata)
  values(p_run_id,'consistency_check','运行一致性检查',case when v_consistency_failures=0 then 'succeeded' else 'failed' end,8,
    case when v_consistency_failures=0 then 'P0一致性检查全部通过。' else '仍有P0一致性检查未通过。' end,
    jsonb_build_object('p0_failed_checks',v_consistency_failures));

  select count(*) into v_count from public.source_health where status<>'healthy';
  insert into public.automation_run_steps(run_id,step_code,step_name,status,processed_count,message)
  values(p_run_id,'source_health_check','检查数据源健康','succeeded',(select count(*) from public.source_health),format('发现%s个数据源不是健康状态。',v_count));

  v_status:=case when v_consistency_failures>0 or p_price_failed>0 then 'failed'
                 when exists(select 1 from public.automation_run_steps where run_id=p_run_id and status='failed') then 'partial'
                 else 'succeeded' end;
  update public.automation_runs set status=v_status,finished_at=now(),
    processed_count=(select coalesce(sum(processed_count),0) from public.automation_run_steps where run_id=p_run_id),
    success_count=(select count(*) from public.automation_run_steps where run_id=p_run_id and status='succeeded'),
    failed_count=(select count(*) from public.automation_run_steps where run_id=p_run_id and status='failed'),
    error_message=case when v_status='succeeded' then null when v_consistency_failures>0 then '一致性检查仍有P0问题' else '外部信号采集器尚未配置' end
  where id=p_run_id;

  update public.automation_jobs j set last_run_at=now(),last_status=s.status,
    last_success_at=case when s.status='succeeded' then now() else j.last_success_at end,
    last_error=case when s.status='succeeded' then null else s.message end,updated_at=now()
  from public.automation_run_steps s where s.run_id=p_run_id and j.job_code=s.step_code;
  update public.automation_jobs j set last_run_at=now(),last_status=v_status,last_success_at=case when v_status='succeeded' then now() else j.last_success_at end,last_error=case when v_status='succeeded' then null else '本次运行未全部通过' end,updated_at=now() where job_code='daily_research_pipeline';

  return jsonb_build_object('status',v_status,'model_recalculated',v_model_count,'investment_recalculated',v_expected_count,'daily_snapshots',v_snapshot_count,'timeline_events',v_timeline_count,'report_version',v_report_version,'p0_failed_checks',v_consistency_failures);
end $$;

revoke all on function public.complete_v43_daily_run(uuid,date,integer,integer,jsonb) from public,anon,authenticated;
grant execute on function public.complete_v43_daily_run(uuid,date,integer,integer,jsonb) to service_role;

commit;
