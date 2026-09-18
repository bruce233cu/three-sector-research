begin;

create or replace function public.evaluate_v4_investment_snapshot()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  t public.investment_thresholds%rowtype;
  c public.companies%rowtype;
  v_base numeric := (new.scenario_results->'中性'->>'return')::numeric;
  v_profit_rank integer := case new.profit_confidence when 'high' then 3 when 'medium' then 2 else 1 end;
  v_prob_rank integer := case new.probability_confidence when 'high' then 3 when 'medium' then 2 else 1 end;
  v_min_profit_rank integer;
  v_min_prob_rank integer;
  v_pass boolean;
  v_class text;
  v_failures text[];
  v_old_pool text;
begin
  select * into t from public.investment_thresholds where is_active=true and effective_from<=new.calculated_at order by effective_from desc limit 1;
  if not found then return new; end if;
  select * into c from public.companies where id=new.company_id;
  if c.company_role is distinct from 'investable_candidate' then return new; end if;

  v_min_profit_rank:=case t.min_profit_confidence when 'high' then 3 when 'medium' then 2 else 1 end;
  v_min_prob_rank:=case t.min_probability_confidence when 'high' then 3 when 'medium' then 2 else 1 end;
  v_pass:=new.expected_return>=t.min_expected_return
    and coalesce(new.annualized_expected_return,-999)>=t.min_annualized_return
    and coalesce(new.risk_reward_ratio,-999)>=t.min_risk_reward
    and coalesce(v_base,-999)>=t.min_base_return
    and v_profit_rank>=v_min_profit_rank and v_prob_rank>=v_min_prob_rank;
  v_class:=case when v_pass then 'high_expected_return' else 'shadow' end;
  v_failures:=array_remove(array[
    case when new.expected_return<t.min_expected_return then '期望收益低于当前门槛' end,
    case when coalesce(new.annualized_expected_return,-999)<t.min_annualized_return then '年化期望收益低于当前门槛' end,
    case when coalesce(new.risk_reward_ratio,-999)<t.min_risk_reward then '风险收益比低于当前门槛' end,
    case when coalesce(v_base,-999)<t.min_base_return then '中性情景收益低于当前门槛' end,
    case when v_profit_rank<v_min_profit_rank then '利润可信度不足' end,
    case when v_prob_rank<v_min_prob_rank then '概率可信度不足' end
  ]::text[],null);

  insert into public.investment_assessments(company_id,expected_return_snapshot_id,threshold_id,expected_return,annualized_expected_return,base_return,max_downside,risk_reward,profit_confidence,probability_confidence,passed,classification,failure_reasons,check_results)
  values(new.company_id,new.id,t.id,new.expected_return,new.annualized_expected_return,v_base,new.max_assumed_downside,new.risk_reward_ratio,new.profit_confidence,new.probability_confidence,v_pass,v_class,v_failures,
    jsonb_build_object('rule_code',t.rule_code,'rule_is_provisional',t.is_provisional,'expected_return_pass',new.expected_return>=t.min_expected_return,'annualized_return_pass',coalesce(new.annualized_expected_return,-999)>=t.min_annualized_return,'risk_reward_pass',coalesce(new.risk_reward_ratio,-999)>=t.min_risk_reward,'base_return_pass',coalesce(v_base,-999)>=t.min_base_return,'profit_confidence_pass',v_profit_rank>=v_min_profit_rank,'probability_confidence_pass',v_prob_rank>=v_min_prob_rank))
  on conflict(expected_return_snapshot_id,threshold_id) do nothing;

  v_old_pool:=c.research_pool_status;
  update public.companies set
    research_pool_status=case when v_pass then 'research' else 'shadow' end,
    investment_assessment_status=case when v_pass then 'high_expected_return' else 'evaluated' end,
    status=case when v_pass then '高期望收益' else '影子池' end,
    shadow_reason=case when v_pass then null else array_to_string(v_failures,'；') end,
    transition_reason=case when v_pass then '完成投资价值评估并通过当前配置门槛' else '完成投资价值评估，但未通过当前配置门槛' end,
    reactivation_condition=case when v_pass then '持续验证核心假设；任一门槛跌破则降级' else '价格、利润模型或证据变化后重新运行投资价值评估' end,
    last_transition_at=case when v_old_pool is distinct from (case when v_pass then 'research' else 'shadow' end) then now() else last_transition_at end,
    updated_at=now()
  where id=new.company_id;

  if v_old_pool is distinct from (case when v_pass then 'research' else 'shadow' end) then
    insert into public.company_state_transitions(company_id,from_status,to_status,transition_type,transition_reason,model_version,metadata)
    values(new.company_id,v_old_pool,case when v_pass then 'high_expected_return' else 'shadow' end,
      case when v_pass then 'high_expected_return_upgrade' else 'shadow_downgrade' end,
      case when v_pass then '新的投资价值快照通过当前配置门槛' else array_to_string(v_failures,'；') end,
      coalesce((select max(model_version) from public.profit_models where company_id=new.company_id),1),
      jsonb_build_object('expected_return_snapshot_id',new.id,'threshold_id',t.id,'classification',v_class));
  end if;
  return new;
end $$;

revoke all on function public.evaluate_v4_investment_snapshot() from public,anon,authenticated;
grant execute on function public.evaluate_v4_investment_snapshot() to service_role;
drop trigger if exists evaluate_v4_investment_snapshot_trigger on public.expected_return_snapshots;
create trigger evaluate_v4_investment_snapshot_trigger after insert on public.expected_return_snapshots for each row execute function public.evaluate_v4_investment_snapshot();

commit;
