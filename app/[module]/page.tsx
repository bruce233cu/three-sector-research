"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowRight, ChevronDown, ExternalLink, Search } from "lucide-react";
import { Shell, Badge, firms as fallbackFirms, sigs as fallbackSigs, tracks } from "../research-ui";
import { useResearchData } from "../../hooks/use-research-data";

const modules: Record<string, {nav:string; title:string; desc:string; step:number}> = {
  signals:{nav:"前置信号",title:"信息输入",desc:"先比较上一状态，只记录真正改变核心假设的信息",step:1},
  opportunities:{nav:"机会池",title:"硬筛与机会池",desc:"五项硬筛通过后，才进入正式研究",step:2},
  companies:{nav:"公司研究",title:"公司研究档案",desc:"把产业信号穿透到公司订单、收入和利润",step:3},
  profit:{nav:"净利润核算",title:"可追溯净利润核算",desc:"底层变量自动推导三情景利润，每个数字都能查看依据",step:4},
  odds:{nav:"动态期望收益",title:"动态期望收益池",desc:"基本面概率与股价严格分离，按期望收益和可信度排序",step:5},
  industry:{nav:"产业链地图",title:"产业链映射",desc:"需求端变化如何传导到真正受益公司",step:3},
  daily:{nav:"历史日报",title:"独立日报与复盘",desc:"独立复盘层可在 Step 5 为空时照常运行；有收益快照时再追加预测验证",step:6},
};
const flow = [["信息输入","/signals"],["硬筛入池","/opportunities"],["公司穿透","/companies"],["利润核算","/profit"],["期望收益","/odds"],["独立复盘","/daily"]];

export default function Page() {
  const { module } = useParams<{ module: string }>();
  const data = useResearchData(fallbackFirms, fallbackSigs);
  const config = modules[module];
  if (!config) return null;
  return <Shell active={config.nav}>
    <header className="research-head"><div><p className="eyebrow">RESEARCH WORKFLOW / STEP {config.step}</p><h1>{config.title}</h1><p>{config.desc}</p></div><div className="health"><i /> {data.live ? "数据库实时数据" : "正在连接数据库"}</div></header>
    <ResearchFlow active={config.step} data={data}/>
    <ModuleView module={module} data={data}/>
  </Shell>;
}

