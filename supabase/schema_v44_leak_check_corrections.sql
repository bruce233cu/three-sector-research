begin;

create table if not exists public.historical_leak_check_corrections (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id),
  original_check_id uuid not null references public.historical_leak_checks(id),
  corrected_result text not null check (corrected_result in ('passed','failed','not_verifiable')),
  corrected_violation_count integer not null default 0,
  corrected_detail text not null,
  correction_reason text not null,
  created_at timestamptz not null default now(),
  unique(original_check_id)
);

alter table public.historical_leak_check_corrections enable row level security;
drop policy if exists historical_leak_check_corrections_public_read on public.historical_leak_check_corrections;
create policy historical_leak_check_corrections_public_read
  on public.historical_leak_check_corrections for select to anon, authenticated using (true);
grant select on public.historical_leak_check_corrections to anon, authenticated;
grant all on public.historical_leak_check_corrections to service_role;

drop trigger if exists historical_leak_check_corrections_immutable on public.historical_leak_check_corrections;
create trigger historical_leak_check_corrections_immutable
before update or delete on public.historical_leak_check_corrections
for each row execute function public.reject_history_mutation();

insert into public.historical_leak_check_corrections (
  test_run_id,original_check_id,corrected_result,corrected_violation_count,
  corrected_detail,correction_reason
)
select
  l.test_run_id,l.id,'failed',1,
  '预热期候选库含1条负面公告，但它是在历史判断日之后才入库；严格可用的负面信息仍为0条，因此负面覆盖不通过。',
  '原检查把“严格可用负面信息为0”写成“候选资料没有负面记录”，结论没有变化，但描述需要更正。'
from public.historical_leak_checks l
where l.check_code='negative_information_coverage'
on conflict (original_check_id) do nothing;

commit;
