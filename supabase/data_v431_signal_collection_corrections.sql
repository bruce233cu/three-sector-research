begin;

update public.signals
set status='invalid',
    action='无效信息',
    company_name=replace(replace(company_name,'<em>',''),'</em>',''),
    metadata=metadata||jsonb_build_object(
      'screening_correction_at',now(),
      'screening_correction_reason',
      case
        when title like '%报告摘要%' or title like '%提示性公告%'
          then '同一份报告的摘要或提示公告不能重复算作独立变化。'
        when title like '%年度报告%'
          then '只知道报告已经发布，还不知道财报内容发生了什么，不能直接作为有效变化。'
        when title like '%回购注销%' or title like '%限制性股票%' or title like '%通知债权人%' or title like '%法律意见书%'
          then '股权激励回购注销属于配套程序，不能按公司主动回购利好处理。'
        when title like '%不向下修正%'
          then '“不向下修正”不能按负面下修处理。'
        else '公告标题不足以证明发生了可进入机会确认的真实变化。'
      end
    ),
    updated_at=now()
where metadata->>'source'='automated_official_disclosure'
  and title not like '%减值%';

update public.raw_clues r
set screening_status='rejected',
    rejection_reason=coalesce(
      r.rejection_reason,
      '复核后确认：公告标题不足以证明发生了可进入机会确认的真实变化。'
    ),
    company_names=array(
      select replace(replace(value,'<em>',''),'</em>','')
      from unnest(r.company_names) value
    ),
    metadata=r.metadata||jsonb_build_object(
      'screening_correction_at',now(),
      'screening_correction_reason','自动采集首次验收时发现规则过宽，已保留原始记录但不再作为有效信号。'
    )
from public.signals s
where s.raw_clue_id=r.id
  and s.metadata->>'source'='automated_official_disclosure'
  and s.status='invalid';

update public.signals
set company_name=replace(replace(company_name,'<em>',''),'</em>','')
where metadata->>'source'='automated_official_disclosure'
  and company_name like '%<em>%';

update public.raw_clues r
set company_names=array(
  select replace(replace(value,'<em>',''),'</em>','')
  from unnest(r.company_names) value
)
where r.metadata->>'source_code'='cninfo_disclosure'
  and exists(select 1 from unnest(r.company_names) value where value like '%<em>%');

commit;
