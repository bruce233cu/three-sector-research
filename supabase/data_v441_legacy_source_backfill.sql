begin;

insert into public.source_registry(
  source_code,source_name,source_category,official_level,source_url,source_type,
  sector_scope,data_scope,access_method,requires_login,historical_accessible,
  historical_validation_support,update_frequency,priority,status,automation_enabled,notes
) values
('company_official','公司与客户官方页面','company','A','https://www.cninfo.com.cn/','公司官方',
 array['机器人','商业航天','AI'],array['公司新闻','客户合作','产品发布','投资者关系'],
 '分散公开网页',false,true,'partial','不定期',2,'unconfigured',false,'已有真实资料，尚未建立统一自动采集。'),
('government_official','政府与主管部门官方页面','policy','S','https://www.gov.cn/','政府官方',
 array['机器人','商业航天','AI'],array['产业政策','主管部门信息','地方项目'],
 '分散公开网页',false,true,'partial','不定期',2,'unconfigured',false,'已有真实资料，尚未建立统一自动采集。'),
('space_agency_official','国家航天主管机构','industry','S','https://www.cnsa.gov.cn/','航天官方',
 array['商业航天'],array['发射','卫星','航天工程','监管'],
 '公开网页',false,true,'partial','不定期',1,'unconfigured',false,'商业航天官方来源，尚未建立自动采集。'),
('authoritative_media','权威媒体','industry','B','https://www.reuters.com/','权威媒体',
 array['机器人','商业航天','AI'],array['海外需求','客户变化','产业风险','交叉验证'],
 '公开网页',false,false,'none','每日',3,'unconfigured',false,'只能辅助验证；今天能访问不等于历史时点稳定可得。'),
('industry_media','产业媒体与科技媒体','industry','C','https://www.stdaily.com/','产业媒体',
 array['机器人','商业航天','AI'],array['产业线索','技术动态','会议与公司采访'],
 '公开网页',false,false,'none','每日',4,'unconfigured',false,'只作为线索，不能单独进入核心模型。'),
('secondary_disclosure','二次转载的公司披露','company','C','https://stock.stockstar.com/notice/','二次披露',
 array['机器人','商业航天','AI'],array['公告转载','财报转载'],
 '公开网页',false,false,'none','不定期',4,'unconfigured',false,'必须回到交易所或公司原文后才能升级证据等级。'),
('market_reference','第三方行情参考','market','C','https://www.investing.com/','第三方行情',
 array['机器人','商业航天','AI'],array['历史价格参考'],
 '公开网页',false,false,'realtime_only','交易日',4,'unconfigured',false,'只作参考，不替代同一时点的正式价格快照。'),
('legacy_unverified','旧记录中无法确认的来源','industry','D','https://www.gov.cn/','来源待补',
 array['机器人','商业航天','AI'],array['旧信号待补来源'],
 '无法确认',false,false,'none','不确定',5,'unconfigured',false,'原记录没有可用URL或明确来源，不能作为核心证据。')
on conflict(source_code) do update set
  source_name=excluded.source_name,source_category=excluded.source_category,
  official_level=excluded.official_level,source_url=excluded.source_url,
  source_type=excluded.source_type,sector_scope=excluded.sector_scope,
  data_scope=excluded.data_scope,access_method=excluded.access_method,
  requires_login=excluded.requires_login,historical_accessible=excluded.historical_accessible,
  historical_validation_support=excluded.historical_validation_support,
  update_frequency=excluded.update_frequency,priority=excluded.priority,
  status=excluded.status,automation_enabled=excluded.automation_enabled,
  notes=excluded.notes,updated_at=now();

insert into public.source_health(source_code,source_name,source_type,status,last_error,last_run_message,metadata)
select source_code,source_name,source_category,'not_configured',
  case when source_code='legacy_unverified' then '旧记录缺少真实来源，需要逐条补证。'
       else '已有资料，但尚未配置统一自动采集。' end,
  '来源已登记，不冒充自动运行。',
  jsonb_build_object('legacy_backfill',true,'category',source_category,'automation_enabled',false)
from public.source_registry r
where source_code in (
  'company_official','government_official','space_agency_official','authoritative_media',
  'industry_media','secondary_disclosure','market_reference','legacy_unverified'
)
on conflict(source_code) do nothing;