function ResearchFlow({active,data}:{active:number;data:any}) {
  const modelCompanies=new Set(data.profitModels.map((x:any)=>x.company_id||x.companyCode)).size;
  const validOddsCompanies=new Set(data.expectedReturns.map((x:any)=>x.company_id)).size;
  const counts=[`${data.sigs.length} 条`,`${data.opportunities.length} 条`,`${data.firms.length} 家`,`${modelCompanies} 家`,`${validOddsCompanies} 家`,`${data.reports.length} 期`];
  return <><div className="research-flow">{flow.map(([name,href],i)=><Link className={`${active===i+1?"active":""} ${i===5?"independent":""}`} href={href} key={href}><span>{i+1}</span><div><small>{name}</small><strong>{counts[i]}</strong></div>{i===5?<em>独立层</em>:i<4?<ArrowRight size={15}/>:null}</Link>)}</div><p className="flow-relationship">Step 1–5 是筛选与估值主链；Step 6 独立记录每日研究，只有存在 Step 5 快照时才追加预测验证。</p></>;
}
function ModuleView({module,data}:{module:string;data:any}) {
  if(module==="signals") return <SignalsTable rows={data.sigs}/>;
  if(module==="opportunities") return <OpportunityTable rows={data.opportunities}/>;
  if(module==="companies"||module==="industry") return <CompanyTable rows={data.firms} industry={module==="industry"}/>;
  if(module==="profit") return <ProfitTable rows={data.profitModels} parameters={data.modelParameters}/>;
  if(module==="odds") return <OddsTable rows={data.expectedReturns} firms={data.firms} parameters={data.modelParameters}/>;
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
  return <TableFrame count={shown.length} query={query} onQuery={setQuery} placeholder="搜索机会、公司或状态"><div className="logic-scroll"><table className="logic-table"><thead><tr><th>机会ID</th><th>机会 / 核心公司</th><th>赛道</th><th>状态升级证据</th><th>硬筛</th><th>综合分</th><th>当前阶段</th><th>下一验证</th><th>动作</th></tr></thead><tbody>{shown.map(r=><RowGroup key={r.id||r.code} open={open===(r.id||r.code)} onOpen={()=>setOpen(open===(r.id||r.code)?null:(r.id||r.code))} cells={[
    r.code,<><b>{r.name||r.opportunity_name}</b><small>{r.company}</small></>,<Badge tone={tracks[r.track]}>{r.track}</Badge>,r.upgrade_evidence||r.core_upgrade_evidence,r.pass_result||"—",<strong className="score">{fmt(r.composite_score)}</strong>,<Status value={r.stage}/>,r.next_verification,<Status value={r.action||"研究"}/>
  ]}><DetailGrid items={[["状态链",r.status_chain],["入池理由",r.pool_reason],["产业空间",r.market_space?`${r.market_space}亿元`:null],["公司市值",r.reference_market_cap?`${r.reference_market_cap}亿元`:null],["变化 / 空间 / 认知差",scoreLine(r)],["公司映射 / 赔率 / 验证",scoreLine2(r)],["逻辑破坏条件",r.break_condition],["下一步研究",r.next_research]]}/></RowGroup>)}</tbody></table></div></TableFrame>;
}
function CompanyTable({rows,industry}:{rows:any[];industry:boolean}){
  const [open,setOpen]=useState<string|null>(null);
  const [query,setQuery]=useState(""); const shown=filterRows(rows,query);
  return <TableFrame count={shown.length} query={query} onQuery={setQuery} placeholder="搜索公司、代码或产业链位置"><div className="logic-scroll"><table className="logic-table"><thead><tr><th>公司 / 代码</th><th>赛道</th><th>产业链位置</th><th>{industry?"核心业务":"入池逻辑"}</th><th>市值</th><th>研究阶段</th><th>关键缺口</th><th>档案</th></tr></thead><tbody>{shown.map(r=><RowGroup key={r.code} open={open===r.code} onOpen={()=>setOpen(open===r.code?null:r.code)} cells={[
    <><b>{r.name}</b><small>{r.stockCode||r.code}</small></>,<Badge tone={tracks[r.track]}>{r.track}</Badge>,r.chain,industry?r.coreBusiness:r.reason,r.marketCap,<Status value={r.stage}/>,r.metadata?.key_gap||r.keyAssumptions,<Link href={`/company/${r.code}`}>完整档案 <ArrowRight size={13}/></Link>
  ]}><DetailGrid items={[["核心产品 / 业务",r.coreBusiness],["已确认数据",r.metadata?.confirmed_data],["业务状态",r.metadata?.business_stage||r.metadata?.robot_business_status],["利润核算状态",accountingLabel(r.accountingStatus)],["当前阻断原因",r.accountingBlocker],["客户 / 验证",r.metadata?.customers_validation],["关键假设",r.keyAssumptions],["下一验证节点",r.metadata?.next_verification]]}/></RowGroup>)}</tbody></table></div></TableFrame>;
}
function ProfitTable({rows,parameters}:{rows:any[];parameters:any[]}){
  const [open,setOpen]=useState<string|null>(null);
  const [query,setQuery]=useState("");
  const scenarioOrder:any={悲观:0,中性:1,乐观:2};
  const grouped=Object.values(filterRows(rows,query).reduce((acc:any,r:any)=>{(acc[r.companyName]??=[]).push(r);return acc},{})).map((items:any)=>items.sort((a:any,b:any)=>(scenarioOrder[a.scenario]??9)-(scenarioOrder[b.scenario]??9)));
  const completeness=(items:any[])=>{const r=items.find(x=>x.scenario==="中性")||items[0];return [r.units,r.asp,r.gross_margin,r.expense_ratio,r.legacy_profit,r.pe_multiple,r.reference_market_cap,r.evidence].filter(v=>v!=null&&v!=="").length};
  grouped.sort((a:any,b:any)=>completeness(b)-completeness(a)||String(a[0].companyName).localeCompare(String(b[0].companyName),"zh-CN"));
  return <TableFrame count={grouped.length} query={query} onQuery={setQuery} placeholder="搜索公司或核算假设"><div className="profit-groups">
    {(grouped as any[]).map((items:any[])=>{const base=items.find(x=>x.scenario==="中性")||items[0];const name=base.companyName;const done=completeness(items);const missing=[...new Set(items.flatMap(x=>x.missing_inputs||[]))];const isOpen=open===name;return <section className={`profit-company ${isOpen?"open":""}`} key={name}>
      <button className="profit-company-head" onClick={()=>setOpen(isOpen?null:name)}><span><b>{name}</b><small>{base.companyCode||""} · {base.fiscal_year}E · {modelTypeLabel(base.model_type)}</small></span><span><small>利润可信度</small><b><Confidence value={base.profit_confidence}/></b></span><span><small>核算完成度</small><b className={done>=7?"done":"pending"}>{done}/8</b></span><span className="missing-cell"><small>核心未确认变量</small><b>{missing.length?missing.join("、"):"参数已完整"}</b></span><span><small>当前结论</small><b>{base.model_status==="complete"?"可用于决策":"数据不足 / 待核实"}</b></span><ChevronDown size={17}/></button>
      {isOpen&&<div className="profit-detail"><div className="logic-scroll"><table className="logic-table profit-scenario-table"><thead><tr><th>情景</th><th>模型类型</th><th>收入</th><th>毛利率</th><th>费用率</th><th>增量净利润</th><th>传统业务利润</th><th>总归母净利润</th><th>估值倍数</th><th>目标市值</th><th>状态</th></tr></thead><tbody>{items.map(r=><tr key={r.id}><td><Status value={r.scenario}/></td><td>{modelTypeLabel(r.model_type)}</td><td>{modelValue(r.revenue,"亿")}</td><td>{modelPct(r.gross_margin)}</td><td>{modelPct(r.expense_ratio)}</td><td>{modelValue(r.net_profit,"亿")}</td><td>{modelValue(r.legacy_profit,"亿")}</td><td>{modelValue(r.total_profit,"亿")}</td><td>{modelMultiple(r.pe_multiple,false)}</td><td>{modelValue(r.target_market_cap,"亿")}</td><td><Status value={r.model_status==="complete"?"可用于决策":"待关键数据"}/></td></tr>)}</tbody></table></div>
        <div className="evidence-title"><div><strong>查看依据</strong><span>原始输入、证据等级与推算逻辑</span></div><small>事实 ≠ 预测 ≠ 推算 ≠ 假设</small></div>
        {items.map(r=>{const ps=parameters.filter((p:any)=>p.profit_model_id===r.id);return <section className="scenario-evidence" key={`e-${r.id}`}><h3>{r.scenario}情景 · {r.fiscal_year}E</h3><div className="logic-scroll"><table className="logic-table evidence-table"><thead><tr><th>参数</th><th>数值</th><th>数据类型</th><th>证据</th><th>来源</th><th>状态</th><th>推算逻辑</th></tr></thead><tbody>{ps.map((p:any)=><tr key={p.id}><td><b>{p.parameter_name}</b><small>{p.parameter_key}</small></td><td>{p.parameter_value==null?"待核实":`${Number(p.parameter_value).toLocaleString("zh-CN")}${p.unit||""}`}</td><td><DataType value={p.data_type}/></td><td><Evidence value={p.evidence_grade}/></td><td>{p.source_url?<a href={p.source_url} target="_blank" rel="noreferrer">{p.source_name||"原始来源"} <ExternalLink size={12}/></a>:(p.source_name||"待补来源")}</td><td>{p.is_confirmed?"已确认":"待核实"}</td><td>{p.derivation_logic||"—"}</td></tr>)}</tbody></table></div><DetailGrid items={[["使用公式",r.calculation_trace?.formula],["中间结果",traceLine(r.calculation_trace?.intermediate)],["最终结果",r.total_profit==null?"关键参数不足，未输出正式净利润":`${r.total_profit}亿元`],["最大不确定性",r.max_uncertainty],["最需要验证",r.most_needed_evidence]]}/></section>})}
      </div>}
    </section>})}
  </div><div className="formula-note"><b>统一利润链：</b>业务模型输入 → 收入 → 毛利润 → 销售/管理/研发/财务费用 → 税 → 新业务归母净利润 → 传统业务利润 → 总归母净利润</div></TableFrame>;
}
function OddsTable({rows,firms,parameters}:{rows:any[];firms:any[];parameters:any[]}){
  const [open,setOpen]=useState<string|null>(null);
  const [query,setQuery]=useState(""); const shown=filterRows(rows,query).sort((a,b)=>Number(b.expected_return)-Number(a.expected_return));
  return <TableFrame count={shown.length} query={query} onQuery={setQuery} placeholder="搜索公司、状态或变化原因"><div className="logic-scroll"><table className="logic-table expectation-table"><thead><tr><th>日期</th><th>公司</th><th>当前价 / 市值</th><th>悲观收益</th><th>中性收益</th><th>乐观收益</th><th>期望收益</th><th>年化期望</th><th>最大下行</th><th>风险收益比</th><th>可信度</th><th>较上次</th><th>当前状态</th></tr></thead><tbody>{shown.map(r=>{const s=r.scenario_results||{};const firm=firms.find(f=>f.code===r.external_code);const ps=parameters.filter((p:any)=>p.profit_models?.company_id===r.company_id);const quality=qualityCounts(ps);return <RowGroup key={r.id} open={open===r.id} onOpen={()=>setOpen(open===r.id?null:r.id)} cells={[
    r.trade_date,<><b>{r.company_name}</b><small>{firm?.stockCode||r.stock_code}</small></>,<>{money(r.current_price,"元")}<small>{money(r.current_market_cap,"亿")}</small></>,scenarioCell(s["悲观"]),scenarioCell(s["中性"]),scenarioCell(s["乐观"]),<strong className="expected-main">{returnPct(r.expected_return)}</strong>,returnPct(r.annualized_expected_return),returnPct(r.max_assumed_downside),r.risk_reward_ratio==null?"待核实":Number(r.risk_reward_ratio).toFixed(2),<><Confidence value={r.profit_confidence}/><small>利润 / 概率</small><Confidence value={r.probability_confidence}/></>,returnPct(r.change_vs_previous),<Status value={r.research_status}/>
  ]}><div className="expectation-evidence"><div className="expectation-cards">{["悲观","中性","乐观"].map(x=><article key={x}><span>{x}情景 · 概率 {s[x]?.probability_pct??"—"}%</span><strong>{returnPct(s[x]?.return)}</strong><small>净利润 {money(s[x]?.net_profit,"亿")} · {s[x]?.valuation_method||"—"} {s[x]?.valuation_multiple??"—"}倍</small><p>目标市值 {money(s[x]?.target_market_cap,"亿")}</p></article>)}</div><div className="quality-strip"><b>数据质量</b><span>A 事实 {quality.fact}</span><span>B 可靠参考 {quality.reference}</span><span>C 模型推算 {quality.inference}</span><span>D 人工假设 {quality.assumption}</span><em>核心风险：{firm?.metadata?.gaps||"待补充"}</em></div><DetailGrid items={[["查看依据",r.calculation_trace?.formula],["股价来源",r.calculation_trace?.price_source?.url?<a href={r.calculation_trace.price_source.url} target="_blank" rel="noreferrer">{r.calculation_trace.price_source.name} <ExternalLink size={12}/></a>:"待补来源"],["本次为什么变化",r.change_reason],["变化驱动",driverLabel(r.change_driver)],["目标兑现时间",`${r.target_date} · 约${Number(r.years_to_target).toFixed(1)}年`],["模型指纹",r.model_fingerprint?.slice(0,16)+"…"]]}/></div></RowGroup>})}</tbody></table></div><div className="formula-note"><b>期望收益：</b>悲观收益×悲观概率 + 中性收益×中性概率 + 乐观收益×乐观概率。股价只改变收益空间，不直接改变基本面概率。</div>{shown.length===0&&<div className="blocked-empty"><strong>暂无可排序的正式期望收益</strong><p>只有“三情景利润完整 + 概率合计100% + 最新价格已入库”的公司才会出现；缺口会保留在Step 4并显示具体原因。</p></div>}</TableFrame>;
}
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
function filterRows(rows:any[],query:string){const q=query.trim().toLowerCase();return q?rows.filter(r=>JSON.stringify(r).toLowerCase().includes(q)):rows}
