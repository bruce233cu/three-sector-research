begin;

update public.profit_models p
set model_type='component',
    target_date=make_date(p.fiscal_year,12,31),
    profit_confidence='low',
    core_unconfirmed_variables='["ASP","机器人业务毛利率","费用率","2028年传统业务利润","合理估值倍数"]'::jsonb,
    max_uncertainty='机器人力学传感器ASP与独立毛利率未披露',
    most_needed_evidence='产品ASP、机器人业务毛利率、费用率及2028年传统业务利润的可追溯依据',
    updated_at=now()
from public.companies c
where p.company_id=c.id and c.name='柯力传感';

insert into public.model_parameters(profit_model_id,parameter_key,parameter_name,parameter_value,normalized_value,unit,data_type,source_name,source_url,source_published_at,evidence_grade,is_confirmed,is_inferred,is_manual_assumption,derivation_logic,source_document_id,notes)
select p.id,'company_sales_volume','公司销量',p.units,p.units,'只','manual_assumption','历史研究表情景假设',null,p.model_date,'D',false,false,true,
  '悲观/中性/乐观分别沿用1万/3万/10万只情景，仅用于框架占位，尚无公开订单或产能证据确认。',null,'待核实，不代表正式销量预测'
from public.profit_models p join public.companies c on c.id=p.company_id where c.name='柯力传感'
on conflict (profit_model_id,parameter_key) do update set parameter_value=excluded.parameter_value,normalized_value=excluded.normalized_value,updated_at=now();

insert into public.model_parameters(profit_model_id,parameter_key,parameter_name,parameter_value,normalized_value,unit,data_type,source_name,source_url,source_published_at,evidence_grade,is_confirmed,is_inferred,is_manual_assumption,derivation_logic,source_document_id,notes)
select p.id,'legacy_profit','传统业务归母净利润',3.41,3.41,'亿元','model_inference','柯力传感2025年年度报告（原模型引用，原文URL待补）',null,null,'C',false,true,false,
  '3.41亿元是2025年公司整体归母净利润历史基准，不等于2028年传统业务利润；暂保留作待验证基准，正式模型前必须替换。',null,'历史事实与未来预测严格分离'
from public.profit_models p join public.companies c on c.id=p.company_id where c.name='柯力传感'
on conflict (profit_model_id,parameter_key) do update set parameter_value=excluded.parameter_value,normalized_value=excluded.normalized_value,derivation_logic=excluded.derivation_logic,updated_at=now();

insert into public.model_parameters(profit_model_id,parameter_key,parameter_name,parameter_value,normalized_value,unit,data_type,source_name,source_url,source_published_at,evidence_grade,is_confirmed,is_inferred,is_manual_assumption,derivation_logic,notes)
select p.id,'tax_rate','税率',0.15,0.15,'%','manual_assumption','原模型暂定值',null,null,'D',false,false,true,'现有模型使用15%，尚未绑定目标年度有效税率来源。','待核实'
from public.profit_models p join public.companies c on c.id=p.company_id where c.name='柯力传感'
on conflict (profit_model_id,parameter_key) do update set parameter_value=excluded.parameter_value,normalized_value=excluded.normalized_value,updated_at=now();

insert into public.model_parameters(profit_model_id,parameter_key,parameter_name,parameter_value,normalized_value,unit,data_type,source_name,source_url,source_published_at,evidence_grade,is_confirmed,is_inferred,is_manual_assumption,derivation_logic,notes)
select p.id,x.parameter_key,x.parameter_name,null,null,x.unit,'manual_assumption',null,null,null,'D',false,false,true,'关键数据尚未取得，不参与正式计算。','待核实'
from public.profit_models p join public.companies c on c.id=p.company_id
cross join (values ('asp','ASP','元/只'),('gross_margin','机器人业务毛利率','%'),('expense_ratio','费用率','%'),('valuation_multiple','合理估值倍数','倍')) x(parameter_key,parameter_name,unit)
where c.name='柯力传感'
on conflict (profit_model_id,parameter_key) do update set parameter_value=null,normalized_value=null,derivation_logic=excluded.derivation_logic,updated_at=now();

insert into public.price_snapshots(company_id,trade_date,close_price,shares_outstanding,market_cap,source_name,source_url,source_published_at,evidence_grade,metadata)
select c.id,date '2026-09-11',46.76,2.81,131.40,'Investing.com 柯力传感历史行情','https://hk.investing.com/equities/keli-sensing-tech-ningbo-historical-data',date '2026-09-12','B',
  jsonb_build_object('migration_source','valuation_scenarios','verification_status','historical_price_requires_secondary_check')
from public.companies c where c.name='柯力传感'
on conflict (company_id,trade_date,source_name) do nothing;

select public.recalculate_profit_model(p.id)
from public.profit_models p join public.companies c on c.id=p.company_id
where c.name='柯力传感';

insert into public.model_change_log(company_id,profit_model_id,change_type,previous_state,new_state,change_reason,evidence_ids)
select p.company_id,p.id,'v3_traceability_upgrade',
  jsonb_build_object('model_type',null,'parameter_sources','embedded text only'),
  jsonb_build_object('model_type',p.model_type,'model_status',p.model_status,'missing_inputs',p.missing_inputs,'profit_confidence',p.profit_confidence),
  '将旧三情景模型升级为参数级可追溯模型；未补造缺失ASP、毛利率、费用率与估值倍数。','[]'::jsonb
from public.profit_models p join public.companies c on c.id=p.company_id
where c.name='柯力传感'
and not exists (select 1 from public.model_change_log l where l.profit_model_id=p.id and l.change_type='v3_traceability_upgrade');

commit;
