-- V4.2 latest daily report: keep focus companies and counter-evidence complete
-- even when no same-day price snapshot was produced.
with latest as (
  select max(report_date) report_date from public.daily_reports
),
focus as (
  select jsonb_agg(jsonb_build_object(
    'company', c.name,
    'code', c.stock_code,
    'status', c.research_pool_status,
    'price', cds.close_price,
    'market_cap', coalesce(cds.market_cap,c.market_cap),
    'profit_base', cds.profit_base,
    'probability_base', cds.base_probability,
    'expected_return', ia.expected_return,
    'risk_reward', ia.risk_reward,
    'profit_confidence', ia.profit_confidence,
    'probability_confidence', ia.probability_confidence,
    'today_change', dor.evidence_for,
    'conclusion', coalesce(c.shadow_reason,c.transition_reason,dor.action),
    'next_trigger', coalesce(c.reactivation_condition,dor.next_verification)
  ) order by case when dor.action='重点研究' then 0 when c.research_pool_status='shadow' then 1 else 2 end) payload
  from public.daily_opportunity_reviews dor
  join latest l on l.report_date=dor.report_date
  join public.companies c on c.name=dor.company_name
  left join lateral (
    select * from public.company_daily_snapshots x
    where x.company_id=c.id and x.trade_date<=dor.report_date
    order by x.trade_date desc limit 1
  ) cds on true
  left join lateral (
    select * from public.investment_assessments x
    where x.company_id=c.id and x.assessed_at::date<=dor.report_date
    order by x.assessed_at desc limit 1
  ) ia on true
  where dor.action in ('重点研究','研究','观察')
),
risks as (
  select jsonb_agg(jsonb_build_object(
    'company', coalesce(dor.company_name,dor.opportunity_external_id),
    'result', case when dor.action='观察' then '风险恶化/继续观察' else '主要反证' end,
    'reason', dor.evidence_against,
    'source', null,
    'next_verification', dor.next_verification
  ) order by dor.opportunity_external_id) payload
  from public.daily_opportunity_reviews dor
  join latest l on l.report_date=dor.report_date
  where nullif(trim(dor.evidence_against),'') is not null
)
update public.daily_reports dr
set frozen_snapshot=jsonb_set(
  jsonb_set(dr.frozen_snapshot,'{focus_companies}',coalesce(focus.payload,'[]'::jsonb),true),
  '{risks}',coalesce(risks.payload,'[]'::jsonb),true
)
from latest, focus, risks
where dr.report_date=latest.report_date;
