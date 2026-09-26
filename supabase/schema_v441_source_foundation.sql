begin;

create table if not exists public.source_registry (
  source_code text primary key,
  source_name text not null,
  source_category text not null check(source_category in (
    'company','policy','demand','industry','supply_chain','market','negative_counterevidence'
  )),
  official_level text not null check(official_level in ('S','A','B','C','D')),
  source_url text not null,
  source_type text not null,
  sector_scope text[] not null default array['机器人','商业航天','AI']::text[],
  data_scope text[] not null default '{}'::text[],
  access_method text not null,
  requires_login boolean not null default false,
  historical_accessible boolean not null default false,
  historical_validation_support text not null default 'none'
    check(historical_validation_support in ('full','partial','realtime_only','none')),
  update_frequency text,
  priority integer not null default 3 check(priority between 1 and 5),
  status text not null default 'unconfigured'
    check(status in ('active','degraded','failed','unconfigured','paused')),
  automation_enabled boolean not null default false,
  collector_code text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.raw_clues
  add column if not exists source_code text,
  add column if not exists source_category text,
  add column if not exists source_grade text,
  add column if not exists historical_availability text,
  add column if not exists availability_risk text,
  add column if not exists original_title text,
  add column if not exists underlying_event_id text,
  add column if not exists positive_negative_neutral text,
  add column if not exists available_at timestamptz;

alter table public.signals
  add column if not exists source_code text,
  add column if not exists source_name text,
  add column if not exists source_category text,
  add column if not exists published_at timestamptz,
  add column if not exists discovered_at timestamptz,
  add column if not exists historical_availability text,
  add column if not exists availability_risk text,
  add column if not exists original_title text,
  add column if not exists underlying_event_id text,
  add column if not exists positive_negative_neutral text,
  add column if not exists is_official boolean;

alter table public.source_health
  add column if not exists last_failed_at timestamptz,
  add column if not exists last_result_count integer not null default 0,
  add column if not exists last_new_count integer not null default 0,
  add column if not exists last_run_message text;

alter table public.source_health drop constraint if exists source_health_status_check;
alter table public.source_health add constraint source_health_status_check
  check(status in (
    'healthy','healthy_no_new_data','healthy_no_new_trade','degraded','failed','not_configured'
  ));

create table if not exists public.source_category_coverage_daily (
  id uuid primary key default gen_random_uuid(),
  coverage_date date not null,
  sector_id uuid not null references public.sectors(id) on delete restrict,
  source_category text not null check(source_category in (
    'company','policy','demand','industry','supply_chain','market','negative_counterevidence'
  )),
  registered_source_count integer not null default 0,
  automated_source_count integer not null default 0,
  attempted_source_count integer not null default 0,
  healthy_source_count integer not null default 0,
  raw_record_count integer not null default 0,
  signal_count integer not null default 0,
  negative_record_count integer not null default 0,
  coverage_pct numeric not null default 0,
  coverage_status text not null check(coverage_status in ('covered','partial','missing')),
  notes text,
  automation_run_id uuid references public.automation_runs(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique(coverage_date,sector_id,source_category)
);

create table if not exists public.historical_source_category_coverage (
  id uuid primary key default gen_random_uuid(),
  test_run_id uuid not null references public.historical_validation_runs(id) on delete restrict,
  source_category text not null check(source_category in (
    'company','policy','demand','industry','supply_chain','market','negative_counterevidence'
  )),
  collected_count integer not null default 0,
  available_count integer not null default 0,
  excluded_count integer not null default 0,
  coverage_pct numeric not null default 0,
  conclusion text not null,
  created_at timestamptz not null default now(),
  unique(test_run_id,source_category)
);

create index if not exists raw_clues_source_code_idx on public.raw_clues(source_code,discovered_at desc);
create index if not exists raw_clues_source_category_idx on public.raw_clues(source_category,discovered_at desc);
create index if not exists raw_clues_underlying_event_idx on public.raw_clues(underlying_event_id);
create index if not exists signals_source_code_idx on public.signals(source_code,signal_date desc);
create index if not exists source_coverage_date_idx on public.source_category_coverage_daily(coverage_date desc,sector_id);

insert into public.source_registry(
  source_code,source_name,source_category,official_level,source_url,source_type,
  sector_scope,data_scope,access_method,requires_login,historical_accessible,
  historical_validation_support,update_frequency,priority,status,automation_enabled,
  collector_code,notes
) values
('cninfo_disclosure','巨潮资讯法定信息披露平台','company','S','https://www.cninfo.com.cn/','公司披露',
 array['机器人','商业航天','AI'],array['公告','订单','客户','扩产','财报','风险','供应链交叉验证'],
 '公开接口',false,true,'partial','每日',1,'active',true,'v43-daily-pipeline',
 '自动覆盖当前研究公司；严格历史验证仍受当时公司池范围限制。'),
('sse_disclosure','上海证券交易所公告','company','S','https://www.sse.com.cn/disclosure/listedinfo/announcement/','交易所公告',
 array['机器人','商业航天','AI'],array['上交所上市公司公告'],
 '公开网页',false,true,'full','每日',1,'unconfigured',false,null,'已登记，当前由巨潮统一入口覆盖，尚未建立直连采集。'),
('szse_disclosure','深圳证券交易所公告','company','S','https://www.szse.cn/disclosure/listed/notice/index.html','交易所公告',
 array['机器人','商业航天','AI'],array['深交所上市公司公告'],
 '公开网页',false,true,'full','每日',1,'unconfigured',false,null,'已登记，当前由巨潮统一入口覆盖，尚未建立直连采集。'),
('bse_disclosure','北京证券交易所公告','company','S','https://www.bse.cn/disclosure/announcement.html','交易所公告',
 array['机器人','商业航天','AI'],array['北交所上市公司公告'],
 '公开网页',false,true,'full','每日',2,'unconfigured',false,null,'已登记，尚未建立自动采集。'),
('company_ir','公司官网与投资者关系','company','A','https://www.cninfo.com.cn/','公司官方',
 array['机器人','商业航天','AI'],array['公司官网','投资者关系','业绩说明会'],
 '分散公开网页',false,true,'partial','不定期',2,'unconfigured',false,null,'来源分散，需逐公司登记，不把未接入页面算作已覆盖。'),
('gov_policy','中国政府网最新政策','policy','S','https://www.gov.cn/zhengce/zuixin/','政府正式文件',
 array['机器人','商业航天','AI'],array['产业政策','规划','标准','监管变化'],
 '公开JSON列表与原文',false,true,'full','每日',1,'active',true,'v43-daily-pipeline','只保留与三大赛道相关的正式政策。'),
('local_government','地方政府与地方主管部门','policy','S','https://www.gov.cn/home/2023-03/29/content_5748953.htm','地方政府正式信息',
 array['机器人','商业航天','AI'],array['地方产业项目','园区建设','企业落地','地方政策'],
 '分散公开网页',false,true,'partial','不定期',2,'unconfigured',false,null,'已有真实地方政府资料，但尚未形成统一自动采集入口。'),
('miit_policy','工业和信息化部','policy','S','https://www.miit.gov.cn/','主管部门官方',
 array['机器人','商业航天','AI'],array['专项行动','标准','产业规划','行业管理'],
 '公开网页',false,true,'partial','每日',1,'unconfigured',false,null,'已登记；页面稳定性验证未完成，不作为本期自动采集入口。'),
('ccgp_procurement','中国政府采购网','demand','A','https://www.ccgp.gov.cn/cggg/zygg/gkzb/','政府采购',
 array['机器人','商业航天','AI'],array['招标','采购数量','设备采购','项目需求'],
 '公开网页',false,true,'full','每日',1,'active',true,'v43-daily-pipeline','用于验证下游是否真实花钱，不等同于供应商已经获得订单。'),
('customer_official','下游客户公告与官网','demand','A','https://www.cninfo.com.cn/','客户官方',
 array['机器人','商业航天','AI'],array['客户CAPEX','扩产','设备采购','出货量'],
 '分散公开网页',false,true,'partial','不定期',1,'unconfigured',false,null,'需扩展客户清单后才能形成稳定覆盖。'),
('nbs_industry','国家统计局数据发布','industry','A','https://www.stats.gov.cn/sj/zxfb/','官方产业统计',
 array['机器人','商业航天','AI'],array['工业产量','行业增速','价格变化','固定资产投资'],
 '公开网页与原文',false,true,'full','月度',1,'active',true,'v43-daily-pipeline','当前检查最新发布并从正文识别三大赛道关键词。'),
('industry_associations','行业协会与产业联盟','industry','A','https://www.miit.gov.cn/','行业官方',
 array['机器人','商业航天','AI'],array['行业标准','白皮书','产业会议','出货统计'],
 '分散公开网页',false,true,'partial','不定期',2,'unconfigured',false,null,'尚未逐赛道确认长期稳定的协会入口。'),
('cross_chain_official','上下游官方交叉验证','supply_chain','A','https://www.cninfo.com.cn/','供应链官方',
 array['机器人','商业航天','AI'],array['客户','供应商','竞争对手','核心零部件'],
 '跨公司公开披露',false,true,'partial','每日',2,'active',true,'v43-daily-pipeline','依赖当前公司与客户池，覆盖仍不完整。'),
('eastmoney_quote','东方财富行情','market','B','https://quote.eastmoney.com/','公开行情',
 array['机器人','商业航天','AI'],array['价格','成交量','市值','市场共识验证'],
 '公开行情接口',false,false,'realtime_only','交易日',1,'active',true,'v43-daily-pipeline','只用于市场验证，不作为基本面事实来源。'),
('cninfo_risk','法定披露风险与反证','negative_counterevidence','S','https://www.cninfo.com.cn/','公司与客户正式风险披露',
 array['机器人','商业航天','AI'],array['取消','延期','下修','减值','诉讼','处罚','风险提示'],
 '公开接口',false,true,'partial','每日',1,'active',true,'v43-daily-pipeline','与公司公告同源，但单独统计负面覆盖，不能把没有抓到解释成没有风险。'),
('csrc_enforcement','证监会监管与处罚','negative_counterevidence','S','https://www.csrc.gov.cn/','监管信息',
 array['机器人','商业航天','AI'],array['处罚','立案','重大风险'],
 '公开网页',false,true,'partial','不定期',2,'unconfigured',false,null,'已登记，尚未建立自动采集。')
on conflict(source_code) do update set
  source_name=excluded.source_name,source_category=excluded.source_category,
  official_level=excluded.official_level,source_url=excluded.source_url,
  source_type=excluded.source_type,sector_scope=excluded.sector_scope,
  data_scope=excluded.data_scope,access_method=excluded.access_method,
  requires_login=excluded.requires_login,historical_accessible=excluded.historical_accessible,
  historical_validation_support=excluded.historical_validation_support,
  update_frequency=excluded.update_frequency,priority=excluded.priority,
  status=excluded.status,automation_enabled=excluded.automation_enabled,
  collector_code=excluded.collector_code,notes=excluded.notes,updated_at=now();

update public.raw_clues r set
  source_code=coalesce(r.source_code,case
    when r.source_name ilike '%巨潮%' then 'cninfo_disclosure'
    when r.source_name ilike '%工信%' then 'miit_policy'
    when r.source_name ilike '%政府%' then 'gov_policy'
    when r.source_name ilike '%东方财富%' then 'eastmoney_quote'
    else null end),
  source_category=coalesce(r.source_category,case
    when coalesce(r.sentiment,'')='negative' then 'negative_counterevidence'
    when r.source_name ilike '%工信%' or r.source_name ilike '%政府%' then 'policy'
    when r.source_name ilike '%巨潮%' then 'company'
    else 'industry' end),
  source_grade=coalesce(r.source_grade,case when r.source_name ilike '%巨潮%' then 'S' else r.evidence_level end),
  historical_availability=coalesce(r.historical_availability,case
    when r.source_name ilike '%巨潮%' and r.published_at is not null
      and r.discovered_at <= r.published_at + interval '1 day' then 'A'
    when r.published_at is not null then 'B' else 'C' end),
  availability_risk=coalesce(r.availability_risk,case
    when r.published_at is null then '无法确认准确公开时间'
    when r.discovered_at > r.published_at + interval '1 day' then '系统并非在公开当时采集，不能用于更早历史判断'
    else '公开入口稳定，系统采集时间已记录' end),
  original_title=coalesce(r.original_title,r.title),
  underlying_event_id=coalesce(r.underlying_event_id,r.dedupe_key),
  positive_negative_neutral=coalesce(r.positive_negative_neutral,r.sentiment,'neutral'),
  available_at=coalesce(r.available_at,r.published_at)
where r.source_code is null or r.source_category is null or r.historical_availability is null;

update public.raw_clues set source_code='local_government'
where source_code='gov_policy' and source_name ilike '%松江%';

update public.signals s set source_code='local_government'
from public.raw_clues r where s.raw_clue_id=r.id and r.source_code='local_government';

update public.signals s set
  source_code=coalesce(s.source_code,r.source_code),
  source_name=coalesce(s.source_name,r.source_name),
  source_category=coalesce(s.source_category,r.source_category,'company'),
  source_grade=coalesce(s.source_grade,r.source_grade,r.evidence_level),
  published_at=coalesce(s.published_at,r.published_at,s.signal_date::timestamptz),
  discovered_at=coalesce(s.discovered_at,r.discovered_at,s.created_at),
  historical_availability=coalesce(s.historical_availability,r.historical_availability,'B'),
  availability_risk=coalesce(s.availability_risk,r.availability_risk,'现有记录中无法确认当时稳定可得性'),
  original_title=coalesce(s.original_title,r.original_title,s.title),
  underlying_event_id=coalesce(s.underlying_event_id,r.underlying_event_id,(s.metadata->>'dedupe_key')),
  positive_negative_neutral=coalesce(s.positive_negative_neutral,r.positive_negative_neutral,s.metadata->>'direction','neutral'),
  is_official=coalesce(s.is_official,(coalesce(r.source_grade,s.source_grade) in ('S','A')))
from public.raw_clues r
where s.raw_clue_id=r.id;

insert into public.source_health(source_code,source_name,source_type,status,last_error,metadata)
select r.source_code,r.source_name,r.source_type,
  'not_configured',
  case when r.automation_enabled then '自动采集已配置，等待首次真实运行。' else '来源已登记，但尚未配置自动采集。' end,
  jsonb_build_object('registry_seed',true,'category',r.source_category,'automation_enabled',r.automation_enabled)
from public.source_registry r
where not exists(select 1 from public.source_health h where h.source_code=r.source_code)
on conflict(source_code) do nothing;

insert into public.historical_source_category_coverage(
  test_run_id,source_category,collected_count,available_count,excluded_count,coverage_pct,conclusion
)
select run.id,category.code,
  case
    when category.code='company' then greatest(run.collected_record_count-stats.negative_record_count,0)
    when category.code='negative_counterevidence' then stats.negative_record_count
    else 0 end,
  0,
  case
    when category.code='company' then greatest(run.collected_record_count-stats.negative_record_count,0)
    when category.code='negative_counterevidence' then stats.negative_record_count
    else 0 end,
  0,
  case
    when category.code='company' then '候选资料主要来自公司公告，但系统当时没有采集时间证据，严格可用为0。'
    when category.code='negative_counterevidence' then '候选库有负面公告，但系统当时没有采到，严格可用负面信息仍为0。'
    else '该历史窗口没有按统一规则重建这一层来源，覆盖为0。' end
from public.historical_validation_runs run
cross join lateral (
  select count(*) filter(where sentiment='negative')::integer as negative_record_count
  from public.historical_raw_records h where h.test_run_id=run.id
) stats
cross join (values
 ('company'),('policy'),('demand'),('industry'),('supply_chain'),('market'),('negative_counterevidence')
) category(code)
on conflict(test_run_id,source_category) do nothing;

alter table public.source_registry enable row level security;
alter table public.source_category_coverage_daily enable row level security;
alter table public.historical_source_category_coverage enable row level security;

grant select on public.source_registry,public.source_category_coverage_daily,public.historical_source_category_coverage to anon,authenticated;
grant select,insert,update,delete on public.source_registry,public.source_category_coverage_daily,public.historical_source_category_coverage to service_role;

do $$ begin
  if not exists(select 1 from pg_policies where schemaname='public' and tablename='source_registry' and policyname='source_registry_read') then
    create policy source_registry_read on public.source_registry for select to anon,authenticated using(true);
  end if;
  if not exists(select 1 from pg_policies where schemaname='public' and tablename='source_category_coverage_daily' and policyname='source_category_coverage_read') then
    create policy source_category_coverage_read on public.source_category_coverage_daily for select to anon,authenticated using(true);
  end if;
  if not exists(select 1 from pg_policies where schemaname='public' and tablename='historical_source_category_coverage' and policyname='historical_source_category_coverage_read') then
    create policy historical_source_category_coverage_read on public.historical_source_category_coverage for select to anon,authenticated using(true);
  end if;
end $$;

commit;