with classified as (
  select id,
    case
      when source_url ilike '%ccgp.gov.cn%' then 'ccgp_procurement'
      when source_url ilike '%miit.gov.cn%' then 'miit_policy'
      when source_url ilike '%cnsa.gov.cn%' then 'space_agency_official'
      when source_url ilike '%gov.cn%' or source_name ilike '%政府%' or source_name ilike '%经信%' then 'government_official'
      when source_url ilike '%reuters.com%' then 'authoritative_media'
      when source_url ilike any(array['%nvidia.com%','%aboutamazon.com%','%gf.com%','%qualcomm.com%','%xiaopeng.com%','%galactic-energy.cn%']) then 'company_official'
      when source_url ilike '%stockstar.com%' or source_url ilike '%money.finance.sina.com.cn%' then 'secondary_disclosure'
      when source_url ilike '%investing.com%' then 'market_reference'
      when coalesce(source_url,'') in ('','待补原始URL','来源链接见日报高价值信号③') then 'legacy_unverified'
      else 'industry_media'
    end as code
  from public.raw_clues where source_code is null
)
update public.raw_clues r set
  source_code=c.code,
  source_category=sr.source_category,
  source_grade=sr.official_level,
  historical_availability=case
    when sr.official_level in ('S','A') and r.published_at is not null then 'B'
    when sr.official_level in ('B','C') then 'C'
    else 'D' end,
  availability_risk=case
    when sr.official_level in ('S','A') then '当时公开，但现有记录无法证明系统在公开当日稳定采到。'
    when sr.official_level in ('B','C') then '今天能查到，但历史实时可得性较低，不能进入严格历史核心证据包。'
    else '原始来源无法确认，不能作为核心证据。' end,
  original_title=coalesce(r.original_title,r.title),
  underlying_event_id=coalesce(r.underlying_event_id,r.dedupe_key,r.external_id,r.id::text),
  positive_negative_neutral=coalesce(r.positive_negative_neutral,r.sentiment,'neutral'),
  available_at=coalesce(r.available_at,r.published_at)
from classified c join public.source_registry sr on sr.source_code=c.code
where r.id=c.id;

with classified as (
  select id,
    case
      when source_url ilike '%cninfo.com.cn%' then 'cninfo_disclosure'
      when source_url ilike '%ccgp.gov.cn%' then 'ccgp_procurement'
      when source_url ilike '%miit.gov.cn%' then 'miit_policy'
      when source_url ilike '%cnsa.gov.cn%' then 'space_agency_official'
      when source_url ilike '%gov.cn%' then 'government_official'
      when source_url ilike '%reuters.com%' then 'authoritative_media'
      when source_url ilike any(array['%nvidia.com%','%aboutamazon.com%','%gf.com%','%qualcomm.com%','%xiaopeng.com%','%galactic-energy.cn%']) then 'company_official'
      when source_url ilike '%stockstar.com%' or source_url ilike '%money.finance.sina.com.cn%' then 'secondary_disclosure'
      when source_url ilike '%investing.com%' then 'market_reference'
      when coalesce(source_url,'') in ('','待补原始URL','来源链接见日报高价值信号③') then 'legacy_unverified'
      else 'industry_media'
    end as code
  from public.signals where source_code is null
)
update public.signals s set
  source_code=c.code,
  source_name=sr.source_name,
  source_category=sr.source_category,
  source_grade=coalesce(nullif(regexp_replace(coalesce(s.source_grade,''),'[^SABCD].*$','','g'),''),sr.official_level),
  published_at=coalesce(s.published_at,s.signal_date::timestamptz),
  discovered_at=coalesce(s.discovered_at,s.created_at),
  historical_availability=case
    when sr.official_level in ('S','A') then 'B'
    when sr.official_level in ('B','C') then 'C'
    else 'D' end,
  availability_risk=case
    when sr.official_level in ('S','A') then '当时公开，但现有记录无法证明系统在公开当日稳定采到。'
    when sr.official_level in ('B','C') then '今天能查到，但历史实时可得性较低，不能进入严格历史核心证据包。'
    else '原始来源无法确认，不能作为核心证据。' end,
  original_title=coalesce(s.original_title,s.title),
  underlying_event_id=coalesce(s.underlying_event_id,s.metadata->>'dedupe_key',s.external_id,s.id::text),
  positive_negative_neutral=coalesce(s.positive_negative_neutral,s.metadata->>'direction','neutral'),
  is_official=sr.official_level in ('S','A')
from classified c join public.source_registry sr on sr.source_code=c.code
where s.id=c.id;

update public.raw_clues r set source_grade=sr.official_level
from public.source_registry sr
where r.source_code=sr.source_code and r.source_grade is null;

commit;
