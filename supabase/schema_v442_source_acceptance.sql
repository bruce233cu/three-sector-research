begin;

alter table public.source_registry add column if not exists operational_status text not null default 'registered_unconfigured';
alter table public.source_registry add column if not exists realtime_available boolean not null default false;
alter table public.source_registry add column if not exists historical_available boolean not null default false;
alter table public.source_registry add column if not exists historical_strict_available boolean not null default false;
alter table public.source_registry add column if not exists historical_capability text not null default 'realtime_only';
alter table public.source_registry add column if not exists historical_availability_risk text not null default 'high';
alter table public.source_registry add column if not exists primary_use text[] not null default '{}';
alter table public.source_registry add column if not exists proxy_covered_by text;
alter table public.source_registry add column if not exists audit_evidence text;
alter table public.source_registry add column if not exists audited_at timestamptz;

alter table public.source_registry drop constraint if exists source_registry_operational_status_check;
alter table public.source_registry add constraint source_registry_operational_status_check check (
  operational_status in ('automated_active','manual_available','registered_unconfigured','degraded','unavailable')
);
alter table public.source_registry drop constraint if exists source_registry_historical_capability_check;
alter table public.source_registry add constraint source_registry_historical_capability_check check (
  historical_capability in ('realtime_only','historical_partial','historical_full','unavailable')
);
alter table public.source_registry drop constraint if exists source_registry_historical_availability_risk_check;
alter table public.source_registry add constraint source_registry_historical_availability_risk_check check (
  historical_availability_risk in ('low','medium','high')
);

alter table public.source_category_coverage_daily add column if not exists manual_available_source_count integer not null default 0;
alter table public.source_category_coverage_daily add column if not exists unconfigured_source_count integer not null default 0;
alter table public.source_category_coverage_daily add column if not exists planned_source_count integer not null default 0;
alter table public.source_category_coverage_daily add column if not exists successful_source_count integer not null default 0;
alter table public.source_category_coverage_daily add column if not exists effective_source_count integer not null default 0;
alter table public.source_category_coverage_daily add column if not exists historical_strict_source_count integer not null default 0;
alter table public.source_category_coverage_daily add column if not exists integration_rate_pct numeric not null default 0;
alter table public.source_category_coverage_daily add column if not exists collection_success_rate_pct numeric not null default 0;
alter table public.source_category_coverage_daily add column if not exists effective_data_coverage_pct numeric not null default 0;
alter table public.source_category_coverage_daily add column if not exists historical_strict_availability_pct numeric not null default 0;

comment on column public.source_category_coverage_daily.coverage_pct is
  'V4.4.1 legacy field. Do not present as source coverage. V4.4.2 uses four explicit rates.';

create table if not exists public.source_watch_targets (
  id uuid primary key default gen_random_uuid(),
  entity_name text not null,
  stock_code text,
  sector_id uuid references public.sectors(id) on delete set null,
  target_role text not null check (target_role in ('research_company','customer','supplier','competitor','industry_validator')),
  source_code text not null references public.source_registry(source_code) on update cascade,
  official_page_url text,
  page_type text not null default 'disclosure',
  collection_channel text not null default 'manual',
  enabled boolean not null default true,
  priority integer not null default 3,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(entity_name,target_role,source_code)
);

