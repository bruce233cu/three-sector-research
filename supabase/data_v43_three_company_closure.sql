begin;

do $$
declare
  cid uuid;
  pm record;
  v_revenue numeric;
  v_gm numeric;
  v_exp numeric;
  v_legacy numeric;
  v_pe numeric;
  v_projects numeric;
  v_project_value numeric;
  v_share numeric;
  v_recognition numeric;
begin
  select id into cid from public.companies where stock_code='300775.SZ';
  for pm in select * from public.profit_models where company_id=cid and scenario in ('悲观','中性','乐观') loop
    update public.profit_models set model_version=2,model_status='draft',status='建模中',model_type='project',target_date='2028-12-31',
      reference_market_cap=(select market_cap from public.price_snapshots where company_id=cid order by trade_date desc,captured_at desc limit 1),
      profit_confidence='low',max_uncertainty='商业航天订单金额、收入确认节奏和独立毛利率尚未披露',
      most_needed_evidence='可归属商业航天的订单金额、交付节奏和分业务毛利率',
      core_unconfirmed_variables='["商业航天项目数量","单项目价值","公司份额","收入确认比例","独立毛利率","估值倍数"]'::jsonb,
      assumptions='2025年归母净利润3.89亿元是历史基准；2028商业航天增量全部是明确标注的情景推算，不是公司承诺。',
      evidence='三角防务2025年年度报告历史利润基准；商业航天参数仍待公司公告或订单验证。',updated_at=now()
    where id=pm.id;

    if pm.scenario='悲观' then
      v_projects:=2;v_project_value:=200000000;v_share:=0.30;v_recognition:=0.50;v_gm:=0.25;v_exp:=0.15;v_legacy:=3.00;v_pe:=20;
    elsif pm.scenario='中性' then
      v_projects:=5;v_project_value:=300000000;v_share:=0.40;v_recognition:=0.70;v_gm:=0.32;v_exp:=0.12;v_legacy:=3.89;v_pe:=28;
    else
      v_projects:=10;v_project_value:=500000000;v_share:=0.50;v_recognition:=0.80;v_gm:=0.38;v_exp:=0.10;v_legacy:=4.50;v_pe:=35;
    end if;

    delete from public.model_parameters where profit_model_id=pm.id;
    insert into public.model_parameters(profit_model_id,parameter_key,parameter_name,parameter_value,normalized_value,unit,data_type,source_name,source_url,source_published_at,evidence_grade,is_confirmed,is_inferred,is_manual_assumption,derivation_logic,notes) values
      (pm.id,'project_count','商业航天项目数量',v_projects,v_projects,'个','manual_assumption','2028情景假设',null,null,'D',false,false,true,'用于覆盖小批验证、规模交付和明显放量三种情景；不是公司披露的订单数量。','最大不确定性之一'),
      (pm.id,'project_value','单项目总价值',v_project_value,v_project_value,'元','manual_assumption','2028情景假设',null,null,'D',false,false,true,'项目总价值用于情景计算，不代表三角防务可以取得全部价值。','人工假设'),
      (pm.id,'company_share','公司可取得份额',v_share,v_share,'%','manual_assumption','2028情景假设',null,null,'D',false,false,true,'按锻件和结构件环节可能取得的价值比例构造区间。','人工假设'),
      (pm.id,'recognition_ratio','目标年度收入确认比例',v_recognition,v_recognition,'%','manual_assumption','2028情景假设',null,null,'D',false,false,true,'反映订单到收入存在生产、验收和交付周期。','人工假设'),
      (pm.id,'gross_margin','商业航天增量毛利率',v_gm,v_gm,'%','model_inference','2025年年度报告历史业务参考','https://www.cninfo.com.cn/new/disclosure/stock?stockCode=300775','2026-04-01','C',false,true,false,'公司没有单独披露商业航天毛利率，以历史业务和规模差异构造区间。','不能当作公司事实'),
      (pm.id,'expense_ratio','增量费用率',v_exp,v_exp,'%','model_inference','2025年年度报告历史费用参考','https://www.cninfo.com.cn/new/disclosure/stock?stockCode=300775','2026-04-01','C',false,true,false,'按规模效应构造悲观到乐观区间。','不能当作公司事实'),
      (pm.id,'tax_rate','所得税率',0.15,0.15,'%','manual_assumption','统一税率假设',null,null,'D',false,false,true,'统一使用15%情景税率。','人工假设'),
      (pm.id,'legacy_profit','传统业务归母净利润',v_legacy,v_legacy,'亿元',case when pm.scenario='中性' then 'reliable_reference' else 'model_inference' end,'三角防务2025年年度报告','https://www.cninfo.com.cn/new/disclosure/stock?stockCode=300775','2026-04-01',case when pm.scenario='中性' then 'B' else 'C' end,pm.scenario='中性',pm.scenario<>'中性',false,'2025年归母净利润3.89亿元是历史锚点；悲观和乐观是2028情景推算。','历史事实与未来预测分开'),
      (pm.id,'valuation_multiple','PE估值倍数',v_pe,v_pe,'倍','manual_assumption','2028估值情景',null,null,'D',false,false,true,'临时估值区间，待历史盲测校准。','待历史校准');
    update public.profit_models set pe_multiple=v_pe where id=pm.id;
    perform public.recalculate_profit_model(pm.id);
  end loop;

  update public.companies set accounting_status='model_complete',accounting_blocker=null,valuation_status='completed',shadow_stage='investment_value',
    profit_note='2028E三情景模型已完成，全部商业航天增量参数均为低可信度情景假设',
    odds_note='已完成投资价值评估；是否通过由统一门槛决定',updated_at=now() where id=cid;

  update public.probability_assessments set superseded_at=now() where company_id=cid and superseded_at is null;
  insert into public.probability_assessments(company_id,profit_model_id,scenario,target_event,probability_pct,probability_confidence,rule_score,mapped_probability_pct,evidence_basis,rationale,assessment_version,effective_at)
  select cid,p.id,p.scenario,case p.scenario when '悲观' then '商业航天订单兑现慢，传统业务利润回落' when '中性' then '商业航天逐步贡献收入，传统业务保持2025年利润水平' else '星箭批量制造明显放量并形成规模效应' end,
    case p.scenario when '悲观' then 30 when '中性' then 50 else 20 end,'low',case p.scenario when '中性' then 4 else 3 end,
    case p.scenario when '悲观' then 30 when '中性' then 50 else 20 end,
    jsonb_build_array(jsonb_build_object('dimension','历史利润','evidence','2025年归母净利润3.89亿元为历史锚点','source','https://www.cninfo.com.cn/new/disclosure/stock?stockCode=300775'),jsonb_build_object('dimension','订单归属','evidence','商业航天订单金额和利润尚未单独披露','source',null)),
    '有历史利润基准，但缺少可归属商业航天订单、交付和毛利率，因此概率可信度为低。',2,now()
  from public.profit_models p where p.company_id=cid;

  insert into public.company_timeline_events(company_id,event_at,event_type,title,description,evidence_level,data_type,change_driver,change_reason,system_status,model_version,current_state)
  select cid,min(oc.created_at),'formal_pool','公司映射进入建模','现有机会映射记录确认三角防务为星箭批量制造相关上市公司，随后建立三情景模型。','C','reliable_reference','initial','来自真实机会—公司映射记录，不补造更早日期。','公司建模',1,jsonb_build_object('opportunity','星箭批量制造/西部航天超级工厂')
  from public.opportunity_companies oc where oc.company_id=cid
  and not exists(select 1 from public.company_timeline_events e where e.company_id=cid and e.title='公司映射进入建模');

  insert into public.company_timeline_events(company_id,event_at,event_type,title,description,evidence_level,data_type,change_driver,change_reason,system_status,model_version,current_state,is_model_revision)
  select cid,now(),'model_revision','三情景模型首次完整冻结','完成悲观、中性、乐观利润、概率与估值；商业航天增量输入全部明确标为人工假设或模型推算。','D','model_inference','model_revision','原模型只有空壳，无法进入投资价值计算。','模型完成',2,jsonb_build_object('profit_confidence','low','probability_confidence','low'),true
  where not exists(select 1 from public.company_timeline_events e where e.company_id=cid and e.title='三情景模型首次完整冻结');

  perform public.recalculate_expected_return(cid,current_date);
