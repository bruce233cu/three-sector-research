begin;

alter table public.profit_models
  add column if not exists model_type text,
  add column if not exists model_version integer not null default 1,
  add column if not exists target_date date,
  add column if not exists profit_confidence text,
  add column if not exists core_unconfirmed_variables jsonb not null default '[]'::jsonb,
  add column if not exists max_uncertainty text,
  add column if not exists most_needed_evidence text,
  add column if not exists calculation_trace jsonb not null default '{}'::jsonb,
  add column if not exists updated_at timestamptz not null default now();

alter table public.profit_models drop constraint if exists profit_models_model_type_check;
alter table public.profit_models add constraint profit_models_model_type_check
  check (model_type is null or model_type in ('component','material','equipment','finished_product','service','project','ai_capex','custom'));
alter table public.profit_models drop constraint if exists profit_models_profit_confidence_check;
alter table public.profit_models add constraint profit_models_profit_confidence_check
  check (profit_confidence is null or profit_confidence in ('high','medium','low'));

create table if not exists public.model_parameters (
  id uuid primary key default gen_random_uuid(),
  profit_model_id uuid not null references public.profit_models(id) on delete cascade,
  parameter_key text not null,
  parameter_name text not null,
  parameter_value numeric,
  normalized_value numeric,
  unit text,
  data_type text not null,
  source_name text,
  source_url text,
  source_published_at date,
  entered_at timestamptz not null default now(),
  evidence_grade text not null,
  is_confirmed boolean not null default false,
  is_inferred boolean not null default false,
  is_manual_assumption boolean not null default false,
  derivation_logic text,
  source_document_id uuid references public.source_documents(id) on delete set null,
  notes text,
  updated_at timestamptz not null default now(),
  unique (profit_model_id, parameter_key),
  check (data_type in ('fact','external_forecast','model_inference','manual_assumption')),
  check (evidence_grade in ('S','A','B','C','D')),
  check (not is_manual_assumption or data_type = 'manual_assumption'),
  check (not is_inferred or data_type = 'model_inference')
);

create table if not exists public.probability_assessments (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  profit_model_id uuid references public.profit_models(id) on delete set null,
  scenario text not null,
  target_event text not null,
  probability_pct integer not null,
  probability_confidence text not null,
  rule_score numeric,
  mapped_probability_pct integer,
  historical_calibration_pct numeric,
  evidence_basis jsonb not null default '[]'::jsonb,
  rationale text not null,
  assessment_version integer not null default 1,
  effective_at timestamptz not null default now(),
  superseded_at timestamptz,
  created_at timestamptz not null default now(),
  check (scenario in ('悲观','中性','乐观')),
  check (probability_pct in (10,20,30,40,50,60,70,80,90,95)),
  check (mapped_probability_pct is null or mapped_probability_pct in (10,20,30,40,50,60,70,80,90,95)),
  check (probability_confidence in ('high','medium','low')),
  unique (company_id, scenario, assessment_version)
);

create table if not exists public.probability_changes (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  scenario text not null,
  previous_probability_pct integer,
  new_probability_pct integer not null,
  trigger_evidence jsonb not null default '{}'::jsonb,
  reason text not null,
  adjustment_type text not null,
  changed_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  check (scenario in ('悲观','中性','乐观')),
  check (adjustment_type in ('system_rule','manual_review')),
  check (previous_probability_pct is null or previous_probability_pct in (10,20,30,40,50,60,70,80,90,95)),
  check (new_probability_pct in (10,20,30,40,50,60,70,80,90,95))
);

create table if not exists public.price_snapshots (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  trade_date date not null,
  close_price numeric not null,
  shares_outstanding numeric,
  market_cap numeric not null,
  source_name text not null,
  source_url text,
  source_published_at date,
  evidence_grade text not null default 'B',
  captured_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  unique (company_id, trade_date, source_name),
  check (close_price > 0 and market_cap > 0),
  check (evidence_grade in ('S','A','B','C','D'))
);

