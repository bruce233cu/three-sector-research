"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowRight, ChevronDown, CircleHelp, ExternalLink, Info, RotateCcw, Search, X } from "lucide-react";
import { Shell, Badge, firms as fallbackFirms, sigs as fallbackSigs, tracks } from "../research-ui";
import { useResearchData } from "../../hooks/use-research-data";

const modules: Record<string, any> = {
  signals:{nav:"变化发现",title:"变化发现",desc:"今天发生了哪些值得继续研究的变化？",step:1},
  opportunities:{nav:"机会池",title:"机会确认",desc:"哪些变化真正形成了值得持续追踪的产业机会？",step:2},
  companies:{nav:"公司筛选",title:"公司发现与筛选",desc:"这些产业机会最终可能让哪些公司真正赚钱？",step:3},
  profit:{nav:"利润估值",title:"利润与估值核算",desc:"如果逻辑兑现，公司未来可能赚多少钱、值多少钱？",step:4},
  odds:{nav:"投资价值",title:"投资价值评估",desc:"以今天这个价格和兑现概率，当前是否具有足够投资价值？",step:5},
  validation:{nav:"持续验证",title:"持续验证",desc:"后续事实正在加强还是破坏原来的判断？",step:6},
  industry:{nav:"产业链地图",title:"产业链映射",desc:"一个产业机会如何映射到多个受益公司和验证对象？",step:3},
  daily:{nav:"日报归档",title:"日报归档",desc:"日报是横向信息入口和工作台，不属于六步主流程。",step:0},
  guide:{nav:"系统说明",title:"V4 系统说明书",desc:"六步主链、五类研究对象与回流机制的统一定义。",step:0},
};
const flow = [["变化发现","/signals"],["机会池","/opportunities"],["公司筛选","/companies"],["利润估值","/profit"],["投资价值","/odds"],["持续验证","/validation"]];

export default function Page() {
  const { module } = useParams<{ module: string }>();
  const data = useResearchData(fallbackFirms, fallbackSigs);
  const config = modules[module];
  const [help,setHelp]=useState(false);
  if (!config) return null;
  return <Shell active={config.nav}>
    <header className="research-head"><div><p className="eyebrow">{config.step?`V4 RESEARCH WORKFLOW / STEP ${config.step}`:"V4 RESEARCH SYSTEM"}</p><h1>{config.title}</h1><p>{config.desc}</p></div><div className="head-actions"><button className="help-button" onClick={()=>setHelp(true)}><CircleHelp size={15}/> 本页说明</button><div className="health"><i /> {data.live ? "数据库实时数据" : "正在连接数据库"}</div></div></header>
    {config.step>0&&<ResearchFlow active={config.step} data={data} onHelp={()=>setHelp(true)}/>}
    <ModuleView module={module} data={data}/>
    {help&&<HelpDrawer module={module} onClose={()=>setHelp(false)}/>}
  </Shell>;
}

