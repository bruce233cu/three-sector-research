"use client";
import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  CircleHelp,
  ExternalLink,
  X,
} from "lucide-react";
import {
  Shell,
  Badge,
  firms as fallbackFirms,
  sigs as fallbackSigs,
  tracks,
} from "../../research-ui";
import { useResearchData } from "../../../hooks/use-research-data";

export default function Page() {
  const { code } = useParams<{ code: string }>();
  const data = useResearchData(fallbackFirms, fallbackSigs);
  const c = data.firms.find((x: any) => x.code === code);
  const [tab, setTab] = useState("公司逻辑");
  const [help, setHelp] = useState(false);
  if (!c) return null;
  const models = data.profitModels.filter((x: any) => x.companyCode === c.code);
  const expected = data.expectedReturns.filter(
    (x: any) => x.company_id === c.id,
  )[0];
  const prices = data.prices.filter((x: any) => x.company_id === c.id);
  const parameters = data.modelParameters.filter(
    (x: any) => x.profit_models?.company_id === c.id,
  );
  const probabilities = data.probabilities.filter(
    (x: any) => x.company_id === c.id,
  );
  const timeline = data.timelineEvents.filter(
    (x: any) => x.company_id === c.id,
  );
  const transitions = data.stateTransitions.filter(
    (x: any) => x.company_id === c.id,
  );
  const snapshots = data.dailySnapshots.filter(
    (x: any) => x.company_id === c.id,
  );
  const validations = data.validationEvents.filter(
    (x: any) => x.company_id === c.id,
  );
  const assessment = data.investmentAssessments.find(
    (x: any) => x.company_id === c.id,
  );
  const mapping = data.opportunityCompanies.find(
    (x: any) => x.company_id === c.id,
  );
  const opportunity = data.opportunities.find(
    (x: any) => x.id === mapping?.opportunity_id,
  );
  const decisions = data.screeningDecisions.filter(
    (x: any) =>
      x.object_id === c.id ||
      x.metadata?.company_id === c.id ||
      x.object_id === opportunity?.id,
  );
  const scenarios = expected?.scenario_results || {};
  const risk =
    assessment?.failure_reasons?.join("；") ||
    c.shadowReason ||
    c.metadata?.gaps ||
    c.accountingBlocker ||
    "暂无新增风险";
  const latest =
    timeline[0]?.change_reason ||
    timeline[0]?.title ||
    transitions[0]?.transition_reason ||
    c.transitionReason ||
    "暂无变化";
  return (
    <Shell active="公司筛选">
      <div className="company-detail-top">
        <Link className="back" href="/companies">
          <ArrowLeft size={14} />
          返回公司筛选
        </Link>
        <div className="head-actions">
          <Link className="help-button" href={`/timeline?company=${c.code}`}>
            完整时间轴
            <ArrowRight size={14} />
          </Link>
          <button className="help-button" onClick={() => setHelp(true)}>
            <CircleHelp size={16} />
            本页说明
          </button>
        </div>
      </div>
      <section className="company-decision-hero">
        <div className="company-identity">
          <div>
            <Badge tone={tracks[c.track]}>{c.track}</Badge>
            <Status value={frontStatus(c)} />
          </div>
          <h1>
            {c.name}
            <small>{c.stockCode || c.code}</small>
          </h1>
          <p>
            所属机会：{opportunity?.name || "待建立可追溯映射"}
            <br />
            {c.transitionReason || c.reason}
          </p>
          <div className="decision-sentence">
            <span>当前结论</span>
            <strong>{decision(c, expected)}</strong>
          </div>
        </div>
        <div className="decision-numbers">
          <Metric
            label="最新价格"
            value={
              prices[0]?.close_price == null
                ? "待核实"
                : `${prices[0].close_price}元`
            }
          />
          <Metric
            label="当前市值"
            value={
              expected?.current_market_cap == null
                ? c.marketCap
                : `${Number(expected.current_market_cap).toFixed(1)}亿`
            }
          />
          <Metric
            label="综合期望收益"
            value={pct(expected?.expected_return)}
            accent
          />
          <Metric label="中性收益" value={pct(scenarios["中性"]?.return)} />
          <Metric
            label="最大假设下行"
            value={pct(expected?.max_assumed_downside)}
          />
          <Metric
            label="风险收益比"
            value={
              expected?.risk_reward_ratio == null
                ? "待核实"
                : Number(expected.risk_reward_ratio).toFixed(2)
            }
          />
          <Metric
            label="利润 / 概率可信度"
            value={`${confidence(expected?.profit_confidence)} / ${confidence(expected?.probability_confidence)}`}
          />
          <Metric label="观察阶段" value={stageLabel(c.shadowStage)} />
        </div>
      </section>
      <div className="company-conclusion-grid">
        <Conclusion label="为什么" value={c.transitionReason || c.reason} />
        <Conclusion label="最新变化" value={latest} />
        <Conclusion label="主要风险" value={risk} />
        <Conclusion
          label="下一触发条件"
          value={c.reactivationCondition || c.keyAssumptions}
        />
      </div>
      <section className="company-research-path">
        <div>
          <b>查看研究路径</b>
          <span>
            机会确认 → 公司映射 → 公司建模 → 投资价值评估 → 高期望收益
          </span>
        </div>
        <div>
          {[
            "opportunity_confirmation",
            "company_mapping",
            "company_modeling",
            "investment_value",
            "high_expected_return",
          ].map((x) => {
            const d = decisions.find((v: any) => v.stage === x);
            return (
              <span key={x}>
                {pathLabel(x)} {d ? (d.decision === "fail" ? "✕" : "✓") : "—"}
              </span>
            );
          })}
        </div>
        <strong>当前：{frontStatus(c)}</strong>
      </section>
      <div className="detail-tabs company-tabs">
        {["公司逻辑", "模型与估值", "证据", "时间轴"].map((x) => (
          <button
            className={tab === x ? "active" : ""}
            onClick={() => setTab(x)}
            key={x}
          >
            {x}
          </button>
        ))}
      </div>
      {tab === "公司逻辑" && <CompanyLogic c={c} validations={validations} />}
      {tab === "模型与估值" && (
        <ModelValuation
          models={models}
          expected={expected}
          probabilities={probabilities}
          prices={prices}
          scenarios={scenarios}
          data={data}
          companyId={c.id}
        />
      )}
      {tab === "证据" && <EvidenceView parameters={parameters} sourceRegistry={data.sourceRegistry || []} />}
      {tab === "时间轴" && (
        <TimelineView
          timeline={timeline}
          transitions={transitions}
          snapshots={snapshots}
          data={data}
        />
      )}
      {help && (
        <div className="help-backdrop" onClick={() => setHelp(false)}>
          <aside className="help-drawer" onClick={(e) => e.stopPropagation()}>
            <button className="help-close" onClick={() => setHelp(false)}>
              <X size={18} />
            </button>
            <p className="eyebrow">PAGE GUIDE</p>
            <h2>统一公司详情</h2>
            <dl>
              <div>
                <dt>这个页面看什么</dt>
                <dd>
                  一家公司是否仍值得关注，以及理由、变化、风险和下一触发。
                </dd>
              </div>
              <div>
                <dt>这个页面不看什么</dt>
                <dd>不需要再去独立的利润、概率、估值和时间轴页面。</dd>
              </div>
              <div>
                <dt>什么数据会出现</dt>
                <dd>公司逻辑、模型与估值、分级证据、关键时间轴。</dd>
              </div>
              <div>
                <dt>为什么公司在这里</dt>
                <dd>已与产业机会建立映射，或作为产业验证对象持续跟踪。</dd>
              </div>
              <div>
                <dt>下一步应该去哪</dt>
                <dd>根据瓶颈等待价格、利润、概率或证据触发。</dd>
              </div>
            </dl>
          </aside>
        </div>
      )}
    </Shell>
  );
}

