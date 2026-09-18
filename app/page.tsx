"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, ExternalLink } from "lucide-react";
import { Shell, Badge, firms as fallbackFirms, sigs as fallbackSigs, tracks } from "./research-ui";
import { useResearchData } from "../hooks/use-research-data";

export default function Home() {
  const data = useResearchData(fallbackFirms, fallbackSigs);
  const recentReports = data.reports.slice(0,7);
  const [selectedId,setSelectedId] = useState<string>("");
  useEffect(()=>{if(!selectedId&&recentReports[0]?.id)setSelectedId(recentReports[0].id)},[recentReports,selectedId]);
  const report = recentReports.find((r:any)=>r.id===selectedId) || recentReports[0];
  const todaySignals = data.sigs.filter((s:any)=>s.date===report?.report_date);
  const sections = splitReport(report?.report_markdown || "");
  const trackLines = (sections["30秒结论"]||[]).filter((x:string)=>/^(机器人|商业航天|AI)/.test(x));
  const quality = report?.coverage_quality || {};
  const clues = data.rawClues.filter((x:any)=>x.occurred_on===report?.report_date);
  const sectorReviews = data.sectorReviews.filter((x:any)=>x.report_date===report?.report_date);
  return <Shell active="日报">
    <header className="daily-desk-head">
      <div><p className="eyebrow">{report?.report_date || "实时更新"} · THREE SECTOR DAILY</p><h1>三大赛道机会日报</h1><p>先看结论和筛选结果，再进入明细验证。</p></div>
      <div className="health"><i /> {data.live?"数据库实时数据":"正在连接数据库"}</div>
    </header>

    <nav className="report-switcher" aria-label="最近7期日报">
      <div><span>日报归档</span><small>最近7期</small></div>
      {recentReports.map((r:any,i:number)=><button className={r.id===report?.id?"active":""} onClick={()=>setSelectedId(r.id)} key={r.id}><b>{r.report_date}</b><small>{i===0?"最新":r.strongest_sector||"历史日报"}</small></button>)}
      <Link href="/daily">全部归档 <ArrowRight size={13}/></Link>
    </nav>

    <section className="funnel-strip">
      <Metric label="原始线索" value={report?.raw_clue_count??"—"} note="当日扫描总量"/>
      <ArrowRight/>
      <Metric label="有效信号" value={report?.valid_signal_count??"—"} note="达到结构化门槛"/>
      <ArrowRight/>
      <Metric label="机会变化" value={report?.new_pool_count??"—"} note="历史字段兼容显示"/>
      <ArrowRight/>
      <Metric label="待验证" value={report?.pending_verification_count??"—"} note="下一步研究"/>
      <div className="desk-status"><span>最强赛道</span><strong>{report?.strongest_sector||"—"}</strong><small>{report?.research_can_end?"当日研究已完成":"仍需继续研究"}</small></div>
    </section>

    {data.expectedReturns.length>0&&<section className="daily-signal-panel expectation-home"><PanelTitle n="00" title="投资价值评估变化" link="/odds"/><div className="expectation-home-grid">{data.expectedReturns.slice(0,3).map((x:any)=>{const a=data.investmentAssessments.find((v:any)=>v.expected_return_snapshot_id===x.id);return <article key={x.id}><span>{x.company_name}</span><strong>{x.expected_return==null?"待核实":`${Number(x.expected_return)>=0?"+":""}${(Number(x.expected_return)*100).toFixed(1)}%`}</strong><p>{x.change_reason}</p><small>{a?.classification==="high_expected_return"?"高期望收益":a?.classification==="shadow"?"影子池（已完成评估）":"待评估"}</small></article>})}</div></section>}

    {sectorReviews.length>0&&<section className="daily-signal-panel"><PanelTitle n="04" title="三赛道当日判断" link="/daily"/><div className="sector-review-grid">{sectorReviews.map((r:any)=><article key={r.id}><div><Badge tone={tracks[r.track]}>{r.track}</Badge><strong>{r.strength_score==null?"—":`${r.strength_score}/10`}</strong></div><p><b>变化：</b>{r.key_changes||"无实质变化"}</p><p><b>利润与估值：</b>{r.profit_valuation_updates||"暂无可量化变化"}</p><p><b>下一验证：</b>{r.next_verification||"待补充"}</p></article>)}</div></section>}

    {clues.length>0&&<section className="daily-signal-panel"><PanelTitle n="05" title="原始线索筛选底稿" link="/daily"/><div className="logic-scroll"><table className="logic-table compact-table"><thead><tr><th>赛道</th><th>事件</th><th>本次变化</th><th>影响</th><th>市场交易</th><th>筛选结论</th><th>淘汰原因</th><th>来源</th></tr></thead><tbody>{clues.map((c:any)=><tr key={c.id}><td><Badge tone={tracks[c.track]}>{c.track}</Badge></td><td>{c.title}</td><td>{c.current_status||c.summary}</td><td>{c.impact_score||"—"}/10</td><td>{c.market_traded_status||"待判断"}</td><td>{c.screening_status}</td><td>{c.rejection_reason||"—"}</td><td>{c.source_url?<a href={c.source_url} target="_blank" rel="noreferrer">原文 <ExternalLink size={12}/></a>:c.source_name}</td></tr>)}</tbody></table></div></section>}

    <div className="daily-overview-grid">
      <section className="daily-main-panel">
        <PanelTitle n="01" title="30秒结论" link="/daily"/>
        <p className="daily-lead">{report?.summary||"正在读取今日结论…"}</p>
        <div className="track-conclusions">{trackLines.map((line:string)=>{
          const name=line.split(/[ ：:]/)[0];
          return <div key={line}><Badge tone={tracks[name]}>{name}</Badge><p>{line.replace(new RegExp("^"+name+"[ ：:]?"),"")}</p></div>
        })}</div>
      </section>
      <aside className="coverage-panel">
        <PanelTitle n="02" title="覆盖与可信度"/>
        <Quality label="覆盖置信度" value={quality.confidence||"未记录"}/>
        <Quality label="异常扫描" value={quality.anomaly_scan||"未记录"}/>
        <Quality label="关键词矩阵" value={quality.keyword_matrix||"未记录"}/>
        <Quality label="3/7/14日回溯" value={quality.lookback_3_7_14||"未记录"}/>
        <Quality label="交叉验证" value={quality.cross_validation||"未记录"}/>
      </aside>
    </div>

    <section className="daily-signal-panel">
      <PanelTitle n="03" title="当日高价值信号" link="/signals"/>
      <div className="today-signal-head"><span>赛道 / 公司</span><span>变化类型</span><span>上一状态</span><span>本次变化</span><span>强度</span><span>动作</span></div>
      {todaySignals.length?todaySignals.map((s:any)=><Link href={`/signals/${s.id}`} className="today-signal-row" key={s.id}>
        <span><Badge tone={tracks[s.track]}>{s.track}</Badge><b>{s.company}</b></span><span>{s.type}</span><span>{s.previousStatus}</span><span>{s.change}</span><span className="score">{s.score}/5</span><span>{s.state}<ArrowRight size={14}/></span>
      </Link>):<div className="empty-row">今日暂无达到结构化门槛的新信号</div>}
    </section>

    <div className="analysis-grid">
      {Object.entries(sections).filter(([name])=>!["30秒结论"].includes(name)).map(([name,lines])=><section className="analysis-section" key={name}><h2>{name}</h2>{(lines as string[]).map((line,i)=>/^https?:\/\//.test(line)?<a key={i} href={line} target="_blank" rel="noreferrer">查看原始来源 <ExternalLink size={13}/></a>:<p key={i}>{line}</p>)}</section>)}
      {quality.gaps?.length>0&&<section className="analysis-section gap-section"><h2>当前覆盖缺口</h2>{quality.gaps.map((x:string)=><p key={x}>{x}</p>)}</section>}
    </div>
  </Shell>;
}

function Metric({label,value,note}:{label:string;value:any;note:string}){return <div className="funnel-metric"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>}
function PanelTitle({n,title,link}:{n:string;title:string;link?:string}){return <div className="panel-title"><span>{n}</span><h2>{title}</h2>{link&&<Link href={link}>查看全部 <ArrowRight size={13}/></Link>}</div>}
function Quality({label,value}:{label:string;value:string}){return <div className="quality-row"><span>{label}</span><strong>{value}</strong></div>}
function splitReport(markdown:string){
  const result:Record<string,string[]>={}; let current="";
  markdown.split("\n").forEach(raw=>{const line=raw.trim();if(!line||line.startsWith("# "))return;if(line.startsWith("## ")){current=line.slice(3);result[current]=[];return}if(!current)return;result[current].push(line.replace(/^[-*]\s+/,""))});
  return result;
}
