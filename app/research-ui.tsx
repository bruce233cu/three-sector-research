"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  Building2,
  Calculator,
  FileClock,
  LayoutDashboard,
  Map,
  Search,
  Target,
  RefreshCw,
  CircleHelp,
} from "lucide-react";
export const tracks: Record<string, string> = {
  机器人: "blue",
  商业航天: "amber",
  AI: "violet",
};
export const firms = [
  {
    code: "ROB-KELI-001",
    stockCode: "603662.SH",
    name: "柯力传感",
    track: "机器人",
    stage: "正式入池/重点研究",
    odds: "待核算",
    profit: "待核算",
    rank: "S",
    score: 7.9,
    marketCap: "141.1亿",
    reason: "力学传感器由送样/小批量跨入批量供应",
  },
  {
    code: "OPP-SPACE-MFG-001",
    name: "三角防务",
    track: "商业航天",
    stage: "正式入池",
    odds: "评分4/10",
    profit: "待核算",
    rank: "A",
    score: 8.0,
    marketCap: "122亿",
    reason: "星箭双超级工厂进入施工招标",
  },
  {
    code: "OPP-SPACE-ROCKET-001",
    name: "神剑股份/飞沃科技",
    track: "商业航天",
    stage: "正式入池",
    odds: "评分4.5/10",
    profit: "待核算",
    rank: "A",
    score: 7.9,
    marketCap: "101亿",
    reason: "智神星一号首飞入轨，进入回收复飞验证",
  },
  {
    code: "OPP-ROB-001",
    name: "银河通用/宁德时代",
    track: "机器人",
    stage: "正式入池/待映射",
    odds: "未核算",
    profit: "未上市/待映射",
    rank: "A",
    score: 7.5,
    marketCap: "待映射",
    reason: "多头部工业客户与千台级累计订单",
  },
  {
    code: "OPP-AI-POWER-001",
    name: "金盘科技",
    track: "AI",
    stage: "待硬筛",
    odds: "未核算",
    profit: "待核算",
    rank: "B",
    score: 7.0,
    marketCap: "296亿",
    reason: "AIDC订单+336%、收入+123%，但共识较高",
  },
];
export const sigs = [
  {
    id: "ROB-0908",
    date: "2026-09-08",
    track: "机器人",
    type: "批量交付/收入兑现",
    company: "长盈精密",
    title: "H1人形机器人零组件交付约86万件，相关收入2.43亿元，同比+537.64%",
    score: "4.25",
    state: "观察",
    source: "https://www.stcn.com/article/detail/4173733.html",
    change:
      "交付量半年超过去年全年并形成真实收入，但市值约334亿元且已被市场交易",
    verify: "H2收入和毛利、整机订单交付、新基地利用率",
  },
  {
    id: "SPACE-0907",
    date: "2026-09-07",
    track: "商业航天",
    type: "政府采购",
    company: "待映射",
    title: "三项运载火箭发射服务采购预算合计约7.9亿元",
    score: "4.5",
    state: "入池",
    source:
      "https://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260904_27272489.htm",
    change: "从单项2.7亿元升级为多任务真实预算",
    verify: "9月28日前后中标结果、火箭型号、A股供应链与单箭价值量",
  },
  {
    id: "ROB-0906",
    date: "2026-09-06",
    track: "机器人",
    type: "订单/批量供应",
    company: "柯力传感",
    title: "H1力学传感器销量超2000只，4月以来月订单持续破千",
    score: "4.5",
    state: "入池",
    source: "https://stock.stockstar.com/notice/SN2026082800003781.shtml",
    change: "力学传感器由送样和小批量正式向批量供应过渡",
    verify: "ASP、毛利率、1万/3万/10万只销量对应净利润",
  },
  {
    id: "SPACE-0906",
    date: "2026-09-06",
    track: "商业航天",
    type: "政府采购",
    company: "待映射",
    title: "巡航卫星运载火箭发射服务公开采购，预算2.7亿元",
    score: "4.0",
    state: "观察",
    source:
      "https://www.ccgp.gov.cn/cggg/zygg/gkzb/202609/t20260904_27272481.htm",
    change: "卫星需求由规划转化为真实发射采购",
    verify: "合格投标人、开标结果与中标方A股供应链",
  },
  {
    id: "SPACE-0904",
    date: "2026-09-04",
    track: "商业航天",
    type: "首飞/产业验证",
    company: "飞沃科技",
    title: "智神星一号首飞成功入轨，可复用火箭进入轨道验证",
    score: "4.5",
    state: "入池",
    source: "https://galactic-energy.cn/index.php/Show/cid/11/aid/275",
    change: "从整箭地面验证推进至首飞入轨",
    verify: "后续2—3发回收验证、飞沃订单与收入",
  },
  {
    id: "ROB-0904",
    date: "2026-09-04",
    track: "机器人",
    type: "财报/批量交付",
    company: "优必选/待映射",
    title: "H1全尺寸人形机器人销量921台、收入5.9亿元",
    score: "4.0",
    state: "观察",
    source: "https://news.qq.com/rain/a/20260830A04KDJ00",
    change: "产业进入实际销售、收入与毛利兑现阶段",
    verify: "A股供应商定点、单机价值量、半年报收入",
  },
  {
    id: "AI-0904",
    date: "2026-09-04",
    track: "AI",
    type: "扩产/资本开支",
    company: "长电科技",
    title: "拟65亿元定增，先进封装及AI电源/存储项目投资约76.7亿元",
    score: "3.5",
    state: "观察",
    source:
      "https://money.finance.sina.com.cn/corp/go.php/vCB_AllBulletin/stockid/600584.phtml",
    change: "AI需求向先进封装、电源和存储形成真实产能投资",
    verify: "项目进度与更小市值供应商",
  },
  {
    id: "SPACE-RKT-0902",
    date: "2026-09-02",
    track: "商业航天",
    type: "首飞/技术验证",
    company: "神剑股份/飞沃科技",
    title: "智神星一号首次成功入轨",
    score: "4.6",
    state: "入池",
    source: "https://www.stdaily.com/web/gdxw/2026-09/01/content_573106.html",
    change: "由大型地面试验升级为轨道级验证",
    verify: "一级回收、复飞频率和供应商收入",
  },
  {
    id: "SPACE-MFG-0902",
    date: "2026-09-02",
    track: "商业航天",
    type: "招标/扩产",
    company: "三角防务",
    title: "星箭双超级工厂投资超38亿元，计划进入建设招标",
    score: "4.4",
    state: "入池",
    source: "https://m.jiemian.com/article/14994159.html",
    change: "基础设施由规划升级至施工招标",
    verify: "持股比例、产能、订单和会计利润归属",
  },
  {
    id: "AI-POWER-0902",
    date: "2026-09-02",
    track: "AI",
    type: "订单/收入兑现",
    company: "金盘科技",
    title: "AIDC新签订单同比+336%，收入同比+123%",
    score: "4.3",
    state: "观察",
    source: "",
    change: "AI电力需求传导至真实订单和收入，但共识较高",
    verify: "Q3数据、SST客户测试与中性赔率",
  },
  {
    id: "AI-CAPEX-0902",
    date: "2026-09-02",
    track: "AI",
    type: "需求验证/并购",
    company: "金盘科技",
    title: "AWS新增200万颗GPU，全球资本继续配置数据中心电力与冷却",
    score: "4.4",
    state: "观察",
    source:
      "https://press.aboutamazon.com/aws/2026/8/aws-and-nvidia-to-deliver-2-million-additional-gpus-and-next-generation-infrastructure-for-agentic-and-physical-ai",
    change: "电力散热瓶颈升级为全球大型公司真实资本配置",
    verify: "Q3订单、SST采购、桐乡产线与赔率",
  },
  {
    id: "SPACE-LAUNCH-0902",
    date: "2026-09-02",
    track: "商业航天",
    type: "连续发射",
    company: "待映射",
    title: "长八甲此前10次发射成功，继续执行低轨组网任务",
    score: "4.0",
    state: "观察",
    source: "https://www.nbd.com.cn/articles/2026-09-02/4570138.html",
    change: "低轨星座向高频连续发射演化",
    verify: "月度发射频率与零部件批量订单",
  },
  {
    id: "ROB-0901",
    date: "2026-09-01",
    track: "机器人",
    type: "订单规模验证",
    company: "银河通用/宁德时代",
    title: "累计订单达到千台级，并与多家头部工业客户合作",
    score: "4.5",
    state: "入池",
    source: "",
    change: "从单一产线运行升级为多客户千台级订单",
    verify: "订单拆分、交付回款、复购与单机毛利",
  },
  {
    id: "ROB-SUP-0901",
    date: "2026-09-01",
    track: "机器人",
    type: "量产/扩产",
    company: "智元机器人/敏实集团",
    title: "泰国工厂正式量产，规划年产5000台以上",
    score: "4.0",
    state: "观察",
    source: "",
    change: "海外基地从规划进入正式量产",
    verify: "实际产量、客户、出货和A股供应商",
  },
  {
    id: "SPACE-SUP-0901",
    date: "2026-09-01",
    track: "商业航天",
    type: "招标/扩产",
    company: "西部航天",
    title: "卫星与火箭超级工厂进入施工招标，总投资超38亿元",
    score: "4.0",
    state: "观察",
    source: "",
    change: "批产能力建设由规划进入固定资产落地",
    verify: "施工中标、设备采购与真实订单来源",
  },
  {
    id: "ROB-DEMO-0831",
    date: "2026-08-31",
    track: "机器人",
    type: "真实产线部署",
    company: "福田康明斯",
    title: "天工2.0实景测试近一年，迈向常态部署",
    score: "4.0",
    state: "观察",
    source: "https://www.eet-china.com/mp/a521388.html",
    change: "从能进厂走向长期真实生产节拍",
    verify: "部署台数、工位复制、ROI",
  },
  {
    id: "ROB-S1-0831",
    date: "2026-08-31",
    track: "机器人",
    type: "连续生产验证",
    company: "宁德时代/银河通用",
    title: "Galbot S1在量产线上7×24小时连续运行约3个月",
    score: "5.0",
    state: "观察",
    source: "https://www.eet-china.com/mp/a521388.html",
    change: "跨过连续作业稳定性门槛",
    verify: "采购量、故障率、人工替代比例",
  },
  {
    id: "SPACE-CLOUD-0831",
    date: "2026-08-31",
    track: "商业航天",
    type: "商业化服务",
    company: "太空算力云",
    title: "进入常态化在轨服务，完成数百次调用、服务超百家",
    score: "5.0",
    state: "观察",
    source: "https://kpzg.people.com.cn/n1/2026/0831/c404214-40789141.html",
    change: "由一次性试验升级为持续对外服务",
    verify: "收费、续费、客户结构和扩容",
  },
  {
    id: "SPACE-SAT-0831",
    date: "2026-08-31",
    track: "商业航天",
    type: "卫星交付",
    company: "长光卫星/星瞳九州",
    title: "吉林一号三星完成研制出征，即将执行星组首发",
    score: "4.0",
    state: "观察",
    source: "https://www.ithome.com/0/996/121.htm",
    change: "从规划研制进入首批交付发射",
    verify: "发射结果、后续星组和单星价值量",
  },
  {
    id: "AI-SOI-0831",
    date: "2026-08-31",
    track: "AI",
    type: "长期订单",
    company: "Soitec",
    title: "与超10家光子客户推进多年供货协议并锁定采购量",
    score: "5.0",
    state: "观察",
    source:
      "https://www.reuters.com/world/asia-pacific/soitec-locks-customers-into-multi-year-deals-2026-08-31/",
    change: "硅光SOI供给瓶颈开始显性化",
    verify: "锁定年限、收入增速、扩产与国产替代",
  },
];
export function Badge({
  children,
  tone = "",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
const groups = [
  ["工作台", [["日报", "/", LayoutDashboard],["系统说明", "/guide", CircleHelp]]],
  [
    "发现变化",
    [
      ["变化发现", "/signals", Activity],
      ["机会池", "/opportunities", Target],
    ],
  ],
  [
    "深度研究",
    [
      ["公司筛选", "/companies", Building2],
      ["利润估值", "/profit", Calculator],
      ["投资价值", "/odds", BarChart3],
      ["持续验证", "/validation", RefreshCw],
      ["产业链地图", "/industry", Map],
    ],
  ],
  ["资料归档", [["日报归档", "/daily", FileClock]]],
] as const;
export function Shell({
  active,
  children,
}: {
  active: string;
  children: React.ReactNode;
}) {
  const path = usePathname();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">Σ</div>
          <div>
            <strong>三大赛道</strong>
            <span>高赔率研究系统</span>
          </div>
        </div>
        <nav>
          {groups.map(([g, items]) => (
            <div className="nav-group" key={g}>
              <p>{g}</p>
              {items.map(([n, u, I]) => (
                <Link
                  key={n}
                  href={u}
                  className={
                    (u === "/" ? path === u : path.startsWith(u))
                      ? "active"
                      : ""
                  }
                >
                  <I size={16} />
                  {n}
                  {n === "变化发现" && <em>35</em>}
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="sync">
            <i /> 今日扫描已完成
          </div>
          <p>研究框架 V4 · 状态机</p>
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="crumb">
            三大赛道研究　/　<b>{active}</b>
          </div>
          <label className="search">
            <Search size={15} />
            <input placeholder="搜索公司、代码、信号" />
          </label>
          <div className="avatar">BZ</div>
        </header>
        <div className="content">{children}</div>
      </main>
    </div>
  );
}
