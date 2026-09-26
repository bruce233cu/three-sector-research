"use client";
import { useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  ArrowRight,
  CircleHelp,
  ExternalLink,
  Info,
  RotateCcw,
  Search,
  X,
} from "lucide-react";
import {
  Shell,
  Badge,
  firms as fallbackFirms,
  sigs as fallbackSigs,
  tracks,
} from "../research-ui";
import { useResearchData } from "../../hooks/use-research-data";

const modules: Record<string, any> = {
  daily: {
    nav: "每日研究日报",
    title: "每日研究日报",
    desc: "今天整个研究系统到底发生了什么？",
    eyebrow: "DAILY RESEARCH REPORT",
  },
  signals: {
    nav: "变化发现",
    title: "变化发现",
    desc: "哪些新变化值得继续研究？",
    eyebrow: "CHANGE DISCOVERY · STEP 1",
  },
  opportunities: {
    nav: "机会池",
    title: "机会池",
    desc: "哪些变化已经形成真正的产业机会？",
    eyebrow: "OPPORTUNITY CONFIRMATION · STEP 2",
  },
  companies: {
    nav: "公司筛选",
    title: "公司映射与筛选",
    desc: "这个机会最终会让哪些公司真正受益？",
    eyebrow: "COMPANY MAPPING · STEP 3",
  },
  modeling: {
    nav: "公司建模",
    title: "公司建模",
    desc: "如果逻辑兑现，这家公司未来可能赚多少钱、值多少钱？",
    eyebrow: "COMPANY MODELING · STEP 4",
  },
  odds: {
    nav: "投资价值",
    title: "投资价值",
    desc: "今天哪些公司当前投资价值更高？",
    eyebrow: "INVESTMENT VALUE",
  },
  timeline: {
    nav: "公司时间轴",
    title: "公司时间轴",
    desc: "从第一次发现到现在，公司研究如何演化？",
    eyebrow: "COMPANY RESEARCH HISTORY",
  },
  validation: {
    nav: "验证中心",
    title: "验证中心",
    desc: "过去的判断后来是否兑现？",
    eyebrow: "VALIDATION CENTER",
  },
  "historical-validation": {
    nav: "历史验证",
    title: "历史验证",
    desc: "回到历史某一天时，系统是否真的看不到未来？",
    eyebrow: "V4.4 · HISTORICAL INFORMATION VALIDATION",
  },
  sources: {
    nav: "信息源",
    title: "信息源",
    desc: "每类信息从哪里来、是否真的在采、能不能用于历史验证？",
    eyebrow: "V4.4.1 · SOURCE FOUNDATION",
  },
  guide: {
    nav: "系统说明",
    title: "系统说明",
    desc: "五阶段筛选链与横向验证机制如何协同。",
    eyebrow: "V4.2 SYSTEM GUIDE",
  },
  "system-log": {
    nav: "系统优化记录",
    title: "系统优化记录",
    desc: "整个研究系统是怎样一步步改到今天的？",
    eyebrow: "SYSTEM GROWTH RECORD",
  },
  profit: {
    nav: "公司中心",
    title: "利润与估值",
    desc: "旧入口已并入公司详情的“模型与估值”。",
    eyebrow: "MODEL ARCHIVE",
  },
  industry: {
    nav: "机会中心",
    title: "产业链地图",
    desc: "旧入口已并入机会详情的“产业链”。",
    eyebrow: "INDUSTRY MAP ARCHIVE",
  },
};
export default function Page() {
  const { module } = useParams<{ module: string }>();
  const data = useResearchData(fallbackFirms, fallbackSigs);
  const config = modules[module];
  const [help, setHelp] = useState(false);
  if (!config) return null;
  return (
    <Shell active={config.nav}>
      <header className="research-head">
        <div>
          <p className="eyebrow">{config.eyebrow}</p>
          <h1>{config.title}</h1>
          <p>{config.desc}</p>
        </div>
        <div className="head-actions">
          <button className="help-button" onClick={() => setHelp(true)}>
            <CircleHelp size={16} />
            本页说明
          </button>
          <div className="health">
            <i />
            {data.live ? "数据库实时数据" : "正在连接数据库"}
          </div>
        </div>
      </header>
      <ModuleView module={module} data={data} />
      {help && <HelpDrawer module={module} onClose={() => setHelp(false)} />}
    </Shell>
  );
}
function ModuleView({ module, data }: { module: string; data: any }) {
  if (module === "daily") return <DailyReport data={data} />;
  if (module === "signals") return <SignalDiscovery data={data} />;
  if (module === "opportunities") return <OpportunityCenter data={data} />;
  if (module === "companies") return <CompanyScreening data={data} />;
  if (module === "modeling") return <ModelingCenter data={data} />;
  if (module === "odds") return <InvestmentValue data={data} />;
  if (module === "timeline") return <TimelineCenter data={data} />;
  if (module === "validation") return <ValidationCenter data={data} />;
  if (module === "historical-validation")
    return <HistoricalValidation data={data} />;
  if (module === "sources") return <SourceRegistryView data={data} />;
  if (module === "guide") return <GuideView />;
  if (module === "system-log") return <SystemOptimizationLog data={data} />;
  if (module === "profit") return <LegacyModels data={data} />;
  if (module === "industry")
    return <OpportunityCenter data={data} industryOnly />;
  return null;
}

