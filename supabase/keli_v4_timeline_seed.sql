begin;

do $$
declare
  cid uuid;
  eid uuid;
  er public.expected_return_snapshots%rowtype;
  s jsonb;
begin
  select id into cid from public.companies where stock_code='603662.SH';
  select * into er from public.expected_return_snapshots where company_id=cid order by trade_date desc,calculated_at desc limit 1;
  s:=er.scenario_results;

  if not exists (select 1 from public.company_timeline_events where company_id=cid and event_type='formal_pool' and title='首次正式入池') then
    insert into public.company_timeline_events(company_id,event_at,event_type,title,description,evidence_level,data_type,change_driver,change_reason,system_status,model_version,previous_state,current_state)
    values(cid,'2026-09-17 08:40:18+00','formal_pool','首次正式入池','由机器人力学传感器订单和客户验证信号进入公司研究池；当时尚未形成完整利润与期望收益。','B','reliable_reference','initial','公司穿透证据达到入池标准，但利润模型仍缺ASP、毛利率、费用率和估值。','Step 4待核算',1,'{}'::jsonb,jsonb_build_object('accounting_status','model_blocked','expected_return',null));
  end if;

  if not exists (select 1 from public.company_timeline_events where company_id=cid and event_type='price_change' and event_at='2026-09-17 08:00:00+00') then
    insert into public.company_timeline_events(company_id,event_at,event_type,title,description,source_url,source_publish_date,evidence_level,data_type,price,shares_outstanding,market_cap,previous_state,current_state,change_driver,change_reason,system_status,model_version)
    values(cid,'2026-09-17 08:00:00+00','price_change','价格快照变化','基本面概率尚未建立，仅记录价格从9月11日46.76元变为9月17日50.25元；不倒推、不改写当时不存在的概率。','https://quote.eastmoney.com/sh603662.html','2026-09-18','B','fact',50.25,2.80829868,141.10,jsonb_build_object('trade_date','2026-09-11','price',46.76,'market_cap',131.40,'probabilities',null,'expected_return',null),jsonb_build_object('trade_date','2026-09-17','price',50.25,'market_cap',141.10,'probabilities',null,'expected_return',null),'price','只记录价格与市值变化；当时没有正式概率和期望收益，因此这些字段保持为空。','Step 4待核算',1);
  end if;

  if not exists (select 1 from public.company_timeline_events where company_id=cid and event_type='fundamental_change' and title='半年报与业绩会确认订单进入批量化过渡') then
    insert into public.company_timeline_events(company_id,event_at,event_type,title,description,source_url,source_publish_date,evidence_level,data_type,price,shares_outstanding,market_cap,previous_state,current_state,change_driver,change_reason,system_status,model_version)
    values(cid,'2026-09-17 09:00:00+00','fundamental_change','半年报与业绩会确认订单进入批量化过渡','2026H1销量超2000只，自4月以来月订单持续超1000只；公司解释订单到交付需标定、检测与验收。','https://big5.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-09-17/603662_20260917_B200.pdf','2026-09-17','A','fact',50.25,2.80829868,141.10,jsonb_build_object('confirmed_volume','2025年销量>1500只','monthly_orders',null),jsonb_build_object('confirmed_volume','2026H1销量>2000只','monthly_orders','自4月以来持续>1000只','delivery_constraint','标定/检测/验收周期'),'fundamental','新增一手披露提升销量区间可解释性，但ASP、独立毛利率和精确产能仍未披露。','Step 4补参数',1);
  end if;

  if not exists (select 1 from public.company_timeline_events where company_id=cid and event_type='model_revision' and title='模型由缺值阻塞改为有依据区间') then
    insert into public.company_timeline_events(company_id,event_at,event_type,title,description,source_url,source_publish_date,evidence_level,data_type,price,shares_outstanding,market_cap,profit_bear,profit_base,profit_bull,probability_bear,probability_base,probability_bull,target_market_cap_bear,target_market_cap_base,target_market_cap_bull,expected_return,annualized_expected_return,max_downside,risk_reward,profit_confidence,probability_confidence,previous_state,current_state,change_driver,change_reason,system_status,model_version,is_model_revision,calculation_trace)
    values(cid,'2026-09-18 07:44:33+00','model_revision','模型由缺值阻塞改为有依据区间','保留低可信度：事实、可靠参考、模型推算和人工假设共同形成三情景；不再因缺少直接ASP而停止计算。','https://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-4/2026-04-28/12209189.PDF','2026-04-28','C','model_inference',er.current_price,2.80829868,er.current_market_cap,(s->'悲观'->>'net_profit')::numeric,(s->'中性'->>'net_profit')::numeric,(s->'乐观'->>'net_profit')::numeric,(s->'悲观'->>'probability_pct')::integer,(s->'中性'->>'probability_pct')::integer,(s->'乐观'->>'probability_pct')::integer,(s->'悲观'->>'target_market_cap')::numeric,(s->'中性'->>'target_market_cap')::numeric,(s->'乐观'->>'target_market_cap')::numeric,er.expected_return,er.annualized_expected_return,er.max_assumed_downside,er.risk_reward_ratio,er.profit_confidence,er.probability_confidence,jsonb_build_object('model_version',1,'status','blocked','missing_inputs',jsonb_build_array('ASP','估值倍数','毛利率','费用率'),'expected_return',null),jsonb_build_object('model_version',2,'status','complete','missing_inputs','[]'::jsonb,'expected_return',er.expected_return),'model_revision','旧逻辑把没有直接披露等同于不可计算；新逻辑允许有来源的区间推算，并明确降低可信度。','Step 5继续验证',2,true,er.calculation_trace);
  end if;

  if not exists (select 1 from public.company_timeline_events where company_id=cid and event_type='current' and title='当前动态期望收益快照') then
    insert into public.company_timeline_events(company_id,event_at,event_type,title,description,source_url,source_publish_date,evidence_level,data_type,price,shares_outstanding,market_cap,profit_bear,profit_base,profit_bull,probability_bear,probability_base,probability_bull,target_market_cap_bear,target_market_cap_base,target_market_cap_bull,expected_return,annualized_expected_return,max_downside,risk_reward,profit_confidence,probability_confidence,current_snapshot_id,previous_state,current_state,change_driver,change_reason,system_status,model_version,calculation_trace)
    values(cid,er.calculated_at,'current','当前动态期望收益快照','三情景利润、概率和最新价格完整后正式进入Step 5；结果为低可信度研究值，不是收益承诺。','https://quote.eastmoney.com/sh603662.html',er.trade_date,'C','model_inference',er.current_price,2.80829868,er.current_market_cap,(s->'悲观'->>'net_profit')::numeric,(s->'中性'->>'net_profit')::numeric,(s->'乐观'->>'net_profit')::numeric,(s->'悲观'->>'probability_pct')::integer,(s->'中性'->>'probability_pct')::integer,(s->'乐观'->>'probability_pct')::integer,(s->'悲观'->>'target_market_cap')::numeric,(s->'中性'->>'target_market_cap')::numeric,(s->'乐观'->>'target_market_cap')::numeric,er.expected_return,er.annualized_expected_return,er.max_assumed_downside,er.risk_reward_ratio,er.profit_confidence,er.probability_confidence,er.id,jsonb_build_object('step5_count',0),jsonb_build_object('step5_count',1,'snapshot_id',er.id),'initial','首次形成可追溯的动态期望收益快照。',er.research_status,2,er.calculation_trace);
  end if;
end $$;

update public.company_timeline_events t set current_snapshot_id=(
  select e.id from public.expected_return_snapshots e
  where e.company_id=t.company_id order by e.trade_date desc,e.calculated_at desc limit 1
)
where t.event_type='current' and t.title='当前动态期望收益快照' and t.current_snapshot_id is null;

commit;
