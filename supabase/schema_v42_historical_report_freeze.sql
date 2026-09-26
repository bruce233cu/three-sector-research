-- V4.2: one-time immutable snapshots for legacy daily reports.
update public.daily_reports dr
set frozen_snapshot=jsonb_build_object(
  'report_date',dr.report_date,
  'generated_at',coalesce(dr.created_at,now()),
  'is_frozen',true,
  'headline',dr.summary,
  'stats',jsonb_build_object(
    'new_valid_signals',dr.valid_signal_count,
    'new_opportunities',dr.new_pool_count,
    'opportunity_strengthened',0,
    'opportunity_weakened',0,
    'new_mapped_companies',0,
    'entered_modeling',0,
    'model_completed',0,
    'investment_evaluated',0,
    'high_expected_return',0,
    'to_observe',0,
    'logic_invalidated',0
  ),
  'sectors',coalesce((select jsonb_agg(jsonb_build_object(
    'track',s.name,'strength',dsr.strength_score,
    'demand_change',coalesce(dsr.metadata->>'demand_change',dsr.key_changes),
    'supply_change',coalesce(dsr.metadata->>'supply_change',dsr.evidence_summary),
    'company_change',dsr.company_mapping,
    'opportunity_change',dsr.opportunity_updates,
    'risk',coalesce(dsr.metadata->>'risk',dsr.conclusion),
    'counter_evidence',coalesce(dsr.metadata->>'counter_evidence','当日未记录'),
    'next_verification',dsr.next_verification,
    'conclusion',dsr.conclusion
  )) from public.daily_sector_reviews dsr join public.sectors s on s.id=dsr.sector_id where dsr.report_date=dr.report_date),'[]'::jsonb),
  'opportunity_changes',coalesce((select jsonb_agg(to_jsonb(dor)-'id'-'created_at'-'updated_at') from public.daily_opportunity_reviews dor where dor.report_date=dr.report_date),'[]'::jsonb),
  'company_changes',coalesce((select jsonb_agg(jsonb_build_object(
    'company',c.name,'from',st.from_status,'to',st.to_status,
    'reason',st.transition_reason,'next_step',c.reactivation_condition,'changed_at',st.created_at
  )) from public.company_state_transitions st join public.companies c on c.id=st.company_id where st.created_at::date=dr.report_date),'[]'::jsonb),
  'focus_companies','[]'::jsonb,
  'model_changes',coalesce((select jsonb_agg(jsonb_build_object(
    'company',c.name,'change_type',mcl.change_type,'before',mcl.previous_state,
    'after',mcl.new_state,'reason',mcl.change_reason,'changed_at',mcl.changed_at
  )) from public.model_change_log mcl join public.companies c on c.id=mcl.company_id where mcl.changed_at::date=dr.report_date),'[]'::jsonb),
  'price_odds_changes',coalesce((select jsonb_agg(jsonb_build_object(
    'company',c.name,'price',cds.close_price,'market_cap',cds.market_cap,
    'expected_return',cds.expected_return,'base_return',cds.base_return,
    'fundamental_change',cds.change_driver
  )) from public.company_daily_snapshots cds join public.companies c on c.id=cds.company_id where cds.trade_date=dr.report_date),'[]'::jsonb),
  'watch_changes','[]'::jsonb,
  'risks',coalesce((select jsonb_agg(jsonb_build_object(
    'company',dor.company_name,'result','主要反证','reason',dor.evidence_against,
    'next_verification',dor.next_verification
  )) from public.daily_opportunity_reviews dor where dor.report_date=dr.report_date and nullif(trim(dor.evidence_against),'') is not null),'[]'::jsonb),
  'next_tasks','[]'::jsonb
), report_version='V4.2', generated_at=coalesce(dr.created_at,now())
where dr.frozen_snapshot='{}'::jsonb;
