-- V4.2: persist the evidence lineage from signals to opportunities.
create table if not exists public.opportunity_signal_links (
  id uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references public.opportunities(id) on delete cascade,
  signal_id uuid not null references public.signals(id) on delete cascade,
  relation_reason text not null,
  relation_type text not null default 'formation_evidence',
  linked_at timestamptz not null default now(),
  unique(opportunity_id,signal_id)
);
create index if not exists opportunity_signal_links_signal_idx
  on public.opportunity_signal_links(signal_id);
alter table public.opportunity_signal_links enable row level security;
drop policy if exists "opportunity_signal_links_anon_read" on public.opportunity_signal_links;
create policy "opportunity_signal_links_anon_read" on public.opportunity_signal_links
  for select to anon using (true);
drop policy if exists "opportunity_signal_links_authenticated_all" on public.opportunity_signal_links;
create policy "opportunity_signal_links_authenticated_all" on public.opportunity_signal_links
  for all to authenticated using (true) with check (true);
grant select on public.opportunity_signal_links to anon;
grant select,insert,update,delete on public.opportunity_signal_links to authenticated;

insert into public.opportunity_signal_links
  (opportunity_id,signal_id,relation_reason,relation_type)
select o.id,s.id,
  case
    when o.external_id='ROB-KELI-001' then '公司级力学传感器订单与客户验证信号'
    when o.external_id='OPP-ROB-BAOLONG-001' then '保隆编码器与视觉传感器定点/量产信号'
    when o.external_id='OPP-SPACE-MFG-001' then '星箭制造扩产与工厂建设信号'
    when o.external_id='OPP-SPACE-ROCKET-001' then '液体火箭首飞、试车与复用验证信号'
    when o.external_id='OPP-AI-POWER-001' then 'AI数据中心电力订单、CAPEX与约束反证'
    else '人形机器人订单、交付与工业验证信号'
  end,
  case when s.action in ('入池','重点研究') then 'formation_evidence' else 'supporting_evidence' end
from public.opportunities o
join public.signals s on
  (o.external_id='ROB-KELI-001' and s.company_name ilike '%柯力%')
  or (o.external_id='OPP-ROB-BAOLONG-001' and s.company_name ilike '%保隆%')
  or (o.external_id='OPP-SPACE-MFG-001' and (s.external_id ilike '%MFG%' or s.title ilike '%工厂%' or s.title ilike '%制造%'))
  or (o.external_id='OPP-SPACE-ROCKET-001' and s.sector_id=o.sector_id and (s.external_id ilike '%RKT%' or s.title ilike '%火箭%' or s.signal_type ilike '%首飞%'))
  or (o.external_id='OPP-AI-POWER-001' and s.sector_id=o.sector_id and (s.external_id ilike '%POWER%' or s.title ilike '%数据中心%' or s.title ilike '%AIDC%' or s.title ilike '%电力%'))
  or (o.external_id='OPP-ROB-001' and s.sector_id=o.sector_id and coalesce(s.company_name,'') not ilike '%柯力%' and coalesce(s.company_name,'') not ilike '%保隆%' and (s.title ilike '%人形%' or s.title ilike '%机器人%' or s.title ilike '%Galbot%' or s.company_name ilike '%优必选%' or s.company_name ilike '%银河%'))
on conflict(opportunity_id,signal_id) do update set
  relation_reason=excluded.relation_reason,
  relation_type=excluded.relation_type;
