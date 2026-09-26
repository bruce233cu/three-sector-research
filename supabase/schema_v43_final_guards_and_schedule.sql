begin;

alter table public.expected_return_snapshots
  add column if not exists trace_integrity_status text,
  add column if not exists trace_integrity_note text;

alter table public.expected_return_snapshots drop constraint if exists expected_return_price_trace_required;
alter table public.expected_return_snapshots drop constraint if exists expected_return_model_trace_required;
alter table public.expected_return_snapshots disable trigger expected_returns_immutable;
update public.expected_return_snapshots
set trace_integrity_status=case when price_snapshot_id is not null and model_version is not null and cardinality(model_snapshot_ids)=3 and cardinality(probability_assessment_ids)=3 then 'complete' else 'historical_incomplete' end,
    trace_integrity_note=case when price_snapshot_id is not null and model_version is not null and cardinality(model_snapshot_ids)=3 and cardinality(probability_assessment_ids)=3 then '价格、模型版本和概率记录均可追溯。' else '旧快照生成时没有保存完整模型或概率引用；保留原值，但不得用于历史盲测。' end;
alter table public.expected_return_snapshots enable trigger expected_returns_immutable;
alter table public.expected_return_snapshots
  add constraint expected_return_price_trace_required check(price_snapshot_id is not null) not valid,
  add constraint expected_return_model_trace_required check(model_version is not null and cardinality(model_snapshot_ids)=3 and cardinality(probability_assessment_ids)=3) not valid;

drop trigger if exists daily_reports_immutable on public.daily_reports;
create trigger daily_reports_immutable before update or delete on public.daily_reports for each row execute function public.reject_history_mutation();

create or replace function public.capture_unlogged_company_state_change()
returns trigger
language plpgsql
set search_path=''
as $$
begin
  if row(old.company_role,old.research_pool_status,old.valuation_status,old.investment_assessment_status,old.status)
     is distinct from row(new.company_role,new.research_pool_status,new.valuation_status,new.investment_assessment_status,new.status)
     and coalesce(new.transition_reason,'') not like '完成投资价值评估%'
  then
    insert into public.company_state_transitions(company_id,from_status,to_status,transition_type,transition_reason,model_version,metadata)
    values(new.id,coalesce(old.research_pool_status,old.status),coalesce(new.research_pool_status,new.status),'manual_correction',
      coalesce(nullif(new.transition_reason,''),'公司状态字段发生变化'),
      coalesce((select max(model_version) from public.profit_models where company_id=new.id),1),
      jsonb_build_object('before',jsonb_build_object('role',old.company_role,'pool',old.research_pool_status,'valuation',old.valuation_status,'assessment',old.investment_assessment_status,'display',old.status),'after',jsonb_build_object('role',new.company_role,'pool',new.research_pool_status,'valuation',new.valuation_status,'assessment',new.investment_assessment_status,'display',new.status)));
  end if;
  return new;
end $$;

drop trigger if exists capture_unlogged_company_state_change_trigger on public.companies;
create trigger capture_unlogged_company_state_change_trigger after update on public.companies for each row execute function public.capture_unlogged_company_state_change();

update public.companies set status='产业验证对象',
  transition_reason=case name
    when 'Oracle' then '海外公司，仅用于验证AI资本开支、数据中心建设和融资约束，不进入A股赔率计算'
    when '东方空间' then '未上市火箭公司，用于验证商业航天制造和发射进度，不进入股票赔率计算'
    when '东风汽车集团' then '作为机器人客户验证需求，不直接作为机器人零部件投资标的'
    when '星际荣耀' then '未上市火箭公司，用于验证可重复使用火箭进展，不进入股票赔率计算'
    else transition_reason end,
  reactivation_condition=coalesce(reactivation_condition,case when stock_code is null then '上市或出现明确可投资供应链映射后重新评估' else '若系统开放对应市场直接投资，再重新评估投资角色' end),
  updated_at=now()
where company_role='industry_validator' and status<>'产业验证对象';

-- A real database scheduler calls the protected Edge Function every day at
-- 00:00 UTC, which is 08:00 China Standard Time.
do $$
declare existing_id bigint;
begin
  select jobid into existing_id from cron.job where jobname='v43-daily-research-pipeline';
  if existing_id is not null then perform cron.unschedule(existing_id); end if;
  perform cron.schedule(
    'v43-daily-research-pipeline',
    '0 0 * * *',
    $job$
      select net.http_post(
        url:='https://pdtlzleqsoftuxdnbdey.supabase.co/functions/v1/v43-daily-pipeline',
        headers:=jsonb_build_object(
          'Content-Type','application/json',
          'Authorization','Bearer '||(select decrypted_secret from vault.decrypted_secrets where name='v43_edge_anon_key' order by created_at desc limit 1)
        ),
        body:=jsonb_build_object('run_date',current_date,'trigger_type','scheduled')
      );
    $job$
  );
end $$;

update public.automation_jobs set is_scheduled=true,scheduler_kind='Supabase数据库定时任务',updated_at=now()
where job_code='daily_research_pipeline';
update public.automation_jobs set is_scheduled=true,scheduler_kind='由每日完整研究流程调用',updated_at=now()
where job_code in ('signal_collection','opportunity_update','company_mapping_check','price_update','model_recalculation','investment_recalculation','shadow_scan','daily_report_generation','consistency_check','source_health_check');
update public.automation_jobs set is_scheduled=true,scheduler_kind='数据库触发器',updated_at=now()
where job_code in ('daily_snapshot','company_timeline');

commit;
