"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Shell, Badge, firms as fallbackFirms, sigs as fallbackSigs, tracks } from "../../research-ui";
import { useResearchData } from "../../../hooks/use-research-data";
export default function Page() {
  const { code } = useParams<{ code: string }>();
  const data = useResearchData(fallbackFirms, fallbackSigs);
  const { firms, profitModels, valuations, snapshots } = data;
  const c = firms.find((x) => x.code === code);
  if (!c) return null;
  const companyModels = profitModels.filter((x:any)=>x.companyCode===c.code);
  const companyValuations = valuations.filter((x:any)=>x.companyCode===c.code);
  const companySnapshots = snapshots.filter((x:any)=>x.companyCode===c.code);
  const companyParameters = data.modelParameters.filter((x:any)=>x.profit_models?.company_id===c.id);
  const companyProbabilities = data.probabilities.filter((x:any)=>x.company_id===c.id);
  const companyProbabilityChanges = data.probabilityChanges.filter((x:any)=>x.company_id===c.id);
  const companyPrices = data.prices.filter((x:any)=>x.company_id===c.id);
  const companyExpected = data.expectedReturns.filter((x:any)=>x.company_id===c.id);
  const companyReverse = data.reverseValuations.filter((x:any)=>x.company_id===c.id);
  const companySensitivities = data.sensitivities.filter((x:any)=>x.company_id===c.id);
  const companyValidations = data.predictionValidations.filter((x:any)=>x.company_id===c.id);
  const companyTimeline = data.timelineEvents.filter((x:any)=>x.company_id===c.id);
  const companyTransitions = data.stateTransitions.filter((x:any)=>x.company_id===c.id);
  const companyAssessments = data.investmentAssessments.filter((x:any)=>x.company_id===c.id);
  const companyDaily = data.dailySnapshots.filter((x:any)=>x.company_id===c.id).slice().reverse().map((x:any)=>({...x,expected_return_pct:Number(x.expected_return)*100}));
  const sections = [
    ["01","公司业务",c.coreBusiness],
    ["02","为什么现在在这里",c.transitionReason || c.reason],
    ["03","产业链位置",c.chain],
    ["04","已确认经营数据",c.metadata?.confirmed_data || "待补充可追溯经营数据"],
    ["05","客户与验证",c.metadata?.customers || "待补充客户和订单验证"],
    ["06","下一步需要什么",c.reactivationCondition || c.accountingBlocker || c.keyAssumptions],
  ];
  return (
    <Shell active="公司筛选">
      <Link className="back" href="/companies">
        <ArrowLeft size={14} />
        返回公司列表
      </Link>
      <div className="record-head">
        <div>
          <Badge tone={tracks[c.track]}>{c.track}</Badge>
          <Badge>{poolLabel(c)}</Badge>
          <h1>
          {c.name} <small>{c.stockCode || c.code}</small>
          </h1>
          <p>最后更新：{c.metadata?.profile_date || c.updatedAt?.slice(0,10) || "待确认"} · V4状态机持续验证中</p>
        </div>
        <div>
          <span>综合置信度</span>
          <strong>
            {Math.round((c.score || 0) * 10)}<small>/100</small>
          </strong>
        </div>
        <div>
          <span>当前赔率</span>
          <strong>{c.odds}</strong>
        </div>
      </div>
      <div className="decision-strip">
        <div><span>当前池子</span><strong>{poolLabel(c)}</strong></div>
        <div><span>变化强度</span><strong>{c.score.toFixed(1)} / 10</strong></div>
        <div><span>为什么在这里</span><strong>{c.transitionReason||c.reason}</strong></div>
        <div><span>重新升级条件</span><strong>{c.reactivationCondition||"持续验证核心假设"}</strong></div>
      </div>
      <div className="detail-layout">
        <div className="detail-main">
          {sections.map((x) => (
            <section className="detail-section" key={x[0]}>
              <div>
                <span>{x[0]}</span>
                <h2>{x[1]}</h2>
              </div>
              <p>{x[2]}</p>
            </section>
          ))}
        </div>
        <aside className="detail-side">
          <section>
            <h3>净利润与赔率</h3>
            <dl>
              <div>
                <dt>当前市值</dt>
                <dd>{c.marketCap}</dd>
              </div>
              <div>
                <dt>目标净利润</dt>
                <dd>{c.profit}</dd>
              </div>
              <div>
                <dt>核算状态</dt>
                <dd>{valuationLabel(c.valuationStatus)}</dd>
              </div>
              <div>
                <dt>投资评估</dt>
                <dd>{assessmentLabel(c.investmentAssessmentStatus)}</dd>
              </div>
            </dl>
          </section>
          {companyModels.length > 0 && <section><h3>利润模型状态</h3><dl>{companyModels.map((m:any)=><div key={m.id}><dt>{m.fiscal_year}E · {m.scenario}</dt><dd>{m.units ? `${Number(m.units).toLocaleString()}只` : "待核算"}</dd></div>)}</dl><p>缺失参数保持为空，不输出虚假利润。</p></section>}
          <section><h3>模型可信度</h3><dl><div><dt>利润可信度</dt><dd>{confidenceLabel(companyModels[0]?.profit_confidence)}</dd></div><div><dt>概率可信度</dt><dd>{confidenceLabel(companyExpected[0]?.probability_confidence)}</dd></div><div><dt>最大不确定性</dt><dd>{companyModels[0]?.max_uncertainty||"待建立模型"}</dd></div><div><dt>最需要验证</dt><dd>{companyModels[0]?.most_needed_evidence||c.accountingBlocker||"待核实"}</dd></div></dl></section>
        </aside>
      </div>
      {companyModels.length > 0 && <section className="compact-panel model-panel"><div className="section-title"><div><span>07</span><div><h2>净利润三情景</h2><p>销量、ASP、利润及关键缺口</p></div></div></div>
        <div className="model-grid model-head"><span>年份/情景</span><span>销量</span><span>ASP</span><span>收入</span><span>净利润</span><span>状态</span></div>
        {companyModels.map((m:any)=><div className="model-grid" key={m.id}><span>{m.fiscal_year}E · {m.scenario}</span><span>{m.units??"待核实"}</span><span>{m.asp??"待核实"}</span><span>{m.revenue??"待核实"}</span><span>{m.total_profit??m.net_profit??"待核实"}</span><span>{m.status}</span></div>)}
      </section>}
      {companyValuations.length > 0 && <section className="compact-panel model-panel"><div className="section-title"><div><span>08</span><div><h2>赔率历史快照</h2><p>每次价格变化保留记录，不覆盖历史</p></div></div></div>
        <div className="model-grid model-head"><span>日期</span><span>股价</span><span>当前市值</span><span>2倍目标市值</span><span>上行倍数</span><span>结论</span></div>
        {companyValuations.map((v:any)=><div className="model-grid" key={v.id}><span>{v.valuation_date}</span><span>{v.current_price??"—"}</span><span>{v.reference_market_cap??"—"}亿</span><span>{v.target_market_cap??"—"}亿</span><span>{v.upside_multiple?Number(v.upside_multiple).toFixed(2)+"x":"待核算"}</span><span>{v.conclusion}</span></div>)}
      </section>}
      <section className="compact-panel model-panel"><div className="section-title"><div><span>09</span><div><h2>投资时间轴</h2><p>关键节点默认展示；旧记录只追加，不覆盖</p></div></div></div>
        {companyTimeline.length?companyTimeline.map((e:any)=><details className="investment-event" key={e.id}><summary><time>{e.event_at?.slice(0,10)}</time><span><b>{eventTypeLabel(e.event_type)}</b><strong>{e.title}</strong><small>{e.change_reason}</small></span><span><b>股价 / 市值</b><strong>{e.price==null?"—":`${e.price}元`} / {e.market_cap==null?"—":`${e.market_cap}亿`}</strong></span><span><b>中性概率</b><strong>{e.probability_base==null?"—":`${e.probability_base}%`}</strong></span><span><b>期望收益</b><strong>{returnPct(e.expected_return)}</strong></span><span><b>状态</b><strong>{e.system_status}</strong></span></summary><div className="event-detail"><DetailBlock label="事件摘要" value={e.description}/><DetailBlock label="变化前" value={jsonText(e.previous_state)}/><DetailBlock label="变化后" value={jsonText(e.current_state)}/><DetailBlock label="完整计算" value={jsonText(e.calculation_trace)}/><div><span>原始来源</span>{e.source_url?<a href={e.source_url} target="_blank" rel="noreferrer">打开原文 <ExternalLink size={12}/></a>:<p>本节点无外部来源</p>}</div></div></details>):<Empty text="尚未形成关键投资节点"/>}
        {companySnapshots.length>0&&<details className="legacy-timeline"><summary>查看旧版研究快照（{companySnapshots.length}）</summary>{companySnapshots.map((s:any)=><div className="timeline-row" key={s.id}><time>{s.snapshot_date}</time><div><strong>{s.conclusion_status}</strong><p>{s.thesis}</p></div></div>)}</details>}
        {companyTransitions.length>0&&<details className="legacy-timeline"><summary>查看V4状态流转（{companyTransitions.length}）</summary>{companyTransitions.map((s:any)=><div className="timeline-row" key={s.id}><time>{s.created_at?.slice(0,10)}</time><div><strong>{s.from_status||"首次分类"} → {s.to_status}</strong><p>{s.transition_reason}</p></div></div>)}</details>}
      </section>
      <section className="compact-panel model-panel"><div className="section-title"><div><span>10</span><div><h2>股价 vs 期望收益</h2><p>每日快照自动积累；价格变化不会改写基本面概率</p></div></div></div>
        {companyDaily.length?<><div className="trend-chart"><ResponsiveContainer width="100%" height={280}><LineChart data={companyDaily} margin={{top:18,right:20,left:8,bottom:8}}><XAxis dataKey="trade_date" stroke="#657f8c"/><YAxis yAxisId="price" stroke="#65d7d0"/><YAxis yAxisId="return" orientation="right" stroke="#d7aa62" unit="%"/><Tooltip contentStyle={{background:"#0b1821",border:"1px solid #29424e"}}/><Line yAxisId="price" type="monotone" dataKey="close_price" name="股价（元）" stroke="#65d7d0" strokeWidth={2}/><Line yAxisId="return" type="monotone" dataKey="expected_return_pct" name="期望收益（%）" stroke="#d7aa62" strokeWidth={2}/></LineChart></ResponsiveContainer></div><div className="daily-snapshot-list">{companyDaily.map((d:any)=><span key={d.id}><b>{d.trade_date}</b> 收盘 {d.close_price}元 · 期望 {returnPct(d.expected_return)} · 概率 {d.bear_probability}/{d.base_probability}/{d.bull_probability} · {driverLabel(d.change_driver)}</span>)}</div></>:<Empty text="尚未保存每日模型快照"/>}
      </section>
      <section className="compact-panel model-panel"><div className="section-title"><div><span>10</span><div><h2>参数依据</h2><p>事实、预测、推算和人工假设分开显示</p></div></div></div>
        {companyParameters.length?<div className="logic-scroll"><table className="logic-table evidence-table"><thead><tr><th>情景</th><th>参数</th><th>数值</th><th>类型</th><th>证据等级</th><th>来源</th><th>状态</th><th>推算逻辑</th></tr></thead><tbody>{companyParameters.map((p:any)=><tr key={p.id}><td>{p.profit_models?.scenario}</td><td><b>{p.parameter_name}</b><small>{p.parameter_key}</small></td><td>{p.parameter_value==null?"待核实":`${Number(p.parameter_value).toLocaleString("zh-CN")}${p.unit||""}`}</td><td>{dataTypeLabel(p.data_type)}</td><td><span className={`evidence-grade grade-${String(p.evidence_grade).toLowerCase()}`}>{p.evidence_grade}</span></td><td>{p.source_url?<a href={p.source_url} target="_blank" rel="noreferrer">{p.source_name||"原始来源"} <ExternalLink size={12}/></a>:(p.source_name||"待补来源")}</td><td>{p.is_confirmed?"已确认":"待核实"}</td><td>{p.derivation_logic||"—"}</td></tr>)}</tbody></table></div>:<Empty text="尚未建立参数级依据"/>}
      </section>
      <section className="compact-panel model-panel"><div className="section-title"><div><span>11</span><div><h2>概率与动态期望收益</h2><p>概率只随基本面证据变化；价格只改变收益空间</p></div></div></div>
        {companyExpected.length?<>{companyExpected.map((e:any)=><div className="expectation-summary" key={e.id}><div><span>期望收益</span><strong>{returnPct(e.expected_return)}</strong></div><div><span>年化期望</span><strong>{returnPct(e.annualized_expected_return)}</strong></div><div><span>最大假设下行</span><strong>{returnPct(e.max_assumed_downside)}</strong></div><div><span>风险收益比</span><strong>{e.risk_reward_ratio==null?"待核实":Number(e.risk_reward_ratio).toFixed(2)}</strong></div><p>{e.change_reason}</p></div>)}<div className="logic-scroll"><table className="logic-table"><thead><tr><th>情景</th><th>概率</th><th>可信度</th><th>对应事件</th><th>依据</th><th>生效时间</th></tr></thead><tbody>{companyProbabilities.map((p:any)=><tr key={p.id}><td>{p.scenario}</td><td>{p.probability_pct}%</td><td>{confidenceLabel(p.probability_confidence)}</td><td>{p.target_event}</td><td>{p.rationale}</td><td>{p.effective_at?.slice(0,10)}</td></tr>)}</tbody></table></div></>:<Empty text="利润模型或三情景概率尚不完整，未生成正式期望收益"/>}
        {companyProbabilityChanges.length>0&&<div className="history-mini"><h3>概率调整历史</h3>{companyProbabilityChanges.map((p:any)=><p key={p.id}><b>{p.changed_at?.slice(0,10)} · {p.scenario}</b> {p.previous_probability_pct??"—"}% → {p.new_probability_pct}% · {p.reason}</p>)}</div>}
        {companyAssessments.length>0&&<div className="history-mini"><h3>V4投资价值分流</h3>{companyAssessments.map((a:any)=><p key={a.id}><b>{a.classification==="high_expected_return"?"高期望收益":"影子池"}</b> {a.failure_reasons?.length?`未通过：${a.failure_reasons.join("；")}`:"已通过当前配置门槛"}</p>)}</div>}
      </section>
      <section className="compact-panel model-panel"><div className="section-title"><div><span>12</span><div><h2>价格、反向估值与敏感性</h2><p>先问当前价格隐含了多少利润，再看模型最怕哪个变量</p></div></div></div>
        {companyPrices.length?<div className="logic-scroll"><table className="logic-table"><thead><tr><th>交易日</th><th>收盘价</th><th>市值</th><th>来源</th><th>证据等级</th></tr></thead><tbody>{companyPrices.map((p:any)=><tr key={p.id}><td>{p.trade_date}</td><td>{p.close_price}元</td><td>{p.market_cap}亿元</td><td>{p.source_url?<a href={p.source_url} target="_blank" rel="noreferrer">{p.source_name} <ExternalLink size={12}/></a>:p.source_name}</td><td>{p.evidence_grade}</td></tr>)}</tbody></table></div>:<Empty text="尚未接入可追溯价格快照"/>}
        {companyReverse.length>0&&<div className="reverse-grid">{companyReverse.map((r:any)=><article key={`${r.target_multiple}-${r.pe_multiple}`}><span>{r.target_multiple}倍市值 · {r.pe_multiple}倍PE</span><strong>需净利润 {Number(r.required_net_profit).toFixed(2)}亿</strong><small>目标市值 {Number(r.target_market_cap).toFixed(1)}亿</small></article>)}</div>}
        {companySensitivities.length?<div className="logic-scroll"><table className="logic-table"><thead><tr><th>变量</th><th>基准</th><th>冲击后</th><th>净利润</th><th>目标市值</th><th>期望收益</th><th>风险提示</th></tr></thead><tbody>{companySensitivities.map((s:any)=><tr key={s.id}><td>{s.parameter_key}</td><td>{s.base_value}</td><td>{s.shocked_value}</td><td>{s.resulting_net_profit??"待核实"}</td><td>{s.resulting_target_market_cap??"待核实"}</td><td>{returnPct(s.resulting_expected_return)}</td><td>{s.risk_note}</td></tr>)}</tbody></table></div>:<Empty text="正式模型未完成，暂不输出敏感性结果"/>}
      </section>
      <section className="compact-panel model-panel"><div className="section-title"><div><span>13</span><div><h2>预测结果验证</h2><p>记录当时判断，30/90/180日及一年后反查对错</p></div></div></div>{companyValidations.length?<div className="logic-scroll"><table className="logic-table"><thead><tr><th>首次入选</th><th>入选价</th><th>当日期望收益</th><th>30日</th><th>90日</th><th>180日</th><th>一年</th><th>最大涨幅</th><th>最大回撤</th><th>结果</th></tr></thead><tbody>{companyValidations.map((v:any)=><tr key={v.id}><td>{v.first_qualified_at}</td><td>{v.entry_price}</td><td>{returnPct(v.entry_expected_return)}</td><td>{v.price_30d??"待验证"}</td><td>{v.price_90d??"待验证"}</td><td>{v.price_180d??"待验证"}</td><td>{v.price_1y??"待验证"}</td><td>{returnPct(v.max_gain)}</td><td>{returnPct(v.max_drawdown)}</td><td>{v.final_result||"pending"}</td></tr>)}</tbody></table></div>:<Empty text="尚未出现满足门槛的正式高期望收益候选"/>}</section>
    </Shell>
  );
}

