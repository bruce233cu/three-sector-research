begin;

create or replace function public.sync_company_market_cap_from_price()
returns trigger
language plpgsql
security definer
set search_path=''
as $$
begin
  update public.companies
  set market_cap=new.market_cap,
      last_updated_at=greatest(coalesce(last_updated_at,new.trade_date),new.trade_date),
      updated_at=now()
  where id=new.company_id
    and (market_cap is distinct from new.market_cap
      or last_updated_at is null
      or last_updated_at<=new.trade_date);
  return new;
end $$;

drop trigger if exists trg_sync_company_market_cap_from_price on public.price_snapshots;
create trigger trg_sync_company_market_cap_from_price
after insert on public.price_snapshots
for each row execute function public.sync_company_market_cap_from_price();

with latest as (
  select distinct on(company_id) company_id,market_cap,trade_date
  from public.price_snapshots
  order by company_id,trade_date desc,captured_at desc
)
update public.companies c
set market_cap=l.market_cap,
    last_updated_at=greatest(coalesce(c.last_updated_at,l.trade_date),l.trade_date),
    updated_at=now()
from latest l
where c.id=l.company_id
  and c.market_cap is distinct from l.market_cap;

commit;