create table if not exists public.expected_return_snapshots (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  trade_date date not null,
  current_price numeric not null,
  current_market_cap numeric not null,
  target_date date not null,
  scenario_results jsonb not null,
  expected_return numeric not null,
  max_assumed_downside numeric,
  risk_reward_ratio numeric,
  years_to_target numeric,
  annualized_expected_return numeric,
  profit_confidence text,
  probability_confidence text,
  research_status text not null,
  change_vs_previous numeric,
  change_driver text not null,
  change_reason text not null,
  model_fingerprint text not null,
  calculation_trace jsonb not null,
  calculated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  check (profit_confidence is null or profit_confidence in ('high','medium','low')),
  check (probability_confidence is null or probability_confidence in ('high','medium','low')),
  check (change_driver in ('initial','price','fundamental','dual','risk_deterioration')),
  unique (company_id, trade_date, current_market_cap, model_fingerprint)
);

create table if not exists public.sensitivity_results (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  profit_model_id uuid references public.profit_models(id) on delete cascade,
  parameter_key text not null,
  base_value numeric,
  shocked_value numeric,
  shock_pct numeric,
  resulting_net_profit numeric,
  resulting_target_market_cap numeric,
  resulting_expected_return numeric,
  impact_rank integer,
  risk_note text,
  calculated_at timestamptz not null default now()
);

create table if not exists public.prediction_validations (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  entry_snapshot_id uuid not null references public.expected_return_snapshots(id) on delete restrict,
  first_qualified_at date not null,
  entry_price numeric not null,
  entry_market_cap numeric not null,
  entry_expected_return numeric not null,
  entry_profit_forecast jsonb not null,
  entry_probabilities jsonb not null,
  entry_thesis text not null,
  price_30d numeric,
  price_90d numeric,
  price_180d numeric,
  price_1y numeric,
  max_gain numeric,
  max_drawdown numeric,
  profit_realized boolean,
  assumptions_realized jsonb not null default '{}'::jsonb,
  final_result text,
  error_reason text,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique (company_id, entry_snapshot_id),
  check (final_result is null or final_result in ('correct','incorrect','pending'))
);

