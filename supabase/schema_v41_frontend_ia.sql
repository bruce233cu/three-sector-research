-- V4.1 keeps the V4 state machine and adds one presentation-facing discriminator.
alter table public.companies
  add column if not exists shadow_stage text;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'companies_shadow_stage_check'
  ) then
    alter table public.companies
      add constraint companies_shadow_stage_check
      check (shadow_stage is null or shadow_stage in ('mapping','modeling','investment_value'));
  end if;
end $$;

update public.companies
set shadow_stage = case
  when valuation_status = 'completed' or investment_assessment_status in ('evaluated','shadow','failed') then 'investment_value'
  when accounting_status = 'ready_to_model' or valuation_status = 'in_progress' then 'modeling'
  else 'mapping'
end
where research_pool_status = 'shadow'
  and shadow_stage is null;

comment on column public.companies.shadow_stage is
  'V4.1 observation stage: mapping, modeling, or investment_value. Internal research workflow remains unchanged.';
