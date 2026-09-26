"use client";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import {
  Shell,
  Badge,
  firms as fallbackFirms,
  sigs as fallbackSigs,
  tracks,
} from "./research-ui";
import { useResearchData } from "../hooks/use-research-data";

const stageLinks: any = {
  change_discovery: ["STEP 1", "变化发现", "信号", "/signals"],
  opportunity_confirmation: ["STEP 2", "机会确认", "机会", "/opportunities"],
  company_mapping: ["STEP 3", "公司映射", "公司", "/companies"],
  company_modeling: ["STEP 4", "公司建模", "模型", "/modeling"],
  investment_value: ["STEP 5", "投资价值", "评估结果", "/odds"],
};
export default function Home() {
  const d = useResearchData(fallbackFirms, fallbackSigs),
    latest = d.reports[0],
    day = latest?.report_date;
  const ds = d.screeningDecisions || [];
  const count = (stage: string, test = (x: any) => x.decision !== "fail") =>
    new Set(
      ds
        .filter((x: any) => x.stage === stage && test(x))
        .map((x: any) => x.object_id),
    ).size;
  const chain = [
    ["change_discovery", count("change_discovery")],
    ["opportunity_confirmation", count("opportunity_confirmation")],
    ["company_mapping", count("company_mapping")],
    [
      "company_modeling",
      count("company_modeling", (x: any) =>
        ["pass", "observe"].includes(x.decision),
      ),
    ],
    ["investment_value", count("investment_value")],
  ];
  const completedModels = new Set(
    d.profitModels
      .filter((x: any) => x.model_status === "complete")
      .map((x: any) => x.company_id),
  ).size;
  const high = count("high_expected_return", (x: any) => x.decision === "pass"),
    observe = d.firms.filter(
      (x: any) => x.researchPoolStatus === "shadow",
    ).length,
    failed = count("high_expected_return", (x: any) => x.decision === "fail");
  const todays = (arr: any[], field: string) =>
    arr.filter((x: any) => String(x[field] || "").startsWith(day || ""));
  const changes = [
    [
      "今日新增重要信号",
      d.sigs.filter((x: any) => x.date === day).length,
      "/signals",
    ],
    [
      "新增机会",
      d.opportunities.filter((x: any) =>
        String(x.created_at || "").startsWith(day || ""),
      ).length,
      "/opportunities",
    ],
    [
      "公司升级",
      todays(d.stateTransitions, "created_at").filter((x: any) =>
        /research|high_expected/.test(x.to_status || ""),
      ).length,
      "/companies",
    ],
    [
      "公司降级",
      todays(d.stateTransitions, "created_at").filter((x: any) =>
        /shadow|watch/.test(x.to_status || ""),
      ).length,
      "/companies",
    ],
    [
      "观察重新激活",
      todays(d.stateTransitions, "created_at").filter(
        (x: any) =>
          /shadow|watch/.test(x.from_status || "") &&
          !/shadow|watch/.test(x.to_status || ""),
      ).length,
      "/companies",
    ],
    [
      "新进入建模",
      new Set(
        todays(d.profitModels, "created_at").map((x: any) => x.company_id),
      ).size,
      "/modeling",
    ],
    [
      "完成建模",
      new Set(
        todays(d.profitModels, "updated_at")
          .filter((x: any) => x.model_status === "complete")
          .map((x: any) => x.company_id),
      ).size,
      "/modeling",
    ],
    [
      "完成投资价值评估",
      todays(d.investmentAssessments, "assessed_at").length,
      "/odds",
    ],
    [
      "进入高期望收益",
      todays(d.investmentAssessments, "assessed_at").filter(
        (x: any) => x.passed,
      ).length,
      "/odds",
    ],
    [
      "退出高期望收益",
      todays(d.stateTransitions, "created_at").filter((x: any) =>
        String(x.from_status).includes("high"),
      ).length,
      "/odds",
    ],
  ];
  const biggest = [...d.expectedReturns].sort(
    (a: any, b: any) =>
      Number(b.expected_return_change || 0) -
      Number(a.expected_return_change || 0),
  )[0];
  const model = [...d.modelChanges].sort((a: any, b: any) =>
    String(b.changed_at).localeCompare(String(a.changed_at)),
  )[0];
  const risk = d.validationEvents.find((x: any) =>
    ["negative", "weaken", "invalidated"].includes(x.effect),
  );
  return (
    <Shell active="研究总览">
      <header className="research-head">
        <div>
          <p className="eyebrow">V4.2 · RESEARCH PIPELINE</p>
          <h1>研究总览</h1>
          <p>整个研究系统现在运行到哪里了？</p>
        </div>
        <div className="health">
          <i />
          {d.live ? "数据库实时数据" : "正在连接数据库"}
        </div>
      </header>
      <section className="overview-grid">
        <div className="pipeline-panel">
          <div className="section-kicker">
            <span>研究筛选链</span>
            <small>每一步统计对象不同，数字不是同一对象的转化漏斗</small>
          </div>
          <div className="pipeline">
            {chain.map(([stage, n]: any, i: number) => {
              const x = stageLinks[stage];
              return (
                <Link href={x[3]} key={stage} className="pipeline-node">
                  <small>{x[0]}</small>
                  <b>{x[1]}</b>
                  <strong>{n}</strong>
                  <span>
                    {x[2]}
                    {stage === "company_modeling"
                      ? ` · ${completedModels}家完成`
                      : ""}
                  </span>
                  {i < chain.length - 1 && <i>↓</i>}
                </Link>
              );
            })}
          </div>
          <div className="final-states">
            <span>最终状态</span>
            <Link href="/odds">
              <b>{high}</b> 高期望收益
            </Link>
            <Link href="/companies">
              <b>{observe}</b> 观察
            </Link>
            <Link href="/odds">
              <b>{failed}</b> 不通过
            </Link>
          </div>
        </div>
        <div className="today-change-panel">
          <div className="section-kicker">
            <span>今日重要变化</span>
            <small>{day || "暂无日报日期"}</small>
          </div>
          <div className="today-change-list">
            {changes.map(([label, n, href]: any) => (
              <Link href={href} key={label}>
                <span>{label}</span>
                <b>{n}</b>
                <ArrowRight size={14} />
              </Link>
            ))}
          </div>
          <div className="change-highlights">
            <article>
              <span>赔率改善最大</span>
              <b>{biggest?.company_name || "暂无数据"}</b>
              <small>{pct(biggest?.expected_return_change)}</small>
            </article>
            <article>
              <span>模型变化最大</span>
              <b>{model?.companies?.name || "暂无数据"}</b>
              <small>{model?.change_reason || "今日无模型修正"}</small>
            </article>
            <article>
              <span>风险恶化公司</span>
              <b>{risk?.companies?.name || "暂无数据"}</b>
              <small>{risk?.conclusion || "今日无新增负面验证"}</small>
            </article>
          </div>
        </div>
      </section>
      <section className="overview-summary">
        <div>
          <Badge tone={tracks[latest?.strongest_sector]}>
            {latest?.strongest_sector || "待确认"}
          </Badge>
          <h2>{latest?.summary || "暂无最新日报结论"}</h2>
          <p>
            第一屏给出结论和变化；详细证据、模型与历史记录进入对应阶段查看。
          </p>
        </div>
        <Link href="/daily">
          打开完整日报
          <ArrowRight size={16} />
        </Link>
      </section>
    </Shell>
  );
}
function pct(v: any) {
  return v == null
    ? "待计算"
    : `${Number(v) >= 0 ? "+" : ""}${(Number(v) * 100).toFixed(1)}%`;
}