create table if not exists public.model_change_log (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  profit_model_id uuid references public.profit_models(id) on delete set null,
  change_type text not null,
  previous_state jsonb,
  new_state jsonb not null,
  change_reason text not null,
  evidence_ids jsonb not null default '[]'::jsonb,
  changed_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

create index if not exists model_parameters_profit_model_idx on public.model_parameters(profit_model_id);
create index if not exists probability_assessments_company_active_idx on public.probability_assessments(company_id, scenario, effective_at desc) where superseded_at is null;
create index if not exists probability_changes_company_idx on public.probability_changes(company_id, changed_at desc);
create index if not exists price_snapshots_company_date_idx on public.price_snapshots(company_id, trade_date desc);
create index if not exists expected_return_company_date_idx on public.expected_return_snapshots(company_id, trade_date desc, calculated_at desc);
create index if not exists sensitivity_company_idx on public.sensitivity_results(company_id, calculated_at desc);
create index if not exists prediction_validation_company_idx on public.prediction_validations(company_id, first_qualified_at desc);
create index if not exists model_change_log_company_idx on public.model_change_log(company_id, changed_at desc);

alter table public.model_parameters enable row level security;
alter table public.probability_assessments enable row level security;
alter table public.probability_changes enable row level security;
alter table public.price_snapshots enable row level security;
alter table public.expected_return_snapshots enable row level security;
alter table public.sensitivity_results enable row level security;
alter table public.prediction_validations enable row level security;
alter table public.model_change_log enable row level security;

revoke all on table public.model_parameters, public.probability_assessments, public.probability_changes,
  public.price_snapshots, public.expected_return_snapshots, public.sensitivity_results,
  public.prediction_validations, public.model_change_log from anon, authenticated;
grant select on table public.model_parameters, public.probability_assessments, public.probability_changes,
  public.price_snapshots, public.expected_return_snapshots, public.sensitivity_results,
  public.prediction_validations, public.model_change_log to anon, authenticated;
grant insert, update, delete on table public.model_parameters, public.probability_assessments, public.probability_changes,
  public.price_snapshots, public.expected_return_snapshots, public.sensitivity_results,
  public.prediction_validations, public.model_change_log to authenticated;

do $$
declare t text;
begin
  foreach t in array array['model_parameters','probability_assessments','probability_changes','price_snapshots','expected_return_snapshots','sensitivity_results','prediction_validations','model_change_log']
  loop
    if not exists (select 1 from pg_policies where schemaname='public' and tablename=t and policyname='public_read_'||t) then
      execute format('create policy %I on public.%I for select to anon, authenticated using (true)', 'public_read_'||t, t);
    end if;
    if not exists (select 1 from pg_policies where schemaname='public' and tablename=t and policyname='authenticated_insert_'||t) then
      execute format('create policy %I on public.%I for insert to authenticated with check ((select auth.uid()) is not null)', 'authenticated_insert_'||t, t);
    end if;
    if not exists (select 1 from pg_policies where schemaname='public' and tablename=t and policyname='authenticated_update_'||t) then
      execute format('create policy %I on public.%I for update to authenticated using ((select auth.uid()) is not null) with check ((select auth.uid()) is not null)', 'authenticated_update_'||t, t);
    end if;
    if not exists (select 1 from pg_policies where schemaname='public' and tablename=t and policyname='authenticated_delete_'||t) then
      execute format('create policy %I on public.%I for delete to authenticated using ((select auth.uid()) is not null)', 'authenticated_delete_'||t, t);
    end if;
  end loop;
end $$;

create or replace function public.recalculate_profit_model(p_profit_model_id uuid)
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $$
declare
  m public.profit_models%rowtype;
  v_revenue numeric;
  v_gross_margin numeric;
  v_selling numeric;
  v_admin numeric;
  v_rnd numeric;
  v_finance numeric;
  v_expense numeric;
  v_tax numeric;
  v_legacy numeric;
  v_incremental numeric;
  v_total numeric;
  v_target numeric;
  v_upside numeric;
  v_missing jsonb := '[]'::jsonb;
  v_trace jsonb;
  p jsonb;
begin
  select * into m from public.profit_models where id=p_profit_model_id for update;
  if not found then raise exception 'profit model not found'; end if;
  select coalesce(jsonb_object_agg(parameter_key, coalesce(normalized_value, parameter_value)), '{}'::jsonb)
    into p from public.model_parameters where profit_model_id=p_profit_model_id;

  if m.model_type='component' then
    if nullif(p->>'company_sales_volume','') is not null and nullif(p->>'asp','') is not null then
      v_revenue := (p->>'company_sales_volume')::numeric * (p->>'asp')::numeric / 100000000;
    elsif nullif(p->>'downstream_volume','') is not null and nullif(p->>'per_unit_quantity','') is not null and nullif(p->>'company_share','') is not null and nullif(p->>'asp','') is not null then
      v_revenue := (p->>'downstream_volume')::numeric * (p->>'per_unit_quantity')::numeric * (p->>'company_share')::numeric * (p->>'asp')::numeric / 100000000;
    else
      if nullif(p->>'company_sales_volume','') is null and not (nullif(p->>'downstream_volume','') is not null and nullif(p->>'per_unit_quantity','') is not null and nullif(p->>'company_share','') is not null) then
        v_missing := v_missing || '["销量/下游销量链"]'::jsonb;
      end if;
      if nullif(p->>'asp','') is null then v_missing := v_missing || '["ASP"]'::jsonb; end if;
    end if;
  elsif m.model_type='material' then
    if p ? 'downstream_demand' and p ? 'unit_consumption' and p ? 'company_share' and p ? 'asp' then
      v_revenue := (p->>'downstream_demand')::numeric * (p->>'unit_consumption')::numeric * (p->>'company_share')::numeric * (p->>'asp')::numeric / 100000000;
    else v_missing := v_missing || '["下游需求量","单位耗用量","公司份额","ASP"]'::jsonb; end if;
  elsif m.model_type='equipment' then
    if p ? 'added_capacity' and p ? 'equipment_value_per_capacity' and p ? 'company_share' then
      v_revenue := (p->>'added_capacity')::numeric * (p->>'equipment_value_per_capacity')::numeric * (p->>'company_share')::numeric / 100000000;
    else v_missing := v_missing || '["新增产能","单位产能设备价值","公司份额"]'::jsonb; end if;
  elsif m.model_type='finished_product' then
    if p ? 'own_volume' and p ? 'asp' then v_revenue := (p->>'own_volume')::numeric*(p->>'asp')::numeric/100000000;
    else v_missing := v_missing || '["自身销量","ASP"]'::jsonb; end if;
  elsif m.model_type='service' then
    if p ? 'service_count' and p ? 'revenue_per_service' then v_revenue := (p->>'service_count')::numeric*(p->>'revenue_per_service')::numeric/100000000;
    else v_missing := v_missing || '["服务次数","单次服务收入"]'::jsonb; end if;
  elsif m.model_type='project' then
    if p ? 'project_count' and p ? 'project_value' and p ? 'company_share' and p ? 'recognition_ratio' then
      v_revenue := (p->>'project_count')::numeric*(p->>'project_value')::numeric*(p->>'company_share')::numeric*(p->>'recognition_ratio')::numeric/100000000;
    else v_missing := v_missing || '["项目数量","单项目价值","公司份额","确认比例"]'::jsonb; end if;
  elsif m.model_type='ai_capex' then
    if p ? 'downstream_capex' and p ? 'segment_value_share' and p ? 'company_share' then
      v_revenue := (p->>'downstream_capex')::numeric*(p->>'segment_value_share')::numeric*(p->>'company_share')::numeric;
    else v_missing := v_missing || '["下游Capex","环节价值占比","公司份额"]'::jsonb; end if;
  else
    if p ? 'revenue' then v_revenue := (p->>'revenue')::numeric; else v_missing := v_missing || '["收入"]'::jsonb; end if;
  end if;

  v_gross_margin := nullif(p->>'gross_margin','')::numeric;
  v_selling := coalesce(nullif(p->>'selling_expense_ratio','')::numeric,0);
  v_admin := coalesce(nullif(p->>'admin_expense_ratio','')::numeric,0);
  v_rnd := coalesce(nullif(p->>'rnd_expense_ratio','')::numeric,0);
  v_finance := coalesce(nullif(p->>'finance_expense_ratio','')::numeric,0);
  v_expense := nullif(p->>'expense_ratio','')::numeric;
  if v_expense is null and (p ? 'selling_expense_ratio' or p ? 'admin_expense_ratio' or p ? 'rnd_expense_ratio' or p ? 'finance_expense_ratio') then
    v_expense := v_selling+v_admin+v_rnd+v_finance;
  end if;
  v_tax := nullif(p->>'tax_rate','')::numeric;
  v_legacy := nullif(p->>'legacy_profit','')::numeric;
  if v_gross_margin is null then v_missing := v_missing || '["毛利率"]'::jsonb; end if;
  if v_expense is null then v_missing := v_missing || '["费用率"]'::jsonb; end if;
  if v_tax is null then v_missing := v_missing || '["税率"]'::jsonb; end if;
  if v_legacy is null then v_missing := v_missing || '["传统业务利润"]'::jsonb; end if;
  if m.pe_multiple is null and nullif(p->>'valuation_multiple','') is null then v_missing := v_missing || '["估值倍数"]'::jsonb; end if;

  if v_revenue is not null and v_gross_margin is not null and v_expense is not null and v_tax is not null then
    v_incremental := (v_revenue*v_gross_margin-v_revenue*v_expense)*(1-v_tax);
  end if;
  if v_incremental is not null and v_legacy is not null then v_total:=v_incremental+v_legacy; end if;
  if v_total is not null and coalesce(m.pe_multiple,nullif(p->>'valuation_multiple','')::numeric) is not null then
    v_target:=v_total*coalesce(m.pe_multiple,(p->>'valuation_multiple')::numeric);
  end if;
  if v_target is not null and m.reference_market_cap>0 then v_upside:=v_target/m.reference_market_cap-1; end if;

  v_trace:=jsonb_build_object('model_type',m.model_type,'formula','收入→毛利润→费用→税→增量归母净利润→传统业务利润→总归母净利润','parameters',p,'intermediate',jsonb_build_object('revenue',v_revenue,'gross_profit',case when v_revenue is null or v_gross_margin is null then null else v_revenue*v_gross_margin end,'expense',case when v_revenue is null or v_expense is null then null else v_revenue*v_expense end,'incremental_net_profit',v_incremental),'result',jsonb_build_object('total_profit',v_total,'target_market_cap',v_target,'upside',v_upside));

  update public.profit_models set revenue=v_revenue, net_profit=v_incremental, gross_margin=v_gross_margin,
    expense_ratio=v_expense, tax_rate=v_tax, legacy_profit=v_legacy, total_profit=v_total,
    target_market_cap=v_target, upside=v_upside, missing_inputs=(select coalesce(jsonb_agg(distinct x),'[]'::jsonb) from jsonb_array_elements(v_missing) x),
    model_status=case when jsonb_array_length(v_missing)=0 then 'complete' else 'blocked' end,
    status=case when jsonb_array_length(v_missing)=0 then '可用于决策' else '待关键数据' end,
    calculation_trace=v_trace, updated_at=now()
  where id=p_profit_model_id;
  return v_trace || jsonb_build_object('missing_inputs',v_missing);
end $$;

create or replace function public.recalculate_expected_return(p_company_id uuid, p_trade_date date default current_date)
returns uuid
language plpgsql
security invoker
set search_path = ''
as $$
declare
  px public.price_snapshots%rowtype;
  v_models jsonb;
  v_probs jsonb;
  v_results jsonb := '{}'::jsonb;
  v_expected numeric := 0;
  v_downside numeric;
  v_target_date date;
  v_years numeric;
  v_annualized numeric;
  v_rr numeric;
  v_fingerprint text;
  v_prev public.expected_return_snapshots%rowtype;
  v_driver text := 'initial';
  v_reason text := '首次生成可用快照';
  v_change numeric;
  v_profit_conf text;
  v_prob_conf text;
  r record;
  v_id uuid;
begin
  select * into px from public.price_snapshots where company_id=p_company_id and trade_date<=p_trade_date order by trade_date desc,captured_at desc limit 1;
  if not found then return null; end if;

  select jsonb_agg(to_jsonb(x) order by case x.scenario when '悲观' then 1 when '中性' then 2 else 3 end), max(target_date), min(profit_confidence)
    into v_models,v_target_date,v_profit_conf
  from (select distinct on (scenario) id,scenario,total_profit,pe_multiple,target_market_cap,target_date,profit_confidence,model_version,updated_at
        from public.profit_models where company_id=p_company_id and model_status='complete' and scenario in ('悲观','中性','乐观')
        order by scenario,model_date desc,model_version desc,updated_at desc) x;
  if v_models is null or jsonb_array_length(v_models)<>3 then return null; end if;

  select jsonb_agg(to_jsonb(x) order by case x.scenario when '悲观' then 1 when '中性' then 2 else 3 end), min(probability_confidence)
    into v_probs,v_prob_conf
  from (select distinct on (scenario) scenario,probability_pct,probability_confidence,assessment_version,effective_at
        from public.probability_assessments where company_id=p_company_id and superseded_at is null and scenario in ('悲观','中性','乐观')
        order by scenario,effective_at desc) x;
  if v_probs is null or jsonb_array_length(v_probs)<>3 or (select sum((z->>'probability_pct')::numeric) from jsonb_array_elements(v_probs) z)<>100 then return null; end if;

  for r in
    select m->>'scenario' scenario,(m->>'total_profit')::numeric total_profit,(m->>'pe_multiple')::numeric pe_multiple,
      (m->>'target_market_cap')::numeric target_market_cap,(p->>'probability_pct')::numeric probability_pct
    from jsonb_array_elements(v_models) m join jsonb_array_elements(v_probs) p on p->>'scenario'=m->>'scenario'
  loop
    v_results:=v_results||jsonb_build_object(r.scenario,jsonb_build_object('net_profit',r.total_profit,'valuation_method','PE','valuation_multiple',r.pe_multiple,'target_market_cap',r.target_market_cap,'return',r.target_market_cap/px.market_cap-1,'probability_pct',r.probability_pct));
    v_expected:=v_expected+(r.target_market_cap/px.market_cap-1)*(r.probability_pct/100);
    v_downside:=least(coalesce(v_downside,0),r.target_market_cap/px.market_cap-1);
  end loop;

  v_target_date:=coalesce(v_target_date,make_date(extract(year from p_trade_date)::int+3,12,31));
  v_years:=greatest((v_target_date-p_trade_date)/365.25,1.0/365.25);
  if 1+v_expected>0 then v_annualized:=power(1+v_expected,1/v_years)-1; end if;
  if v_downside<0 then v_rr:=v_expected/abs(v_downside); end if;
  v_fingerprint:=encode(extensions.digest((v_models::text||v_probs::text),'sha256'),'hex');

  select * into v_prev from public.expected_return_snapshots where company_id=p_company_id order by trade_date desc,calculated_at desc limit 1;
  if found then
    v_change:=v_expected-v_prev.expected_return;
    if v_prev.model_fingerprint=v_fingerprint and v_prev.current_market_cap<>px.market_cap then v_driver:='price';v_reason:=format('基本面模型与概率未变，市值由%s亿元变为%s亿元',v_prev.current_market_cap,px.market_cap);
    elsif v_prev.model_fingerprint<>v_fingerprint and v_prev.current_market_cap=px.market_cap then v_driver:='fundamental';v_reason:='利润模型、估值或情景概率发生变化，价格未变';
    elsif v_prev.model_fingerprint<>v_fingerprint then v_driver:='dual';v_reason:='基本面模型或概率与价格同时变化';
    else v_reason:='输入未发生实质变化'; end if;
    if v_driver in ('fundamental','dual') and v_change<0 then v_driver:='risk_deterioration';v_reason:='基本面模型或概率下修后，期望收益下降'; end if;
  end if;

  insert into public.expected_return_snapshots(company_id,trade_date,current_price,current_market_cap,target_date,scenario_results,expected_return,max_assumed_downside,risk_reward_ratio,years_to_target,annualized_expected_return,profit_confidence,probability_confidence,research_status,change_vs_previous,change_driver,change_reason,model_fingerprint,calculation_trace)
  values(p_company_id,px.trade_date,px.close_price,px.market_cap,v_target_date,v_results,v_expected,v_downside,v_rr,v_years,v_annualized,v_profit_conf,v_prob_conf,
    case when v_profit_conf='high' and v_prob_conf='high' and v_expected>=1 then '高期望收益候选' when v_expected>=0.5 then '进入重点研究价格区间' when v_expected>0 then '继续验证' else '赔率不足' end,
    v_change,v_driver,v_reason,v_fingerprint,jsonb_build_object('formula','Σ(情景收益率×情景概率)','price_source',jsonb_build_object('name',px.source_name,'url',px.source_url,'date',px.trade_date),'models',v_models,'probabilities',v_probs,'scenario_results',v_results,'expected_return',v_expected,'annualized_formula','(1+期望收益)^(1/年数)-1'))
  on conflict (company_id,trade_date,current_market_cap,model_fingerprint) do nothing returning id into v_id;
  if v_id is null then select id into v_id from public.expected_return_snapshots where company_id=p_company_id and trade_date=px.trade_date and current_market_cap=px.market_cap and model_fingerprint=v_fingerprint limit 1; end if;
  return v_id;
end $$;

revoke all on function public.recalculate_profit_model(uuid) from public, anon;
revoke all on function public.recalculate_expected_return(uuid,date) from public, anon;
grant execute on function public.recalculate_profit_model(uuid) to authenticated, service_role;
grant execute on function public.recalculate_expected_return(uuid,date) to authenticated, service_role;

create or replace view public.latest_expected_returns with (security_invoker=true) as
select distinct on (e.company_id) e.*,c.name as company_name,c.stock_code,c.external_code
from public.expected_return_snapshots e join public.companies c on c.id=e.company_id
order by e.company_id,e.trade_date desc,e.calculated_at desc;
grant select on public.latest_expected_returns to anon,authenticated;

create or replace view public.reverse_valuation_requirements with (security_invoker=true) as
select p.company_id,c.name as company_name,p.trade_date,p.market_cap as current_market_cap,t.target_multiple,v.pe_multiple,
  p.market_cap*t.target_multiple as target_market_cap,(p.market_cap*t.target_multiple)/v.pe_multiple as required_net_profit
from (select distinct on (company_id) company_id,trade_date,market_cap from public.price_snapshots order by company_id,trade_date desc,captured_at desc) p
join public.companies c on c.id=p.company_id
cross join (values (1.5::numeric),(2::numeric),(3::numeric)) t(target_multiple)
cross join (values (25::numeric),(30::numeric),(35::numeric),(40::numeric)) v(pe_multiple);
grant select on public.reverse_valuation_requirements to anon,authenticated;

commit;