function Empty({text}:{text:string}){return <div className="blocked-empty"><strong>{text}</strong><p>缺失项保持为空，不使用测试值或假设值冒充正式结果。</p></div>}
function confidenceLabel(v:any){return ({high:"高",medium:"中",low:"低"} as any)[v]||"待核实"}
function dataTypeLabel(v:any){return ({fact:"A 直接事实",reliable_reference:"B 可靠参考",external_forecast:"B 外部预测",model_inference:"C 模型推算",manual_assumption:"D 人工假设"} as any)[v]||v||"待核实"}
function returnPct(v:any){return v==null?"待核实":`${Number(v)>=0?"+":""}${(Number(v)*100).toFixed(1)}%`}
function eventTypeLabel(v:any){return ({first_discovery:"首次发现",focus_research:"重点研究",formal_pool:"正式入池",fundamental_change:"基本面变化",price_change:"价格变化",model_revision:"模型修正",validation:"结果验证",risk_deterioration:"风险恶化",downgrade:"降级",exit:"退出",current:"当前节点"} as any)[v]||v}
function driverLabel(v:any){return ({initial:"首次建立",price:"价格驱动",fundamental:"基本面驱动",model_revision:"模型修正",validation:"结果验证",risk:"风险变化"} as any)[v]||v||"待核实"}
function jsonText(v:any){if(!v||Object.keys(v).length===0)return "—";return JSON.stringify(v,null,2)}
function DetailBlock({label,value}:{label:string;value:any}){return <div><span>{label}</span><pre>{value||"—"}</pre></div>}
function poolLabel(c:any){return c.companyRole==="industry_validator"?"产业验证对象":({research:"研究池",shadow:"影子池",filtered:"筛除",archived:"淘汰/归档"} as any)[c.researchPoolStatus]||c.stage||"待分类"}
function valuationLabel(v:any){return ({not_started:"未开始",in_progress:"核算中",completed:"已完成",insufficient_data:"数据不足"} as any)[v]||"待分类"}
function assessmentLabel(v:any){return ({not_evaluated:"未评估",evaluated:"已完成评估",high_expected_return:"高期望收益",shadow:"影子池",failed:"不通过"} as any)[v]||"待分类"}
