begin;

insert into public.source_registry(
  source_code,source_name,source_category,official_level,source_url,source_type,sector_scope,data_scope,
  access_method,requires_login,historical_accessible,historical_validation_support,update_frequency,priority,
  status,automation_enabled,collector_code,notes,operational_status,realtime_available,historical_available,
  historical_strict_available,historical_capability,historical_availability_risk,primary_use,audit_evidence,audited_at
)
values (
  'industry_demand_statistics','行业出货、装机与投资统计','demand','A','https://www.stats.gov.cn/sj/zxfb/',
  '官方行业需求统计',array['机器人','商业航天','AI'],array['产量','销量','出货','装机','投资','建设'],
  '国家统计局发布页定向抽取',false,true,'full','每日',1,'unconfigured',true,'v43-daily-pipeline',
  '第三类需求机制：与公共采购、客户公告分开，提取行业实际产量、销量、装机和投资记录。',
  'registered_unconfigured',true,true,true,'historical_full','low',
  array['demand_validation','model_input','historical_validation'],'等待V4.4.2采集器首次真实运行。',now()
)
on conflict(source_code) do update set
  source_name=excluded.source_name,source_category=excluded.source_category,sector_scope=excluded.sector_scope,
  data_scope=excluded.data_scope,automation_enabled=true,collector_code=excluded.collector_code,notes=excluded.notes,
  primary_use=excluded.primary_use,updated_at=now();

insert into public.supply_chain_entities(entity_code,entity_name,entity_type,sector_id,listing_code,official_url,metadata)
select
  'WATCH-' || substr(md5(w.entity_name || ':' || w.target_role),1,20),
  w.entity_name,
  case w.target_role when 'customer' then 'customer' when 'competitor' then 'competitor' when 'supplier' then 'supplier' else 'company' end,
  w.sector_id,w.stock_code,w.official_page_url,
  jsonb_build_object('watch_target_id',w.id,'target_role',w.target_role,'source_code',w.source_code)
from public.source_watch_targets w
on conflict(entity_code) do update set
  entity_name=excluded.entity_name,entity_type=excluded.entity_type,sector_id=excluded.sector_id,
  listing_code=excluded.listing_code,official_url=excluded.official_url,metadata=excluded.metadata,updated_at=now();

commit;