function OpportunityCenter({
  data,
  industryOnly = false,
}: {
  data: any;
  industryOnly?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState(industryOnly ? "产业链" : "概览");
  const rows = filterRows(data.opportunities, query);
  const current = data.opportunities.find(
    (x: any) => (x.id || x.code) === selected,
  );
  const signals = current
    ? data.sigs.filter(
        (s: any) =>
          data.opportunitySignalLinks.some(
            (link: any) =>
              link.opportunity_id === current.id && link.signal_id === s.uuid,
          ),
      )
    : [];
  const mappings = current
    ? data.opportunityCompanies.filter(
        (m: any) =>
          m.opportunity_id === current.id ||
          m.opportunities?.external_id === current.code,
      )
    : [];
  return (
    <>
      {!industryOnly && (
        <div className="task-metrics">
          <Metric
            label="当前机会"
            value={data.opportunities.length}
            note="真实产业机会"
          />
          <Metric
            label="已确认"
            value={
              data.opportunities.filter(
                (x: any) => x.opportunity_status === "confirmed",
              ).length
            }
            note="进入公司映射"
          />
          <Metric
            label="近期变化"
            value={
              data.sigs.filter(
                (x: any) => x.date === data.reports[0]?.report_date,
              ).length
            }
            note="当日结构化信号"
          />
        </div>
      )}
      <SearchBox
        value={query}
        onChange={setQuery}
        placeholder="搜索机会、赛道或核心变化"
        count={rows.length}
      />
      <div className="opportunity-grid">
        {rows.map((r: any) => (
          <button
            className={`opportunity-card ${selected === (r.id || r.code) ? "selected" : ""}`}
            key={r.id || r.code}
            onClick={() => {
              setSelected(r.id || r.code);
              setTab(industryOnly ? "产业链" : "概览");
            }}
          >
            <div>
              <Badge tone={tracks[r.track]}>{r.track}</Badge>
              <Status
                value={
                  r.opportunity_status === "confirmed" ? "重点研究" : "观察"
                }
              />
            </div>
            <h2>{r.name || r.opportunity_name}</h2>
            <p>{r.core_change || r.upgrade_evidence || "暂无最新变化"}</p>
            <dl>
              <div>
                <dt>证据等级</dt>
                <dd>{r.evidence_grade || r.rank || "待确认"}</dd>
              </div>
              <div>
                <dt>综合分</dt>
                <dd>{fmt(r.composite_score)}</dd>
              </div>
              <div>
                <dt>共识</dt>
                <dd>{r.consensus_level || "待判断"}</dd>
              </div>
            </dl>
            <footer>
              <span>
                下一步：{r.next_verification || r.core_validation || "待补充"}
              </span>
              <ArrowRight size={15} />
            </footer>
          </button>
        ))}
      </div>
      {current && (
        <section className="inline-detail">
          <div className="detail-conclusion">
            <div>
              <Badge tone={tracks[current.track]}>{current.track}</Badge>
              <h2>{current.name || current.opportunity_name}</h2>
              <p>{current.core_change || current.upgrade_evidence}</p>
            </div>
            <div>
              <span>当前结论</span>
              <strong>
                {current.conclusion ||
                  (current.opportunity_status === "confirmed"
                    ? "值得持续跟踪"
                    : "等待更多证据")}
              </strong>
            </div>
          </div>
          <div className="conclusion-grid">
            <Conclusion
              label="为什么"
              value={current.demand_evidence || current.company_evidence}
            />
            <Conclusion
              label="最新变化"
              value={current.upgrade_evidence || current.core_change}
            />
            <Conclusion
              label="最大风险"
              value={current.counter_evidence || current.break_condition}
            />
            <Conclusion
              label="下一触发"
              value={current.next_verification || current.next_research}
            />
          </div>
          <TabBar
            items={["概览", "产业链", "证据", "相关公司", "变化记录"]}
            value={tab}
            onChange={setTab}
          />
          {tab === "概览" && (
            <DetailGrid
              items={[
                ["需求端", current.demand_evidence],
                ["供给端", current.supply_evidence],
                ["公司端", current.company_evidence],
                [
                  "产业空间",
                  current.market_space ? `${current.market_space}亿元` : null,
                ],
                ["破坏条件", current.break_condition],
              ]}
            />
          )}
          {tab === "产业链" && (
            <DetailGrid
              items={[
                ["产业方向", current.industry_direction || current.name],
                ["核心环节", current.chain_position || current.supply_evidence],
                [
                  "公司映射",
                  mappings
                    .map((m: any) => m.companies?.name)
                    .filter(Boolean)
                    .join("、") ||
                    current.core_company ||
                    "待映射",
                ],
                ["下一研究", current.next_research],
              ]}
            />
          )}
          {tab === "证据" && (
            <>
              <div className="evidence-composition">
                {["S", "A", "B", "C", "D"].map((grade) => (
                  <span key={grade}><b>{grade}级</b>{signals.filter((s: any) => (s.sourceGrade || s.metadata?.evidence_grade || "D") === grade).length}条</span>
                ))}
                {["positive", "negative", "neutral"].map((direction) => (
                  <span key={direction}><b>{polarityLabel(direction)}</b>{signals.filter((s: any) => (s.polarity || s.metadata?.direction || "neutral") === direction).length}条</span>
                ))}
              </div>
              <div className="evidence-cards">
              {signals.length ? (
                signals.map((s: any) => (
                  <article key={s.id}>
                    <Evidence value={s.metadata?.evidence_grade || "B"} />
                    <div>
                      <b>{s.title}</b>
                      <p>{s.change}</p>
                      <small>
                        {s.date} · {s.type} · {s.sourceName || "来源待补"} · {s.sourceCategory ? sourceCategoryLabel(s.sourceCategory) : "来源类型待补"}
                      </small>
                    </div>
                    {s.source && (
                      <a href={s.source} target="_blank" rel="noreferrer">
                        来源
                        <ExternalLink size={12} />
                      </a>
                    )}
                  </article>
                ))
              ) : (
                <Empty text="尚无直接关联的结构化信号" />
              )}
              </div>
            </>
          )}
          {tab === "相关公司" && (
            <div className="company-mini-list">
              {mappings.length ? (
                mappings.map((m: any) => (
                  <Link
                    key={m.id}
                    href={`/company/${m.companies?.external_code || ""}`}
                  >
                    <b>{m.companies?.name}</b>
                    <span>{m.role || m.relation_type || "产业链映射"}</span>
                    <ArrowRight size={14} />
                  </Link>
                ))
              ) : (
                <Empty text="尚未形成可追溯公司映射" />
              )}
            </div>
          )}
          {tab === "变化记录" && (
            <div className="timeline-compact">
              {signals.length ? (
                signals.map((s: any) => (
                  <div key={s.id}>
                    <time>{s.date}</time>
                    <b>{s.change}</b>
                    <span>
                      {s.previousStatus} → {s.state}
                    </span>
                  </div>
                ))
              ) : (
                <Empty text="暂无变化记录" />
              )}
            </div>
          )}
        </section>
      )}
    </>
  );
}

function CompanyCenter({ data }: { data: any }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("全部");
  const rows = filterRows(
    data.firms.filter(
      (c: any) => filter === "全部" || frontStatus(c) === filter,
    ),
    query,
  );
  return (
    <>
      <div className="pool-tabs v41-tabs">
        {["全部", "高期望收益", "重点研究", "观察", "产业验证", "归档"].map(
          (x) => (
            <button
              className={filter === x ? "active" : ""}
              onClick={() => setFilter(x)}
              key={x}
            >
              {x}
            </button>
          ),
        )}
      </div>
      <SearchBox
        value={query}
        onChange={setQuery}
        placeholder="搜索公司、代码、赛道或状态"
        count={rows.length}
      />
      <section className="logic-card">
        <div className="logic-scroll">
          <table className="logic-table company-center-table">
            <thead>
              <tr>
                <th>公司</th>
                <th>赛道</th>
                <th>当前状态</th>
                <th>当前结论</th>
                <th>期望收益</th>
                <th>双重可信度</th>
                <th>最近变化</th>
                <th>下一触发</th>
                <th>更新时间</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c: any) => {
                const e = data.expectedReturns.find(
                  (x: any) => x.company_id === c.id,
                );
                return (
                  <tr key={c.id}>
                    <td>
                      <Link href={`/company/${c.code}`}>
                        <b>{c.name}</b>
                        <small>{c.stockCode || c.code}</small>
                      </Link>
                    </td>
                    <td>
                      <Badge tone={tracks[c.track]}>{c.track}</Badge>
                    </td>
                    <td>
                      <Status value={frontStatus(c)} />
                    </td>
                    <td>{c.transitionReason || c.reason}</td>
                    <td>{returnPct(e?.expected_return)}</td>
                    <td>
                      {confidence(e?.profit_confidence)} /{" "}
                      {confidence(e?.probability_confidence)}
                    </td>
                    <td>{latestCompanyChange(c, data)}</td>
                    <td>{c.reactivationCondition || c.keyAssumptions}</td>
                    <td>{(c.updatedAt || "").slice(0, 10) || "待确认"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!rows.length && <Empty text="当前筛选暂无公司" />}
      </section>
    </>
  );
}

function InvestmentValue({ data }: { data: any }) {
  const [tab, setTab] = useState("高期望收益");
  const enriched = data.expectedReturns.map((r: any) => ({
    ...r,
    assessment: data.investmentAssessments.find(
      (a: any) => a.expected_return_snapshot_id === r.id,
    ),
    firm: data.firms.find((c: any) => c.id === r.company_id),
  }));
  const group = (r: any) =>
    r.assessment?.classification === "high_expected_return"
      ? "高期望收益"
      : r.assessment?.classification === "failed"
        ? "不通过"
        : "观察等待";
  const rows = enriched
    .filter((r: any) => group(r) === tab)
    .sort(
      (a: any, b: any) => Number(b.expected_return) - Number(a.expected_return),
    );
  const today = data.reports[0]?.report_date;
  return (
    <>
      <div className="task-metrics five">
        <Metric
          label="高期望收益"
          value={enriched.filter((x: any) => group(x) === "高期望收益").length}
          note="达到当前门槛"
        />
        <Metric
          label="观察等待"
          value={enriched.filter((x: any) => group(x) === "观察等待").length}
          note="保存模型等待触发"
        />
        <Metric
          label="今日升级"
          value={
            data.stateTransitions.filter(
              (x: any) =>
                x.created_at?.startsWith(today) &&
                String(x.to_status).includes("high"),
            ).length
          }
          note="进入高期望"
        />
        <Metric
          label="今日降级"
          value={
            data.stateTransitions.filter(
              (x: any) =>
                x.created_at?.startsWith(today) &&
                String(x.to_status).includes("shadow"),
            ).length
          }
          note="转入观察"
        />
        <Metric
          label="赔率改善"
          value={
            data.expectedReturns.filter(
              (x: any) =>
                x.trade_date === today && Number(x.expected_return_change) > 0,
            ).length
          }
          note="价格或模型驱动"
        />
      </div>
      <TabBar
        items={["高期望收益", "观察等待", "不通过"]}
        value={tab}
        onChange={setTab}
      />
      <div className="investment-list">
        {rows.map((r: any) => {
          const s = r.scenario_results || {};
          return (
            <Link
              className="investment-card"
              href={`/company/${r.external_code || r.firm?.code}`}
              key={r.id}
            >
              <div className="investment-rank">
                <Status value={tab === "观察等待" ? "观察" : tab} />
                <h2>{r.company_name}</h2>
                <span>{r.stock_code || r.firm?.stockCode}</span>
              </div>
              <strong className="investment-return">
                {returnPct(r.expected_return)}
                <small>综合期望收益</small>
              </strong>
              <div className="investment-scenarios">
                <span>悲观 {returnPct(s["悲观"]?.return)}</span>
                <span>中性 {returnPct(s["中性"]?.return)}</span>
                <span>乐观 {returnPct(s["乐观"]?.return)}</span>
              </div>
              <div className="investment-risk">
                <span>最大下行 {returnPct(r.max_assumed_downside)}</span>
                <span>
                  风险收益比{" "}
                  {r.risk_reward_ratio == null
                    ? "待核实"
                    : Number(r.risk_reward_ratio).toFixed(2)}
                </span>
                <span>
                  可信度 {confidence(r.profit_confidence)} /{" "}
                  {confidence(r.probability_confidence)}
                </span>
              </div>
              {tab === "观察等待" && (
                <div className="bottleneck">
                  <b>当前瓶颈</b>
                  <p>
                    {r.assessment?.failure_reasons?.join("；") ||
                      r.firm?.shadowReason ||
                      "尚未达到当前配置门槛"}
                  </p>
                  <small>
                    重新激活：
                    {r.firm?.reactivationCondition ||
                      "等待价格、利润或概率改善"}
                  </small>
                </div>
              )}
              <ArrowRight size={17} />
            </Link>
          );
        })}
        {!rows.length && <Empty text={`当前暂无${tab}公司`} />}
      </div>
    </>
  );
}

function ValidationCenter({ data }: { data: any }) {
  const [tab, setTab] = useState("持续验证");
  const tracking = data.firms.filter(
    (x: any) =>
      ["research", "shadow"].includes(x.researchPoolStatus) ||
      x.investmentAssessmentStatus === "high_expected_return",
  );
  return (
    <>
      <div className="task-metrics">
        <Metric
          label="验证对象"
          value={tracking.length}
          note="跨机会、公司与投资价值"
        />
        <Metric
          label="验证事件"
          value={data.validationEvents.length}
          note="事实只追加，不覆盖"
        />
        <Metric
          label="已有结果"
          value={data.predictionValidations.length}
          note="30/90/180日与一年"
        />
      </div>
      <div className="feedback-loop">
        <RotateCcw size={18} />
        <div>
          <b>验证横跨整个研究过程</b>
          <span>
            基本面事实更新公司模型；价格变化只重算投资价值。验证中心负责查看结果，不是后台第六步。
          </span>
        </div>
      </div>
      <TabBar items={["持续验证", "结果验证"]} value={tab} onChange={setTab} />
      {tab === "持续验证" ? (
        <section className="logic-card">
          <div className="logic-scroll">
            <table className="logic-table">
              <thead>
                <tr>
                  <th>公司</th>
                  <th>当前状态</th>
                  <th>最近验证</th>
                  <th>验证结论</th>
                  <th>影响方向</th>
                  <th>下一验证日</th>
                  <th>下一触发</th>
                </tr>
              </thead>
              <tbody>
                {tracking.map((c: any) => {
                  const e = data.validationEvents.find(
                    (x: any) => x.company_id === c.id,
                  );
                  return (
                    <tr key={c.id}>
                      <td>
                        <Link href={`/company/${c.code}`}>
                          <b>{c.name}</b>
                          <small>{c.stockCode}</small>
                        </Link>
                      </td>
                      <td>
                        <Status value={frontStatus(c)} />
                      </td>
                      <td>
                        {e?.validation_date ||
                          c.lastValidationAt?.slice(0, 10) ||
                          "待验证"}
                      </td>
                      <td>{e?.conclusion || c.transitionReason}</td>
                      <td>{effectLabel(e?.effect)}</td>
                      <td>{c.nextValidationAt?.slice(0, 10) || "待安排"}</td>
                      <td>{c.reactivationCondition || c.keyAssumptions}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : (
        <section className="logic-card">
          <div className="logic-scroll">
            <table className="logic-table">
              <thead>
                <tr>
                  <th>公司</th>
                  <th>首次入选</th>
                  <th>入选价</th>
                  <th>当日期望</th>
                  <th>30日</th>
                  <th>90日</th>
                  <th>180日</th>
                  <th>一年</th>
                  <th>结果</th>
                </tr>
              </thead>
              <tbody>
                {data.predictionValidations.map((v: any) => (
                  <tr key={v.id}>
                    <td>{v.companies?.name}</td>
                    <td>{v.first_qualified_at}</td>
                    <td>{v.entry_price ?? "待验证"}</td>
                    <td>{returnPct(v.entry_expected_return)}</td>
                    <td>{v.price_30d ?? "待验证"}</td>
                    <td>{v.price_90d ?? "待验证"}</td>
                    <td>{v.price_180d ?? "待验证"}</td>
                    <td>{v.price_1y ?? "待验证"}</td>
                    <td>
                      <Status value={v.final_result || "待验证"} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!data.predictionValidations.length && (
            <Empty text="尚未到达结果验证窗口" />
          )}
        </section>
      )}
    </>
  );
}

function HistoricalValidation({ data }: { data: any }) {
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const runs = data.historicalRuns || [];
  const run =
    runs.find((x: any) => x.id === selectedRun) || runs[0];
  if (!run) return <Empty text="尚未建立历史验证测试" />;
  const days = (data.historicalDays || [])
    .filter((x: any) => x.test_run_id === run.id)
    .sort((a: any, b: any) =>
      String(a.simulation_date).localeCompare(String(b.simulation_date)),
    );
  const day =
    days.find((x: any) => x.simulation_date === selectedDay) ||
    days[days.length - 1];
  const leakCorrections = new Map(
    (data.historicalLeakCheckCorrections || []).map((x: any) => [
      x.original_check_id,
      x,
    ]),
  );
  const leaks = (data.historicalLeakChecks || [])
    .filter((x: any) => x.test_run_id === run.id)
    .map((x: any) => {
      const correction = leakCorrections.get(x.id) as any;
      return correction
        ? {
            ...x,
            result: correction.corrected_result,
            violation_count: correction.corrected_violation_count,
            detail: correction.corrected_detail,
            correction_reason: correction.correction_reason,
          }
        : x;
    });
  const coverage = (data.historicalSourceCoverage || []).filter(
    (x: any) => x.test_run_id === run.id,
  );
  const categoryCoverage = (data.historicalSourceCategoryCoverage || []).filter(
    (x: any) => x.test_run_id === run.id,
  );
  const raw = (data.historicalRawRecords || []).filter(
    (x: any) => x.test_run_id === run.id,
  );
  const availability = (data.historicalAvailableRecords || []).filter(
    (x: any) => x.validation_day_id === day?.id,
  );
  const rawById = new Map(raw.map((x: any) => [x.id, x]));
  const searches = (data.historicalSearchLogs || []).filter(
    (x: any) => x.test_run_id === run.id,
  );
  const companies = (data.historicalCompanies || []).filter(
    (x: any) => x.test_run_id === run.id,
  );
  const funnel = [
    ["收集到的历史资料", run.collected_record_count],
    ["当时稳定可获得", run.available_record_count],
    ["进入系统证据包", day?.available_raw_record_count || 0],
    ["有效信号", run.signal_count],
    ["形成机会", run.opportunity_count],
    ["映射公司", run.company_count],
    ["进入模型", run.model_count],
    ["完成投资价值判断", run.assessment_count],
  ];
  return (
    <div className="historical-validation">
      <section className="historical-warning">
        <div>
          <span>本模块只验信息，不验收益</span>
          <h2>先证明系统回到过去时真的看不到未来</h2>
          <p>无证据时必须回答“当时无法确认”；无效测试会保留，但不能进入效果统计。</p>
        </div>
        <Status value={historicalStatus(run.status)} />
      </section>

      <section className="historical-run-list" aria-label="历史验证测试列表">
        {runs.map((item: any) => (
          <button
            key={item.id}
            className={item.id === run.id ? "active" : ""}
            onClick={() => {
              setSelectedRun(item.id);
              setSelectedDay(null);
            }}
          >
            <span>{item.sector}</span>
            <b>{item.test_name}</b>
            <small>{item.start_date} — {item.end_date}</small>
            <em>{historicalStatus(item.status)}</em>
          </button>
        ))}
      </section>

      <section className="historical-first-screen">
        <div className="historical-title-row">
          <div>
            <Badge tone={tracks[run.sector]}>{run.sector}</Badge>
            <h2>{run.test_name}</h2>
            <p>{run.conclusion}</p>
          </div>
          <div className="historical-gate">
            <strong>{run.can_enter_v45 ? "可以进入V4.5" : "禁止进入V4.5"}</strong>
            <span>P0 {run.p0_count} · P1 {run.p1_count}</span>
          </div>
        </div>
        <dl className="historical-boundaries">
          <Field k="预热开始" v={run.warmup_start_date} />
          <Field k="正式开始" v={run.start_date} />
          <Field k="停止判断" v={run.end_date} />
          <Field k="回放方式" v="历史来源重建" />
          <Field k="模型版本" v={run.model_version} />
          <Field k="规则版本" v={run.rule_version} />
          <Field k="门槛版本" v={`${run.threshold_version}（临时规则）`} />
          <Field k="数据源版本" v={run.source_version} />
          <Field k="搜索规则" v={run.search_rule_version} />
          <Field k="Git版本" v={String(run.git_commit_sha).slice(0, 12)} />
          <Field k="信息覆盖率" v={`${run.information_coverage_pct}%`} />
          <Field k="稳定可获得比例" v={`${run.stable_available_pct}%`} />
        </dl>
        <div className="historical-leak-summary">
          <article><span>未来信息泄漏</span><strong>{run.future_leak_count}</strong></article>
          <article><span>模型知识泄漏</span><strong>{run.model_knowledge_leak_count}</strong></article>
          <article><span>后验搜索违规</span><strong>{run.hindsight_search_violation_count}</strong></article>
          <article className={Number(run.dataset_construction_bias_count) ? "bad" : ""}><span>资料库构建偏差</span><strong>{run.dataset_construction_bias_count}</strong></article>
        </div>
        <div className="historical-category-summary">
          {categoryCoverage.map((item: any) => (
            <article key={item.id}>
              <span>{sourceCategoryLabel(item.source_category)}</span>
              <strong>{item.coverage_pct}%</strong>
              <small>{item.available_count} 条严格可用</small>
            </article>
          ))}
        </div>
      </section>

      <section className="historical-panel">
        <header><h2>信息漏斗</h2><p>这里只检查过程是否真实完整，不显示未来涨跌。</p></header>
        <div className="historical-funnel">
          {funnel.map(([label, value], index) => (
            <div key={String(label)}>
              <small>{index + 1}</small><span>{label}</span><strong>{value}</strong>
            </div>
          ))}
        </div>
      </section>

      <section className="historical-panel">
        <header><h2>严格泄漏检查</h2><p>FAILED 会让整次测试变成无效；无法验证不会被当成通过。</p></header>
        <div className="historical-checks">
          {leaks.map((check: any) => (
            <article key={check.id} className={check.result}>
              <div><b>{check.check_name}</b><span>{check.severity}</span></div>
              <strong>{leakResult(check.result)}</strong>
              <p>{check.detail}</p>
              {check.correction_reason && <small>已更正：{check.correction_reason}</small>}
            </article>
          ))}
        </div>
      </section>

      <section className="historical-panel">
        <header><h2>来源覆盖</h2><p>“排除”不等于没有信息，而是不能证明当时系统已经拿到。</p></header>
        <div className="source-coverage-grid category">
          {categoryCoverage.map((item: any) => (
            <article key={item.id}>
              <b>{sourceCategoryLabel(item.source_category)}</b>
              <dl>
                <Field k="抓到" v={item.collected_count} />
                <Field k="严格可用" v={item.available_count} />
                <Field k="排除" v={item.excluded_count} />
                <Field k="覆盖率" v={`${item.coverage_pct}%`} />
              </dl>
              <p>{item.conclusion}</p>
            </article>
          ))}
        </div>
        <div className="source-coverage-grid">
          {coverage.map((item: any) => (
            <article key={item.id}>
              <b>{item.source_type}</b>
              <dl>
                <Field k="抓到" v={item.collected_count} />
                <Field k="可用" v={item.available_count} />
                <Field k="排除" v={item.excluded_count} />
                <Field k="可得性风险" v={item.availability_risk_count} />
                <Field k="负面信息" v={item.negative_record_count} />
              </dl>
              <p>{item.conclusion}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="historical-panel">
        <header>
          <div><h2>按日回放</h2><p>每天北京时间08:00冻结证据包，晚到资料不会反向进入。</p></div>
          <label className="historical-day-select">
            回放日期
            <select value={day?.simulation_date || ""} onChange={(e) => setSelectedDay(e.target.value)}>
              {days.map((item: any) => <option key={item.id} value={item.simulation_date}>{item.simulation_date}</option>)}
            </select>
          </label>
        </header>
        {day && (
          <>
            <div className="historical-day-summary">
              <strong>{day.simulation_date}</strong>
              <span>可用资料 {day.available_raw_record_count}</span>
              <span>排除资料 {day.excluded_record_count}</span>
              <span>信号 {day.signal_count}</span>
              <span>机会 {day.opportunity_count}</span>
              <span>公司 {day.company_count}</span>
              <span>模型 {day.model_count}</span>
              <span>投资判断 {day.assessment_count}</span>
            </div>
            <div className="historical-replay-conclusion"><b>当天结论</b><p>{day.replay_conclusion}</p></div>
            <details className="excluded-records" open>
              <summary>查看被排除资料（{availability.filter((x: any) => x.inclusion_status === "excluded").length}）</summary>
              <div>
                {availability.filter((x: any) => x.inclusion_status === "excluded").map((item: any) => {
                  const record = rawById.get(item.historical_raw_record_id) as any;
                  return (
                    <article key={item.id}>
                      <div><Evidence value={record?.availability_status} /><b>{record?.title || "资料已保留"}</b></div>
                      <p>{exclusionReason(item.exclusion_reason)}</p>
                      <small>公开：{record?.published_at || "无法确认"} · 入库：{record?.ingested_at || "无法确认"}</small>
                    </article>
                  );
                })}
              </div>
            </details>
          </>
        )}
      </section>

      <section className="historical-panel two-column">
        <div>
          <h2>搜索路径回放</h2>
          {searches.length ? searches.map((item: any) => (
            <article key={item.id}><b>{item.query}</b><p>{item.reason}</p></article>
          )) : <p className="plain-empty">本轮没有使用今天的搜索排名，也没有按赢家公司名定向搜索。</p>}
        </div>
        <div>
          <h2>公司发现路径</h2>
          {companies.length ? companies.map((item: any) => (
            <article key={item.id}><b>{item.company_name}</b><p>{item.discovery_reason}</p></article>
          )) : <p className="plain-empty">证据包为空，公司发现没有启动；这项目前无法验证，不能算通过。</p>}
        </div>
      </section>
    </div>
  );
}

function historicalStatus(value: string) {
  return ({ draft: "草稿", ready: "待运行", running: "运行中", completed: "已完成", invalid: "无效", failed: "运行失败" } as any)[value] || value;
}
function leakResult(value: string) {
  return ({ passed: "通过", failed: "失败", not_verifiable: "无法验证" } as any)[value] || value;
}
function exclusionReason(value: string) {
  return ({
    published_after_as_of: "当时尚未公开",
    available_after_as_of: "当时尚不可获得",
    ingested_after_decision_time: "系统是在判断日之后才采集到",
    published_time_unknown: "无法确认准确公开时间",
    availability_time_unknown: "无法确认当时是否可访问",
    ingested_time_unknown: "无法确认系统何时采到",
    historical_reconstruction_not_true_point_in_time: "只能事后重建，不能证明当时系统已获得",
  } as any)[value] || "不满足严格历史时间边界";
}

function SignalDiscovery({ data }: { data: any }) {
  const day = data.reports[0]?.report_date;
  const valid = data.screeningDecisions.filter(
    (x: any) => x.stage === "change_discovery" && x.decision !== "fail",
  );
  return (
    <>
      <div className="task-metrics five">
        <Metric
          label="今日新增"
          value={data.sigs.filter((x: any) => (x.discoveredAt?.slice(0, 10) || x.date) === day).length}
          note={day || "最新日报"}
        />
        <Metric
          label="过去7天"
          value={
            data.sigs.filter((x: any) => daysFrom(x.date, day) <= 6).length
          }
          note="结构化变化"
        />
        <Metric
          label="高重要度"
          value={data.sigs.filter((x: any) => Number(x.score) >= 4).length}
          note="评分≥4"
        />
        <Metric
          label="待验证"
          value={valid.filter((x: any) => x.decision === "observe").length}
          note="保留观察"
        />
        <Metric
          label="进入机会判断"
          value={valid.filter((x: any) => x.decision === "pass").length}
          note="有决策原因"
        />
      </div>
      <section className="signal-list">
        {data.sigs.map((s: any) => {
          const dec = data.screeningDecisions.find(
            (x: any) =>
              x.stage === "change_discovery" && x.object_name === s.title,
          );
          const link = data.opportunitySignalLinks.find(
            (x: any) => x.signal_id === s.uuid,
          );
          const opp = data.opportunities.find(
            (o: any) => o.id === link?.opportunity_id,
          );
          return (
            <details key={s.id}>
              <summary>
                <time>{s.date}</time>
                <Badge tone={tracks[s.track]}>{s.track}</Badge>
                <div>
                  <b>{s.title}</b>
                  <small>
                    {s.type} · 证据{" "}
                    {s.metadata?.evidence_grade ||
                      s.metadata?.source_grade ||
                      "待确认"}{" "}
                    · 强度 {s.score}
                  </small>
                </div>
                <Status
                  value={
                    dec?.decision === "pass"
                      ? "进入机会确认"
                      : dec?.decision === "fail"
                        ? "无效信息"
                        : "继续观察"
                  }
                />
                <span>{s.verify}</span>
              </summary>
              <div className="signal-detail">
                <p>
                  <b>发生了什么：</b>
                  {s.change}
                </p>
                <p>
                  <b>当前判断：</b>
                  {dec?.reason || "待补充筛选原因"}
                </p>
                <p>
                  <b>首次发现：</b>
                  {s.discoveredAt?.slice(0, 16).replace("T", " ") || s.metadata?.first_discovered_at || s.date}
                </p>
                <p><b>来源名称：</b>{s.sourceName || "现有记录中无法确认"}</p>
                <p><b>来源类型：</b>{s.sourceCategory ? sourceCategoryLabel(s.sourceCategory) : "现有记录中无法确认"}</p>
                <p><b>发布时间：</b>{s.publishedAt?.slice(0, 16).replace("T", " ") || s.date}</p>
                <p><b>可信等级：</b>{s.sourceGrade || "待确认"} · {s.isOfficial ? "官方" : "非官方或待确认"}</p>
                <p><b>历史可得性：</b>{availabilityLabel(s.historicalAvailability)}；{s.availabilityRisk || "现有记录中无法确认"}</p>
                <p>
                  <b>影响机会：</b>
                  {opp?.name || s.metadata?.opportunity_id || "尚未形成机会"}
                </p>
                {s.source ? (
                  <a href={s.source} target="_blank" rel="noreferrer">
                    查看原始来源 <ExternalLink size={12} />
                  </a>
                ) : (
                  <span>URL 暂无数据</span>
                )}
              </div>
            </details>
          );
        })}
      </section>
    </>
  );
}

function CompanyScreening({ data }: { data: any }) {
  const [filter, setFilter] = useState("全部");
  const rows = data.firms.filter(
    (c: any) => filter === "全部" || screenStatus(c) === filter,
  );
  const mapped = data.screeningDecisions.filter(
    (x: any) => x.stage === "company_mapping",
  );
  return (
    <>
      <div className="task-metrics five">
        <Metric label="映射公司" value={mapped.length} note="含产业验证对象" />
        <Metric
          label="可投资公司"
          value={
            data.firms.filter(
              (x: any) => x.companyRole !== "industry_validator",
            ).length
          }
          note="可进入赔率计算"
        />
        <Metric
          label="产业验证对象"
          value={
            data.firms.filter(
              (x: any) => x.companyRole === "industry_validator",
            ).length
          }
          note="不直接算A股赔率"
        />
        <Metric
          label="进入建模"
          value={
            data.screeningDecisions.filter(
              (x: any) =>
                x.stage === "company_modeling" &&
                ["pass", "observe"].includes(x.decision),
            ).length
          }
          note="已有阶段决策"
        />
        <Metric
          label="观察 / 不通过"
          value={`${mapped.filter((x: any) => x.decision === "observe").length} / ${mapped.filter((x: any) => x.decision === "fail").length}`}
          note="横向暂停或退出"
        />
      </div>
      <TabBar
        items={["全部", "进入建模", "观察", "产业验证", "不通过"]}
        value={filter}
        onChange={setFilter}
      />
      <div className="company-screen-list">
        {rows.map((c: any) => {
          const map = data.opportunityCompanies.find(
            (x: any) => x.company_id === c.id,
          );
          const opp = data.opportunities.find(
            (x: any) => x.id === map?.opportunity_id,
          );
          const dec = mapped.find((x: any) => x.object_id === c.id);
          return (
            <Link href={`/company/${c.code}`} key={c.id}>
              <div>
                <b>{c.name}</b>
                <small>{c.stockCode || c.code}</small>
              </div>
              <span>{opp?.name || "待映射机会"}</span>
              <span>{c.chain || "待确认"}</span>
              <span>
                {c.companyRole === "industry_validator"
                  ? "产业验证对象"
                  : "可投资公司"}
              </span>
              <p>{map?.rationale || c.reason}</p>
              <strong>
                {c.metadata?.evidence_strength || c.rank || "待确认"}
              </strong>
              <span>{c.profit || "待判断"}</span>
              <Status value={screenStatus(c)} />
              <span>
                {dec?.next_step || c.reactivationCondition || c.keyAssumptions}
              </span>
              <ArrowRight size={15} />
            </Link>
          );
        })}
      </div>
    </>
  );
}

function DailyReport({ data }: { data: any }) {
  const [date, setDate] = useState(data.reports[0]?.report_date || "");
  const report =
    data.reports.find((x: any) => x.report_date === date) || data.reports[0];
  const s = report?.frozen_snapshot || {};
  const stats = s.stats || {};
  const sectors =
    s.sectors || data.sectorReviews.filter((x: any) => x.report_date === date);
  const overview = [
    ...(s.opportunity_changes || []),
    ...(s.company_changes || []),
    ...(s.model_changes || []),
  ].slice(0, 5);
  return (
    <>
      <div className="report-toolbar">
        <div className="date-switch">
          {data.reports.slice(0, 7).map((r: any, i: number) => (
            <button
              className={date === r.report_date ? "active" : ""}
              onClick={() => setDate(r.report_date)}
              key={r.report_date}
            >
              {i === 0 ? "今天" : i === 1 ? "昨天" : r.report_date.slice(5)}
            </button>
          ))}
        </div>
        <label>
          选择日期{" "}
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
      </div>
      {!report ? (
        <Empty text="所选日期暂无冻结日报" />
      ) : (
        <>
          <section className="report-hero">
            <div>
              <span>{date} · 机器人 / 商业航天 / AI</span>
              <h2>{report.summary || "当日暂无总结"}</h2>
              <p>该页读取生成当日冻结快照，未来数据不会反向改写。</p>
            </div>
            <Status value={s.is_frozen ? "已冻结" : "历史格式"} />
          </section>
          <div className="daily-source-strip">
            <span>当日主要来源</span>
            {Array.from(new Map(
              data.sigs
                .filter((item: any) => (item.discoveredAt?.slice(0, 10) || item.date) === date && item.sourceName)
                .map((item: any) => [item.sourceCode || item.sourceName, item]),
            ).values()).slice(0, 6).map((item: any) => (
              <a key={item.sourceCode || item.sourceName} href={item.source || "#"} target={item.source ? "_blank" : undefined} rel="noreferrer">
                <b>{item.sourceName}</b>
                <small>{item.sourceGrade || "待确认"}级 · {sourceCategoryLabel(item.sourceCategory)}</small>
              </a>
            ))}
            {!data.sigs.some((item: any) => (item.discoveredAt?.slice(0, 10) || item.date) === date && item.sourceName) && <em>当日冻结记录中暂无结构化来源名称</em>}
          </div>
          <div className="daily-stats">
            {[
              [
                "新增有效信号",
                stats.new_valid_signals ?? report.valid_signal_count,
              ],
              ["新增机会", stats.new_opportunities ?? report.new_pool_count],
              ["机会增强", stats.opportunity_strengthened],
              ["机会减弱", stats.opportunity_weakened],
              ["新增映射公司", stats.new_mapped_companies],
              ["进入建模", stats.entered_modeling],
              ["建模完成", stats.model_completed],
              ["完成价值评估", stats.investment_evaluated],
              ["进入高期望", stats.high_expected_return],
              ["转观察", stats.to_observe],
              ["逻辑失效", stats.logic_invalidated],
            ].map(([a, b]: any) => (
              <article key={a}>
                <span>{a}</span>
                <b>{b ?? 0}</b>
              </article>
            ))}
          </div>
          <ReportSection n="01" title="今日总览">
            {overview.length ? (
              overview.map((x: any, i: number) => (
                <article className="report-story" key={i}>
                  <b>
                    {x.opportunity_external_id ||
                      x.company ||
                      x.change_type ||
                      `重要变化 ${i + 1}`}
                  </b>
                  <p>
                    {x.evidence_for ||
                      x.reason ||
                      x.change_reason ||
                      x.action ||
                      "发生状态变化"}
                  </p>
                  <small>
                    影响：
                    {x.to || x.current_stage || x.change_type || "继续验证"} ·
                    重要性：
                    {x.next_step || x.next_verification || "影响下一阶段判断"}
                  </small>
                </article>
              ))
            ) : (
              <p className="muted">
                当日没有新增状态流转；核心结论见顶部摘要。
              </p>
            )}
          </ReportSection>
          <ReportSection n="02" title="三大赛道日报">
            <div className="sector-report-grid">
              {["机器人", "商业航天", "AI"].map((track) => {
                const x = sectors.find(
                  (v: any) => (v.track || v.sectors?.name) === track,
                );
                return (
                  <article key={track}>
                    <Badge tone={tracks[track]}>{track}</Badge>
                    <Field
                      k="今日新增信号"
                      v={
                        data.sigs.filter(
                          (z: any) => (z.discoveredAt?.slice(0, 10) || z.date) === date && z.track === track,
                        ).length
                      }
                    />
                    <Field
                      k="需求端变化"
                      v={x?.demand_change || x?.key_changes}
                    />
                    <Field
                      k="供给端变化"
                      v={x?.supply_change || x?.evidence_summary}
                    />
                    <Field
                      k="公司端变化"
                      v={x?.company_change || x?.company_mapping}
                    />
                    <Field
                      k="机会变化"
                      v={x?.opportunity_change || x?.opportunity_updates}
                    />
                    <Field
                      k="相关公司变化"
                      v={x?.company_change || x?.company_mapping}
                    />
                    <Field k="核心风险" v={x?.risk || x?.conclusion} />
                    <Field k="主要反证" v={x?.counter_evidence} />
                    <Field k="下一验证点" v={x?.next_verification} />
                  </article>
                );
              })}
            </div>
          </ReportSection>
          <ReportList
            n="03"
            title="今日机会变化"
            rows={s.opportunity_changes}
            fields={[
              ["机会", "company_name"],
              ["昨日状态", "previous_stage"],
              ["今日状态", "current_stage"],
              ["变化方向", "action"],
              ["新增证据", "evidence_for"],
              ["新增反证", "evidence_against"],
              ["映射变化", "price_valuation_change"],
              ["下一验证", "next_verification"],
            ]}
          />
          <ReportList
            n="04"
            title="今日公司筛选变化"
            rows={s.company_changes}
            fields={[
              ["公司", "company"],
              ["原状态", "from"],
              ["新状态", "to"],
              ["变化原因", "reason"],
              ["当前卡点", "reason"],
              ["下一步", "next_step"],
            ]}
          />
          <ReportList
            n="05"
            title="重点公司"
            rows={s.focus_companies}
            fields={[
              ["公司", "company"],
              ["当前状态", "status"],
              ["当前价格", "price"],
              ["当前市值", "market_cap"],
              ["中性利润", "profit_base"],
              ["中性概率", "probability_base"],
              ["综合期望收益", "expected_return"],
              ["风险收益比", "risk_reward"],
              ["利润可信度", "profit_confidence"],
              ["概率可信度", "probability_confidence"],
              ["当前结论", "conclusion"],
              ["下一触发", "next_trigger"],
            ]}
          />
          <ReportList
            n="06"
            title="模型变化"
            rows={s.model_changes}
            fields={[
              ["公司", "company"],
              ["类型", "change_type"],
              ["原值", "before"],
              ["新值", "after"],
              ["原因", "reason"],
            ]}
          />
          <ReportList
            n="07"
            title="价格与赔率变化"
            rows={s.price_odds_changes}
            fields={[
              ["公司", "company"],
              ["价格", "price"],
              ["基本面", "fundamental_change"],
              ["期望收益", "expected_return"],
              ["中性收益", "base_return"],
              ["结论", "conclusion"],
            ]}
          />
          <ReportList
            n="08"
            title="观察池异动"
            rows={s.watch_changes}
            fields={[
              ["公司", "company"],
              ["观察阶段", "stage"],
              ["原因", "reason"],
              ["状态", "status"],
              ["重新激活条件", "trigger"],
            ]}
          />
          <ReportList
            n="09"
            title="风险与反证"
            rows={s.risks}
            fields={[
              ["对象", "company"],
              ["类型", "result"],
              ["新增负面证据", "reason"],
              ["来源", "source"],
            ]}
          />
          <ReportList
            n="10"
            title="下一步验证任务"
            rows={s.next_tasks}
            fields={[
              ["任务", "title"],
              ["公司", "company"],
              ["优先级", "priority"],
              ["状态", "status"],
              ["日期", "due_date"],
            ]}
          />
        </>
      )}
    </>
  );
}

function ModelingCenter({ data }: { data: any }) {
  const groups = [
    ...new Map(
      data.profitModels.map((m: any) => [
        m.company_id,
        {
          firm: data.firms.find((c: any) => c.id === m.company_id),
          models: data.profitModels.filter(
            (x: any) => x.company_id === m.company_id,
          ),
        },
      ]),
    ).values(),
  ] as any[];
  const completed = groups.filter((g: any) =>
    g.models.some((m: any) => m.model_status === "complete"),
  );
  return (
    <>
      <div className="task-metrics">
        <Metric
          label="待建模"
          value={
            data.firms.filter(
              (x: any) =>
                x.valuationStatus === "not_started" &&
                x.companyRole !== "industry_validator",
            ).length
          }
          note="已映射可投资公司"
        />
        <Metric
          label="建模中"
          value={groups.length - completed.length}
          note="关键输入待补"
        />
        <Metric
          label="已完成"
          value={completed.length}
          note="三情景可用于决策"
        />
        <Metric
          label="暂不可建模"
          value={
            data.firms.filter(
              (x: any) => x.valuationStatus === "insufficient_data",
            ).length
          }
          note="利润不可测或数据不足"
        />
      </div>
      <div className="model-list">
        {groups.map((g: any) => {
          const f = g.firm || {},
            base = g.models.find((x: any) => x.scenario === "中性"),
            prob = data.probabilities.find((x: any) => x.company_id === f.id),
            val = data.valuations.find(
              (x: any) => x.company_id === f.id && x.scenario === "中性",
            );
          return (
            <Link href={`/company/${f.code}`} key={f.id}>
              <div>
                <b>{f.name}</b>
                <small>{f.stockCode || f.code}</small>
              </div>
              <span>{base?.model_type || "公司基本面模型"}</span>
              <span>
                {base?.model_status === "complete" ? "100%" : "关键输入待补"}
              </span>
              <strong>{money(base?.net_profit)}</strong>
              <strong>
                {money(val?.target_market_cap || base?.target_market_cap)}
              </strong>
              <span>
                {confidence(prob?.confidence || prob?.probability_confidence)}
              </span>
              <span>{confidence(base?.profit_confidence)}</span>
              <Status
                value={
                  base?.model_status === "complete" ? "已完成" : "暂不可建模"
                }
              />
              <span>
                {base?.most_needed_evidence ||
                  base?.max_uncertainty ||
                  "等待新证据"}
              </span>
              <ArrowRight size={15} />
            </Link>
          );
        })}
      </div>
    </>
  );
}

function TimelineCenter({ data }: { data: any }) {
  const q = useSearchParams().get("company");
  const [selected, setSelected] = useState(
    q ||
      data.firms.find((x: any) => x.name === "柯力传感")?.code ||
      data.firms[0]?.code,
  );
  const f = data.firms.find((x: any) => x.code === selected) || data.firms[0];
  if (!f) return <Empty text="正在读取公司时间轴" />;
  const mapping = data.opportunityCompanies.find(
    (x: any) => x.company_id === f?.id,
  );
  const opportunity = data.opportunities.find(
    (x: any) => x.id === mapping?.opportunity_id,
  );
  const events = data.timelineEvents.filter(
    (x: any) => x.company_id === f?.id && x.is_key_event !== false,
  );
  const decisions = data.screeningDecisions
    .filter(
      (x: any) =>
        x.object_id === f?.id ||
        x.metadata?.company_id === f?.id ||
        x.object_id === opportunity?.id,
    )
    .map((x: any) => ({
      event_at: x.evaluated_at,
      event_type: x.stage,
      title: stageName(x.stage),
      change_reason: x.reason,
      system_status: x.decision,
      model_version: x.metadata?.model_version,
      source_url: x.metadata?.source_url,
    }));
  const all = [...events, ...decisions].sort((a: any, b: any) =>
    String(a.event_at).localeCompare(String(b.event_at)),
  );
  const snaps = data.dailySnapshots.filter((x: any) => x.company_id === f?.id);
  const expected = data.expectedReturns.find(
    (x: any) => x.company_id === f?.id,
  );
  return (
    <div className="timeline-center">
      <aside>
        <p>公司列表</p>
        {data.firms.map((c: any) => {
          const e = data.expectedReturns.find(
            (x: any) => x.company_id === c.id,
          );
          return (
            <button
              className={c.id === f?.id ? "active" : ""}
              onClick={() => setSelected(c.code)}
              key={c.id}
            >
              <b>{c.name}</b>
              <small>{c.stockCode || c.track}</small>
              <span>
                {frontStatus(c)} · {returnPct(e?.expected_return)}
              </span>
            </button>
          );
        })}
      </aside>
      <section>
        <div className="timeline-company-head">
          <div>
            <Badge tone={tracks[f?.track]}>{f?.track}</Badge>
            <h2>{f?.name}</h2>
            <p>
              首次发现 {all[0]?.event_at?.slice(0, 10) || "待确认"} · 当前{" "}
              {frontStatus(f)} · 当前期望收益{" "}
              {returnPct(expected?.expected_return)}
            </p>
          </div>
          <Link href={`/company/${f?.code}`}>
            统一公司详情
            <ArrowRight size={14} />
          </Link>
        </div>
        <div className="research-path">
          {[
            "opportunity_confirmation",
            "company_mapping",
            "company_modeling",
            "investment_value",
            "high_expected_return",
          ].map((x) => {
            const d = decisions.find((v: any) => v.event_type === x);
            return (
              <div
                key={x}
                className={
                  d?.system_status === "fail" ? "failed" : d ? "done" : ""
                }
              >
                <b>{stageName(x)}</b>
                <span>
                  {d ? (d.system_status === "fail" ? "✕" : "✓") : "—"}
                </span>
                <small>{d?.change_reason || "暂无决策"}</small>
              </div>
            );
          })}
        </div>
        <div className="full-timeline">
          {all.map((e: any, i: number) => (
            <article key={e.id || i}>
              <time>{String(e.event_at).slice(0, 10)}</time>
              <div>
                <Badge>{eventName(e.event_type)}</Badge>
                <h3>{e.title}</h3>
                <p>{e.change_reason || e.description || "暂无变化原因"}</p>
                <dl>
                  <Field k="当日价格" v={e.price} />
                  <Field k="当日市值" v={e.market_cap} />
                  <Field
                    k="悲/中/乐利润"
                    v={[e.profit_bear, e.profit_base, e.profit_bull]
                      .filter((x: any) => x != null)
                      .join(" / ")}
                  />
                  <Field
                    k="悲/中/乐概率"
                    v={[
                      e.probability_bear,
                      e.probability_base,
                      e.probability_bull,
                    ]
                      .filter((x: any) => x != null)
                      .join(" / ")}
                  />
                  <Field k="期望收益" v={returnPct(e.expected_return)} />
                  <Field k="风险收益比" v={e.risk_reward} />
                  <Field k="当前状态" v={e.system_status} />
                  <Field k="模型版本" v={e.model_version} />
                </dl>
                {e.source_url && (
                  <a href={e.source_url} target="_blank" rel="noreferrer">
                    证据来源 <ExternalLink size={12} />
                  </a>
                )}
              </div>
            </article>
          ))}
        </div>
        <details className="model-details">
          <summary>展开每日快照（{snaps.length}）</summary>
          <div className="snapshot-list">
            {snaps.map((x: any) => (
              <div key={x.id}>
                <time>{x.trade_date}</time>
                <span>价格 {x.close_price ?? "—"}</span>
                <span>市值 {x.market_cap ?? "—"}</span>
                <span>期望 {returnPct(x.expected_return)}</span>
                <span>{x.change_driver || "daily_snapshot"}</span>
              </div>
            ))}
          </div>
        </details>
      </section>
    </div>
  );
}

const sourceCategories = [
  { code: "company", name: "公司", purpose: "确认公司自己的订单、客户、扩产、业绩与风险。" },
  { code: "policy", name: "政策", purpose: "发现国家和地方产业方向、标准与监管变化。" },
  { code: "demand", name: "需求", purpose: "验证下游是否真的在采购、扩产和花钱。" },
  { code: "industry", name: "产业", purpose: "确认产量、出货、技术路线和行业结构是否变化。" },
  { code: "supply_chain", name: "供应链", purpose: "用客户、供应商和竞争对手交叉验证公司说法。" },
  { code: "market", name: "市场", purpose: "观察价格、成交和市值是否开始形成市场共识，不当作基本面事实。" },
  { code: "negative_counterevidence", name: "负面反证", purpose: "单独寻找取消、延期、下修、减值、诉讼和竞争恶化。" },
];

function SourceRegistryView({ data }: { data: any }) {
  const [category, setCategory] = useState("全部");
  const registry = data.sourceRegistry || [];
  const healthByCode = new Map(
    (data.sourceHealth || []).map((item: any) => [item.source_code, item]),
  );
  const latestDate = (data.sourceCoverageDaily || [])[0]?.coverage_date;
  const coverage = (data.sourceCoverageDaily || []).filter(
    (item: any) => item.coverage_date === latestDate,
  );
  const visibleCategories = sourceCategories.filter(
    (item) => category === "全部" || item.code === category,
  );
  const automated = registry.filter((item: any) => item.operational_status === "automated_active");
  const manual = registry.filter((item: any) => item.operational_status === "manual_available");
  const unconfigured = registry.filter((item: any) => item.operational_status === "registered_unconfigured");
  const historicalStrict = registry.filter((item: any) => item.historical_strict_available);
  const trulyChecked = registry.filter((item: any) => {
    const health = healthByCode.get(item.source_code) as any;
    return health?.last_checked_at?.slice(0, 10) === latestDate;
  });
  const succeeded = trulyChecked.filter((item: any) =>
    ["healthy", "healthy_no_new_data", "healthy_no_new_trade"].includes((healthByCode.get(item.source_code) as any)?.status),
  );
  const failed = registry.filter((item: any) =>
    item.operational_status === "degraded" || ["failed", "degraded"].includes((healthByCode.get(item.source_code) as any)?.status),
  );
  const integrationRate = registry.length ? Math.round(automated.length / registry.length * 100) : 0;
  const collectionRate = trulyChecked.length ? Math.round(succeeded.length / trulyChecked.length * 100) : 0;
  const effectiveCodes = new Set((data.rawClues || []).filter((row: any) => row.discovered_at?.slice(0, 10) === latestDate && row.screening_status !== "rejected").map((row: any) => row.source_code).filter(Boolean));
  const effectiveRate = trulyChecked.length ? Math.round(effectiveCodes.size / trulyChecked.length * 100) : 0;
  const historicalRate = registry.length ? Math.round(historicalStrict.length / registry.length * 100) : 0;
  const statusText = (value: string) => ({
    automated_active: "自动运行", manual_available: "手工可用", registered_unconfigured: "仅登记未配置",
    degraded: "已接入但降级", unavailable: "不可用", realtime_only: "仅实时", historical_partial: "历史部分", historical_full: "历史完整",
  } as Record<string, string>)[value] || value || "待验收";
  return (
    <div className="source-registry-view">
      <section className="source-foundation-hero">
        <div>
          <span>来源登记不等于已经跑通</span>
          <h2>先看信息从哪里来，再判断结论能不能信</h2>
          <p>当前登记 {registry.length} 个来源；真实自动运行 {automated.length} 个；手工可用 {manual.length} 个；仅登记未配置 {unconfigured.length} 个。</p>
        </div>
        <div className="source-health-summary">
          <article><span>今日计划 / 尝试</span><strong>{trulyChecked.length}</strong></article>
          <article><span>今日成功</span><strong>{succeeded.length}</strong></article>
          <article><span>失败 / 降级</span><strong>{failed.length}</strong></article>
          <article><span>历史严格可用</span><strong>{historicalStrict.length}</strong></article>
        </div>
      </section>
      <section className="source-rate-grid">
        <article><span>来源接入率</span><strong>{integrationRate}%</strong><small>{automated.length} 自动 / {registry.length} 登记</small></article>
        <article><span>今日采集成功率</span><strong>{collectionRate}%</strong><small>{succeeded.length} 成功 / {trulyChecked.length} 尝试</small></article>
        <article><span>有效数据覆盖率</span><strong>{effectiveRate}%</strong><small>{effectiveCodes.size} 个有效来源 / {trulyChecked.length} 尝试</small></article>
        <article><span>历史严格可用率</span><strong>{historicalRate}%</strong><small>{historicalStrict.length} 严格可用 / {registry.length} 登记</small></article>
      </section>
      <section className="source-gap-section">
        <header><h2>当前信息盲区</h2><p>没有抓到负面不等于没有负面；未关闭的缺口会一直显示。</p></header>
        <div className="source-gap-grid">
          {(data.sourceGaps || []).filter((gap: any) => gap.status !== "closed").map((gap: any) => (
            <article key={gap.id}><span>{gap.sector_code || "跨赛道"} · {gap.source_category}</span><b>{gap.gap_title}</b><p>{gap.gap_description}</p><small>{gap.next_action || "待制定补齐方案"}</small></article>
          ))}
          {!(data.sourceGaps || []).length && <Empty text="尚未登记来源缺口" />}
        </div>
      </section>
      <div className="filter-pills source-filter">
        <button className={category === "全部" ? "active" : ""} onClick={() => setCategory("全部")}>全部</button>
        {sourceCategories.map((item) => (
          <button key={item.code} className={category === item.code ? "active" : ""} onClick={() => setCategory(item.code)}>{item.name}</button>
        ))}
      </div>
      {visibleCategories.map((group) => {
        const rows = registry.filter((item: any) => item.source_category === group.code);
        const categoryHealth = rows.filter((item: any) => (healthByCode.get(item.source_code) as any)?.last_checked_at?.slice(0, 10) === latestDate);
        const categorySuccess = categoryHealth.filter((item: any) => ["healthy", "healthy_no_new_data", "healthy_no_new_trade"].includes((healthByCode.get(item.source_code) as any)?.status));
        return (
          <section className="source-category-section" key={group.code}>
            <header>
              <div><span>{String(sourceCategories.indexOf(group) + 1).padStart(2, "0")}</span><h2>{group.name}层</h2></div>
              <p>{group.purpose}</p>
            </header>
            <div className="category-source-counts">
              <span>登记 <b>{rows.length}</b></span>
              <span>自动 <b>{rows.filter((x: any) => x.operational_status === "automated_active").length}</b></span>
              <span>手工 <b>{rows.filter((x: any) => x.operational_status === "manual_available").length}</b></span>
              <span>未配置 <b>{rows.filter((x: any) => x.operational_status === "registered_unconfigured").length}</b></span>
              <span>今日成功 <b>{categorySuccess.length}</b></span>
              <span>历史严格 <b>{rows.filter((x: any) => x.historical_strict_available).length}</b></span>
            </div>
            <div className="source-card-grid">
              {rows.map((source: any) => {
                const health = healthByCode.get(source.source_code) as any;
                return (
                  <article key={source.source_code}>
                    <div className="source-card-top">
                      <div><Evidence value={source.official_level} /><b>{source.source_name}</b></div>
                      <Status value={statusText(source.operational_status)} />
                    </div>
                    <p>{source.notes}</p>
                    <dl>
                      <Field k="来源类型" v={source.source_type} />
                      <Field k="作用标签" v={(source.primary_use || []).join("、") || "待补"} />
                      <Field k="最近成功" v={health?.last_success_at?.slice(0, 16).replace("T", " ") || "尚未真实成功"} />
                      <Field k="实时可用" v={source.realtime_available ? "是" : "否"} />
                      <Field k="历史可用" v={source.historical_available ? "是" : "否"} />
                      <Field k="历史严格可用" v={source.historical_strict_available ? "是" : "否"} />
                      <Field k="历史能力" v={source.historical_capability || "待验收"} />
                      <Field k="历史风险" v={source.historical_availability_risk || "待验收"} />
                      <Field k="代理覆盖" v={source.proxy_covered_by || "独立来源/不适用"} />
                    </dl>
                    {source.audit_evidence && <small className="source-audit">验收：{source.audit_evidence}</small>}
                    {health?.last_error && <small className="source-error">最近问题：{health.last_error}</small>}
                    <a href={source.source_url} target="_blank" rel="noreferrer">打开官方来源 <ExternalLink size={12} /></a>
                  </article>
                );
              })}
              {!rows.length && <Empty text="这一层尚未登记来源" />}
            </div>
          </section>
        );
      })}
      <section className="source-coverage-section">
        <header><h2>三大赛道七层今日结果</h2><p>单元格只表示当天有效记录；来源接入率、采集成功率和历史可用率已分开计算。</p></header>
        {latestDate ? (
          <div className="coverage-matrix">
            <div className="coverage-head"><b>赛道</b>{sourceCategories.map((item) => <b key={item.code}>{item.name}</b>)}</div>
            {["机器人", "商业航天", "AI"].map((sector) => (
              <div className="coverage-row" key={sector}>
                <b>{sector}</b>
                {sourceCategories.map((item) => {
                  const cell = coverage.find((row: any) => row.sectors?.name === sector && row.source_category === item.code);
                  return <span className={cell?.coverage_status || "missing"} key={item.code}>{coverageStatusLabel(cell?.coverage_status)}<small>{cell?.raw_record_count || 0}条 · 接入{cell?.integration_rate_pct ?? 0}%</small></span>;
                })}
              </div>
            ))}
          </div>
        ) : <Empty text="等待完整日流程生成第一份来源覆盖快照" />}
      </section>
    </div>
  );
}

function GuideView() {
  const pages = [
    ["研究总览", "筛选链运行到哪里、今天哪里变化。"],
    [
      "每日研究日报",
      "完整冻结当天的信号、机会、公司、模型、赔率、风险与任务。",
    ],
    ["变化发现", "新变化是否值得进入机会确认。"],
    ["机会池", "多条变化是否已经形成产业机会。"],
    ["公司筛选", "谁真正受益，谁只是产业验证对象。"],
    ["公司建模", "利润、目标市值与概率的三情景模型。"],
    ["投资价值", "叠加今日价格后是否有足够赔率。"],
    ["公司时间轴", "完整研究路径与关键历史节点。"],
    ["验证中心", "持续验证旧判断后来是否兑现。"],
  ];
  return (
    <>
      <section className="guide-hero v41-guide">
        <div>
          <span>唯一后台筛选链</span>
          <h2>变化发现 → 机会确认 → 公司映射 → 公司建模 → 投资价值</h2>
          <p>持续验证、公司时间轴和观察状态横跨阶段，不是第六步。</p>
        </div>
        <RotateCcw size={42} />
      </section>
      <div className="guide-capabilities">
        <article>
          <b>每日研究日报</b>
          <p>按生成日期冻结，集中回答今天三大赛道发生了什么。</p>
        </article>
        <article>
          <b>观察</b>
          <p>
            后台仍为 shadow，并记录 mapping / modeling /
            investment_value、暂停原因和重新激活条件。
          </p>
        </article>
        <article>
          <b>产业验证对象</b>
          <p>
            未上市公司、海外龙头、客户和供应商用于验证产业，但不计算 A
            股投资赔率。
          </p>
        </article>
        <article>
          <b>公司时间轴</b>
          <p>保存价格、利润、概率、状态、原因、来源和模型版本的关键节点。</p>
        </article>
        <article>
          <b>持续验证</b>
          <p>可以推动机会重判、模型重算和投资价值重算。</p>
        </article>
        <article>
          <b>验证中心</b>
          <p>把旧判断与后续事实、价格结果放在一起核验。</p>
        </article>
      </div>
      <section className="front-pages">
        <h2>最终页面职责</h2>
        {pages.map(([a, b]) => (
          <article key={a}>
            <b>{a}</b>
            <p>{b}</p>
          </article>
        ))}
      </section>
    </>
  );
}

const optimizationTypes = [
  "界面调整",
  "逻辑调整",
  "数据修复",
  "自动化修复",
  "模型调整",
  "日报调整",
  "公司时间轴",
  "历史测试",
];

function SystemOptimizationLog({ data }: { data: any }) {
  const [version, setVersion] = useState("全部");
  const [type, setType] = useState("全部");
  const records = data.optimizationRecords || [];
  const versionValues = Array.from(
    new Set(records.map((x: any) => x.version as string)),
  ).sort((a, b) => {
    const left = a.replace(/^V/i, "").split(".").map(Number);
    const right = b.replace(/^V/i, "").split(".").map(Number);
    const length = Math.max(left.length, right.length);
    for (let i = 0; i < length; i += 1) {
      const difference = (right[i] || 0) - (left[i] || 0);
      if (difference) return difference;
    }
    return 0;
  });
  const versions = ["全部", ...versionValues];
  const visible = records.filter(
    (x: any) =>
      (version === "全部" || x.version === version) &&
      (type === "全部" || (x.change_types || []).includes(type)),
  );
  const groups = versions
    .filter((x) => x !== "全部")
    .map((v) => ({
      version: v,
      records: visible.filter((x: any) => x.version === v),
    }))
    .filter((x) => x.records.length > 0);

  return (
    <div className="optimization-log">
      <section className="optimization-intro">
        <div>
          <span>给未来自己的系统成长记录本</span>
          <h2>先记住为什么改，再记录改了什么</h2>
          <p>
            这里记录整个研究系统的变化。公司本身的变化，仍然只放在公司时间轴。
          </p>
        </div>
        <div className="optimization-count">
          <strong>{records.length}</strong>
          <span>条真实修改记录</span>
        </div>
      </section>

      <section className="optimization-filters" aria-label="筛选系统优化记录">
        <div>
          <span>按版本</span>
          <div className="filter-pills">
            {versions.map((x) => (
              <button
                key={x}
                className={version === x ? "active" : ""}
                onClick={() => setVersion(x)}
              >
                {x}
              </button>
            ))}
          </div>
        </div>
        <div>
          <span>按类型</span>
          <div className="filter-pills">
            {["全部", ...optimizationTypes].map((x) => (
              <button
                key={x}
                className={type === x ? "active" : ""}
                onClick={() => setType(x)}
              >
                {x}
              </button>
            ))}
          </div>
        </div>
      </section>

      {groups.length ? (
        <div className="optimization-timeline">
          {groups.map((group) => (
            <section className="optimization-version" key={group.version}>
              <header>
                <b>{group.version}</b>
                <span>{group.records[0]?.record_date}</span>
              </header>
              <div className="optimization-version-records">
                {group.records.map((record: any) => (
                  <OptimizationRecord key={record.id} record={record} />
                ))}
              </div>
            </section>
          ))}
        </div>
      ) : (
        <Empty text="当前筛选条件下暂无记录" />
      )}
    </div>
  );
}

function OptimizationRecord({ record }: { record: any }) {
  const list = (value: any) => (Array.isArray(value) ? value : []);
  return (
    <article className="optimization-record">
      <div className="optimization-record-top">
        <div className="optimization-tags">
          {(record.change_types || []).map((x: string) => (
            <span key={x}>{x}</span>
          ))}
        </div>
        <Status value={record.acceptance_result} />
      </div>
      <div className="optimization-summary">
        <small>一句话总结</small>
        <h3>{record.one_line_summary}</h3>
      </div>
      <div className="optimization-why">
        <small>为什么改</small>
        <p>{record.why_changed}</p>
      </div>

      <details className="optimization-details">
        <summary>展开完整记录</summary>
        <div className="optimization-detail-body">
          <LogList title="当时发现的问题" items={list(record.problems_found)} />
          <LogList title="这次主要改了什么" items={list(record.main_changes)} />
          <section className="optimization-outcome">
            <h4>改完以后应该变成什么样</h4>
            <p>{record.expected_result}</p>
          </section>
          <section>
            <h4>这次改动范围</h4>
            <div className="optimization-change-grid">
              <ChangeFact
                label="改数据库"
                changed={record.database_changed}
                note={record.database_change_summary}
              />
              <ChangeFact
                label="改筛选逻辑"
                changed={record.screening_logic_changed}
                note={record.screening_logic_summary}
              />
              <ChangeFact
                label="改自动化"
                changed={record.automation_changed}
                note={record.automation_change_summary}
              />
              <div>
                <span>旧数据</span>
                <strong>{record.old_data_impact}</strong>
              </div>
            </div>
          </section>
          <LogList title="重要决定" items={list(record.important_decisions)} />
          <section className="optimization-result">
            <div>
              <span>验收结果</span>
              <strong>{record.acceptance_result}</strong>
            </div>
            <LogList
              title="还剩什么问题"
              items={list(record.unresolved_issues)}
            />
            <div>
              <span>下一步准备做什么</span>
              <p>{record.next_step}</p>
            </div>
          </section>
          <details className="technical-details">
            <summary>查看技术细节</summary>
            <pre>{JSON.stringify(record.technical_details || {}, null, 2)}</pre>
          </details>
        </div>
      </details>
    </article>
  );
}

function LogList({ title, items }: { title: string; items: string[] }) {
  return (
    <section>
      <h4>{title}</h4>
      {items.length ? (
        <ul>
          {items.map((x, i) => (
            <li key={`${title}-${i}`}>{x}</li>
          ))}
        </ul>
      ) : (
        <p>现有记录中无法确认</p>
      )}
    </section>
  );
}

function ChangeFact({
  label,
  changed,
  note,
}: {
  label: string;
  changed: boolean;
  note?: string;
}) {
  return (
    <div>
      <span>{label}</span>
      <strong>{changed ? "有" : "没有"}</strong>
      {changed && note && <p>{note}</p>}
    </div>
  );
}
function LegacyModels({ data }: { data: any }) {
  const companies = [
    ...new Map(data.profitModels.map((m: any) => [m.companyCode, m])).values(),
  ] as any[];
  return (
    <>
      <Moved to="公司详情 / 模型与估值" href="/companies" />
      <div className="company-mini-list">
        {companies.map((m: any) => (
          <Link href={`/company/${m.companyCode}`} key={m.companyCode}>
            <b>{m.companyName}</b>
            <span>
              {m.fiscal_year}E · {m.model_status || "核算中"}
            </span>
            <ArrowRight size={14} />
          </Link>
        ))}
      </div>
    </>
  );
}
function DailyArchive({ data }: { data: any }) {
  return (
    <>
      <Moved to="今日工作台 / 历史" href="/" />
      <div className="archive-list">
        {data.reports.map((r: any) => (
          <article key={r.id}>
            <time>{r.report_date}</time>
            <div>
              <b>{r.summary || "当日研究记录"}</b>
              <p>
                最强赛道：{r.strongest_sector || "—"} · 有效信号{" "}
                {r.valid_signal_count ?? "—"}
              </p>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
function ReportSection({
  n,
  title,
  children,
}: {
  n: string;
  title: string;
  children: any;
}) {
  return (
    <section className="report-section">
      <header>
        <span>{n}</span>
        <h2>{title}</h2>
      </header>
      <div>{children}</div>
    </section>
  );
}
function ReportList({
  n,
  title,
  rows = [],
  fields,
}: {
  n: string;
  title: string;
  rows: any[];
  fields: string[][];
}) {
  return (
    <ReportSection n={n} title={title}>
      {rows?.length ? (
        <div className="report-records">
          {rows.map((r: any, i: number) => (
            <article key={i}>
              {fields.map(([label, key]) => (
                <Field key={key} k={label} v={r?.[key]} />
              ))}
            </article>
          ))}
        </div>
      ) : (
        <p className="muted">当日无新增记录；系统没有用示例数据补位。</p>
      )}
    </ReportSection>
  );
}
function Field({ k, v }: { k: string; v: any }) {
  return (
    <div className="field">
      <span>{k}</span>
      <b>{display(v)}</b>
    </div>
  );
}
function display(v: any) {
  if (v == null || v === "") return "暂无数据";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}
function daysFrom(a: string, b: string) {
  if (!a || !b) return 99;
  return Math.abs((new Date(b).getTime() - new Date(a).getTime()) / 86400000);
}
function money(v: any) {
  return v == null ? "待计算" : `${Number(v).toFixed(2)}亿`;
}
function stageName(v: any) {
  return (
    (
      {
        change_discovery: "变化发现",
        opportunity_confirmation: "机会确认",
        company_mapping: "公司映射",
        company_modeling: "公司建模",
        investment_value: "投资价值评估",
        high_expected_return: "高期望收益",
      } as any
    )[v] || v
  );
}
function eventName(v: any) {
  return (
    (
      {
    first_discovery: "首次发现",
    formal_pool: "首次发现 / 正式入池",
    opportunity_mapping: "机会映射",
        company_mapping: "公司映射",
        modeling_started: "进入建模",
        modeling_completed: "建模完成",
        fundamental_change: "基本面变化",
        price_change: "价格变化",
        model_revision: "模型修正",
        probability_adjustment: "概率调整",
        valuation_adjustment: "估值调整",
    investment_status_change: "投资状态变化",
    status_transition: "投资状态变化",
    current: "当前投资价值快照",
        result_validation: "结果验证",
      } as any
    )[v] || stageName(v)
  );
}
function Moved({ to, href }: { to: string; href: string }) {
  return (
    <div className="object-note">
      <Info size={16} />
      <span>
        该旧入口已迁移至 <b>{to}</b>；此处保留历史数据追溯。
      </span>
      <Link href={href}>
        前往新入口
        <ArrowRight size={14} />
      </Link>
    </div>
  );
}
function HelpDrawer({
  module,
  onClose,
}: {
  module: string;
  onClose: () => void;
}) {
  const h = helpContent[module] || helpContent.guide;
  return (
    <div className="help-backdrop" onClick={onClose}>
      <aside className="help-drawer" onClick={(e) => e.stopPropagation()}>
        <button className="help-close" onClick={onClose}>
          <X size={18} />
        </button>
        <p className="eyebrow">PAGE GUIDE</p>
        <h2>{h.title}</h2>
        <dl>
          {[
            ["这个页面看什么", h.look],
            ["这个页面不看什么", h.not],
            ["什么数据会出现", h.data],
            ["为什么会出现在这里", h.why],
            ["下一步应该去哪", h.next],
          ].map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </aside>
    </div>
  );
}
const helpContent: any = {
  daily: {
    title: "每日研究日报",
    look: "当天三大赛道的完整研究变化。",
    not: "不是新闻摘要，也不使用未来数据回写历史。",
    data: "冻结的信号、机会、公司、模型、赔率、风险与任务。",
    why: "每天形成一份可追溯研究底稿。",
    next: "沿日报中的对象进入对应筛选阶段。",
  },
  signals: {
    title: "变化发现",
    look: "新变化是否值得继续研究。",
    not: "不在这里做公司估值。",
    data: "信号、来源、证据等级、当前判断与下一步。",
    why: "达到结构化变化门槛才会出现。",
    next: "通过后进入机会池。",
  },
  opportunities: {
    title: "机会池",
    look: "产业机会的当前结论、变化、风险与映射。",
    not: "不在这里做公司完整估值。",
    data: "真实机会、关联信号、产业链与公司映射。",
    why: "多条变化共同形成一个可跟踪机会。",
    next: "选择公司进入公司筛选或统一公司详情。",
  },
  companies: {
    title: "公司映射与筛选",
    look: "谁真正受益、谁只是产业验证对象。",
    not: "不展开详细 PE 与完整利润模型。",
    data: "映射公司、角色、受益逻辑、证据、结论与下一步。",
    why: "公司与机会已有可解释的产业链关系。",
    next: "通过后进入公司建模。",
  },
  modeling: {
    title: "公司建模",
    look: "悲观/中性/乐观利润、目标市值与概率。",
    not: "不在这里用价格直接下投资结论。",
    data: "公司基本面模型、完成度、可信度和缺口。",
    why: "公司映射通过且利润具备可测基础。",
    next: "模型完成后进入投资价值。",
  },
  odds: {
    title: "投资价值",
    look: "今天的期望收益、下行与风险收益比。",
    not: "完成测算不等于高期望收益。",
    data: "已完成价格、概率与模型计算的公司。",
    why: "完成评估后按门槛分流。",
    next: "进入公司详情判断瓶颈和证据。",
  },
  timeline: {
    title: "公司时间轴",
    look: "公司从首次发现到验证结果的完整历史。",
    not: "默认不铺开每日价格快照。",
    data: "关键事件、筛选决策、模型版本与证据来源。",
    why: "进入公司映射后持续保存研究演化。",
    next: "进入统一公司详情或展开每日快照。",
  },
  validation: {
    title: "验证中心",
    look: "旧判断后来是否被事实支持、结果是否兑现。",
    not: "不是后台研究流程第六步。",
    data: "持续验证事件与结果验证记录。",
    why: "所有需继续跟踪的对象都会进入验证视图。",
    next: "根据新事实回到机会、模型或投资价值。",
  },
  "historical-validation": {
    title: "历史验证",
    look: "当时系统实际能看到什么，哪些资料因时间或可得性被排除。",
    not: "不是收益回测，不评价涨跌，也不把结果写回实时研究状态。",
    data: "独立历史证据包、时间边界、来源覆盖、排除原因和泄漏检查。",
    why: "每次测试先锁定日期与版本；发现未来泄漏或资料库偏差就判定无效。",
    next: "先补齐严格历史来源和当时证券池，通过后才进入动态盲测。",
  },
  sources: {
    title: "信息源",
    look: "七类来源分别接了什么、是否真的运行、能否用于历史验证。",
    not: "来源登记不等于已经采集成功，也不代表来源里的每条内容都会成为有效信号。",
    data: "来源等级、用途、健康状态、最近成功、自动采集、历史可得性和赛道覆盖。",
    why: "重要判断需要知道证据从哪里来，并及时暴露需求、供应链和负面信息盲区。",
    next: "先补失败和缺失层，再回到变化发现核对具体信号。",
  },
  guide: {
    title: "系统说明",
    look: "五步筛选链与日报、时间轴、验证如何协同。",
    not: "不提供新的研究结论。",
    data: "状态机、横向能力和页面职责。",
    why: "用于统一系统语义。",
    next: "从研究总览开始。",
  },
  "system-log": {
    title: "系统优化记录",
    look: "系统当时哪里不好用、为什么改、改完怎么样。",
    not: "不是公司变化记录，也不是给程序员看的开发日志。",
    data: "每个版本的修改原因、问题、重要决定、验收结果和下一步。",
    why: "每次系统修改完成后都会留下一条大白话记录。",
    next: "按版本或类型筛选，也可以展开查看完整记录。",
  },
};
function SearchBox({
  value,
  onChange,
  placeholder,
  count,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  count: number;
}) {
  return (
    <div className="v41-search">
      <label>
        <Search size={16} />
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
        />
      </label>
      <span>{count} 条</span>
    </div>
  );
}
function TabBar({
  items,
  value,
  onChange,
}: {
  items: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="detail-tabs">
      {items.map((x) => (
        <button
          className={x === value ? "active" : ""}
          onClick={() => onChange(x)}
          key={x}
        >
          {x}
        </button>
      ))}
    </div>
  );
}
function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: any;
  note: string;
}) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </article>
  );
}
function Conclusion({ label, value }: { label: string; value: any }) {
  return (
    <article>
      <span>{label}</span>
      <p>{value || "暂无数据"}</p>
    </article>
  );
}
function DetailGrid({ items }: { items: any[][] }) {
  return (
    <div className="detail-grid v41-detail-grid">
      {items
        .filter((x) => x[1] != null && x[1] !== "")
        .map(([k, v]) => (
          <div key={k}>
            <span>{k}</span>
            <div>{v}</div>
          </div>
        ))}
    </div>
  );
}
function Status({ value }: { value: any }) {
  return (
    <span
      className={`status ${String(value).includes("高期望") || String(value).includes("重点") ? "good" : String(value).includes("不通过") ? "bad" : ""}`}
    >
      {value || "待确认"}
    </span>
  );
}
function Evidence({ value }: { value: any }) {
  return (
    <span
      className={`evidence-grade grade-${String(value || "D").toLowerCase()}`}
    >
      {value || "D"}
    </span>
  );
}
function Empty({ text }: { text: string }) {
  return (
    <div className="blocked-empty">
      <strong>{text}</strong>
      <p>缺失项保持为空，不使用静态示例替代真实数据。</p>
    </div>
  );
}
function frontStatus(c: any) {
  if (c.companyRole === "industry_validator") return "产业验证";
  if (c.investmentAssessmentStatus === "high_expected_return")
    return "高期望收益";
  if (c.researchPoolStatus === "research") return "重点研究";
  if (c.researchPoolStatus === "shadow") return "观察";
  if (c.researchPoolStatus === "archived") return "归档";
  return "不通过";
}
function screenStatus(c: any) {
  if (c.companyRole === "industry_validator") return "产业验证";
  if (c.researchPoolStatus === "shadow") return "观察";
  if (
    c.researchPoolStatus === "research" ||
    c.valuationStatus === "completed" ||
    c.valuationStatus === "insufficient_data"
  )
    return "进入建模";
  return "不通过";
}
function latestCompanyChange(c: any, data: any) {
  const e = data.timelineEvents.find((x: any) => x.company_id === c.id);
  const t = data.stateTransitions.find((x: any) => x.company_id === c.id);
  return (
    e?.change_reason ||
    e?.title ||
    t?.transition_reason ||
    c.transitionReason ||
    "暂无变化"
  );
}
function confidence(v: any) {
  return ({ high: "高", medium: "中", low: "低" } as any)[v] || "待核实";
}
function sourceCategoryLabel(value: any) {
  return ({
    company: "公司",
    policy: "政策",
    demand: "需求",
    industry: "产业",
    supply_chain: "供应链",
    market: "市场验证",
    negative_counterevidence: "负面反证",
  } as any)[value] || "待分类";
}
function sourceHealthLabel(value: any) {
  return ({
    healthy: "正常",
    healthy_no_new_data: "正常但今天无新数据",
    healthy_no_new_trade: "正常但今天无新交易",
    degraded: "降级",
    failed: "失败",
    not_configured: "未配置",
  } as any)[value] || "未配置";
}
function historicalSupportLabel(value: any) {
  return ({
    full: "支持（从真实采集日起）",
    partial: "部分支持（仍需核对当时可得性）",
    realtime_only: "仅支持实时",
    none: "不支持",
  } as any)[value] || "无法确认";
}
function availabilityLabel(value: any) {
  return ({
    A: "A：当时公开且稳定可获得",
    B: "B：当时公开，但无法确认系统稳定获得",
    C: "C：今天能查到，历史实时可得性低",
    D: "D：后验整理",
  } as any)[value] || "现有记录中无法确认";
}
function polarityLabel(value: any) {
  return ({ positive: "正面", negative: "负面", neutral: "中性" } as any)[value] || "待判断";
}
function coverageStatusLabel(value: any) {
  return ({ covered: "已覆盖", partial: "部分", missing: "不足" } as any)[value] || "不足";
}
function returnPct(v: any) {
  return v == null
    ? "待计算"
    : `${Number(v) >= 0 ? "+" : ""}${(Number(v) * 100).toFixed(1)}%`;
}
function effectLabel(v: any) {
  return (
    (
      {
        strengthen: "增强",
        weaken: "减弱",
        neutral: "中性",
        revalue: "重估投资价值",
        recalculate_profit: "重算公司模型",
      } as any
    )[v] || "继续观察"
  );
}
function fmt(v: any) {
  return v == null ? "待确认" : Number(v).toFixed(1);
}
function filterRows(rows: any[], query: string) {
  const q = query.trim().toLowerCase();
  return q
    ? rows.filter((r) => JSON.stringify(r).toLowerCase().includes(q))
    : rows;
}
