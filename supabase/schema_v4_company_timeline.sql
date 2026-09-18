begin;

alter table public.model_parameters drop constraint if exists model_parameters_data_type_check;
alter table public.model_parameters add constraint model_parameters_data_type_check
  check (data_type in ('fact','reliable_reference','external_forecast','model_inference','manual_assumption'));

create table if not exists public.company_timeline_events (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  event_at timestamptz not null,
  event_type text not null check (event_type in ('first_discovery','focus_research','formal_pool','fundamental_change','price_change','model_revision','validation','risk_deterioration','downgrade','exit','current')),
  title text not null,
  description text,
  source_id uuid references public.source_documents(id) on delete set null,
  source_url text,
  source_publish_date date,
  evidence_level text not null check (evidence_level in ('S','A','B','C','D')),
  data_type text not null check (data_type in ('fact','reliable_reference','external_forecast','model_inference','manual_assumption')),
  price numeric,
  shares_outstanding numeric,
  market_cap numeric,
  profit_bear numeric,
  profit_base numeric,
  profit_bull numeric,
  probability_bear integer,
  probability_base integer,
  probability_bull integer,
  target_market_cap_bear numeric,
  target_market_cap_base numeric,
  target_market_cap_bull numeric,
  expected_return numeric,
  annualized_expected_return numeric,
  max_downside numeric,
  risk_reward numeric,
  profit_confidence text check (profit_confidence is null or profit_confidence in ('high','medium','low')),
  probability_confidence text check (probability_confidence is null or probability_confidence in ('high','medium','low')),
  previous_state jsonb not null default '{}'::jsonb,
  current_state jsonb not null default '{}'::jsonb,
  change_driver text not null check (change_driver in ('initial','price','fundamental','model_revision','validation','risk')),
  change_reason text not null,
  system_status text not null,
  model_version integer not null default 1,
  is_key_event boolean not null default true,
  is_model_revision boolean not null default false,
  validation_status text not null default 'not_applicable',
  calculation_trace jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.company_daily_snapshots (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies(id) on delete cascade,
  expected_return_snapshot_id uuid not null references public.expected_return_snapshots(id) on delete restrict,
  trade_date date not null,
  close_price numeric not null,
  shares_outstanding numeric,
  market_cap numeric not null,
  bear_return numeric not null,
  base_return numeric not null,
  bull_return numeric not null,
  bear_probability integer not null,
  base_probability integer not null,
  bull_probability integer not null,
  expected_return numeric not null,
  annualized_expected_return numeric,
  max_downside numeric,
  risk_reward numeric,
  profit_bear numeric,
  profit_base numeric,
  profit_bull numeric,
  system_status text not null,
  model_version integer not null,
  model_fingerprint text not null,
  change_driver text not null,
  created_at timestamptz not null default now(),
  unique(company_id, trade_date, market_cap, model_fingerprint)
);

alter table public.company_timeline_events add column if not exists previous_snapshot_id uuid references public.expected_return_snapshots(id) on delete restrict;
alter table public.company_timeline_events add column if not exists current_snapshot_id uuid references public.expected_return_snapshots(id) on delete restrict;

create index if not exists company_timeline_company_date_idx on public.company_timeline_events(company_id,event_at desc);
create index if not exists company_daily_company_date_idx on public.company_daily_snapshots(company_id,trade_date desc);
create index if not exists company_timeline_source_id_idx on public.company_timeline_events(source_id);
create index if not exists company_timeline_previous_snapshot_idx on public.company_timeline_events(previous_snapshot_id);
create unique index if not exists company_timeline_current_snapshot_uidx on public.company_timeline_events(current_snapshot_id) where current_snapshot_id is not null;
create index if not exists company_daily_expected_snapshot_idx on public.company_daily_snapshots(expected_return_snapshot_id);

alter table public.company_timeline_events enable row level security;
alter table public.company_daily_snapshots enable row level security;
grant select on public.company_timeline_events, public.company_daily_snapshots to anon, authenticated;
grant select,insert,update,delete on public.company_timeline_events, public.company_daily_snapshots to service_role;

drop policy if exists anon_read_company_timeline_events on public.company_timeline_events;
create policy anon_read_company_timeline_events on public.company_timeline_events for select to anon using (true);
drop policy if exists authenticated_read_company_timeline_events on public.company_timeline_events;
create policy authenticated_read_company_timeline_events on public.company_timeline_events for select to authenticated using (true);
drop policy if exists anon_read_company_daily_snapshots on public.company_daily_snapshots;
create policy anon_read_company_daily_snapshots on public.company_daily_snapshots for select to anon using (true);
drop policy if exists authenticated_read_company_daily_snapshots on public.company_daily_snapshots;
create policy authenticated_read_company_daily_snapshots on public.company_daily_snapshots for select to authenticated using (true);

create or replace function public.capture_company_daily_snapshot()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  px public.price_snapshots%rowtype;
  s jsonb := new.scenario_results;
  v_version integer;
begin
  select * into px from public.price_snapshots
  where company_id=new.company_id and trade_date=new.trade_date
  order by captured_at desc limit 1;
  select max(model_version) into v_version from public.profit_models where company_id=new.company_id;
  insert into public.company_daily_snapshots(
    company_id,expected_return_snapshot_id,trade_date,close_price,shares_outstanding,market_cap,
    bear_return,base_return,bull_return,bear_probability,base_probability,bull_probability,
    expected_return,annualized_expected_return,max_downside,risk_reward,
    profit_bear,profit_base,profit_bull,system_status,model_version,model_fingerprint,change_driver
  ) values (
    new.company_id,new.id,new.trade_date,new.current_price,px.shares_outstanding,new.current_market_cap,
    (s->'悲观'->>'return')::numeric,(s->'中性'->>'return')::numeric,(s->'乐观'->>'return')::numeric,
    (s->'悲观'->>'probability_pct')::integer,(s->'中性'->>'probability_pct')::integer,(s->'乐观'->>'probability_pct')::integer,
    new.expected_return,new.annualized_expected_return,new.max_assumed_downside,new.risk_reward_ratio,
    (s->'悲观'->>'net_profit')::numeric,(s->'中性'->>'net_profit')::numeric,(s->'乐观'->>'net_profit')::numeric,
    new.research_status,coalesce(v_version,1),new.model_fingerprint,new.change_driver
  ) on conflict do nothing;
  return new;
end $$;

drop trigger if exists capture_company_daily_snapshot_trigger on public.expected_return_snapshots;
create trigger capture_company_daily_snapshot_trigger
after insert on public.expected_return_snapshots
for each row execute function public.capture_company_daily_snapshot();

create or replace function public.capture_key_timeline_event()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  prev public.expected_return_snapshots%rowtype;
  px public.price_snapshots%rowtype;
  s jsonb := new.scenario_results;
  v_type text;
  v_title text;
  v_key boolean := false;
  v_source jsonb := new.calculation_trace->'price_source';
begin
  select * into prev from public.expected_return_snapshots
  where company_id=new.company_id and id<>new.id
  order by trade_date desc,calculated_at desc limit 1;
  select * into px from public.price_snapshots where company_id=new.company_id and trade_date=new.trade_date order by captured_at desc limit 1;

  if new.change_driver='initial' then v_type:='formal_pool';v_title:='首次进入动态期望收益池';v_key:=true;
  elsif new.change_driver='price' and abs(coalesce(new.change_vs_previous,0))>=0.10 then v_type:='price_change';v_title:='价格驱动的赔率明显变化';v_key:=true;
  elsif new.change_driver in ('fundamental','dual') then v_type:='fundamental_change';v_title:='基本面模型或概率发生变化';v_key:=true;
  elsif new.change_driver='risk_deterioration' then v_type:='risk_deterioration';v_title:='风险恶化导致期望收益下修';v_key:=true;
  end if;
  if not v_key then return new; end if;

  insert into public.company_timeline_events(
    company_id,event_at,event_type,title,description,source_url,source_publish_date,evidence_level,data_type,
    price,shares_outstanding,market_cap,profit_bear,profit_base,profit_bull,
    probability_bear,probability_base,probability_bull,target_market_cap_bear,target_market_cap_base,target_market_cap_bull,
    expected_return,annualized_expected_return,max_downside,risk_reward,profit_confidence,probability_confidence,
    previous_snapshot_id,current_snapshot_id,previous_state,current_state,change_driver,change_reason,system_status,model_version,calculation_trace
  ) values (
    new.company_id,new.calculated_at,v_type,v_title,new.change_reason,v_source->>'url',new.trade_date,
    case when new.profit_confidence='high' and new.probability_confidence='high' then 'B' else 'C' end,'model_inference',
    new.current_price,px.shares_outstanding,new.current_market_cap,
    (s->'悲观'->>'net_profit')::numeric,(s->'中性'->>'net_profit')::numeric,(s->'乐观'->>'net_profit')::numeric,
    (s->'悲观'->>'probability_pct')::integer,(s->'中性'->>'probability_pct')::integer,(s->'乐观'->>'probability_pct')::integer,
    (s->'悲观'->>'target_market_cap')::numeric,(s->'中性'->>'target_market_cap')::numeric,(s->'乐观'->>'target_market_cap')::numeric,
    new.expected_return,new.annualized_expected_return,new.max_assumed_downside,new.risk_reward_ratio,new.profit_confidence,new.probability_confidence,
    prev.id,new.id,
    case when prev.id is null then '{}'::jsonb else jsonb_build_object('price',prev.current_price,'market_cap',prev.current_market_cap,'probabilities',prev.scenario_results,'expected_return',prev.expected_return,'status',prev.research_status) end,
    jsonb_build_object('price',new.current_price,'market_cap',new.current_market_cap,'probabilities',new.scenario_results,'expected_return',new.expected_return,'status',new.research_status),
    case when new.change_driver='dual' then 'fundamental' else new.change_driver end,new.change_reason,new.research_status,
    coalesce((select max(model_version) from public.profit_models where company_id=new.company_id),1),new.calculation_trace
  ) on conflict (current_snapshot_id) where current_snapshot_id is not null do nothing;
  return new;
end $$;

drop trigger if exists capture_key_timeline_event_trigger on public.expected_return_snapshots;
create trigger capture_key_timeline_event_trigger
after insert on public.expected_return_snapshots
for each row execute function public.capture_key_timeline_event();

commit;
