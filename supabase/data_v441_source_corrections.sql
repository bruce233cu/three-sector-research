begin;

insert into public.source_registry(
  source_code,source_name,source_category,official_level,source_url,source_type,
  sector_scope,data_scope,access_method,requires_login,historical_accessible,
  historical_validation_support,update_frequency,priority,status,automation_enabled,notes
) values (
  'local_government','地方政府与地方主管部门','policy','S',
  'https://www.gov.cn/home/2023-03/29/content_5748953.htm','地方政府正式信息',
  array['机器人','商业航天','AI'],array['地方产业项目','园区建设','企业落地','地方政策'],
  '分散公开网页',false,true,'partial','不定期',2,'unconfigured',false,
  '已有真实地方政府资料，但尚未形成统一自动采集入口。'
) on conflict(source_code) do update set
  source_name=excluded.source_name,source_category=excluded.source_category,
  official_level=excluded.official_level,source_url=excluded.source_url,
  source_type=excluded.source_type,sector_scope=excluded.sector_scope,
  data_scope=excluded.data_scope,access_method=excluded.access_method,
  historical_accessible=excluded.historical_accessible,
  historical_validation_support=excluded.historical_validation_support,
  status=excluded.status,automation_enabled=excluded.automation_enabled,notes=excluded.notes,
  updated_at=now();

insert into public.source_health(
  source_code,source_name,source_type,status,last_error,last_run_message,metadata
) values (
  'local_government','地方政府与地方主管部门','policy','not_configured',
  '已有人工采集资料，但尚未配置统一自动采集。',
  '来源已登记，不冒充自动运行。',
  jsonb_build_object('registry_seed',true,'category','policy','automation_enabled',false)
) on conflict(source_code) do nothing;

update public.raw_clues set source_code='local_government'
where source_code='gov_policy' and source_name ilike '%松江%';

update public.signals s set source_code='local_government'
from public.raw_clues r where s.raw_clue_id=r.id and r.source_code='local_government';

update public.raw_clues set
  occurred_on='2026-09-15',
  published_at='2026-09-15T10:00:00+08:00',
  available_at='2026-09-15T10:00:00+08:00'
where source_code='nbs_industry' and title in (
  '8月份国民经济运行平稳、发展向新向优',
  '2026年8月份规模以上工业增加值增长5.2%',
  '2026年1—8月份全国固定资产投资基本情况'
);

update public.signals s set
  signal_date='2026-09-15',
  published_at='2026-09-15T10:00:00+08:00'
from public.raw_clues r
where s.raw_clue_id=r.id and r.source_code='nbs_industry';

update public.raw_clues set
  screening_status='rejected',
  current_status='invalid',
  rejection_reason='只在统计口径说明中出现“卫星传输服务”，不能证明商业航天产业发生变化。',
  sentiment='neutral',
  positive_negative_neutral='neutral',
  opportunity_keywords='{}'::text[],
  metadata=metadata||jsonb_build_object(
    'screening_correction','V4.4.1首次运行发现宽关键词误判，已保留原记录并标记无效。',
    'is_real_change',false
  )
where source_code='nbs_industry' and title='2026年1—8月份全国固定资产投资基本情况';

update public.signals s set
  status='invalid',
  action='无效信息',
  positive_negative_neutral='neutral',
  verification_needed='已核对：命中来自统计口径定义，不构成三大赛道真实变化。',
  metadata=s.metadata||jsonb_build_object(
    'screening_correction','V4.4.1首次运行发现宽关键词误判，信号已标记无效。'
  )
from public.raw_clues r
where s.raw_clue_id=r.id
  and r.source_code='nbs_industry'
  and r.title='2026年1—8月份全国固定资产投资基本情况';

update public.raw_clues set
  sector_id=(select id from public.sectors where name='机器人'),
  sentiment='positive',
  positive_negative_neutral='positive',
  opportunity_keywords=array['工业机器人','服务机器人']::text[]
where source_code='nbs_industry' and title in (
  '8月份国民经济运行平稳、发展向新向优',
  '2026年8月份规模以上工业增加值增长5.2%'
);

update public.signals s set
  sector_id=(select id from public.sectors where name='机器人'),
  positive_negative_neutral='positive',
  metadata=s.metadata||jsonb_build_object('direction','positive')
from public.raw_clues r
where s.raw_clue_id=r.id
  and r.source_code='nbs_industry'
  and r.title in (
    '8月份国民经济运行平稳、发展向新向优',
    '2026年8月份规模以上工业增加值增长5.2%'
  );

update public.source_category_coverage_daily c set
  raw_record_count=(
    select count(*) from public.raw_clues r
    where r.discovered_at::date=c.coverage_date
      and r.sector_id=c.sector_id
      and r.source_category=c.source_category
      and coalesce(r.screening_status,'')<>'rejected'
  ),
  signal_count=(
    select count(*) from public.signals s
    where s.discovered_at::date=c.coverage_date
      and s.sector_id=c.sector_id
      and s.source_category=c.source_category
      and coalesce(s.status,'')<>'invalid'
  ),
  negative_record_count=(
    select count(*) from public.raw_clues r
    where r.discovered_at::date=c.coverage_date
      and r.sector_id=c.sector_id
      and r.source_category=c.source_category
      and coalesce(r.screening_status,'')<>'rejected'
      and r.sentiment='negative'
  ),
  coverage_status=case
    when c.healthy_source_count=0 then 'missing'
    when exists(
      select 1 from public.raw_clues r
      where r.discovered_at::date=c.coverage_date
        and r.sector_id=c.sector_id
        and r.source_category=c.source_category
        and coalesce(r.screening_status,'')<>'rejected'
    ) then 'covered'
    else 'partial'
  end,
  notes=case
    when c.healthy_source_count=0 then '自动来源未成功检查，当前覆盖不足。'
    when exists(
      select 1 from public.raw_clues r
      where r.discovered_at::date=c.coverage_date
        and r.sector_id=c.sector_id
        and r.source_category=c.source_category
        and coalesce(r.screening_status,'')<>'rejected'
    ) then '来源已成功检查，并取得该赛道的真实记录。'
    else '来源已成功检查，但今天没有该赛道新增；不能解释成产业没有变化。'
  end
where c.coverage_date='2026-09-20';

commit;
