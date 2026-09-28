"use client";

import { useEffect, useState } from "react";
import { Activity, AlertTriangle, CheckCircle2, Database, Radar, Snowflake } from "lucide-react";
import { Shell } from "../research-ui";

type Sample = {
  trade_date: string;
  industry_name: string;
  taxonomy_code: string;
  member_count: number | null;
  valid_member_count: number | null;
  coverage: number | null;
  sector_return: number | null;
  rs_10: number | null;
  stage_frozen: boolean | null;
  status: "SUCCESS" | "PARTIAL" | "FAIL" | "RUNNING";
};

type MainlineStatus = {
  phase: { version: string; phase: string; gate: string; status: string };
  counts: { total: number; success: number; partial: number; fail: number; running: number };
  health: Record<string, string | null>;
  recent_samples: Sample[];
  updated_at: string | null;
};

const empty: MainlineStatus = {
  phase: { version: "V2.2", phase: "Phase 1D", gate: "G1", status: "建设中" },
  counts: { total: 15, success: 0, partial: 0, fail: 0, running: 0 },
  health: {},
  recent_samples: [],
  updated_at: null,
};

const value = (v: unknown, suffix = "") =>
  v === null || v === undefined || v === "" ? "数据不足" : `${v}${suffix}`;
const pct = (v: number | null) => (v == null ? "数据不足" : `${(v * 100).toFixed(1)}%`);
const num = (v: number | null, digits = 2) => (v == null ? "数据不足" : Number(v).toFixed(digits));

export default function MainlinePage() {
  const [data, setData] = useState<MainlineStatus>(empty);
  const [live, setLive] = useState(false);
  useEffect(() => {
    fetch("/api/mainline", { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json();
      })
      .then((next) => { setData(next); setLive(true); })
      .catch(() => setLive(false));
  }, []);

  const cards = [
    ["总样本", data.counts.total, "固定 5 日期 × 3 行业"],
    ["成功", data.counts.success, "覆盖达标且未冻结"],
    ["部分", data.counts.partial, "有结果但质量冻结"],
    ["失败", data.counts.fail, "未形成有效板块快照"],
    ["运行中", data.counts.running, "受控补跑中的样本"],
  ];
  const health = [
    ["历史板块定义", data.health.taxonomy],
    ["历史板块成员", data.health.membership],
    ["行情数据", data.health.market_data],
    ["市值数据", data.health.market_cap],
    ["缓存状态", data.health.cache],
    ["Freeze状态", data.health.freeze],
    ["最近 run_id", data.health.latest_run_id],
    ["最近运行时间", data.health.latest_run_at],
  ];

  return (
    <Shell active="A股主线">
      <main className="mainline-page">
        <header className="mainline-hero">
          <div>
            <p className="eyebrow">MARKET RESEARCH / MAINLINE V2.2</p>
            <h1>A股主线识别</h1>
            <p>识别当前全A市场的行业与板块强弱变化，与三大赛道公司深度研究相互独立。</p>
          </div>
          <div className={`mainline-live ${live ? "ok" : "warn"}`}>
            <Activity size={16} />{live ? "真实运行数据" : "数据连接不足"}
          </div>
        </header>

        <section className="phase-banner">
          <div><span>当前版本</span><strong>{data.phase.version}</strong></div>
          <div><span>当前 Phase</span><strong>{data.phase.phase}</strong></div>
          <div><span>当前 Gate</span><strong>{data.phase.gate}</strong></div>
          <div><span>当前状态</span><strong className="amber">{data.phase.status}</strong></div>
          <p><AlertTriangle size={16} />当前只验收板块级客观数据闭环，尚未进入 S1–S4 与主线状态判断。</p>
        </section>

        <section>
          <div className="mainline-section-head"><div><span>01</span><h2>Phase 1D 真实 POC</h2></div><small>{value(data.updated_at)}</small></div>
          <div className="mainline-stat-grid">
            {cards.map(([label, n, note]) => <article key={String(label)}><span>{label}</span><strong>{n}</strong><small>{note}</small></article>)}
          </div>
        </section>

        <section className="mainline-health-layout">
          <div className="mainline-panel">
            <div className="mainline-section-head"><div><Database size={18}/><h2>数据健康</h2></div></div>
            <div className="health-list">
              {health.map(([label, v]) => <div key={label}><span>{label}</span><strong>{value(v)}</strong></div>)}
            </div>
          </div>
          <div className="mainline-panel boundary-card">
            <div className="mainline-section-head"><div><Radar size={18}/><h2>系统边界</h2></div></div>
            <p>本模块只识别市场和板块，长期保存板块级指标、质量状态与审计证据。</p>
            <p>公司利润、估值、赔率和投资价值属于“三大赛道深度研究”，不在本模块内计算。</p>
            <div><CheckCircle2 size={16}/> 不回灌全A逐股历史库</div>
            <div><Snowflake size={16}/> 覆盖不足时冻结，不以0补缺失</div>
          </div>
        </section>

        <section className="mainline-panel samples-panel">
          <div className="mainline-section-head"><div><span>02</span><h2>最近板块样本</h2></div><small>仅展示真实运行结果</small></div>
          {data.recent_samples.length ? (
            <div className="mainline-table-wrap"><table><thead><tr><th>日期 / 行业</th><th>代码</th><th>成员</th><th>有效</th><th>覆盖率</th><th>板块收益</th><th>RS 10</th><th>质量状态</th></tr></thead>
            <tbody>{data.recent_samples.map((row) => <tr key={`${row.trade_date}-${row.taxonomy_code}`}><td><strong>{row.industry_name}</strong><small>{row.trade_date}</small></td><td>{row.taxonomy_code}</td><td>{value(row.member_count)}</td><td>{value(row.valid_member_count)}</td><td>{pct(row.coverage)}</td><td>{row.sector_return == null ? "待计算" : `${num(row.sector_return)}%`}</td><td>{row.rs_10 == null ? "待计算" : num(row.rs_10)}</td><td><span className={`sample-status ${row.status.toLowerCase()}`}>{row.status}</span></td></tr>)}</tbody></table></div>
          ) : <div className="empty-state">暂无可展示的真实板块样本；页面不会使用静态假数据替代。</div>}
        </section>

        <section className="mainline-coming"><h2>后续入口</h2><div>{["市场雷达 /mainline/radar", "历史回放 /mainline/history", "数据健康 /mainline/health", "规则说明 /mainline/rules"].map(x => <span key={x}>{x}<small>建设中 · 尚未开放</small></span>)}</div></section>
      </main>
    </Shell>
  );
}
