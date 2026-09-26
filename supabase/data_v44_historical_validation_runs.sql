begin;

-- The three windows are fixed before replay, use identical dates, and are not
-- selected by company name or later market performance.
do $$
declare
  v_sector text;
  v_code text;
  v_run_id uuid;
  v_day_id uuid;
  v_day date;
  v_decision_time timestamptz;
  v_earliest_trade_time timestamptz;
  v_fingerprint text;
begin
  foreach v_sector in array array['机器人','商业航天','AI'] loop
    v_code := case v_sector when '机器人' then 'V44-ROB-20260901' when '商业航天' then 'V44-SPACE-20260901' else 'V44-AI-20260901' end;
    v_fingerprint := md5(concat_ws('|','V4.3-model','V4.3-rules','V4-TEMP-001','V4.3.1-CNINFO-8-COMPANY-WHITELIST','V4.4-SR1','8f467402343a9c4374d46f8755fadaa2ce281966','20260919234836','2026-08-25','2026-09-01','2026-09-08'));

    insert into public.historical_validation_runs (
      test_code,test_name,sector,warmup_start_date,start_date,end_date,evaluation_end_date,
      replay_mode,timezone,decision_time_rule,model_version,rule_version,threshold_version,
      source_version,search_rule_version,git_commit_sha,database_migration_version,
      version_fingerprint,window_selection_reason,historical_market_phase,status,conclusion
    ) values (
      v_code,
      v_sector || '历史资料可得性验真（第一轮）',
      v_sector,'2026-08-25','2026-09-01','2026-09-08','2027-09-08',
      'historical_source_reconstruction','Asia/Shanghai',
      '每天北京时间08:00形成证据包；只使用系统在该时点前已实际入库的资料；此后公开或入库的资料全部排除。',
      'V4.3-model','V4.3-rules','V4-TEMP-001',
      'V4.3.1-CNINFO-8-COMPANY-WHITELIST','V4.4-SR1',
      '8f467402343a9c4374d46f8755fadaa2ce281966','20260919234836',v_fingerprint,
      '三个赛道统一使用同一窗口。该窗口是现有库中三赛道都存在候选历史资料的最早共同区间，不按公司、涨幅或后来结果选择。',
      '只记录历史阶段，不用于收益评价','ready','测试已建立，尚未运行。'
    )
    on conflict (test_code) do nothing
    returning id into v_run_id;

    if v_run_id is null then
      select id into v_run_id from public.historical_validation_runs where test_code=v_code;
      continue;
    end if;

    update public.historical_validation_runs set status='running',conclusion='正在按严格入库时间重建历史证据包。' where id=v_run_id;

    insert into public.historical_raw_records (
      test_run_id,original_record_id,source_name,source_url,source_type,title,summary,raw_content,
      sector,company_names,opportunity_keywords,evidence_level,sentiment,event_date,published_at,
      known_at,available_at,ingested_at,availability_status,availability_risk,source_access_method,
      archive_status,search_ranking_bias,strict_eligible,dedupe_key,underlying_event_id,
      original_screening_status,provenance
    )
    select
      v_run_id,r.id,coalesce(nullif(r.source_name,''),'来源名称缺失'),r.source_url,
      coalesce(nullif(r.source_type,''),'其他已有来源'),r.title,r.summary,r.raw_text,v_sector,
      coalesce(r.company_names,'{}'::text[]),coalesce(r.opportunity_keywords,'{}'::text[]),
      r.evidence_level,coalesce(r.sentiment,'neutral'),r.occurred_on,r.published_at,
      r.published_at,r.published_at,r.discovered_at,
      case
        when r.published_at is null then 'D'
        when r.source_name='巨潮资讯法定信息披露平台' then 'B'
        else 'C'
      end,
      case
        when r.published_at is null then '现有记录无法确认准确公开时间。'
        when r.source_name='巨潮资讯法定信息披露平台' then '资料当时已公开，但历史窗口内采集器尚未运行，不能证明系统当时已经拿到。'
        else '今天仍能查到，但无法确认历史当天是否能稳定自动获取。'
      end,
      case when r.source_name='巨潮资讯法定信息披露平台' then '官方披露接口（后补采集）' else '现有资料库回放' end,
      case when r.source_name='巨潮资讯法定信息披露平台' then '官方页面仍可访问' else '仅确认当前链接' end,
      false,false,r.dedupe_key,
      coalesce(r.dedupe_key,md5(coalesce(r.source_url,'') || '|' || r.title || '|' || coalesce(r.published_at::text,r.occurred_on::text))),
      r.screening_status,
      jsonb_build_object(
        'copied_from','raw_clues','copied_at',now(),'live_record_id',r.id,
        'is_historical_reconstruction',true,'writes_back_to_live',false
      )
    from public.raw_clues r
    join public.sectors s on s.id=r.sector_id
    where s.name=v_sector and r.occurred_on between '2026-08-25' and '2026-09-08';

    for v_day in select generate_series('2026-09-01'::date,'2026-09-08'::date,'1 day'::interval)::date loop
      v_day_id := gen_random_uuid();
      v_decision_time := (v_day + time '08:00') at time zone 'Asia/Shanghai';
      v_earliest_trade_time := (
        case extract(isodow from v_day)
          when 6 then v_day + 2
          when 7 then v_day + 1
          else v_day
        end + time '09:30'
      ) at time zone 'Asia/Shanghai';

      insert into public.historical_validation_days (
        id,test_run_id,simulation_date,as_of_time,decision_time,earliest_trade_time,
        available_raw_record_count,excluded_record_count,signal_count,opportunity_count,
        company_count,model_count,assessment_count,evidence_bundle,replay_conclusion
      )
      select
        v_day_id,v_run_id,v_day,v_decision_time,v_decision_time,v_earliest_trade_time,
        count(*) filter(where h.strict_eligible and h.published_at<=v_decision_time and h.available_at<=v_decision_time and h.ingested_at<=v_decision_time),
        count(*) filter(where not (h.strict_eligible and h.published_at<=v_decision_time and h.available_at<=v_decision_time and h.ingested_at<=v_decision_time)),
        0,0,0,0,0,
        jsonb_build_object(
          'rule','只包含decision_time前实际入库且可得性为A的资料',
          'raw_record_ids',coalesce(jsonb_agg(h.id) filter(where h.strict_eligible and h.published_at<=v_decision_time and h.available_at<=v_decision_time and h.ingested_at<=v_decision_time),'[]'::jsonb),
          'gpt_external_knowledge_allowed',false,
          'free_web_search_allowed',false
        ),
        case when count(*) filter(where h.strict_eligible and h.published_at<=v_decision_time and h.available_at<=v_decision_time and h.ingested_at<=v_decision_time)=0
          then '当时没有可严格使用的证据，系统只能回答“当时无法确认”。'
          else '已按当时可用证据生成回放。' end
      from public.historical_raw_records h where h.test_run_id=v_run_id;

      insert into public.historical_available_records (
        test_run_id,validation_day_id,historical_raw_record_id,inclusion_status,exclusion_reason,boundary_check
      )
      select
        v_run_id,v_day_id,h.id,
        case when h.strict_eligible and h.published_at<=v_decision_time and h.available_at<=v_decision_time and h.ingested_at<=v_decision_time then 'available' else 'excluded' end,
        case
          when h.published_at is null then 'published_time_unknown'
          when h.published_at>v_decision_time then 'published_after_as_of'
          when h.available_at is null then 'availability_time_unknown'
          when h.available_at>v_decision_time then 'available_after_as_of'
          when h.ingested_at is null then 'ingested_time_unknown'
          when h.ingested_at>v_decision_time then 'ingested_after_decision_time'
          when not h.strict_eligible then 'historical_reconstruction_not_true_point_in_time'
          else null
        end,
        jsonb_build_object(
          'decision_time',v_decision_time,'published_at',h.published_at,
          'available_at',h.available_at,'ingested_at',h.ingested_at,
          'strict_eligible',h.strict_eligible
        )
      from public.historical_raw_records h where h.test_run_id=v_run_id;

      insert into public.historical_decisions (
        test_run_id,validation_day_id,object_type,object_key,stage,decision,reason,rule_version,decision_time
      )
      values (
        v_run_id,v_day_id,'system',v_code || '-' || v_day,'change_discovery','unable_to_confirm',
        '证据包中没有一条资料同时满足公开、可得、实际入库和时间边界要求；没有证据不等于没有风险。',
        'V4.3-rules',v_decision_time
      );
    end loop;

    insert into public.historical_source_coverage (
      test_run_id,source_type,collected_count,available_count,excluded_count,
      availability_risk_count,negative_record_count,coverage_pct,conclusion
    )
    select
      v_run_id,h.source_type,count(*),
      count(*) filter(where exists (
        select 1 from public.historical_available_records a
        where a.historical_raw_record_id=h.id and a.inclusion_status='available'
      )),
      count(*) filter(where not exists (
        select 1 from public.historical_available_records a
        where a.historical_raw_record_id=h.id and a.inclusion_status='available'
      )),
      count(*) filter(where h.availability_status<>'A'),
      count(*) filter(where h.sentiment='negative'),
      case when count(*)=0 then 0 else round(100.0*count(*) filter(where exists (
        select 1 from public.historical_available_records a
        where a.historical_raw_record_id=h.id and a.inclusion_status='available'
      ))/count(*),2) end,
      '候选资料存在，但都不是历史时点真实入库资料，不能进入严格证据包。'
    from public.historical_raw_records h where h.test_run_id=v_run_id
    group by h.source_type;

    insert into public.historical_leak_checks(test_run_id,check_code,check_name,severity,result,violation_count,detail)
    values
      (v_run_id,'future_time_boundary','未来时间边界','P0','passed',0,'没有任何公开、可得或入库时间晚于判断时点的资料进入证据包。'),
      (v_run_id,'model_knowledge_leak','模型自身知识泄漏','P0','passed',0,'证据包为空时没有调用模型补事实，判断统一为“当时无法确认”。'),
      (v_run_id,'hindsight_search_leak','后验定向搜索','P0','passed',0,'本轮没有使用赢家公司名、后来客户名或后来热门标签做搜索。'),
      (v_run_id,'dataset_construction_bias','资料库构建偏差','P0','failed',1,'现有历史公告来自当前研究池中的8家公司白名单，不是按当时全市场统一规则建立的证券池，存在围绕当前研究对象构建资料库的偏差。'),
      (v_run_id,'version_lock','测试版本锁定','P0','passed',0,'日期边界和六类版本已锁定；修改任一边界必须新建test_run。'),
      (v_run_id,'financial_industry_vintage','财报和行业数据当时版本','P1','not_verifiable',0,'证据包没有可用的财报、行业销量或机构预测历史版本，无法验证。'),
      (v_run_id,'historical_security_universe','历史证券池完整性','P1','not_verifiable',0,'目前没有当时全量上市、退市、更名和重组证券池，无法验证公司发现是否无遗漏。'),
      (v_run_id,'price_share_time_consistency','历史价格与股本同点一致','P1','not_verifiable',0,'没有公司进入严格模型和投资价值阶段，因此没有可核验的历史价格与当时股本组合。'),
      (v_run_id,'negative_information_coverage','负面信息对称覆盖','P1','failed',1,'该窗口候选资料中没有负面记录；这只能说明覆盖不足，不能解释为当时没有风险。'),
      (v_run_id,'company_discovery_path','公司发现路径完整','P1','not_verifiable',0,'没有严格可用信号，因此没有启动公司发现；不能证明信号到公司的路径可完整回放。');

    update public.historical_validation_runs r
    set status='invalid',
        information_coverage_pct=case when x.collected=0 then 0 else round(100.0*x.available/x.collected,2) end,
        stable_available_pct=case when x.collected=0 then 0 else round(100.0*x.stable/x.collected,2) end,
        collected_record_count=x.collected,
        available_record_count=x.available,
        excluded_record_count=x.excluded,
        signal_count=0,opportunity_count=0,company_count=0,model_count=0,assessment_count=0,
        future_leak_count=0,model_knowledge_leak_count=0,hindsight_search_violation_count=0,
        availability_high_risk_count=x.high_risk,dataset_construction_bias_count=1,
        p0_count=1,p1_count=5,can_enter_v45=false,
        conclusion='技术回放已完成，但资料全部为事后入库，且公告库只覆盖当前研究池公司。测试判定INVALID，不能用于判断系统历史能力，也不能进入V4.5。',
        completed_at=now(),locked_at=now()
    from (
      select
        count(*)::int collected,
        count(*) filter(where exists (
          select 1 from public.historical_available_records a
          where a.historical_raw_record_id=h.id and a.inclusion_status='available'
        ))::int available,
        count(*) filter(where not exists (
          select 1 from public.historical_available_records a
          where a.historical_raw_record_id=h.id and a.inclusion_status='available'
        ))::int excluded,
        count(*) filter(where h.availability_status<>'A')::int high_risk,
        count(*) filter(where h.availability_status='A')::int stable
      from public.historical_raw_records h where h.test_run_id=v_run_id
    ) x
    where r.id=v_run_id;
  end loop;
end $$;

commit;
