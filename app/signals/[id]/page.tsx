"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Shell, Badge, tracks } from "../../research-ui";
import { useResearchData } from "../../../hooks/use-research-data";
export default function Page() {
  const { id } = useParams<{ id: string }>();
  const { sigs, firms } = useResearchData([], []);
  const s = sigs.find((x) => x.id === id);
  if (!s) return null;
  const company = firms.find((x) => s.company.includes(x.name));
  return (
    <Shell active="今日工作台">
      <Link className="back" href="/signals">
        <ArrowLeft size={14} />
        返回信号列表
      </Link>
      <article className="signal-record">
        <p className="eyebrow">SIGNAL RECORD / {s.date}</p>
        <Badge tone={tracks[s.track]}>{s.track}</Badge>
        <Badge>{s.type}</Badge>
        <Badge>{s.state}</Badge>
        <h1>{s.title}</h1>
        <p className="lead">
          这条变化可能通过需求确认、供应链扩产、订单兑现和利润释放传导到上市公司。
        </p>
        <div className="signal-facts">
          {[
            ["相关公司", company ? <Link href={`/company/${company.code}`}>{s.company}</Link> : s.company],
            ["影响强度", s.score + " / 5"],
            ["影响周期", "3–12个月"],
            ["当前动作", s.state],
            ["来源名称", s.sourceName || "现有记录中无法确认"],
            ["来源类型", sourceCategoryLabel(s.sourceCategory)],
            ["发布时间", s.publishedAt?.slice(0, 16).replace("T", " ") || s.date],
            ["可信等级", `${s.sourceGrade || "待确认"} · ${s.isOfficial ? "官方" : "非官方或待确认"}`],
            ["历史可得性", availabilityLabel(s.historicalAvailability)],
          ].map((x) => (
            <div key={x[0]}>
              <span>{x[0]}</span>
              <strong>{x[1]}</strong>
            </div>
          ))}
        </div>
        <section>
          <h2>产业链传导</h2>
          <div className="flow">
            <span>需求变化</span>
            <ArrowRight />
            <span>订单验证</span>
            <ArrowRight />
            <span>产能交付</span>
            <ArrowRight />
            <span>利润兑现</span>
          </div>
        </section>
        <section>
          <h2>下一步验证</h2>
          <p>{s.verify}</p>
          {s.source && (
            <a href={s.source} target="_blank" rel="noreferrer">
              查看原始来源
            </a>
          )}
        </section>
      </article>
    </Shell>
  );
}
function sourceCategoryLabel(value: any) {
  return ({
    company: "公司", policy: "政策", demand: "需求", industry: "产业",
    supply_chain: "供应链", market: "市场验证", negative_counterevidence: "负面反证",
  } as any)[value] || "待分类";
}
function availabilityLabel(value: any) {
  return ({
    A: "A：当时公开且稳定可获得",
    B: "B：当时公开，但无法确认稳定获得",
    C: "C：今天能查到，历史实时可得性低",
    D: "D：后验整理",
  } as any)[value] || "现有记录中无法确认";
}
