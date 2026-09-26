begin;

insert into public.opportunity_companies(opportunity_id,company_id,role,mapping_status,accounting_status,rationale,company_role,research_pool_status)
select o.id,c.id,'稀土永磁材料候选','pending',c.accounting_status,
  '可能受益于人形机器人永磁材料需求，但客户、单机价值量、ASP和正式供货时间仍未确认，因此只保留观察，不进入建模。',
  c.company_role,c.research_pool_status
from public.companies c join public.opportunities o on o.name='人形机器人工业规模化'
where c.name='金力永磁'
on conflict(opportunity_id,company_id) do nothing;

insert into public.screening_decisions(object_type,object_id,object_name,stage,decision,reason,next_step,rule_version,evaluated_at,metadata)
select 'company',c.id,c.name,'company_mapping','observe',oc.rationale,c.reactivation_condition,'V4.3.1',now(),
  jsonb_build_object('opportunity_id',oc.opportunity_id,'mapping_status',oc.mapping_status)
from public.companies c join public.opportunity_companies oc on oc.company_id=c.id
where c.name='金力永磁';

commit;