function ResearchFlow({active,data,onHelp}:{active:number;data:any;onHelp:()=>void}) {
  const research=data.firms.filter((x:any)=>x.researchPoolStatus==="research").length,shadow=data.firms.filter((x:any)=>x.researchPoolStatus==="shadow").length;
  const completed=data.firms.filter((x:any)=>x.valuationStatus==="completed").length,assessed=data.investmentAssessments.length,high=data.investmentAssessments.filter((x:any)=>x.classification==="high_expected_return").length;
  const tracking=data.firms.filter((x:any)=>["research","shadow"].includes(x.researchPoolStatus)||x.investmentAssessmentStatus==="high_expected_return").length;
  const counts=[`${data.sigs.length}条信号`,`${data.opportunities.length}个机会`,`${data.firms.length}家映射 · ${research}研究 · ${shadow}影子`,`${completed}家完成`,`${assessed}家已评估 · ${high}高期望`,`${tracking}家公司跟踪`];
  return <><div className="research-flow">{flow.map(([name,href],i)=><Link className={active===i+1?"active":""} href={href} key={href}><span>{i+1}</span><div><small>{name}</small><strong>{counts[i]}</strong></div>{i<5?<ArrowRight size={15}/>:<RotateCcw size={15}/>}</Link>)}</div><div className="flow-relationship"><span>统计对象依次是信号、机会、公司、可估值公司、已评估公司和跟踪公司；不是简单递减漏斗。Step 6 新证据可回流 Step 4 / 5。</span><button onClick={onHelp}>查看流程说明</button></div></>;
}
function ModuleView({module,data}:{module:string;data:any}) {
  if(module==="signals") return <SignalsTable rows={data.sigs}/>;
  if(module==="opportunities") return <OpportunityTable rows={data.opportunities}/>;
  if(module==="companies"||module==="industry") return <CompanyTable rows={data.firms} industry={module==="industry"}/>;
  if(module==="profit") return <ProfitTable rows={data.profitModels} parameters={data.modelParameters}/>;
  if(module==="odds") return <OddsTable rows={data.expectedReturns} firms={data.firms} parameters={data.modelParameters} assessments={data.investmentAssessments} thresholds={data.investmentThresholds}/>;
  if(module==="validation") return <ValidationView data={data}/>;
  if(module==="guide") return <GuideView/>;
  return <DailyTable rows={data.reports} data={data}/>;
}
function TableFrame({children,count,placeholder="搜索当前表格",query,onQuery,filters}:{children:any;count:number;placeholder?:string;query:string;onQuery:(v:string)=>void;filters?:any}) {
  return <section className="logic-card"><div className="logic-toolbar"><label><Search size={15}/><input value={query} onChange={e=>onQuery(e.target.value)} placeholder={placeholder}/></label>{filters}<span>当前 {count} 条记录</span><em>点击行查看完整证据链</em></div>{children}</section>;
}
function SignalsTable({rows}:{rows:any[]}){
  const [open,setOpen]=useState<string|null>(null);
  const [query,setQuery]=useState(""); const [track,setTrack]=useState("全部赛道"); const [action,setAction]=useState("全部动作"); const [date,setDate]=useState("全部日期");
  const dates=[...new Set(rows.map(r=>r.date))].sort().reverse();
  const shown=filterRows(rows,query).filter(r=>(track==="全部赛道"||r.track===track)&&(action==="全部动作"||r.state===action)&&(date==="全部日期"||r.date===date));
  const filters=<div className="table-filters"><select value={track} onChange={e=>setTrack(e.target.value)}><option>全部赛道</option><option>机器人</option><option>商业航天</option><option>AI</option></select><select value={action} onChange={e=>setAction(e.target.value)}><option>全部动作</option>{[...new Set(rows.map(r=>r.state).filter(Boolean))].map(x=><option key={x}>{x}</option>)}</select><select value={date} onChange={e=>setDate(e.target.value)}><option>全部日期</option>{dates.map(x=><option key={x}>{x}</option>)}</select>{(track!=="全部赛道"||action!=="全部动作"||date!=="全部日期")&&<button onClick={()=>{setTrack("全部赛道");setAction("全部动作");setDate("全部日期")}}>清除筛选</button>}</div>;
  return <TableFrame count={shown.length} query={query} onQuery={setQuery} filters={filters} placeholder="搜索信号、公司或机会ID"><div className="logic-scroll"><table className="logic-table"><thead><tr><th>日期</th><th>机会ID</th><th>赛道 / 公司</th><th>信息类型</th><th>上一状态</th><th>本次变化</th><th>强度</th><th>市场交易</th><th>动作</th></tr></thead><tbody>{shown.map(r=><RowGroup key={r.id} open={open===r.id} onOpen={()=>setOpen(open===r.id?null:r.id)} cells={[
    r.date,r.id,<><Badge tone={tracks[r.track]}>{r.track}</Badge><b>{r.company}</b></>,r.type,r.previousStatus,r.change,<strong className="score">{r.score}/5</strong>,r.tradedStatus,<Status value={r.state}/>
  ]}><DetailGrid items={[["信息标题",r.title],["改变了什么",r.change],["后续验证",r.verify],["事实来源",r.source?<a href={r.source} target="_blank" rel="noreferrer">打开原始来源 <ExternalLink size={13}/></a>:"待补来源"],["影响链条",r.metadata?.affected_chain],["下一节点",joinValue(r.metadata?.next_nodes)]]}/></RowGroup>)}</tbody></table></div></TableFrame>;
}
function OpportunityTable({rows}:{rows:any[]}){
  const [open,setOpen]=useState<string|null>(null);
  const [query,setQuery]=useState(""); const shown=filterRows(rows,query);
  return <><div className="object-note"><Info size={15}/><span>本页统计的是“产业机会”，不是股票。一条机会可由多条信号形成，也可映射多家公司。</span></div><TableFrame count={shown.length} query={query} onQuery={setQuery} placeholder="搜索产业机会、方向或状态"><div className="logic-scroll"><table className="logic-table"><thead><tr><th>机会ID</th><th>产业机会</th><th>赛道</th><th>核心变化</th><th>确认状态</th><th>综合分</th><th>共识程度</th><th>核心验证点</th><th>动作</th></tr></thead><tbody>{shown.map(r=><RowGroup key={r.id||r.code} open={open===(r.id||r.code)} onOpen={()=>setOpen(open===(r.id||r.code)?null:(r.id||r.code))} cells={[
    r.code,<><b>{r.name||r.opportunity_name}</b><small>映射：{r.company}</small></>,<Badge tone={tracks[r.track]}>{r.track}</Badge>,r.core_change||r.upgrade_evidence,<Status value={r.opportunity_status==="confirmed"?"已确认":"待确认"}/>,<strong className="score">{fmt(r.composite_score)}</strong>,r.consensus_level||"待判断",r.core_validation||r.next_verification,<Status value={r.action||"研究"}/>
  ]}><DetailGrid items={[["需求端证据",r.demand_evidence],["供给端证据",r.supply_evidence],["公司端证据",r.company_evidence],["产业空间",r.market_space?`${r.market_space}亿元`:null],["主要反证",r.counter_evidence||r.break_condition],["下一步研究",r.next_research],["注意", "机会确认不等于任何股票自动进入研究池"]]}/></RowGroup>)}</tbody></table></div></TableFrame></>;
}
function CompanyTable({rows,industry}:{rows:any[];industry:boolean}){
  const [open,setOpen]=useState<string|null>(null);
  const [query,setQuery]=useState(""); const [tab,setTab]=useState("all");
  const counts={research:rows.filter(r=>r.researchPoolStatus==="research").length,shadow:rows.filter(r=>r.researchPoolStatus==="shadow").length,validator:rows.filter(r=>r.companyRole==="industry_validator").length,archived:rows.filter(r=>r.researchPoolStatus==="archived").length};
  const filtered=tab==="all"?rows:tab==="validator"?rows.filter(r=>r.companyRole==="industry_validator"):rows.filter(r=>r.researchPoolStatus===tab);
  const shown=filterRows(filtered,query);
  const filters=<PoolTabs value={tab} onChange={setTab} items={[["all",`全部映射 ${rows.length}`],["research",`研究池 ${counts.research}`],["shadow",`影子池 ${counts.shadow}`],["validator",`产业验证 ${counts.validator}`],["archived",`淘汰/归档 ${counts.archived}`]]}/>;
  return <><div className="v4-summary"><MetricCard label="公司映射" value={rows.length} note="一个机会可对应多家公司"/><MetricCard label="研究池" value={counts.research} note="默认进入利润估值"/><MetricCard label="影子池" value={counts.shadow} note="保留并等待重激活"/><MetricCard label="产业验证对象" value={counts.validator} note="不进入股票赔率核算"/></div><TableFrame count={shown.length} query={query} onQuery={setQuery} filters={filters} placeholder="搜索公司、代码或产业链位置"><div className="logic-scroll"><table className="logic-table"><thead><tr><th>公司 / 代码</th><th>角色</th><th>赛道 / 位置</th><th>当前状态原因</th><th>市值</th><th>当前池子</th><th>下一步需要什么</th><th>档案</th></tr></thead><tbody>{shown.map(r=><RowGroup key={r.code||r.id} open={open===r.id} onOpen={()=>setOpen(open===r.id?null:r.id)} cells={[
    <><b>{r.name}</b><small>{r.stockCode||r.code||"未上市"}</small></>,roleLabel(r.companyRole),<><Badge tone={tracks[r.track]}>{r.track}</Badge><small>{r.chain}</small></>,r.transitionReason||r.reason,r.marketCap,<Status value={poolLabel(r)}/>,r.reactivationCondition||r.accountingBlocker,<Link href={`/company/${r.code}`}>完整档案 <ArrowRight size={13}/></Link>
  ]}><DetailGrid items={[["为什么现在在这里",r.transitionReason],["为什么没有进入下一阶段",r.shadowReason||r.accountingBlocker],["重新激活条件",r.reactivationCondition],["利润估值状态",valuationLabel(r.valuationStatus)],["投资评估状态",assessmentLabel(r.investmentAssessmentStatus)],["已确认数据",r.metadata?.confirmed_data],["核心业务",r.coreBusiness],["关键假设",r.keyAssumptions]]}/></RowGroup>)}</tbody></table></div></TableFrame></>;
}
function ProfitTable({rows,parameters}:{rows:any[];parameters:any[]}){
  const [open,setOpen]=useState<string|null>(null);
  const [query,setQuery]=useState("");
  const scenarioOrder:any={悲观:0,中性:1,乐观:2};
  const grouped=Object.values(filterRows(rows,query).reduce((acc:any,r:any)=>{(acc[r.companyName]??=[]).push(r);return acc},{})).map((items:any)=>items.sort((a:any,b:any)=>(scenarioOrder[a.scenario]??9)-(scenarioOrder[b.scenario]??9)));
  const completeness=(items:any[])=>{const r=items.find(x=>x.scenario==="中性")||items[0];return [r.units,r.asp,r.gross_margin,r.expense_ratio,r.legacy_profit,r.pe_multiple,r.reference_market_cap,r.evidence].filter(v=>v!=null&&v!=="").length};
  grouped.sort((a:any,b:any)=>completeness(b)-completeness(a)||String(a[0].companyName).localeCompare(String(b[0].companyName),"zh-CN"));
  const completed=(grouped as any[]).filter(x=>x.every((r:any)=>r.model_status==="complete")).length;
  return <><div className="v4-summary"><MetricCard label="研究池模型" value={grouped.length} note="历史模型全部保留"/><MetricCard label="已完成" value={completed} note="形成三情景利润与目标市值"/><MetricCard label="核算中/不足" value={(grouped as any[]).length-completed} note="缺口保持为空"/><MetricCard label="重要说明" value="≠买入" note="完成估值不代表值得投资"/></div><TableFrame count={grouped.length} query={query} onQuery={setQuery} placeholder="搜索公司或核算假设"><div className="profit-groups">
    {(grouped as any[]).map((items:any[])=>{const base=items.find(x=>x.scenario==="中性")||items[0];const name=base.companyName;const done=completeness(items);const missing=[...new Set(items.flatMap(x=>x.missing_inputs||[]))];const isOpen=open===name;return <section className={`profit-company ${isOpen?"open":""}`} key={name}>
      <button className="profit-company-head" onClick={()=>setOpen(isOpen?null:name)}><span><b>{name}</b><small>{base.companyCode||""} · {base.fiscal_year}E · {modelTypeLabel(base.model_type)}</small></span><span><small>利润可信度</small><b><Confidence value={base.profit_confidence}/></b></span><span><small>核算完成度</small><b className={done>=7?"done":"pending"}>{done}/8</b></span><span className="missing-cell"><small>核心未确认变量</small><b>{missing.length?missing.join("、"):"参数已完整"}</b></span><span><small>当前结论</small><b>{base.model_status==="complete"?"可用于决策":"数据不足 / 待核实"}</b></span><ChevronDown size={17}/></button>
      {isOpen&&<div className="profit-detail"><div className="logic-scroll"><table className="logic-table profit-scenario-table"><thead><tr><th>情景</th><th>模型类型</th><th>收入</th><th>毛利率</th><th>费用率</th><th>增量净利润</th><th>传统业务利润</th><th>总归母净利润</th><th>估值倍数</th><th>目标市值</th><th>状态</th></tr></thead><tbody>{items.map(r=><tr key={r.id}><td><Status value={r.scenario}/></td><td>{modelTypeLabel(r.model_type)}</td><td>{modelValue(r.revenue,"亿")}</td><td>{modelPct(r.gross_margin)}</td><td>{modelPct(r.expense_ratio)}</td><td>{modelValue(r.net_profit,"亿")}</td><td>{modelValue(r.legacy_profit,"亿")}</td><td>{modelValue(r.total_profit,"亿")}</td><td>{modelMultiple(r.pe_multiple,false)}</td><td>{modelValue(r.target_market_cap,"亿")}</td><td><Status value={r.model_status==="complete"?"可用于决策":"待关键数据"}/></td></tr>)}</tbody></table></div>
        <div className="evidence-title"><div><strong>查看依据</strong><span>原始输入、证据等级与推算逻辑</span></div><small>事实 ≠ 预测 ≠ 推算 ≠ 假设</small></div>
        {items.map(r=>{const ps=parameters.filter((p:any)=>p.profit_model_id===r.id);return <section className="scenario-evidence" key={`e-${r.id}`}><h3>{r.scenario}情景 · {r.fiscal_year}E</h3><div className="logic-scroll"><table className="logic-table evidence-table"><thead><tr><th>参数</th><th>数值</th><th>数据类型</th><th>证据</th><th>来源</th><th>状态</th><th>推算逻辑</th></tr></thead><tbody>{ps.map((p:any)=><tr key={p.id}><td><b>{p.parameter_name}</b><small>{p.parameter_key}</small></td><td>{p.parameter_value==null?"待核实":`${Number(p.parameter_value).toLocaleString("zh-CN")}${p.unit||""}`}</td><td><DataType value={p.data_type}/></td><td><Evidence value={p.evidence_grade}/></td><td>{p.source_url?<a href={p.source_url} target="_blank" rel="noreferrer">{p.source_name||"原始来源"} <ExternalLink size={12}/></a>:(p.source_name||"待补来源")}</td><td>{p.is_confirmed?"已确认":"待核实"}</td><td>{p.derivation_logic||"—"}</td></tr>)}</tbody></table></div><DetailGrid items={[["使用公式",r.calculation_trace?.formula],["中间结果",traceLine(r.calculation_trace?.intermediate)],["最终结果",r.total_profit==null?"关键参数不足，未输出正式净利润":`${r.total_profit}亿元`],["最大不确定性",r.max_uncertainty],["最需要验证",r.most_needed_evidence]]}/></section>})}
      </div>}
    </section>})}
  </div><div className="formula-note"><b>统一利润链：</b>业务模型输入 → 收入 → 毛利润 → 费用 → 税 → 新业务利润 → 传统业务利润 → 总归母净利润。完成本页只代表“可估值”，不代表“高赔率”。</div></TableFrame></>;
}
function OddsTable({rows,firms,parameters,assessments,thresholds}:{rows:any[];firms:any[];parameters:any[];assessments:any[];thresholds:any[]}){
  const [open,setOpen]=useState<string|null>(null);
  const [query,setQuery]=useState(""); const [tab,setTab]=useState("all");
  const enriched=rows.map(r=>({...r,assessment:assessments.find((a:any)=>a.expected_return_snapshot_id===r.id)}));
  const filtered=tab==="all"?enriched:tab==="high"?enriched.filter(r=>r.assessment?.classification==="high_expected_return"):tab==="shadow"?enriched.filter(r=>r.assessment?.classification==="shadow"):enriched.filter(r=>r.assessment?.classification==="failed");
  const shown=filterRows(filtered,query).sort((a,b)=>Number(b.expected_return)-Number(a.expected_return)); const high=enriched.filter(r=>r.assessment?.classification==="high_expected_return").length,shadow=enriched.filter(r=>r.assessment?.classification==="shadow").length,failed=enriched.filter(r=>r.assessment?.classification==="failed").length; const rule=thresholds[0];
  const filters=<PoolTabs value={tab} onChange={setTab} items={[["high",`高期望收益 ${high}`],["shadow",`影子池 ${shadow}`],["all",`全部已评估 ${enriched.length}`],["failed",`不通过 ${failed}`]]}/>;
  return <><div className="v4-summary"><MetricCard label="已完成评估" value={enriched.length} note="算出结果，不等于通过"/><MetricCard label="高期望收益" value={high} note="达到当前配置门槛"/><MetricCard label="影子池" value={shadow} note="保留模型，等待重激活"/><MetricCard label="当前规则" value={rule?.is_provisional?"临时":"正式"} note="待历史盲测校准"/></div><div className="object-note warning"><Info size={15}/><span>expected_return 有值只代表评估完成；只有全部通过配置门槛才进入高期望收益池。</span></div><TableFrame count={shown.length} query={query} onQuery={setQuery} filters={filters} placeholder="搜索公司、状态或变化原因"><div className="logic-scroll"><table className="logic-table expectation-table"><thead><tr><th>日期</th><th>公司</th><th>当前价 / 市值</th><th>悲观收益</th><th>中性收益</th><th>乐观收益</th><th>期望收益 <InfoTip text="三情景收益按对应概率加权"/></th><th>年化期望</th><th>最大下行</th><th>风险收益比</th><th>可信度</th><th>评估分流</th></tr></thead><tbody>{shown.map(r=>{const s=r.scenario_results||{};const firm=firms.find(f=>f.code===r.external_code);const ps=parameters.filter((p:any)=>p.profit_models?.company_id===r.company_id);const quality=qualityCounts(ps);return <RowGroup key={r.id} open={open===r.id} onOpen={()=>setOpen(open===r.id?null:r.id)} cells={[
    r.trade_date,<><b>{r.company_name}</b><small>{firm?.stockCode||r.stock_code}</small></>,<>{money(r.current_price,"元")}<small>{money(r.current_market_cap,"亿")}</small></>,scenarioCell(s["悲观"]),scenarioCell(s["中性"]),scenarioCell(s["乐观"]),<strong className="expected-main">{returnPct(r.expected_return)}</strong>,returnPct(r.annualized_expected_return),returnPct(r.max_assumed_downside),r.risk_reward_ratio==null?"待核实":Number(r.risk_reward_ratio).toFixed(2),<><Confidence value={r.profit_confidence}/><small>利润 / 概率</small><Confidence value={r.probability_confidence}/></>,<Status value={r.assessment?.classification==="high_expected_return"?"高期望收益":r.assessment?.classification==="shadow"?"影子池":"待评估"}/>
  ]}><div className="expectation-evidence"><div className="expectation-cards">{["悲观","中性","乐观"].map(x=><article key={x}><span>{x}情景 · 概率 {s[x]?.probability_pct??"—"}%</span><strong>{returnPct(s[x]?.return)}</strong><small>净利润 {money(s[x]?.net_profit,"亿")} · {s[x]?.valuation_method||"—"} {s[x]?.valuation_multiple??"—"}倍</small><p>目标市值 {money(s[x]?.target_market_cap,"亿")}</p></article>)}</div><div className="quality-strip"><b>数据质量</b><span>A 事实 {quality.fact}</span><span>B 可靠参考 {quality.reference}</span><span>C 模型推算 {quality.inference}</span><span>D 人工假设 {quality.assumption}</span><em>核心风险：{firm?.metadata?.gaps||"待补充"}</em></div><DetailGrid items={[["为什么没有进入高期望收益",r.assessment?.failure_reasons?.join("；")||"尚待评估"],["重新激活条件",firm?.reactivationCondition],["当前门槛",rule?`期望≥${returnPct(rule.min_expected_return)}；年化≥${returnPct(rule.min_annualized_return)}；风险收益比≥${rule.min_risk_reward}；中性收益≥${returnPct(rule.min_base_return)}；利润/概率可信度≥中`:"待配置"],["股价来源",r.calculation_trace?.price_source?.url?<a href={r.calculation_trace.price_source.url} target="_blank" rel="noreferrer">{r.calculation_trace.price_source.name} <ExternalLink size={12}/></a>:"待补来源"],["变化驱动",driverLabel(r.change_driver)],["模型指纹",r.model_fingerprint?.slice(0,16)+"…"]]}/></div></RowGroup>})}</tbody></table></div><div className="formula-note"><b>完成评估 ≠ 通过评估：</b>概率与价格分离；阈值来自配置层，当前为待历史校准的临时规则。</div>{shown.length===0&&<div className="blocked-empty"><strong>当前分类暂无公司</strong><p>公司可能仍在利润核算、影子池或等待新的验证事件。</p></div>}</TableFrame></>;
}
function ValidationView({data}:{data:any}){
  const tracking=data.firms.filter((x:any)=>["research","shadow"].includes(x.researchPoolStatus)||x.investmentAssessmentStatus==="high_expected_return");
  const events=data.validationEvents||[]; const strengthen=events.filter((x:any)=>x.effect==="strengthen").length,weaken=events.filter((x:any)=>x.effect==="weaken").length,revalue=events.filter((x:any)=>[4,5].includes(x.return_to_step)).length;
  return <><div className="v4-summary"><MetricCard label="持续验证对象" value={tracking.length} note="研究池 + 影子池 + 高期望收益"/><MetricCard label="新增验证事件" value={events.length} note="证据只追加，不覆盖"/><MetricCard label="逻辑增强 / 减弱" value={`${strengthen} / ${weaken}`} note="由新事实决定"/><MetricCard label="待回流重算" value={revalue} note="返回 Step 4 或 Step 5"/></div><div className="feedback-loop"><RotateCcw size={18}/><div><b>持续验证不是终点</b><span>新订单、ASP、毛利率等基本面证据回流 Step 4；价格或概率变化回流 Step 5。</span></div><Link href="/profit">回到利润估值</Link><Link href="/odds">回到投资价值</Link></div><section className="logic-card"><div className="logic-scroll"><table className="logic-table"><thead><tr><th>公司</th><th>当前池子</th><th>为什么在这里</th><th>下一验证日</th><th>重新升级条件</th><th>最近验证</th></tr></thead><tbody>{tracking.map((c:any)=><tr key={c.id}><td><Link href={`/company/${c.code}`}><b>{c.name}</b><small>{c.stockCode}</small></Link></td><td><Status value={poolLabel(c)}/></td><td>{c.transitionReason}</td><td>{c.nextValidationAt?.slice(0,10)||"待安排"}</td><td>{c.reactivationCondition||"持续跟踪核心假设"}</td><td>{c.lastValidationAt?.slice(0,10)||"待验证"}</td></tr>)}</tbody></table></div></section>{events.length>0&&<section className="validation-events"><h2>验证事件与回流</h2>{events.map((e:any)=><article key={e.id}><time>{e.validation_date}</time><div><b>{e.companies?.name} · {e.title}</b><p>{e.conclusion}</p></div><Status value={effectLabel(e.effect)}/><span>{e.return_to_step?`回流 Step ${e.return_to_step}`:"继续观察"}</span></article>)}</section>}</>;
}
function GuideView(){
  const steps=[
    ["01","变化发现","原始信号","值得继续研究的变化","形成结构化信号","进入机会确认"],
    ["02","机会确认","产业机会","多条信号共同证明机会","确认或继续等待","映射多个公司"],
    ["03","公司筛选","公司与验证对象","判断谁真正赚钱","研究/影子/验证/归档","研究池进入估值"],
    ["04","利润估值","研究池上市公司","三情景利润与目标市值","完成/核算中/数据不足","完成后进入评估"],
    ["05","投资价值","完成估值公司","结合概率和今天价格判断","高期望/影子/不通过","进入持续验证"],
    ["06","持续验证","研究/影子/高期望公司","新事实增强还是破坏判断","保持/升级/降级/回流","回到 Step 4/5"],
  ];
  const pools=[["信号库","所有值得继续研究的变化，不等于机会。"],["机会池","经多条证据确认、值得持续追踪的产业机会。"],["研究池","值得投入研究资源并进入利润估值的可投资公司。"],["影子池","逻辑未失效，但受证据、赔率、概率或价格限制，等待重新激活。"],["产业验证对象","用于验证需求、出货或技术路线，不直接进入股票赔率核算。"],["高期望收益池","完成利润、估值、概率和价格评估，并达到当前配置门槛的候选公司。"]];
  return <><section className="guide-hero"><div><span>V4 核心原则</span><h2>七个问题，六步主链，一个闭环</h2><p>信号 ≠ 机会；公司映射 ≠ 研究池；完成估值 ≠ 值得投资；算出收益 ≠ 高期望收益。</p></div><RotateCcw size={42}/></section><div className="guide-steps">{steps.map(s=><article key={s[0]}><span>{s[0]}</span><h3>{s[1]}</h3><dl><div><dt>处理对象</dt><dd>{s[2]}</dd></div><div><dt>进入条件</dt><dd>{s[3]}</dd></div><div><dt>退出标准</dt><dd>{s[4]}</dd></div><div><dt>下一步</dt><dd>{s[5]}</dd></div></dl></article>)}</div><section className="pool-glossary"><h2>所有池子的统一定义</h2><div>{pools.map(([a,b])=><article key={a}><b>{a}</b><p>{b}</p></article>)}</div></section><div className="object-note"><Info size={15}/><span>日报是工作台，时间轴是横向能力，历史盲测与模拟盘是未来验证层；它们都不是第 7 步。</span></div></>;
}
function HelpDrawer({module,onClose}:{module:string;onClose:()=>void}){
  const h=helpContent[module]||helpContent.guide;
  return <div className="help-backdrop" onClick={onClose}><aside className="help-drawer" onClick={e=>e.stopPropagation()}><button className="help-close" onClick={onClose}><X size={18}/></button><p className="eyebrow">PAGE GUIDE</p><h2>{h.title}</h2><p className="help-answer">{h.answer}</p><dl>{[["处理对象",h.object],["进入条件",h.enter],["离开条件",h.leave],["结果代表",h.means],["结果不代表",h.not],["下一步",h.next],["未进入下一步的原因",h.block]].map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl></aside></div>;
}
const helpContent:any={
 signals:{title:"变化发现",answer:"今天发生了哪些值得继续研究的变化？",object:"公告、财报、订单、政策、产能、技术与竞争变化。",enter:"相较上一状态出现可验证的新变化。",leave:"聚合为产业机会，或证据不足转为普通资料。",means:"值得继续研究的结构化信号。",not:"不代表产业机会已经成立，更不代表公司值得投资。",next:"与其他信号共同进入机会确认。",block:"缺少变化、来源或对产业链的实质影响。"},
 opportunities:{title:"机会确认",answer:"哪些变化形成了产业投资机会？",object:"由多条信号共同支撑的产业机会。",enter:"需求、供给或公司端出现连续且可验证的状态升级。",leave:"确认后进入公司映射；反证增强则降为待确认。",means:"产业方向值得持续追踪。",not:"不代表任何股票已经入池。",next:"沿产业链寻找可投资公司与验证对象。",block:"证据单一、共识过高或关键反证未排除。"},
 companies:{title:"公司发现与筛选",answer:"产业机会最终可能让哪些公司真正赚钱？",object:"可投资公司和产业验证对象。",enter:"与已确认机会存在可解释的产业链关系。",leave:"研究池进入估值；影子池等待重激活；错误映射归档。",means:"解释公司当前角色和资源优先级。",not:"公司映射不等于进入研究池。",next:"研究池公司进入利润与估值核算。",block:"映射、证据、利润弹性、概率或价格不满足。"},
 profit:{title:"利润与估值核算",answer:"逻辑兑现时，公司可能赚多少、值多少？",object:"研究池中的可投资公司。",enter:"公司映射明确且值得投入估值资源。",leave:"形成三情景利润与目标市值后进入投资价值评估。",means:"公司已经可以建立基础估值模型。",not:"不代表赔率高、值得买或进入高期望收益池。",next:"叠加概率、价格与风险做投资价值评估。",block:"销量、ASP、毛利率、费用率或传统业务利润不足。"},
 odds:{title:"投资价值评估",answer:"以今天价格和兑现概率，是否具有足够投资价值？",object:"已完成三情景利润与估值的公司。",enter:"目标市值、概率、最新价格和市值均完整。",leave:"分流为高期望、影子或不通过。",means:"完成评估与是否通过门槛是两件事。",not:"expected_return 有值不等于高期望收益。",next:"进入持续验证，并随价格或基本面变化重算。",block:"赔率、风险收益比、中性收益或可信度不足。"},
 validation:{title:"持续验证",answer:"后续事实正在加强还是破坏原判断？",object:"研究池、影子池和高期望收益公司。",enter:"公司需要持续跟踪关键假设或价格。",leave:"逻辑失效归档；新证据触发回流。",means:"判断保持、升级、降级或重新估值。",not:"不是日报期数，也不是单向流程终点。",next:"基本面证据回流 Step 4；价格/概率回流 Step 5。",block:"缺少可执行的下一验证条件。"},
 daily:{title:"日报归档",answer:"今天有哪些变化、升级、降级和待处理事项？",object:"每日工作记录。",enter:"每日研究任务完成后归档。",leave:"不参与主流程分流。",means:"横向工作台与历史记录。",not:"不是六步主链中的某一步。",next:"把新信息送入变化发现或持续验证。",block:"无。"},
 guide:{title:"V4 系统说明",answer:"整套系统如何从变化走到持续验证？",object:"六步流程、池子、状态机和回流规则。",enter:"任何需要理解系统逻辑的人。",leave:"无。",means:"统一业务语义。",not:"不是投资建议或新增研究功能。",next:"从变化发现开始。",block:"无。"}
};
function DailyTable({rows,data}:{rows:any[];data:any}){
  const [open,setOpen]=useState<string|null>(null);
  const [query,setQuery]=useState(""); const shown=filterRows(rows,query);
  useEffect(()=>{if(!open&&rows[0]?.id)setOpen(rows[0].id)},[rows,open]);
  return <TableFrame count={shown.length} query={query} onQuery={setQuery} placeholder="搜索日期或最强赛道"><div className="logic-scroll"><table className="logic-table daily-table"><thead><tr><th>日期</th><th>最强赛道</th><th>原始线索</th><th>有效信号</th><th>新增入池</th><th>待验证</th><th>研究状态</th><th>完整分析</th></tr></thead><tbody>{shown.map((r,i)=><RowGroup key={r.id} open={open===r.id} onOpen={()=>setOpen(open===r.id?null:r.id)} cells={[
    <><b>{r.report_date}</b>{i===0&&<small className="latest">最新</small>}</>,<Badge tone={tracks[r.strongest_sector]}>{r.strongest_sector||"—"}</Badge>,r.raw_clue_count,r.valid_signal_count,r.new_pool_count,r.pending_verification_count,<Status value={r.research_can_end?"当日完成":"继续跟踪"}/>,<span className="expand-label">{r.report_markdown?"查看完整分析":"仅有历史摘要"} <ChevronDown size={14}/></span>
  ]}><DailyDetail report={r} data={data}/></RowGroup>)}</tbody></table></div></TableFrame>;
}
function RowGroup({cells,children,open,onOpen}:{cells:any[];children:any;open:boolean;onOpen:()=>void}){
  return <><tr className={open?"open":""} onClick={onOpen}>{cells.map((c,i)=><td key={i}>{c??"—"}</td>)}</tr>{open&&<tr className="expanded-row"><td colSpan={cells.length}>{children}</td></tr>}</>;
}
function DetailGrid({items}:{items:any[][]}){return <div className="detail-grid">{items.filter(x=>x[1]!=null&&x[1]!=="").map(([k,v])=><div key={k}><span>{k}</span><div>{v}</div></div>)}</div>}
function PoolTabs({value,onChange,items}:{value:string;onChange:(v:string)=>void;items:string[][]}){return <div className="pool-tabs">{items.map(([v,n])=><button className={value===v?"active":""} onClick={()=>onChange(v)} key={v}>{n}</button>)}</div>}
function MetricCard({label,value,note}:{label:string;value:any;note:string}){return <article><span>{label}</span><strong>{value}</strong><small>{note}</small></article>}
function InfoTip({text}:{text:string}){return <span className="info-tip" title={text}><Info size={12}/></span>}
function DailyDetail({report:r,data}:{report:any;data:any}){
  const q=r.coverage_quality||{};
  const clues=data.rawClues.filter((x:any)=>x.occurred_on===r.report_date);
  const sectors=data.sectorReviews.filter((x:any)=>x.report_date===r.report_date);
  const reviews=data.opportunityReviews.filter((x:any)=>x.report_date===r.report_date);
  return <div className="daily-analysis"><div className="daily-summary-block"><span>当日结论</span><p>{r.summary}</p></div><div className="daily-stats"><span>覆盖置信度 <b>{q.confidence||"未记录"}</b></span><span>原始底稿 <b>{clues.length} 条</b></span><span>赛道复盘 <b>{sectors.length}/3</b></span><span>机会复核 <b>{reviews.length} 条</b></span></div><StructuredDaily clues={clues} sectors={sectors} reviews={reviews}/>{r.report_markdown?<ReportBody markdown={r.report_markdown}/>:<div className="archive-note">该日为历史资料导入记录，当时只保存了摘要和结构化指标，未保存完整日报正文。</div>}{q.gaps?.length>0&&<div className="gap-box"><strong>当前覆盖缺口</strong>{q.gaps.map((x:string)=><span key={x}>{x}</span>)}</div>}</div>
}
function StructuredDaily({clues,sectors,reviews}:{clues:any[];sectors:any[];reviews:any[]}){return <>
  {sectors.length>0&&<section className="structured-block"><h3>三赛道逐项复盘</h3><div className="sector-review-grid">{sectors.map(r=><article key={r.id}><div><Badge tone={tracks[r.track]}>{r.track}</Badge><strong>{r.strength_score==null?"—":`${r.strength_score}/10`}</strong></div><p><b>本次变化：</b>{r.key_changes||"无实质变化"}</p><p><b>证据与映射：</b>{r.evidence_summary||"待补充"}</p><p><b>利润/估值：</b>{r.profit_valuation_updates||"暂无可量化变化"}</p><p><b>下一验证：</b>{r.next_verification||"待补充"}</p></article>)}</div></section>}
  {clues.length>0&&<section className="structured-block"><h3>原始线索筛选底稿</h3><div className="logic-scroll"><table className="logic-table compact-table"><thead><tr><th>赛道 / 主体</th><th>事件</th><th>上一状态</th><th>本次变化</th><th>影响</th><th>市场交易</th><th>筛选结论</th><th>淘汰原因</th><th>来源</th></tr></thead><tbody>{clues.map(c=><tr key={c.id}><td><Badge tone={tracks[c.track]}>{c.track}</Badge><b>{c.metadata?.company||c.source_name||"待映射"}</b></td><td>{c.title}</td><td>{c.previous_status||"—"}</td><td>{c.current_status||c.summary}</td><td>{c.impact_score||"—"}/10</td><td>{c.market_traded_status||"待判断"}</td><td><Status value={c.screening_status}/></td><td>{c.rejection_reason||"—"}</td><td>{c.source_url?<a href={c.source_url} target="_blank" rel="noreferrer">原文 <ExternalLink size={12}/></a>:c.source_name}</td></tr>)}</tbody></table></div></section>}
  {reviews.length>0&&<section className="structured-block"><h3>存量机会逐项复核</h3><div className="logic-scroll"><table className="logic-table compact-table"><thead><tr><th>机会 / 公司</th><th>原阶段</th><th>当前阶段</th><th>支持证据</th><th>反证</th><th>价格与估值</th><th>动作</th><th>下一验证</th><th>破坏条件</th></tr></thead><tbody>{reviews.map(x=><tr key={x.id}><td><b>{x.opportunity_external_id}</b><small>{x.company_name}</small></td><td>{x.previous_stage||"—"}</td><td>{x.current_stage||"—"}</td><td>{x.evidence_for||"—"}</td><td>{x.evidence_against||"—"}</td><td>{x.price_valuation_change||"—"}</td><td><Status value={x.action}/></td><td>{x.next_verification||"—"}</td><td>{x.break_condition||"—"}</td></tr>)}</tbody></table></div></section>}
</>}
function ReportBody({markdown}:{markdown:string}){return <div className="report-body">{markdown.split("\n").map((line,i)=>{const t=line.trim();if(!t||t.startsWith("# "))return null;if(t.startsWith("## "))return <h3 key={i}>{t.slice(3)}</h3>;if(t.startsWith("- "))return <div className="report-bullet" key={i}><i/>{t.slice(2)}</div>;if(/^https?:\/\//.test(t))return <a key={i} href={t} target="_blank" rel="noreferrer">原始来源 <ExternalLink size={13}/></a>;return <p key={i}>{t}</p>})}</div>}
function Status({value}:{value:any}){return <span className={`status ${String(value).includes("入池")||String(value).includes("完成")?"good":String(value).includes("淘汰")?"bad":""}`}>{value||"—"}</span>}
function Confidence({value}:{value:any}){const label=({high:"高",medium:"中",low:"低"} as any)[value]||"待核实";return <span className={`confidence confidence-${value||"unknown"}`}>{label}</span>}
function Evidence({value}:{value:any}){return <span className={`evidence-grade grade-${String(value||"D").toLowerCase()}`}>{value||"D"}</span>}
function DataType({value}:{value:any}){return <span className={`data-type type-${value}`}>{({fact:"A 直接事实",reliable_reference:"B 可靠参考",external_forecast:"B 外部预测",model_inference:"C 模型推算",manual_assumption:"D 人工假设"} as any)[value]||value||"待核实"}</span>}
function modelTypeLabel(v:any){return ({component:"零部件",material:"材料",equipment:"设备",finished_product:"整机/产品",service:"服务",project:"项目制",ai_capex:"AI算力链",custom:"自定义"} as any)[v]||"待选择模型"}
function traceLine(v:any){if(!v)return "尚未产生中间结果";return `收入 ${modelValue(v.revenue,"亿")}；毛利润 ${modelValue(v.gross_profit,"亿")}；费用 ${modelValue(v.expense,"亿")}；增量净利润 ${modelValue(v.incremental_net_profit,"亿")}`}
function returnPct(v:any){return v==null?"待核实":`${Number(v)>=0?"+":""}${(Number(v)*100).toFixed(1)}%`}
function scenarioCell(v:any){return v?<><b>{returnPct(v.return)}</b><small>概率 {v.probability_pct}%</small></>:"待核实"}
function driverLabel(v:any){return ({initial:"首次建立",price:"价格驱动",fundamental:"基本面驱动",dual:"双重驱动",risk_deterioration:"风险恶化"} as any)[v]||v||"待核实"}
function qualityCounts(ps:any[]){const unique=new Map<string,any>();ps.forEach(p=>unique.set(p.parameter_key,p));const v=[...unique.values()];return {fact:v.filter(p=>p.data_type==="fact").length,reference:v.filter(p=>["reliable_reference","external_forecast"].includes(p.data_type)).length,inference:v.filter(p=>p.data_type==="model_inference").length,assumption:v.filter(p=>p.data_type==="manual_assumption").length}}
function fmt(v:any){return v==null?"—":Number(v).toFixed(1)}
function num(v:any){return v==null?"待核实":Number(v).toLocaleString("zh-CN")}
function money(v:any,unit:string){return v==null?"待核实":`${Number(v).toLocaleString("zh-CN",{maximumFractionDigits:2})}${unit}`}
function pct(v:any){return v==null?"待核实":`${Number(v)>1?Number(v):Number(v)*100}%`}
function multiple(v:any,x=true){return v==null?"待核实":`${Number(v).toFixed(x?2:0)}x`}
function modelValue(v:any,unit:string){return v==null||Number(v)===0?"待核实":money(v,unit)}
function modelPct(v:any){return v==null||Number(v)===0?"待核实":pct(v)}
function modelMultiple(v:any,x=true){return v==null||Number(v)===0?"待核实":multiple(v,x)}
function joinValue(v:any){return Array.isArray(v)?v.join("；"):v}
function scoreLine(r:any){return `变化 ${fmt(r.change_score)} / 空间 ${fmt(r.industry_score)} / 认知差 ${fmt(r.cognition_gap_score)}`}
function scoreLine2(r:any){return `映射 ${fmt(r.company_mapping_score)} / 赔率 ${fmt(r.odds_score)} / 验证 ${fmt(r.verification_score)}`}
function accountingLabel(v:any){return ({ready_to_model:"已进入核算",model_blocked:"模型待补参数",mapping_required:"映射未完成",excluded_private:"未上市不核算",hard_screen_pending:"待硬筛",not_ready:"尚未达到核算条件"} as any)[v]||v||"尚未判断"}
function poolLabel(r:any){return r.companyRole==="industry_validator"?"产业验证对象":({research:"研究池",shadow:"影子池",filtered:"筛除",archived:"淘汰/归档"} as any)[r.researchPoolStatus]||r.stage||"待分类"}
function roleLabel(v:any){return ({investable_candidate:"可投资标的",industry_validator:"产业验证对象"} as any)[v]||"待分类"}
function valuationLabel(v:any){return ({not_started:"未开始",in_progress:"核算中",completed:"已完成",insufficient_data:"数据不足"} as any)[v]||"待分类"}
function assessmentLabel(v:any){return ({not_evaluated:"未评估",evaluated:"已完成评估",high_expected_return:"高期望收益",shadow:"影子池",failed:"不通过"} as any)[v]||"待分类"}
function effectLabel(v:any){return ({strengthen:"逻辑增强",weaken:"逻辑减弱",neutral:"中性",revalue:"重新估值",recalculate_profit:"重算利润"} as any)[v]||v}
function filterRows(rows:any[],query:string){const q=query.trim().toLowerCase();return q?rows.filter(r=>JSON.stringify(r).toLowerCase().includes(q)):rows}
