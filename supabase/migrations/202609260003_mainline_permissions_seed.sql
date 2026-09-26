begin;

revoke all on schema mainline from public,anon,authenticated;
revoke all on all tables in schema mainline from public,anon,authenticated;
revoke all on all sequences in schema mainline from public,anon,authenticated;
revoke all on all functions in schema mainline from public,anon,authenticated;

grant usage on schema mainline to service_role;
grant select,insert,update,delete on all tables in schema mainline to service_role;
grant usage,select on all sequences in schema mainline to service_role;
grant execute on all functions in schema mainline to service_role;

alter default privileges in schema mainline revoke all on tables from public,anon,authenticated;
alter default privileges in schema mainline revoke all on sequences from public,anon,authenticated;
alter default privileges in schema mainline revoke all on functions from public,anon,authenticated;
alter default privileges in schema mainline grant select,insert,update,delete on tables to service_role;
alter default privileges in schema mainline grant usage,select on sequences to service_role;

alter table mainline.source_snapshots enable row level security;
alter table mainline.run_manifests enable row level security;
alter table mainline.source_registry enable row level security;
alter table mainline.provider_fetch_runs enable row level security;
alter table mainline.security_master enable row level security;
alter table mainline.trading_calendar enable row level security;
alter table mainline.taxonomy_definitions enable row level security;
alter table mainline.membership_history enable row level security;
alter table mainline.stock_daily enable row level security;
alter table mainline.float_market_cap_daily enable row level security;
alter table mainline.benchmark_daily enable row level security;
alter table mainline.adjustment_factors enable row level security;
alter table mainline.corporate_actions enable row level security;
alter table mainline.parameter_profiles enable row level security;
alter table mainline.data_quality_daily enable row level security;
alter table mainline.mainline_lifecycles enable row level security;
alter table mainline.daily_mainline_snapshot enable row level security;

insert into mainline.parameter_profiles(profile_id,mainline_type,rule_version,params_json,effective_from)
values (
  'industry_trend_v2_2_1','B_industry_trend','mainline_v2.2.0',
  '{"benchmark":{"primary":"ALL_A_EQUAL_WEIGHT","secondary":["ALL_A_CAP_WEIGHT"]},"coverage":{"min_sector_return":0.7,"min_breadth":0.7,"min_rs_window":0.9},"candidate":{"rs5_cross_section_pct_max":0.2,"rs10_min":0.0,"win5_min":0.6,"turnover_intensity_min":1.0,"candidate_min_pass_count":3},"confirm":{"rs10_cross_section_pct_max":0.3,"rs10_min":0.0,"win5_min":0.8,"win10_min":0.7,"turnover_pct60_min":0.6,"above_ma20_min":0.6,"breadth_min_pass_count":2,"enhancer_min_pass_count":2,"confirm_consecutive_days":2},"weaken":{"deterioration_group_min":2,"consecutive_days":2,"min_dwell_days_after_confirm":3},"retire":{"core_deterioration_group_min":2,"consecutive_days":3,"rs10_cross_section_pct_exit":0.5,"enhancer_min_pass_count":1},"freeze":{"critical_dataset_failure":true,"source_conflict_freeze":true},"labels":{"enabled":false}}'::jsonb,
  date '2026-09-23'
)
on conflict(profile_id) do nothing;

insert into mainline.source_registry(provider_code,dataset_code,provider_role,provider_name,interface_name,endpoint,field_contract,source_grade,historical_capability,backup_unavailable,priority,source_version,notes)
values
('tushare','trading_calendar','primary','Tushare Pro','trade_cal','https://api.tushare.pro','["exchange","cal_date","is_open","pretrade_date"]','A','historical_full',false,1,'provider_priority_v1','需要TUSHARE_TOKEN'),
('akshare','trading_calendar','backup','AKShare','tool_trade_date_hist_sina',null,'["exchange","cal_date","is_open","pretrade_date"]','B','historical_full',false,1,'provider_priority_v1','需运行环境安装并真实验证'),
('tushare','security_master','primary','Tushare Pro','stock_basic','https://api.tushare.pro','["security_id","ts_code","name","exchange","list_date","delist_date"]','A','historical_full',false,1,'provider_priority_v1','同时拉取L/D/P以保留退市股'),
('akshare','security_master','backup','AKShare','unqualified_current_snapshot',null,'[]','C','realtime_only',true,1,'provider_priority_v1','当前代码名称截面不满足历史主数据合同'),
('tushare','daily_bars','primary','Tushare Pro','daily','https://api.tushare.pro','["security_id","trade_date","open","high","low","close","volume","amount","pct_chg"]','A','historical_full',false,1,'provider_priority_v1',null),
('akshare','daily_bars','backup','AKShare','stock_zh_a_hist',null,'["security_id","trade_date","open","high","low","close","volume","amount","pct_chg"]','B','historical_full',false,1,'provider_priority_v1','批量能力待真实验证'),
('tushare','daily_valuation','primary','Tushare Pro','daily_basic','https://api.tushare.pro','["security_id","trade_date","circ_mv","total_mv","turnover_rate"]','A','historical_full',false,1,'provider_priority_v1',null),
('none','daily_valuation','backup','无合格Backup','backup_unavailable',null,'[]','C','realtime_only',true,1,'provider_priority_v1','禁止用当前截面冒充历史市值'),
('tushare','taxonomies','primary','Tushare Pro','index_classify','https://api.tushare.pro','["taxonomy_type","taxonomy_code","taxonomy_name","taxonomy_version","effective_from"]','A','historical_partial',false,1,'provider_priority_v1',null),
('akshare','taxonomies','backup','AKShare','unqualified_current_snapshot',null,'[]','C','realtime_only',true,1,'provider_priority_v1','缺少可靠版本和有效期'),
('tushare','membership_history','primary','Tushare Pro','index_member_all','https://api.tushare.pro','["security_id","taxonomy_code","effective_from","effective_to"]','A','historical_partial',false,1,'provider_priority_v1','in_date/out_date仍需严格PIT实证'),
('none','membership_history','backup','无合格Backup','backup_unavailable',null,'[]','C','realtime_only',true,1,'provider_priority_v1','当前成分接口不能作为PIT Backup'),
('tushare','index_daily','primary','Tushare Pro','index_daily','https://api.tushare.pro','["index_id","trade_date","open","high","low","close","volume","amount"]','A','historical_full',false,1,'provider_priority_v1',null),
('akshare','index_daily','backup','AKShare','stock_zh_index_daily_em',null,'["index_id","trade_date","open","high","low","close","volume","amount"]','B','historical_full',false,1,'provider_priority_v1','需安装并真实验证')
on conflict(provider_code,dataset_code) do update set
  provider_role=excluded.provider_role,provider_name=excluded.provider_name,
  interface_name=excluded.interface_name,field_contract=excluded.field_contract,
  historical_capability=excluded.historical_capability,
  backup_unavailable=excluded.backup_unavailable,source_version=excluded.source_version,
  notes=excluded.notes,updated_at=now();

commit;
