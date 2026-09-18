begin;

do $$
declare
  cid uuid;
  pm record;
  annual_url text := 'https://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-4/2026-04-28/12209189.PDF';
  half_url text := 'https://stockmc.xueqiu.com/202608/603662_20260828_DCOD.pdf';
  ir_url text := 'https://big5.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-09-17/603662_20260917_B200.pdf';
  v_volume numeric; v_asp numeric; v_gm numeric; v_exp numeric; v_legacy numeric; v_pe numeric;
  v_sell numeric; v_admin numeric; v_rnd numeric; v_fin numeric;
begin
  select id into cid from public.companies where stock_code='603662.SH';

  update public.companies set
    accounting_status='model_complete',
    accounting_blocker=null,
    profit_note='2028E三情景总归母净利润2.63/3.18/4.68亿元（低可信度）',
    odds_note='已进入动态期望收益池；当前结论以低可信度区间为准',
    market_cap=141.10,
    metadata=metadata || jsonb_build_object(
      'gaps','机器人力学传感器ASP未直接披露；2028销量、传统业务利润和估值倍数仍为推算',
      'confirmed_data','2025年机器人力学传感器销量超1500只；2026H1销量超2000只；自4月以来月订单持续超1000只；2025力学传感器系列毛利率43.29%；2025四项费用率合计25.35%',
      'profile_date','2026-09-18',
      'flow_reason','Step 4三情景已完整，概率合计100%，最新价格已入库，因此进入Step 5'
    ), updated_at=now()
  where id=cid;

  insert into public.price_snapshots(company_id,trade_date,close_price,shares_outstanding,market_cap,source_name,source_url,source_published_at,evidence_grade,metadata)
  values(cid,'2026-09-17',50.25,2.80829868,141.10,'公开行情交叉核对（东方财富/搜狐）','https://quote.eastmoney.com/sh603662.html','2026-09-18','B',jsonb_build_object('verification_status','secondary_market_quote','unit','亿元/亿股'))
  on conflict do nothing;

  for pm in select * from public.profit_models where company_id=cid and scenario in ('悲观','中性','乐观') loop
    if pm.scenario='悲观' then
      v_volume:=10000; v_asp:=2500; v_gm:=0.40; v_exp:=0.28; v_legacy:=2.60; v_pe:=30;
      v_sell:=0.085; v_admin:=0.078; v_rnd:=0.105; v_fin:=0.012;
    elsif pm.scenario='中性' then
      v_volume:=30000; v_asp:=4000; v_gm:=0.4329; v_exp:=0.2535; v_legacy:=3.00; v_pe:=40;
      v_sell:=0.0785; v_admin:=0.0739; v_rnd:=0.0915; v_fin:=0.0096;
    else
      v_volume:=100000; v_asp:=6000; v_gm:=0.47; v_exp:=0.22; v_legacy:=3.40; v_pe:=50;
      v_sell:=0.070; v_admin:=0.065; v_rnd:=0.078; v_fin:=0.007;
    end if;

    delete from public.model_parameters where profit_model_id=pm.id;
    insert into public.model_parameters(profit_model_id,parameter_key,parameter_name,parameter_value,normalized_value,unit,data_type,source_name,source_url,source_published_at,evidence_grade,is_confirmed,is_inferred,is_manual_assumption,derivation_logic,notes) values
      (pm.id,'company_sales_volume','公司销量',v_volume,v_volume,'只','manual_assumption','2025年报、2026H1半年报及9月业绩会',ir_url,'2026-09-17','D',false,false,true,'事实锚点为2025年销量>1500只、2026H1销量>2000只及4月以来月订单>1000只；2028年1/3/10万只为离散情景，不是公司指引。','销量情景假设'),
      (pm.id,'asp','机器人力学传感器ASP',v_asp,v_asp,'元/只','model_inference','柯力传感2025年年度报告',annual_url,'2026-04-28','C',false,true,false,'年报力学传感器系列收入6.1984亿元/销量253.93万只得到全系列均价约244元；机器人多维力产品复杂度显著更高，以约10/16/25倍系列均价构造2500/4000/6000元区间。未获直接报价，属于模型推算。','最大不确定性'),
      (pm.id,'gross_margin','机器人业务毛利率',v_gm,v_gm,'%',case when pm.scenario='中性' then 'reliable_reference' else 'model_inference' end,'柯力传感2025年年度报告',annual_url,'2026-04-28',case when pm.scenario='中性' then 'B' else 'C' end,pm.scenario='中性',pm.scenario<>'中性',false,'2025年力学传感器及仪表系列毛利率43.29%为直接参考；悲观/乐观在该基准上下浮动。','未直接披露机器人业务独立毛利率'),
      (pm.id,'selling_expense_ratio','销售费用率',v_sell,v_sell,'%','model_inference','柯力传感2025年年度报告',annual_url,'2026-04-28','C',false,true,false,'2025销售费用1.2231亿元/收入15.5844亿元=7.85%；按情景调整。','历史事实驱动的2028推算'),
      (pm.id,'admin_expense_ratio','管理费用率',v_admin,v_admin,'%','model_inference','柯力传感2025年年度报告',annual_url,'2026-04-28','C',false,true,false,'2025管理费用1.1516亿元/收入15.5844亿元=7.39%；按情景调整。','历史事实驱动的2028推算'),
      (pm.id,'rnd_expense_ratio','研发费用率',v_rnd,v_rnd,'%','model_inference','柯力传感2025年年度报告',annual_url,'2026-04-28','C',false,true,false,'2025研发费用1.4258亿元/收入15.5844亿元=9.15%；按情景调整。','历史事实驱动的2028推算'),
      (pm.id,'finance_expense_ratio','财务费用率',v_fin,v_fin,'%','model_inference','柯力传感2025年年度报告',annual_url,'2026-04-28','C',false,true,false,'2025财务费用0.1499亿元/收入15.5844亿元=0.96%；按情景调整。','历史事实驱动的2028推算'),
      (pm.id,'expense_ratio','四项费用率合计',v_exp,v_exp,'%','model_inference','柯力传感2025年年度报告',annual_url,'2026-04-28','C',false,true,false,'中性情景沿用2025四项费用率合计25.35%；悲观/乐观反映费用刚性与规模效应。','用于增量利润公式'),
      (pm.id,'tax_rate','所得税率',0.15,0.15,'%','manual_assumption','模型统一税率假设',annual_url,'2026-04-28','D',false,false,true,'按15%情景税率计算；不是公司对2028年有效税率的承诺。','税率假设'),
      (pm.id,'legacy_profit','传统业务归母净利润',v_legacy,v_legacy,'亿元','model_inference','2025年报与2026年半年报',half_url,'2026-08-28','C',false,true,false,'2025归母净利润3.4055亿元；2026H1归母1.3069亿元、扣非1.3560亿元。综合历史基准构造2028年2.6/3.0/3.4亿元区间。','机器人业务外利润基座'),
      (pm.id,'valuation_multiple','PE估值倍数',v_pe,v_pe,'倍','model_inference','当前市值与2025年归母净利润反推',annual_url,'2026-04-28','C',false,true,false,'当前市值约141.1亿元/2025归母净利润3.4055亿元≈41.4倍；以30/40/50倍覆盖估值收缩、维持与成长溢价。','非公司指引');

    update public.profit_models set
      units=v_volume,asp=v_asp,gross_margin=v_gm,expense_ratio=v_exp,tax_rate=0.15,legacy_profit=v_legacy,
      pe_multiple=v_pe,reference_market_cap=141.10,model_type='component',model_version=2,target_date='2028-12-31',
      profit_confidence='low',max_uncertainty='ASP未直接披露，2028销量与估值倍数为情景推算',
      most_needed_evidence='机器人业务独立收入/销量/毛利率披露与可验证客户批量交付',
      core_unconfirmed_variables='["ASP","2028销量","机器人独立毛利率","2028传统业务利润","估值倍数"]'::jsonb,
      assumptions='事实、可靠参考、模型推算与人工假设共同构成区间；低可信度不等于不可计算',
      evidence='2025年报、2026年半年报、2026-09-17业绩说明会公告',updated_at=now()
    where id=pm.id;
    perform public.recalculate_profit_model(pm.id);
  end loop;

  update public.probability_assessments set superseded_at=now() where company_id=cid and superseded_at is null;
  insert into public.probability_assessments(company_id,profit_model_id,scenario,target_event,probability_pct,probability_confidence,rule_score,mapped_probability_pct,evidence_basis,rationale,assessment_version,effective_at)
  select cid,pmodel.id,pmodel.scenario,
    case pmodel.scenario when '悲观' then '2028年销量约1万只、价格和毛利承压' when '中性' then '2028年销量约3万只、毛利率接近现有力学传感器系列' else '2028年销量约10万只并形成规模效应' end,
    case pmodel.scenario when '悲观' then 30 when '中性' then 40 else 30 end,
    'low',case pmodel.scenario when '悲观' then 4 when '中性' then 5 else 4 end,
    case pmodel.scenario when '悲观' then 30 when '中性' then 40 else 30 end,
    jsonb_build_array(
      jsonb_build_object('dimension','行业需求','evidence','机器人力学传感器从研发验证进入小批量到批量化过渡','source',ir_url),
      jsonb_build_object('dimension','客户/订单','evidence','90余家送样；自4月以来月订单持续超1000只；交付存在标定、检测、验收周期','source',ir_url),
      jsonb_build_object('dimension','ASP/毛利率','evidence','ASP未直接披露；力学传感器系列毛利率43.29%仅作参考','source',annual_url),
      jsonb_build_object('dimension','产能/交付','evidence','公司表示具备生产准备与快速响应能力，但未披露精确产能','source',ir_url),
      jsonb_build_object('dimension','竞争格局','evidence','未获得可量化份额数据，维持低可信度','source',ir_url)
    ),
    '按需求、订单、交付、ASP、毛利率、产能与竞争七类证据离散映射；因ASP、份额和精确产能未披露，概率可信度为低。',1,'2026-09-18 08:00:00+00'
  from public.profit_models pmodel where pmodel.company_id=cid and pmodel.scenario in ('悲观','中性','乐观');

  perform public.recalculate_expected_return(cid,'2026-09-17');
end $$;

commit;