function CompanyLogic({ c, validations }: { c: any; validations: any[] }) {
  return (
    <div className="company-tab-grid">
      <section className="tab-panel">
        <h2>业务与产业链位置</h2>
        <Detail
          items={[
            ["核心业务", c.coreBusiness],
            ["产业链位置", c.chain],
            ["与机会的关系", c.reason],
            ["已确认经营数据", c.metadata?.confirmed_data],
            ["客户与验证", c.metadata?.customers],
          ]}
        />
      </section>
      <section className="tab-panel">
        <h2>当前研究判断</h2>
        <Detail
          items={[
            ["当前状态", frontStatus(c)],
            ["为什么在这里", c.transitionReason],
            ["关键假设", c.keyAssumptions],
            ["暂未通过原因", c.shadowReason || c.accountingBlocker],
            ["重新激活条件", c.reactivationCondition],
          ]}
        />
      </section>
      {validations.length > 0 && (
        <section className="tab-panel full">
          <h2>最近验证</h2>
          {validations.map((v) => (
            <article className="validation-note" key={v.id}>
              <time>{v.validation_date}</time>
              <b>{v.title}</b>
              <p>{v.conclusion}</p>
              <Status value={effectLabel(v.effect)} />
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
function ModelValuation({
  models,
  expected,
  probabilities,
  prices,
  scenarios,
  data,
  companyId,
}: {
  models: any[];
  expected: any;
  probabilities: any[];
  prices: any[];
  scenarios: any;
  data: any;
  companyId: string;
}) {
  const reverse = data.reverseValuations.filter(
    (x: any) => x.company_id === companyId,
  );
  const sens = data.sensitivities.filter(
    (x: any) => x.company_id === companyId,
  );
  return (
    <>
      <section className="model-results">
        <Metric
          label="综合期望收益"
          value={pct(expected?.expected_return)}
          accent
        />
        <Metric
          label="年化期望"
          value={pct(expected?.annualized_expected_return)}
        />
        <Metric
          label="最大假设下行"
          value={pct(expected?.max_assumed_downside)}
        />
        <Metric
          label="风险收益比"
          value={
            expected?.risk_reward_ratio == null
              ? "待核实"
              : Number(expected.risk_reward_ratio).toFixed(2)
          }
        />
      </section>
      <section className="scenario-cards">
        {["悲观", "中性", "乐观"].map((name) => {
          const s = scenarios[name];
          const m = models.find((x: any) => x.scenario === name);
          return (
            <article key={name}>
              <span>{name}情景</span>
              <strong>{pct(s?.return)}</strong>
              <dl>
                <div>
                  <dt>概率</dt>
                  <dd>
                    {s?.probability_pct == null
                      ? "待核实"
                      : `${s.probability_pct}%`}
                  </dd>
                </div>
                <div>
                  <dt>净利润</dt>
                  <dd>{money(s?.net_profit, "亿")}</dd>
                </div>
                <div>
                  <dt>目标市值</dt>
                  <dd>{money(s?.target_market_cap, "亿")}</dd>
                </div>
                <div>
                  <dt>利润可信度</dt>
                  <dd>{confidence(m?.profit_confidence)}</dd>
                </div>
              </dl>
            </article>
          );
        })}
      </section>
      <details className="model-details">
        <summary>查看变量、概率、公式与来源</summary>
        <div className="logic-scroll">
          <table className="logic-table">
            <thead>
              <tr>
                <th>情景</th>
                <th>销量</th>
                <th>ASP</th>
                <th>收入</th>
                <th>总净利润</th>
                <th>估值倍数</th>
                <th>模型状态</th>
              </tr>
            </thead>
            <tbody>
              {models.map((m: any) => (
                <tr key={m.id}>
                  <td>{m.scenario}</td>
                  <td>{m.units ?? "待核实"}</td>
                  <td>{m.asp ?? "待核实"}</td>
                  <td>{money(m.revenue, "亿")}</td>
                  <td>{money(m.total_profit, "亿")}</td>
                  <td>
                    {m.pe_multiple == null ? "待核实" : `${m.pe_multiple}x`}
                  </td>
                  <td>{m.model_status || m.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="formula-block">
          {models.map((m: any) => (
            <article key={m.id}>
              <b>{m.scenario}情景公式</b>
              <pre>{m.calculation_trace?.formula || "尚未形成完整公式"}</pre>
              <p>最大不确定性：{m.max_uncertainty || "待核实"}</p>
            </article>
          ))}
        </div>
      </details>
      <details className="model-details">
        <summary>查看价格、反向估值与敏感性</summary>
        <div className="logic-scroll">
          <table className="logic-table">
            <thead>
              <tr>
                <th>交易日</th>
                <th>收盘价</th>
                <th>市值</th>
                <th>来源</th>
              </tr>
            </thead>
            <tbody>
              {prices.map((p: any) => (
                <tr key={p.id}>
                  <td>{p.trade_date}</td>
                  <td>{p.close_price}元</td>
                  <td>{p.market_cap}亿</td>
                  <td>
                    {p.source_url ? (
                      <a href={p.source_url} target="_blank" rel="noreferrer">
                        {p.source_name}
                        <ExternalLink size={12} />
                      </a>
                    ) : (
                      p.source_name
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {reverse.length > 0 && (
          <div className="reverse-grid">
            {reverse.map((r: any) => (
              <article key={r.id || `${r.target_multiple}-${r.pe_multiple}`}>
                <span>
                  {r.target_multiple}倍市值 · {r.pe_multiple}倍PE
                </span>
                <strong>
                  需净利润 {Number(r.required_net_profit).toFixed(2)}亿
                </strong>
              </article>
            ))}
          </div>
        )}
        {sens.length > 0 && (
          <div className="logic-scroll">
            <table className="logic-table">
              <thead>
                <tr>
                  <th>变量</th>
                  <th>基准</th>
                  <th>冲击后</th>
                  <th>期望收益</th>
                  <th>风险提示</th>
                </tr>
              </thead>
              <tbody>
                {sens.map((s: any) => (
                  <tr key={s.id}>
                    <td>{s.parameter_key}</td>
                    <td>{s.base_value}</td>
                    <td>{s.shocked_value}</td>
                    <td>{pct(s.resulting_expected_return)}</td>
                    <td>{s.risk_note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </details>
    </>
  );
}
function EvidenceView({ parameters, sourceRegistry }: { parameters: any[]; sourceRegistry: any[] }) {
  const grades = ["S", "A", "B", "C", "D"];
  return (
    <div className="evidence-groups">
      {grades.map((g) => {
        const rows = parameters.filter(
          (p: any) => String(p.evidence_grade || "D").toUpperCase() === g,
        );
        return (
          <section key={g}>
            <header>
              <Evidence value={g} />
              <div>
                <h2>{gradeLabel(g)}</h2>
                <p>{rows.length} 条参数依据</p>
              </div>
            </header>
            {rows.length ? (
              rows.map((p: any) => (
                <article key={p.id}>
                  <div>
                    <b>{p.parameter_name}</b>
                    <small>
                      {p.profit_models?.scenario} · {p.parameter_key}
                    </small>
                  </div>
                  <strong>
                    {p.parameter_value == null
                      ? "待核实"
                      : `${Number(p.parameter_value).toLocaleString("zh-CN")}${p.unit || ""}`}
                  </strong>
                  <span>{typeLabel(p.data_type)}</span>
                  <p>{p.derivation_logic || "直接引用原始来源"}</p>
                  <em>{p.is_confirmed ? "已进入模型" : "尚未进入模型"}</em>
                  <small>
                    来源类型：{sourceRegistry.find((source: any) =>
                      source.source_name === p.source_name ||
                      (p.source_url && String(p.source_url).startsWith(String(source.source_url)))
                    )?.source_type || "现有记录中无法确认"} ·
                    时间：{p.source_published_at?.slice?.(0, 10) || p.effective_at?.slice?.(0, 10) || "待补"} ·
                    等级：{p.evidence_grade || "D"}
                  </small>
                  {p.source_url ? (
                    <a href={p.source_url} target="_blank" rel="noreferrer">
                      {p.source_name || "原始来源"}
                      <ExternalLink size={12} />
                    </a>
                  ) : (
                    <span>{p.source_name || "待补来源"}</span>
                  )}
                </article>
              ))
            ) : (
              <div className="grade-empty">暂无该等级证据</div>
            )}
          </section>
        );
      })}
    </div>
  );
}
function TimelineView({
  timeline,
  transitions,
  snapshots,
  data,
}: {
  timeline: any[];
  transitions: any[];
  snapshots: any[];
  data: any;
}) {
  return (
    <>
      <section className="key-timeline">
        <h2>关键事件</h2>
        {timeline.length ? (
          timeline.map((e: any) => (
            <article key={e.id}>
              <time>{e.event_at?.slice(0, 10)}</time>
              <div>
                <Status value={eventLabel(e.event_type)} />
                <h3>{e.title}</h3>
                <p>{e.change_reason || e.description}</p>
                <small>
                  期望收益 {pct(e.expected_return)} · 状态{" "}
                  {e.system_status || "—"}
                </small>
              </div>
              {e.source_url && (
                <a href={e.source_url} target="_blank" rel="noreferrer">
                  来源
                  <ExternalLink size={12} />
                </a>
              )}
            </article>
          ))
        ) : (
          <Empty text="尚未形成关键投资节点" />
        )}
      </section>
      {transitions.length > 0 && (
        <details className="model-details">
          <summary>查看状态流转（{transitions.length}）</summary>
          {transitions.map((t: any) => (
            <div className="timeline-row" key={t.id}>
              <time>{t.created_at?.slice(0, 10)}</time>
              <div>
                <b>
                  {t.from_status || "首次分类"} → {t.to_status}
                </b>
                <p>{t.transition_reason}</p>
              </div>
            </div>
          ))}
        </details>
      )}
      <details className="model-details">
        <summary>查看每日快照（{snapshots.length}）</summary>
        {snapshots.length ? (
          <div className="logic-scroll">
            <table className="logic-table">
              <thead>
                <tr>
                  <th>日期</th>
                  <th>收盘价</th>
                  <th>期望收益</th>
                  <th>概率</th>
                  <th>变化驱动</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.map((s: any) => (
                  <tr key={s.id}>
                    <td>{s.trade_date}</td>
                    <td>{s.close_price}元</td>
                    <td>{pct(s.expected_return)}</td>
                    <td>
                      {s.bear_probability}/{s.base_probability}/
                      {s.bull_probability}
                    </td>
                    <td>{driverLabel(s.change_driver)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty text="尚未保存每日快照" />
        )}
      </details>
    </>
  );
}

function Metric({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: any;
  accent?: boolean;
}) {
  return (
    <div className={accent ? "accent" : ""}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
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
function Detail({ items }: { items: any[][] }) {
  return (
    <dl className="company-logic-list">
      {items
        .filter((x) => x[1])
        .map(([a, b]) => (
          <div key={a}>
            <dt>{a}</dt>
            <dd>{b}</dd>
          </div>
        ))}
    </dl>
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
      <p>缺失项保持为空，不使用测试值冒充正式结果。</p>
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
function decision(c: any, e: any) {
  if (frontStatus(c) === "观察")
    return `继续观察：${c.shadowReason || "等待关键条件改善"}`;
  if (frontStatus(c) === "重点研究")
    return "值得继续投入研究，尚待模型或证据完成";
  if (frontStatus(c) === "高期望收益")
    return `当前投资价值较高，期望收益 ${pct(e?.expected_return)}`;
  if (frontStatus(c) === "产业验证")
    return "用于验证产业需求或技术路线，不直接做股票投资判断";
  return "当前不进入重点研究";
}
function confidence(v: any) {
  return ({ high: "高", medium: "中", low: "低" } as any)[v] || "待核实";
}
function pct(v: any) {
  return v == null
    ? "待核实"
    : `${Number(v) >= 0 ? "+" : ""}${(Number(v) * 100).toFixed(1)}%`;
}
function money(v: any, u: string) {
  return v == null
    ? "待核实"
    : `${Number(v).toLocaleString("zh-CN", { maximumFractionDigits: 2 })}${u}`;
}
function stageLabel(v: any) {
  return (
    (
      {
        mapping: "公司映射",
        modeling: "公司建模",
        investment_value: "投资价值",
      } as any
    )[v] || "—"
  );
}
function gradeLabel(v: string) {
  return (
    {
      S: "核心直接证据",
      A: "高质量事实",
      B: "可靠参考",
      C: "模型推算",
      D: "人工假设",
    } as any
  )[v];
}
function typeLabel(v: any) {
  return (
    (
      {
        fact: "事实",
        reliable_reference: "可靠参考",
        external_forecast: "外部预测",
        model_inference: "模型推算",
        manual_assumption: "人工假设",
      } as any
    )[v] || "待分类"
  );
}
function effectLabel(v: any) {
  return (
    (
      {
        strengthen: "逻辑增强",
        weaken: "逻辑减弱",
        neutral: "中性",
        revalue: "重新估值",
        recalculate_profit: "重算模型",
      } as any
    )[v] || "继续观察"
  );
}
function eventLabel(v: any) {
  return (
    (
      {
        first_discovery: "首次发现",
        focus_research: "重点研究",
        formal_pool: "正式入池",
        fundamental_change: "基本面变化",
        price_change: "价格变化",
        model_revision: "模型修正",
        validation: "结果验证",
        risk_deterioration: "风险恶化",
        downgrade: "降级",
        exit: "退出",
        current: "当前节点",
      } as any
    )[v] || v
  );
}
function driverLabel(v: any) {
  return (
    (
      {
        initial: "首次建立",
        price: "价格驱动",
        fundamental: "基本面驱动",
        model_revision: "模型修正",
        validation: "结果验证",
        risk: "风险变化",
      } as any
    )[v] ||
    v ||
    "待核实"
  );
}
function pathLabel(v: any) {
  return (
    (
      {
        opportunity_confirmation: "机会",
        company_mapping: "映射",
        company_modeling: "建模",
        investment_value: "评估",
        high_expected_return: "高期望",
      } as any
    )[v] || v
  );
}