end $$;

do $$
declare
  cid uuid;
  pm record;
  v_revenue numeric;
  v_gm numeric;
  v_exp numeric;
  v_legacy numeric;
  v_pe numeric;
begin
  select id into cid from public.companies where stock_code='301232.SZ';
  for pm in select * from public.profit_models where company_id=cid and scenario in ('悲观','中性','乐观') loop
    update public.profit_models set model_version=2,model_status='draft',status='建模中',model_type='custom',target_date='2028-12-31',
      reference_market_cap=(select market_cap from public.price_snapshots where company_id=cid order by trade_date desc,captured_at desc limit 1),
      profit_confidence='low',max_uncertainty='商业航天收入基数很小，订单、ASP和独立毛利率均未披露',
      most_needed_evidence='商业航天客户、订单金额、交付数量和分业务毛利率',
      core_unconfirmed_variables='["商业航天收入","独立毛利率","费用率","传统业务利润","估值倍数"]'::jsonb,
      assumptions='2025年商业航天收入约123万元只作为低基数事实；2028收入全部是情景推算，不是公司指引。',
      evidence='飞沃科技2025年年度报告和风险提示中的历史收入、利润及商业航天收入占比。',updated_at=now()
    where id=pm.id;

    if pm.scenario='悲观' then v_revenue:=0.05;v_gm:=0.12;v_exp:=0.14;v_legacy:=0.20;v_pe:=25;
    elsif pm.scenario='中性' then v_revenue:=0.50;v_gm:=0.17;v_exp:=0.12;v_legacy:=0.378;v_pe:=35;
    else v_revenue:=2.00;v_gm:=0.25;v_exp:=0.10;v_legacy:=0.70;v_pe:=45;
    end if;

    delete from public.model_parameters where profit_model_id=pm.id;
    insert into public.model_parameters(profit_model_id,parameter_key,parameter_name,parameter_value,normalized_value,unit,data_type,source_name,source_url,source_published_at,evidence_grade,is_confirmed,is_inferred,is_manual_assumption,derivation_logic,notes) values
      (pm.id,'revenue','商业航天增量收入',v_revenue,v_revenue,'亿元','manual_assumption','2028情景假设',null,null,'D',false,false,true,'以2025年约123万元低基数为起点构造0.05/0.50/2.00亿元情景，不是公司指引。','最大不确定性'),
      (pm.id,'gross_margin','商业航天增量毛利率',v_gm,v_gm,'%','model_inference','2025年年度报告紧固件业务参考','https://www.cninfo.com.cn/new/disclosure/stock?stockCode=301232','2026-04-01','C',false,true,false,'公司未披露商业航天独立毛利率，以紧固件历史毛利率附近构造区间。','不能当作公司事实'),
      (pm.id,'expense_ratio','增量费用率',v_exp,v_exp,'%','model_inference','2025年年度报告历史费用参考','https://www.cninfo.com.cn/new/disclosure/stock?stockCode=301232','2026-04-01','C',false,true,false,'按规模效应构造区间。','不能当作公司事实'),
      (pm.id,'tax_rate','所得税率',0.15,0.15,'%','manual_assumption','统一税率假设',null,null,'D',false,false,true,'统一使用15%情景税率。','人工假设'),
      (pm.id,'legacy_profit','传统业务归母净利润',v_legacy,v_legacy,'亿元',case when pm.scenario='中性' then 'reliable_reference' else 'model_inference' end,'飞沃科技2025年年度报告','https://www.cninfo.com.cn/new/disclosure/stock?stockCode=301232','2026-04-01',case when pm.scenario='中性' then 'B' else 'C' end,pm.scenario='中性',pm.scenario<>'中性',false,'2025年归母净利润0.378亿元是历史锚点；悲观和乐观为2028推算。','历史事实与未来预测分开'),
      (pm.id,'valuation_multiple','PE估值倍数',v_pe,v_pe,'倍','manual_assumption','2028估值情景',null,null,'D',false,false,true,'低基数高波动公司临时估值区间，待历史盲测校准。','待历史校准');
    update public.profit_models set pe_multiple=v_pe where id=pm.id;
    perform public.recalculate_profit_model(pm.id);
  end loop;

  update public.companies set accounting_status='model_complete',accounting_blocker=null,valuation_status='completed',shadow_stage='investment_value',
    profit_note='2028E三情景模型已完成，商业航天仍是低基数、低可信度推算',odds_note='已完成投资价值评估；是否通过由统一门槛决定',updated_at=now() where id=cid;

  update public.probability_assessments set superseded_at=now() where company_id=cid and superseded_at is null;
  insert into public.probability_assessments(company_id,profit_model_id,scenario,target_event,probability_pct,probability_confidence,rule_score,mapped_probability_pct,evidence_basis,rationale,assessment_version,effective_at)
  select cid,p.id,p.scenario,case p.scenario when '悲观' then '商业航天继续停留在验证期，传统业务承压' when '中性' then '商业航天收入从低基数逐步增长但仍非主业' else '商业航天进入批量交付并贡献可见利润' end,
    case p.scenario when '悲观' then 40 when '中性' then 50 else 10 end,'low',case p.scenario when '中性' then 3 else 2 end,
    case p.scenario when '悲观' then 40 when '中性' then 50 else 10 end,
    jsonb_build_array(jsonb_build_object('dimension','历史利润','evidence','2025年归母净利润0.378亿元为历史锚点','source','https://www.cninfo.com.cn/new/disclosure/stock?stockCode=301232'),jsonb_build_object('dimension','商业航天基数','evidence','2025年相关收入约123万元、占比约0.05%','source','https://www.cninfo.com.cn/new/disclosure/stock?stockCode=301232')),
    '商业航天收入已有事实基数但规模很小，缺少订单和独立毛利率，乐观情景概率保持较低。',2,now()
  from public.profit_models p where p.company_id=cid;

  insert into public.company_timeline_events(company_id,event_at,event_type,title,description,evidence_level,data_type,change_driver,change_reason,system_status,model_version,current_state)
  select cid,min(oc.created_at),'formal_pool','公司映射进入建模','现有机会映射记录确认飞沃科技与可重复使用液体火箭产业化相关，随后建立独立模型。','C','reliable_reference','initial','来自真实机会—公司映射记录，不补造更早日期。','公司建模',1,jsonb_build_object('opportunity','可重复使用液体火箭产业化')
  from public.opportunity_companies oc where oc.company_id=cid
  and not exists(select 1 from public.company_timeline_events e where e.company_id=cid and e.title='公司映射进入建模');

  insert into public.company_timeline_events(company_id,event_at,event_type,title,description,evidence_level,data_type,change_driver,change_reason,system_status,model_version,current_state,is_model_revision)
  select cid,now(),'model_revision','三情景模型首次完整冻结','完成悲观、中性、乐观利润、概率与估值；商业航天收入情景明确标为人工假设。','D','model_inference','model_revision','原模型只有空壳，无法进入投资价值计算。','模型完成',2,jsonb_build_object('profit_confidence','low','probability_confidence','low'),true
  where not exists(select 1 from public.company_timeline_events e where e.company_id=cid and e.title='三情景模型首次完整冻结');

  perform public.recalculate_expected_return(cid,current_date);