create table if not exists public.supply_chain_entities (
  id uuid primary key default gen_random_uuid(),
  entity_code text not null unique,
  entity_name text not null,
  entity_type text not null check (entity_type in ('company','customer','supplier','competitor','government','institution','product','project')),
  sector_id uuid references public.sectors(id) on delete set null,
  company_id uuid references public.companies(id) on delete set null,
  listing_code text,
  official_url text,
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.supply_chain_relationships (
  id uuid primary key default gen_random_uuid(),
  upstream_entity_id uuid not null references public.supply_chain_entities(id) on delete restrict,
  downstream_entity_id uuid not null references public.supply_chain_entities(id) on delete restrict,
  company_id uuid references public.companies(id) on delete set null,
  relationship_type text not null,
  product_component text,
  evidence_id uuid references public.raw_clues(id) on delete set null,
  underlying_event_id text,
  effective_from date,
  effective_to date,
  confidence numeric check (confidence is null or (confidence >= 0 and confidence <= 1)),
  source_grade text check (source_grade is null or source_grade in ('S','A','B','C','D')),
  status text not null default 'active' check (status in ('candidate','active','weakened','expired','rejected')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (upstream_entity_id <> downstream_entity_id),
  unique(upstream_entity_id,downstream_entity_id,relationship_type,product_component,effective_from)
);

create table if not exists public.source_gap_register (
  id uuid primary key default gen_random_uuid(),
  gap_code text not null unique,
  sector_code text,
  source_category text not null,
  gap_title text not null,
  gap_description text not null,
  severity text not null check (severity in ('high','medium','low')),
  status text not null default 'open' check (status in ('open','partial','closed')),
  next_action text not null,
  evidence jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create index if not exists source_registry_operational_idx on public.source_registry(source_category,operational_status);
create index if not exists source_watch_targets_role_idx on public.source_watch_targets(target_role,enabled,priority);
create index if not exists supply_chain_entities_sector_idx on public.supply_chain_entities(sector_id,entity_type);
create index if not exists supply_chain_relationships_company_idx on public.supply_chain_relationships(company_id,status);
create index if not exists supply_chain_relationships_effective_idx on public.supply_chain_relationships(effective_from,effective_to);
create index if not exists source_gap_register_status_idx on public.source_gap_register(status,severity);

alter table public.source_watch_targets enable row level security;
alter table public.supply_chain_entities enable row level security;
alter table public.supply_chain_relationships enable row level security;
alter table public.source_gap_register enable row level security;
grant select on public.source_watch_targets,public.supply_chain_entities,public.supply_chain_relationships,public.source_gap_register to anon,authenticated;
grant select,insert,update,delete on public.source_watch_targets,public.supply_chain_entities,public.supply_chain_relationships,public.source_gap_register to service_role;

drop policy if exists anon_read_source_watch_targets on public.source_watch_targets;
create policy anon_read_source_watch_targets on public.source_watch_targets for select to anon using (true);
drop policy if exists authenticated_read_source_watch_targets on public.source_watch_targets;
create policy authenticated_read_source_watch_targets on public.source_watch_targets for select to authenticated using (true);
drop policy if exists anon_read_supply_chain_entities on public.supply_chain_entities;
create policy anon_read_supply_chain_entities on public.supply_chain_entities for select to anon using (true);
drop policy if exists authenticated_read_supply_chain_entities on public.supply_chain_entities;
create policy authenticated_read_supply_chain_entities on public.supply_chain_entities for select to authenticated using (true);
drop policy if exists anon_read_supply_chain_relationships on public.supply_chain_relationships;
create policy anon_read_supply_chain_relationships on public.supply_chain_relationships for select to anon using (true);
drop policy if exists authenticated_read_supply_chain_relationships on public.supply_chain_relationships;
create policy authenticated_read_supply_chain_relationships on public.supply_chain_relationships for select to authenticated using (true);
drop policy if exists anon_read_source_gap_register on public.source_gap_register;
create policy anon_read_source_gap_register on public.source_gap_register for select to anon using (true);
drop policy if exists authenticated_read_source_gap_register on public.source_gap_register;
create policy authenticated_read_source_gap_register on public.source_gap_register for select to authenticated using (true);

update public.source_registry r set
  operational_status=case
    when r.source_code='legacy_unverified' then 'unavailable'
    when r.automation_enabled and exists (
      select 1 from public.source_health h where h.source_code=r.source_code
        and h.last_success_at is not null and h.status in ('healthy','healthy_no_new_data','healthy_no_new_trade')
    ) then 'automated_active'
    when r.automation_enabled then 'degraded'
    when r.access_method in ('无法确认') then 'unavailable'
    else 'manual_available'
  end,
  realtime_available=(r.source_code <> 'legacy_unverified'),
  historical_available=r.historical_accessible,
  historical_strict_available=(r.historical_validation_support='full' and r.source_code not in ('cninfo_disclosure')),
  historical_capability=case r.historical_validation_support
    when 'full' then case when r.source_code='cninfo_disclosure' then 'historical_partial' else 'historical_full' end
    when 'partial' then 'historical_partial'
    when 'realtime_only' then 'realtime_only'
    else case when r.source_code='legacy_unverified' then 'unavailable' else 'realtime_only' end
  end,
  historical_availability_risk=case
    when r.historical_validation_support='full' and r.source_code<>'cninfo_disclosure' then 'low'
    when r.historical_accessible then 'medium'
    else 'high'
  end,
  audited_at=now(),
  audit_evidence=case
    when r.automation_enabled then '以 source_health 最近真实检查与成功时间验收；登记本身不算接入。'
    when r.source_code='legacy_unverified' then '旧记录缺少可追溯来源，当前不可用。'
    else '官方入口可人工访问，但没有自动采集记录。'
  end;

update public.source_registry set primary_use=array['company_confirmation','model_input','negative_evidence','historical_validation'] where source_code='cninfo_disclosure';
update public.source_registry set primary_use=array['company_confirmation','historical_validation'],proxy_covered_by='cninfo_disclosure',notes='可人工访问；当前没有独立直连采集，由巨潮代理覆盖，不计为独立自动来源。' where source_code in ('sse_disclosure','szse_disclosure','bse_disclosure');
update public.source_registry set primary_use=array['company_confirmation','supply_chain_validation'] where source_code in ('company_ir','company_official');
update public.source_registry set primary_use=array['change_discovery'] where source_code='secondary_disclosure';
update public.source_registry set primary_use=array['demand_validation','historical_validation'] where source_code='ccgp_procurement';
update public.source_registry set primary_use=array['demand_validation','supply_chain_validation','company_confirmation'] where source_code='customer_official';
update public.source_registry set primary_use=array['change_discovery','demand_validation','model_input','historical_validation'] where source_code='nbs_industry';
update public.source_registry set primary_use=array['change_discovery','historical_validation'] where source_code in ('space_agency_official','industry_associations');
update public.source_registry set primary_use=array['change_discovery'] where source_code in ('industry_media','authoritative_media','legacy_unverified');
update public.source_registry set primary_use=array['market_confirmation'] where source_category='market';
update public.source_registry set primary_use=array['negative_evidence','company_confirmation'] where source_code='cninfo_risk';
update public.source_registry set primary_use=array['negative_evidence','historical_validation'] where source_code='csrc_enforcement';
update public.source_registry set primary_use=array['change_discovery','historical_validation'] where source_category='policy';
update public.source_registry set primary_use=array['supply_chain_validation','change_discovery'] where source_code='cross_chain_official';

insert into public.source_registry(source_code,source_name,source_category,official_level,source_url,source_type,sector_scope,data_scope,access_method,requires_login,historical_accessible,historical_validation_support,update_frequency,priority,status,automation_enabled,collector_code,notes,operational_status,realtime_available,historical_available,historical_strict_available,historical_capability,historical_availability_risk,primary_use,audit_evidence,audited_at)
values
('supply_customer_official','客户侧供应链确认','supply_chain','S','https://www.cninfo.com.cn/','客户法定披露',array['机器人','商业航天','AI'],array['客户采购','供应商确认','项目建设'],'重点客户名单+法定披露代理采集',false,true,'partial','每日',1,'unconfigured',true,'v43-daily-pipeline','按重点客户名单采集；与公司自述分开计数，重复公告使用 underlying_event_id 去重。','registered_unconfigured',true,true,false,'historical_partial','medium',array['demand_validation','supply_chain_validation','company_confirmation'],'等待V4.4.2采集器首次真实运行。',now()),
('supply_supplier_official','供应商侧供应链确认','supply_chain','S','https://www.cninfo.com.cn/','供应商法定披露',array['机器人','商业航天','AI'],array['供货','客户','订单','产能'],'研究公司与重点供应商法定披露',false,true,'partial','每日',1,'unconfigured',true,'v43-daily-pipeline','采集供应商侧订单与供货变化；不能单独证明客户最终采购。','registered_unconfigured',true,true,false,'historical_partial','medium',array['supply_chain_validation','company_confirmation'],'等待V4.4.2采集器首次真实运行。',now()),
('supply_competitor_official','竞争对手侧验证','supply_chain','S','https://www.cninfo.com.cn/','竞争对手法定披露',array['机器人','商业航天','AI'],array['扩产','降价','替代','份额','新产品'],'重点竞争对手名单+法定披露代理采集',false,true,'partial','每日',1,'unconfigured',true,'v43-daily-pipeline','主动发现扩产、降价和替代，不只围绕已有公司池。','registered_unconfigured',true,true,false,'historical_partial','medium',array['supply_chain_validation','negative_evidence','change_discovery'],'等待V4.4.2采集器首次真实运行。',now()),
('procurement_negative','采购取消、流标与延期','negative_counterevidence','A','https://www.ccgp.gov.cn/cggg/zygg/gkzb/','公共采购反证',array['机器人','商业航天','AI'],array['终止','废标','流标','延期','取消'],'政府采购公开页面',false,true,'full','每日',1,'unconfigured',true,'v43-daily-pipeline','与公司风险披露独立的第二种负面机制。0条新增只能写未发现，不能写无风险。','registered_unconfigured',true,true,true,'historical_full','low',array['negative_evidence','demand_validation','historical_validation'],'等待V4.4.2采集器首次真实运行。',now())
on conflict(source_code) do update set
  source_name=excluded.source_name,source_category=excluded.source_category,data_scope=excluded.data_scope,
  automation_enabled=excluded.automation_enabled,collector_code=excluded.collector_code,notes=excluded.notes,
  primary_use=excluded.primary_use,updated_at=now();

insert into public.source_watch_targets(entity_name,stock_code,sector_id,target_role,source_code,official_page_url,page_type,collection_channel,priority,notes)
select v.entity_name,v.stock_code,s.id,v.target_role,v.source_code,v.official_page_url,'disclosure','cninfo_proxy',v.priority,v.notes
from (values
  ('中国移动','600941.SH','AI','customer','customer_official','https://www.chinamobileltd.com/en/ir/reports.php',1,'云与算力资本开支、服务器和数据中心需求'),
  ('中国电信','601728.SH','AI','customer','customer_official','https://www.chinatelecom-h.com/en/ir/reports.php',1,'运营商算力、云网和数据中心资本开支'),
  ('中国联通','600050.SH','AI','customer','customer_official','https://www.chinaunicom-a.com/',2,'算力网络、服务器和智算中心建设'),
  ('比亚迪','002594.SZ','机器人','customer','customer_official','https://www.bydglobal.com/en/InvestorRelations.html',1,'汽车工厂扩产、自动化设备与机器人需求'),
  ('上汽集团','600104.SH','机器人','customer','customer_official','https://www.saicmotor.com/chinese/tzzgx/index.shtml',2,'汽车工厂扩产与工业自动化投入'),
  ('中国卫通','601698.SH','商业航天','customer','customer_official','http://www.chinasatcom.com/',1,'卫星通信、星座和地面站建设'),
  ('汇川技术','300124.SZ','机器人','competitor','supply_competitor_official','https://www.inovance.com/investor/index.html',1,'工业自动化与机器人竞争供给'),
  ('中科曙光','603019.SH','AI','competitor','supply_competitor_official','https://www.sugon.com/investor.html',1,'算力服务器与数据中心竞争供给'),
  ('航天电子','600879.SH','商业航天','competitor','supply_competitor_official','http://www.catec-ltd.cn/',1,'商业航天电子配套竞争供给')
) as v(entity_name,stock_code,sector_name,target_role,source_code,official_page_url,priority,notes)
join public.sectors s on s.name=v.sector_name
on conflict(entity_name,target_role,source_code) do update set
  stock_code=excluded.stock_code,sector_id=excluded.sector_id,official_page_url=excluded.official_page_url,
  collection_channel=excluded.collection_channel,enabled=true,priority=excluded.priority,notes=excluded.notes,updated_at=now();

insert into public.source_watch_targets(entity_name,stock_code,sector_id,target_role,source_code,official_page_url,page_type,collection_channel,priority,notes)
select c.name,c.stock_code,c.sector_id,'supplier','supply_supplier_official',null,'disclosure','cninfo_proxy',1,'现有可投资公司作为供应商侧入口'
from public.companies c where c.company_role='investable_candidate' and c.stock_code is not null
on conflict(entity_name,target_role,source_code) do update set enabled=true,updated_at=now();

insert into public.source_gap_register(gap_code,sector_code,source_category,gap_title,gap_description,severity,status,next_action,evidence)
values
('ROBOT_DEMAND_DEPTH','ROBOT','demand','机器人需求层仍偏薄','已有公共采购和重点汽车客户名单，但人形机器人厂订单与核心零部件采购仍不连续。','high','partial','持续补齐机器人厂采购与汽车自动化CAPEX的可追溯记录。','{"known":"公共采购+汽车客户披露","missing":"机器人厂采购连续序列"}'),
('AI_CAPEX_DEPTH','AI','demand','AI客户CAPEX覆盖不足','已建立三大运营商重点名单，但海外云厂商CAPEX和GPU/ASIC部署仍未形成稳定自动序列。','high','partial','建立云厂商季度CAPEX快照并保存当时可得时间。','{"known":"运营商名单","missing":"云厂商CAPEX连续序列"}'),
('SPACE_SUPPLY_CHAIN','SPACE','supply_chain','商业航天供应链覆盖不足','已加入客户与竞争对象，但星座、卫星采购、地面站和发射配套的供应商确认仍不足。','high','partial','优先补卫星运营商、总装单位和地面站项目的双向确认。','{"known":"中国卫通+航天电子","missing":"星座总装与地面站双向确认"}'),
('NEGATIVE_BREADTH',null,'negative_counterevidence','负面反证仍需连续运行','已增加采购取消/流标机制，但竞争替代、价格下降和CAPEX下修仍需连续记录验证。','high','partial','至少连续7日验证公司风险披露与采购反证两种机制。','{"mechanisms":["法定风险披露","采购取消/流标"]}'),
('HISTORICAL_SECURITY_POOL',null,'historical_validation','历史证券池尚未建立','当前严格历史能力只覆盖来源入口，尚未冻结每个历史时点的可投资证券池。','high','open','建立按日冻结的历史证券池后再重新跑V4.4。','{"blocker":"point-in-time security universe missing"}')
on conflict(gap_code) do update set gap_title=excluded.gap_title,gap_description=excluded.gap_description,severity=excluded.severity,status=excluded.status,next_action=excluded.next_action,evidence=excluded.evidence,updated_at=now();

create or replace view public.source_category_status_summary with (security_invoker=true) as
select
  source_category,
  count(*)::integer registered_count,
  count(*) filter(where operational_status='automated_active')::integer automated_active_count,
  count(*) filter(where operational_status='manual_available')::integer manual_available_count,
  count(*) filter(where operational_status='registered_unconfigured')::integer registered_unconfigured_count,
  count(*) filter(where operational_status='degraded')::integer degraded_count,
  count(*) filter(where operational_status='unavailable')::integer unavailable_count,
  count(*) filter(where historical_strict_available)::integer historical_strict_count,
  round(100.0*count(*) filter(where operational_status='automated_active')/nullif(count(*),0),1) integration_rate_pct,
  round(100.0*count(*) filter(where historical_strict_available)/nullif(count(*),0),1) historical_strict_rate_pct
from public.source_registry group by source_category;
grant select on public.source_category_status_summary to anon,authenticated;

commit;
