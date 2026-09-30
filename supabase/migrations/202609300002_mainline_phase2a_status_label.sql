begin;

create or replace function public.get_mainline_status_v2()
returns jsonb language sql security definer set search_path = pg_catalog, public, mainline as $$
  select public.get_mainline_phase1d_status() || jsonb_build_object(
    'phase', jsonb_build_object(
      'version','V2.2',
      'phase','Phase 2A',
      'gate','S1 POC',
      'status','部分通过 / 待独立验收'
    ),
    'candidate_poc', coalesce((
      select jsonb_agg(to_jsonb(x) order by x.trade_date desc, x.taxonomy_code)
      from (
        select distinct on (trade_date, object_id) trade_date, industry_name, taxonomy_code,
          conditions, valid_condition_count, pass_condition_count, final_decision
        from mainline.phase2a_candidate_checks
        order by trade_date desc, object_id, created_at desc
        limit 40
      ) x
    ), '[]'::jsonb)
  );
$$;

revoke all on function public.get_mainline_status_v2() from public, anon, authenticated;
grant execute on function public.get_mainline_status_v2() to service_role;

commit;