end $$;

-- Append new decisions; never update V4.2 decisions.
insert into public.screening_decisions(object_type,object_id,object_name,stage,decision,reason,next_step,rule_version,evaluated_at,metadata)
select 'company',c.id,c.name,'company_modeling','pass','三情景利润、估值和概率已完整生成，但可信度仍低。','进入投资价值评估，并继续补订单、收入和毛利率证据。','V4.3',now(),jsonb_build_object('model_version',2,'profit_confidence','low')
from public.companies c where c.name in ('三角防务','飞沃科技');

insert into public.screening_decisions(object_type,object_id,object_name,stage,decision,reason,next_step,rule_version,evaluated_at,metadata)
select 'investment',i.id,c.name,'investment_value','evaluated','已使用冻结模型版本、同日价格和股本完成投资价值计算。',coalesce(array_to_string(i.failure_reasons,'；'),'持续跟踪'), 'V4.3',i.assessed_at,jsonb_build_object('company_id',c.id,'expected_return_snapshot_id',i.expected_return_snapshot_id,'classification',i.classification)
from public.investment_assessments i join public.companies c on c.id=i.company_id
where c.name in ('三角防务','飞沃科技') and i.assessed_at=(select max(i2.assessed_at) from public.investment_assessments i2 where i2.company_id=i.company_id);

insert into public.screening_decisions(object_type,object_id,object_name,stage,decision,reason,next_step,rule_version,evaluated_at,metadata)
select 'investment',i.id,c.name,'high_expected_return',case when i.passed then 'pass' else 'fail' end,
  case when i.passed then '通过当前临时投资门槛。' else array_to_string(i.failure_reasons,'；') end,
  case when i.passed then '进入持续验证。' else c.reactivation_condition end,'V4.3',i.assessed_at,
  jsonb_build_object('company_id',c.id,'expected_return',i.expected_return,'risk_reward',i.risk_reward,'rule','V4-TEMP-001')
from public.investment_assessments i join public.companies c on c.id=i.company_id
where c.name in ('三角防务','飞沃科技') and i.assessed_at=(select max(i2.assessed_at) from public.investment_assessments i2 where i2.company_id=i.company_id);

commit;
