import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { AsyncLocalStorage } from "node:async_hooks";
import { businessDate, windowFor, mainlineDecision, independently, overallStatus, stampPayload } from "./policy.mjs";
import { createClient } from "npm:@supabase/supabase-js@2";

type ResearchCompany = {
  id: string;
  name: string;
  stock_code: string;
  sector_id: string | null;
  sectors?: { name?: string } | null;
};

type Quote = {
  code: string;
  name: string;
  tradeDate: string;
  closePrice: number;
  sharesOutstanding: number;
  marketCap: number;
  sourceUrl: string;
};

type Announcement = {
  announcementId?: string;
  announcementTitle?: string;
  announcementTime?: number;
  adjunctUrl?: string;
  secCode?: string;
  secName?: string;
};

type SignalCollectionResult = {
  attemptedSources: number;
  successfulSources: number;
  failedSources: number;
  attemptedCompanies: number;
  successfulCompanies: number;
  failedCompanies: number;
  fetchedCount: number;
  dedupedCount: number;
  rawInsertedCount: number;
  validSignalCount: number;
  errors: Array<{ company: string; error: string }>;
  sourceStatus: "healthy" | "degraded" | "failed";
  sourceDetails?: Array<{
    sourceCode: string;
    status: string;
    fetchedCount: number;
    rawInsertedCount: number;
    validSignalCount: number;
    message: string;
  }>;
};

type ExternalRecord = {
  sourceCode: string;
  sourceName: string;
  sourceCategory: "policy" | "demand" | "industry" | "supply_chain" | "negative_counterevidence";
  sourceType: string;
  sourceGrade: "S" | "A";
  title: string;
  sourceUrl: string;
  publishedAt: string;
  rawText: string;
};


const execution = new AsyncLocalStorage<any>();
async function fetch(input: any, init: any = {}) {
  const context = execution.getStore();
  const signal = AbortSignal.any([AbortSignal.timeout(20000), ...(init.signal ? [init.signal] : []), ...(context?.signal ? [context.signal] : [])]);
  if (context && String(input).includes("/rest/v1/raw_clues") && ["POST","PATCH"].includes(init.method) && typeof init.body === "string") {
    init = {...init, body:JSON.stringify(stampPayload(JSON.parse(init.body),context))};
  }
  return globalThis.fetch(input,{...init,signal});
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });

const sleep = (milliseconds: number) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  try {
    return JSON.stringify(error);
  } catch {
    return String(error);
  }
}

function dateOffset(date: string, days: number) {
  const value = new Date(`${date}T00:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

function cleanTitle(value = "") {
  return value
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

async function sha256(value: string) {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return Array.from(new Uint8Array(digest))
    .map((part) => part.toString(16).padStart(2, "0"))
    .join("");
}

const sectorKeywords: Record<string, string[]> = {
  "机器人": ["机器人", "人形", "具身智能", "机械臂", "智能制造", "力传感器", "编码器", "减速器", "丝杠", "关节", "自动化产线"],
  "商业航天": ["商业航天", "卫星", "火箭", "发射", "星座", "运载", "航天器", "太空"],
  "AI": ["人工智能", "AI", "算力", "数据中心", "服务器", "GPU", "光模块", "硅光", "CPO", "云计算"],
};

const positiveKeywords = [
  "中标", "订单", "合同", "定点", "扩产", "投产", "量产", "交付", "采购",
  "增长", "上修", "客户确认", "技术突破", "业绩预增", "扭亏",
];
const negativeKeywords = [
  "取消", "终止", "延期", "下修", "下降", "亏损", "减值", "客户流失",
  "价格下滑", "产能过剩", "处罚", "诉讼", "风险提示", "业绩预减", "退市", "违约",
];
const contextKeywords = [
  "年度报告", "半年度报告", "季度报告", "业绩预告", "业绩快报", "财务报告",
  "产能", "募投项目", "技术路线", "重大事项", "关联交易", "对外投资",
];
const excludedSignalKeywords = [
  "法律意见书", "律师事务所", "回购注销", "限制性股票", "通知债权人",
  "披露的提示性公告", "报告摘要", "不向下修正",
];

function classifyAnnouncement(title: string, company: ResearchCompany) {
  const sectorName = company.sectors?.name || "";
  const matchedSectorKeywords = Object.entries(sectorKeywords)
    .flatMap(([sector, keywords]) => keywords
      .filter((keyword) => title.toUpperCase().includes(keyword.toUpperCase()))
      .map((keyword) => ({ sector, keyword })));
  const positive = positiveKeywords.filter((keyword) => title.includes(keyword));
  const negative = negativeKeywords.filter((keyword) => title.includes(keyword));
  const context = contextKeywords.filter((keyword) => title.includes(keyword));
  const changeKeywords = [...negative, ...positive];
  const excluded = excludedSignalKeywords.some((keyword) => title.includes(keyword));
  const matchedOwnSector = matchedSectorKeywords.some((item) => item.sector === sectorName);
  const isRelevant = matchedOwnSector || changeKeywords.length > 0 || context.length > 0;
  const isRealChange = isRelevant && changeKeywords.length > 0 && !excluded;
  const sentiment = negative.length > 0
    ? "negative"
    : positive.length > 0
    ? "positive"
    : "neutral";
  return {
    sectorName,
    opportunityKeywords: Array.from(new Set([
      ...matchedSectorKeywords.map((item) => item.keyword),
      ...changeKeywords,
      ...context,
    ])),
    isRelevant,
    isRealChange,
    sentiment,
    signalType: negative[0] || positive[0] || context[0] || "待判断",
  };
}

async function fetchCninfoAnnouncements(
  company: ResearchCompany,
  runDate: string,
): Promise<Announcement[]> {
  const code = company.stock_code.split(".")[0];
  const column = company.stock_code.endsWith(".SH") ? "sse" : "szse";
  const params = new URLSearchParams({
    pageNum: "1",
    pageSize: "30",
    column,
    tabName: "fulltext",
    plate: "",
    stock: "",
    searchkey: company.name,
    secid: "",
    category: "",
    trade: "",
    seDate: `${dateOffset(runDate, -30)}~${runDate}`,
    sortName: "announcementTime",
    sortType: "desc",
    isHLtitle: "true",
  });
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const response = await fetch("https://www.cninfo.com.cn/new/hisAnnouncement/query", {
      method: "POST",
      headers: {
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "referer": `https://www.cninfo.com.cn/new/disclosure/stock?stockCode=${code}`,
        "user-agent": "Mozilla/5.0 three-sector-research/4.3.1",
        "x-requested-with": "XMLHttpRequest",
      },
      body: params.toString(),
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`公告接口返回 ${response.status}`);
    const payload = await response.json();
    if (payload?.announcements === null && Number(payload?.totalRecordNum || 0) === 0) {
      return [];
    }
    if (!Array.isArray(payload?.announcements)) {
      throw new Error("公告接口没有返回可识别的公告列表");
    }
    return payload.announcements;
  } finally {
    clearTimeout(timeout);
  }
}

async function updateSourceHealth(
  client: ReturnType<typeof createClient>,
  sourceCode: string,
  sourceName: string,
  sourceType: string,
  status: string,
  error: string | null,
  metadata: Record<string, unknown>,
) {
  const now = new Date().toISOString();
  const { data: previous } = await client
    .from("source_health")
    .select("consecutive_failures,last_success_at")
    .eq("source_code", sourceCode)
    .maybeSingle();
  const succeeded = ["healthy", "healthy_no_new_data", "healthy_no_new_trade"].includes(status);
  const { error: healthError } = await client.from("source_health").upsert({
    source_code: sourceCode,
    source_name: sourceName,
    source_type: sourceType,
    status,
    last_checked_at: now,
    last_success_at: succeeded ? now : previous?.last_success_at || null,
    last_failed_at: status === "failed" ? now : undefined,
    last_error: error,
    last_result_count: Number(metadata.fetched_count || metadata.result_count || 0),
    last_new_count: Number(metadata.raw_inserted_count || metadata.new_count || 0),
    last_run_message: typeof metadata.message === "string" ? metadata.message : null,
    consecutive_failures: status === "failed"
      ? Number(previous?.consecutive_failures || 0) + 1
      : 0,
    metadata,
    updated_at: now,
  });
  if (healthError) throw healthError;
  await client.from("source_registry").update({
    operational_status: succeeded ? "automated_active" : status === "failed" ? "degraded" : "degraded",
    status: succeeded ? "active" : "degraded",
    audit_evidence: succeeded
      ? "V4.4.2：最近一次自动任务已真实访问该来源并记录结果。"
      : `V4.4.2：自动任务已尝试但未成功：${error || status}`,
    audited_at: now,
    updated_at: now,
  }).eq("source_code", sourceCode);
}

async function collectOfficialSignals(
  client: ReturnType<typeof createClient>,
  companies: ResearchCompany[],
  runDate: string,
): Promise<SignalCollectionResult> {
  const result: SignalCollectionResult = {
    attemptedSources: 4,
    successfulSources: 0,
    failedSources: 0,
    attemptedCompanies: companies.length,
    successfulCompanies: 0,
    failedCompanies: 0,
    fetchedCount: 0,
    dedupedCount: 0,
    rawInsertedCount: 0,
    validSignalCount: 0,
    errors: [],
    sourceStatus: "failed",
  };
  const collected: Array<{ company: ResearchCompany; announcement: Announcement }> = [];
  for (const company of companies) {
    try {
      const announcements = await fetchCninfoAnnouncements(company, runDate);
      result.successfulCompanies += 1;
      result.fetchedCount += announcements.length;
      collected.push(...announcements.map((announcement) => ({ company, announcement })));
      await sleep(120);
    } catch (error) {
      result.failedCompanies += 1;
      result.errors.push({
        company: company.name,
        error: errorMessage(error),
      });
    }
  }
  if (result.successfulCompanies === 0) {
    result.failedSources = 4;
    result.sourceStatus = "failed";
  } else {
    result.successfulSources = 4;
    result.sourceStatus = result.failedCompanies > 0 ? "degraded" : "healthy";
  }

  const seenInBatch = new Set<string>();
  for (const { company, announcement } of collected) {
    const title = cleanTitle(announcement.announcementTitle);
    if (!title) continue;
    const publishedAt = announcement.announcementTime
      ? new Date(Number(announcement.announcementTime)).toISOString()
      : `${runDate}T00:00:00.000Z`;
    const sourceUrl = announcement.adjunctUrl
      ? `https://static.cninfo.com.cn/${String(announcement.adjunctUrl).replace(/^\//, "")}`
      : `https://www.cninfo.com.cn/new/disclosure/stock?stockCode=${company.stock_code.split(".")[0]}`;
    const dedupeKey = await sha256(
      announcement.announcementId
        ? `cninfo:${announcement.announcementId}`
        : `cninfo:${company.stock_code}:${publishedAt.slice(0, 10)}:${title.replace(/[^\p{L}\p{N}]/gu, "")}`,
    );
    if (seenInBatch.has(dedupeKey)) {
      result.dedupedCount += 1;
      continue;
    }
    seenInBatch.add(dedupeKey);
    const { data: existing, error: lookupError } = await client
      .from("raw_clues")
      .select("id")
      .eq("dedupe_key", dedupeKey)
      .maybeSingle();
    if (lookupError) throw new Error(`去重检查失败：${lookupError.message}`);
    if (existing) {
      result.dedupedCount += 1;
      continue;
    }

    const classification = classifyAnnouncement(title, company);
    const screeningStatus = classification.isRealChange
      ? "high_value"
      : classification.isRelevant
      ? "watch"
      : "rejected";
    const summary = classification.isRealChange
      ? `${company.name}通过法定信息披露平台发布“${title}”，已识别为需要进入变化发现核验的公司级变化。`
      : classification.isRelevant
      ? `${company.name}发布“${title}”，与研究范围有关，但仅凭标题还不能确认形成有效变化。`
      : `${company.name}发布“${title}”，当前未命中三大赛道变化规则，不进入有效信号。`;

    const { data: rawClue, error: rawError } = await client
      .from("raw_clues")
      .insert({
        occurred_on: publishedAt.slice(0, 10),
        published_at: publishedAt,
        sector_id: company.sector_id,
        source_type: "交易所公告",
        source_name: "巨潮资讯法定信息披露平台",
        source_url: sourceUrl,
        title,
        summary,
        raw_text: title,
        clue_type: classification.signalType,
        novelty_score: classification.isRealChange ? 8 : classification.isRelevant ? 5 : 2,
        reliability_score: 9,
        is_duplicate: false,
        external_id: `CNINFO-${announcement.announcementId || dedupeKey.slice(0, 20)}`,
        screening_status: screeningStatus,
        rejection_reason: classification.isRealChange
          ? null
          : classification.isRelevant
          ? "与研究范围有关，但公告标题不足以证明发生了可进入机会判断的真实变化。"
          : "没有命中三大赛道的真实变化规则。",
        verification_needed: classification.isRealChange
          ? "打开公告原文核对金额、数量、时间、客户和对利润的实际影响。"
          : "等待出现订单、量产、财报、风险或其他可核实变化。",
        company_names: [cleanTitle(announcement.secName || company.name)],
        opportunity_keywords: classification.opportunityKeywords,
        evidence_level: "S",
        sentiment: classification.sentiment,
        dedupe_key: dedupeKey,
        source_code: "cninfo_disclosure",
        source_category: classification.sentiment === "negative"
          ? "negative_counterevidence"
          : title.includes("客户") || title.includes("供应商") || title.includes("供货")
          ? "supply_chain"
          : "company",
        source_grade: "S",
        historical_availability: "A",
        availability_risk: "法定披露公开入口稳定，系统实际采集时间已记录。",
        original_title: title,
        underlying_event_id: await sha256(`event:${publishedAt.slice(0, 10)}:${title.replace(/[^\p{L}\p{N}]/gu, "")}`),
        positive_negative_neutral: classification.sentiment,
        available_at: publishedAt,
        metadata: {
          collector: "v43-daily-pipeline",
          source_code: "cninfo_disclosure",
          announcement_id: announcement.announcementId || null,
          stock_code: announcement.secCode || company.stock_code,
          sector: classification.sectorName,
          related_to_three_sectors: classification.isRelevant,
          is_real_change: classification.isRealChange,
          polarity: classification.sentiment,
        },
      })
      .select("id")
      .single();
    if (rawError) throw new Error(`原始公告写入失败：${rawError.message}`);
    result.rawInsertedCount += 1;

    if (!classification.isRealChange) continue;
    const sourceId = `AUTO-CNINFO-${announcement.announcementId || dedupeKey.slice(0, 20)}`;
    const { error: documentError } = await client.from("source_documents").upsert({
      source_id: sourceId,
      source_date: publishedAt.slice(0, 10),
      source_grade: "S",
      title,
      source_url: sourceUrl,
      supports: `官方披露显示${company.name}发生“${classification.signalType}”类变化，仍需核对正文后判断影响。`,
      notes: "由每日流程自动发现；公告事实与研究结论分开保存。",
    }, { onConflict: "source_id", ignoreDuplicates: true });
    if (documentError) throw new Error(`证据来源写入失败：${documentError.message}`);
    const { error: signalError } = await client.from("signals").insert({
      sector_id: company.sector_id,
      raw_clue_id: rawClue.id,
      signal_date: publishedAt.slice(0, 10),
      title,
      change_description: summary,
      transmission_logic: "先核对公告正文，再判断是否改变对应机会、公司模型或风险判断。",
      affected_chain: classification.sectorName || null,
      duration_hypothesis: "待公告正文和后续执行证据验证",
      score: classification.sentiment === "negative" ? 8 : 7,
      status: "pending",
      verification_needed: "核对公告正文中的金额、数量、时间、客户、利润影响和反证。",
      external_id: `AUTO-SIGNAL-${announcement.announcementId || dedupeKey.slice(0, 20)}`,
      signal_type: classification.signalType,
      company_name: cleanTitle(announcement.secName || company.name),
      source_url: sourceUrl,
      source_grade: "S",
      source_code: "cninfo_disclosure",
      source_name: "巨潮资讯法定信息披露平台",
      source_category: classification.sentiment === "negative"
        ? "negative_counterevidence"
        : title.includes("客户") || title.includes("供应商") || title.includes("供货")
        ? "supply_chain"
        : "company",
      published_at: publishedAt,
      discovered_at: new Date().toISOString(),
      historical_availability: "A",
      availability_risk: "法定披露公开入口稳定，系统实际采集时间已记录。",
      original_title: title,
      underlying_event_id: await sha256(`event:${publishedAt.slice(0, 10)}:${title.replace(/[^\p{L}\p{N}]/gu, "")}`),
      positive_negative_neutral: classification.sentiment,
      is_official: true,
      consensus_level: "待验证",
      traded_status: "待判断",
      action: "进入机会确认",
      metadata: {
        source: "automated_official_disclosure",
        source_document_id: sourceId,
        direction: classification.sentiment,
        fact_class: "官方披露事实",
        dedupe_key: dedupeKey,
      },
    });
    if (signalError && signalError.code !== "23505") throw new Error(`有效信号写入失败：${signalError.message}`);
    result.validSignalCount += 1;
  }

  const healthError = result.errors.length ? JSON.stringify(result.errors) : null;
  const metadata = {
    enabled: true,
    endpoint: "巨潮资讯法定信息披露平台",
    window_days: 30,
    attempted_companies: result.attemptedCompanies,
    successful_companies: result.successfulCompanies,
    failed_companies: result.failedCompanies,
    fetched_count: result.fetchedCount,
    deduped_count: result.dedupedCount,
    raw_inserted_count: result.rawInsertedCount,
    valid_signal_count: result.validSignalCount,
  };
  await updateSourceHealth(
    client,
    "cninfo_disclosure",
    "巨潮资讯法定信息披露平台",
    "signal",
    result.sourceStatus,
    healthError,
    metadata,
  );
  await updateSourceHealth(
    client,
    "cninfo_risk",
    "法定披露风险与反证",
    "negative_counterevidence",
    result.sourceStatus,
    healthError,
    { ...metadata, message: result.rawInsertedCount ? "已同步检查公告中的取消、延期、下修、减值、诉讼与风险提示。" : "成功检查，0条新增；不等同于没有风险。" },
  );
  await updateSourceHealth(
    client,
    "cross_chain_official",
    "上下游官方交叉验证",
    "supply_chain",
    result.sourceStatus,
    healthError,
    { ...metadata, message: "已检查当前研究公司公告中的客户、供应商、供货与采购关系；客户池覆盖仍不完整。" },
  );
  await updateSourceHealth(
    client,
    "supply_supplier_official",
    "供应商侧供应链确认",
    "supply_chain",
    result.sourceStatus,
    healthError,
    { ...metadata, message: "已真实检查研究公司作为供应商一侧的订单、供货、客户与产能披露；不能单独替代客户确认。" },
  );
  result.sourceDetails = [{
    sourceCode: "cninfo_disclosure",
    status: result.sourceStatus,
    fetchedCount: result.fetchedCount,
    rawInsertedCount: result.rawInsertedCount,
    validSignalCount: result.validSignalCount,
    message: result.rawInsertedCount
      ? `取回${result.fetchedCount}条，新写入${result.rawInsertedCount}条。`
      : `成功检查${result.attemptedCompanies}家公司，0条新增。`,
  }];
  await updateSourceHealth(
    client,
    "external_signal_sources",
    "外部研究信号来源",
    "signal",
    result.sourceStatus,
    healthError,
    { ...metadata, aggregate: true, configured_sources: 4 },
  );
  return result;
}

type WatchTarget = {
  id: string;
  entity_name: string;
  stock_code: string;
  sector_id: string;
  target_role: "customer" | "competitor";
};

async function collectWatchTargetDisclosures(
  client: ReturnType<typeof createClient>,
  runDate: string,
  sectors: Array<{ id: string; name: string }>,
): Promise<SignalCollectionResult> {
  const result: SignalCollectionResult = {
    attemptedSources: 3, successfulSources: 0, failedSources: 0,
    attemptedCompanies: 0, successfulCompanies: 0, failedCompanies: 0,
    fetchedCount: 0, dedupedCount: 0, rawInsertedCount: 0, validSignalCount: 0,
    errors: [], sourceStatus: "failed", sourceDetails: [],
  };
  const { data: targets, error: targetError } = await client.from("source_watch_targets")
    .select("id,entity_name,stock_code,sector_id,target_role")
    .eq("enabled", true)
    .in("target_role", ["customer", "competitor"])
    .not("stock_code", "is", null)
    .order("priority");
  if (targetError) throw targetError;
  const sectorNames = new Map(sectors.map((sector) => [sector.id, sector.name]));
  const stats = {
    customer: { fetched: 0, inserted: 0, succeeded: 0, failed: 0 },
    customerSupply: { fetched: 0, inserted: 0, succeeded: 0, failed: 0 },
    competitor: { fetched: 0, inserted: 0, succeeded: 0, failed: 0 },
  };
  const demandKeywords = ["资本开支", "投资", "采购", "招标", "中标", "扩产", "数据中心", "服务器", "算力", "机器人", "自动化", "卫星", "星座", "地面站"];
  const relationshipKeywords = ["供应商", "客户", "采购", "供货", "中标", "订单", "设备", "合作"];
  const competitorKeywords = ["扩产", "产能", "降价", "价格", "替代", "新产品", "市场份额", "订单", "投产"];
  for (const target of (targets || []) as WatchTarget[]) {
    result.attemptedCompanies += 1;
    const roleStats = target.target_role === "customer" ? stats.customer : stats.competitor;
    try {
      const company: ResearchCompany = {
        id: target.id,
        name: target.entity_name,
        stock_code: target.stock_code,
        sector_id: target.sector_id,
        sectors: { name: sectorNames.get(target.sector_id) || "" },
      };
      const announcements = await fetchCninfoAnnouncements(company, runDate);
      roleStats.fetched += announcements.length;
      if (target.target_role === "customer") stats.customerSupply.fetched += announcements.length;
      result.fetchedCount += announcements.length;
      result.successfulCompanies += 1;
      roleStats.succeeded += 1;
      if (target.target_role === "customer") stats.customerSupply.succeeded += 1;
      for (const announcement of announcements) {
        const title = cleanTitle(announcement.announcementTitle);
        const keywords = target.target_role === "customer" ? demandKeywords : competitorKeywords;
        if (!title || !keywords.some((keyword) => title.includes(keyword))) continue;
        const publishedAt = announcement.announcementTime
          ? new Date(Number(announcement.announcementTime)).toISOString()
          : `${runDate}T00:00:00.000Z`;
        const sourceUrl = announcement.adjunctUrl
          ? `https://static.cninfo.com.cn/${String(announcement.adjunctUrl).replace(/^\//, "")}`
          : `https://www.cninfo.com.cn/new/disclosure/stock?stockCode=${target.stock_code.split(".")[0]}`;
        const eventKey = await sha256(`event:${publishedAt.slice(0, 10)}:${title.replace(/[^\p{L}\p{N}]/gu, "")}`);
        const primarySourceCode = target.target_role === "customer" ? "customer_official" : "supply_competitor_official";
        const primaryCategory = target.target_role === "customer" ? "demand" : "supply_chain";
        const primaryName = target.target_role === "customer" ? "下游客户公告与官网" : "竞争对手侧验证";
        const writes: Array<{ sourceCode: string; sourceName: string; category: string }> = [{
          sourceCode: primarySourceCode, sourceName: primaryName, category: primaryCategory,
        }];
        if (target.target_role === "customer" && relationshipKeywords.some((keyword) => title.includes(keyword))) {
          writes.push({ sourceCode: "supply_customer_official", sourceName: "客户侧供应链确认", category: "supply_chain" });
        }
        for (const write of writes) {
          const dedupeKey = await sha256(`${write.sourceCode}:${announcement.announcementId || sourceUrl}`);
          const { data: existing, error: lookupError } = await client.from("raw_clues")
            .select("id").eq("dedupe_key", dedupeKey).maybeSingle();
          if (lookupError) throw lookupError;
          if (existing) { result.dedupedCount += 1; continue; }
          const polarity = classifyPolarity(title);
          const { error: insertError } = await client.from("raw_clues").insert({
            occurred_on: publishedAt.slice(0, 10), published_at: publishedAt, available_at: publishedAt,
            sector_id: target.sector_id, source_type: "重点对象法定披露", source_name: write.sourceName,
            source_url: sourceUrl, source_code: write.sourceCode, source_category: write.category,
            source_grade: "S", title, original_title: title, raw_text: title,
            summary: `${target.entity_name}发布“${title}”。这是${target.target_role === "customer" ? "需求/客户侧" : "竞争对手侧"}原始证据，仍需核对正文后判断影响。`,
            clue_type: write.category === "demand" ? "客户CAPEX/采购" : "供应链验证",
            novelty_score: 7, reliability_score: 9, is_duplicate: false, screening_status: "watch",
            verification_needed: "核对公告正文的金额、数量、供应商、项目时间和取消条件。",
            company_names: [target.entity_name], opportunity_keywords: [], evidence_level: "S",
            sentiment: polarity, positive_negative_neutral: polarity, dedupe_key: dedupeKey,
            underlying_event_id: eventKey, historical_availability: "A",
            availability_risk: "法定披露入口稳定；严格历史验证仍受当时重点对象名单影响。",
            metadata: { collector: "v43-daily-pipeline", version: "V4.4.2", target_role: target.target_role, target_id: target.id, announcement_id: announcement.announcementId || null },
          });
          if (insertError) throw insertError;
          result.rawInsertedCount += 1;
          roleStats.inserted += 1;
          if (write.sourceCode === "supply_customer_official") stats.customerSupply.inserted += 1;
        }
      }
      await sleep(100);
    } catch (error) {
      const message = errorMessage(error);
      result.failedCompanies += 1;
      roleStats.failed += 1;
      if (target.target_role === "customer") stats.customerSupply.failed += 1;
      result.errors.push({ company: target.entity_name, error: message });
    }
  }
  const healthRows = [
    { code: "customer_official", name: "下游客户公告与官网", category: "demand", value: stats.customer },
    { code: "supply_customer_official", name: "客户侧供应链确认", category: "supply_chain", value: stats.customerSupply },
    { code: "supply_competitor_official", name: "竞争对手侧验证", category: "supply_chain", value: stats.competitor },
  ];
  for (const row of healthRows) {
    const status = row.value.succeeded === 0 ? "failed" : row.value.failed > 0 ? "degraded" : row.value.inserted > 0 ? "healthy" : "healthy_no_new_data";
    await updateSourceHealth(client, row.code, row.name, row.category, status,
      status === "failed" ? "全部重点对象访问失败或名单为空。" : row.value.failed ? `${row.value.failed}个重点对象访问失败。` : null,
      { fetched_count: row.value.fetched, raw_inserted_count: row.value.inserted, successful_targets: row.value.succeeded, failed_targets: row.value.failed,
        message: row.value.inserted ? `真实检查重点对象并新增${row.value.inserted}条。` : "已真实检查重点对象，0条新增；不等于没有变化。" });
    if (status === "failed") result.failedSources += 1; else result.successfulSources += 1;
    result.sourceDetails?.push({ sourceCode: row.code, status, fetchedCount: row.value.fetched, rawInsertedCount: row.value.inserted, validSignalCount: 0, message: row.value.inserted ? `新增${row.value.inserted}条` : "0条新增" });
  }
  result.sourceStatus = result.failedSources === 0 ? "healthy" : result.successfulSources > 0 ? "degraded" : "failed";
  return result;
}

function decodeHtml(value = "") {
  return value
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ")
    .trim();
}

function stripHtml(value = "") {
  return decodeHtml(
    value
      .replace(/<script[\s\S]*?<\/script>/gi, " ")
      .replace(/<style[\s\S]*?<\/style>/gi, " ")
      .replace(/<[^>]+>/g, " "),
  ).slice(0, 12000);
}

async function fetchText(url: string, timeoutMs = 15000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      headers: {
        "user-agent": "Mozilla/5.0 three-sector-research/4.4.1",
        "accept": "text/html,application/json;q=0.9,*/*;q=0.8",
      },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`来源返回 ${response.status}`);
    return await response.text();
  } finally {
    clearTimeout(timeout);
  }
}

function matchedSectors(text: string) {
  const normalized = text
    .replace(/电信、?广播电视及卫星传输服务/g, "")
    .replace(/广播电视和卫星传输服务/g, "")
    .toUpperCase();
  return Object.entries(sectorKeywords)
    .filter(([, keywords]) =>
      keywords.some((keyword) => {
        if (keyword !== "AI") return normalized.includes(keyword.toUpperCase());
        return /(^|[^A-Z])AI([^A-Z]|$)/.test(normalized);
      })
    )
    .map(([sector]) => sector);
}

function classifyPolarity(text: string) {
  if (negativeKeywords.some((keyword) => text.includes(keyword))) return "negative";
  if (positiveKeywords.some((keyword) => text.includes(keyword))) return "positive";
  return "neutral";
}

function classifyRelevantPolarity(text: string, sectorNames: string[]) {
  const contexts: string[] = [];
  for (const sectorName of sectorNames) {
    for (const keyword of sectorKeywords[sectorName] || []) {
      if (keyword === "AI") continue;
      let from = 0;
      while (from < text.length) {
        const index = text.indexOf(keyword, from);
        if (index < 0) break;
        contexts.push(text.slice(Math.max(0, index - 120), index + keyword.length + 160));
        from = index + keyword.length;
      }
    }
  }
  const relevantText = contexts.join(" ");
  if (relevantText && negativeKeywords.some((keyword) => relevantText.includes(keyword))) return "negative";
  if (relevantText && positiveKeywords.some((keyword) => relevantText.includes(keyword))) return "positive";
  return "neutral";
}

function isExternalRealChange(record: ExternalRecord, text: string) {
  if (record.sourceCategory === "negative_counterevidence") {
    return ["终止", "废标", "流标", "取消", "延期", "下降", "下修", "处罚", "替代"]
      .some((keyword) => text.includes(keyword));
  }
  if (record.sourceCategory === "supply_chain") {
    return ["客户", "供应商", "供货", "采购", "订单", "扩产", "降价", "替代"]
      .some((keyword) => text.includes(keyword));
  }
  if (record.sourceCategory === "demand") {
    return ["招标", "中标", "采购", "扩产", "设备", "服务器", "卫星", "机器人"]
      .some((keyword) => text.includes(keyword));
  }
  if (record.sourceCategory === "policy") {
    return ["通知", "意见", "规划", "行动", "标准", "补贴", "监管", "试点", "示范"]
      .some((keyword) => text.includes(keyword));
  }
  return ["增长", "下降", "产量", "出货", "投资", "价格", "增加值", "利润"]
    .some((keyword) => text.includes(keyword));
}

async function fetchGovernmentPolicies(): Promise<{ records: ExternalRecord[]; fetched: number }> {
  const sourceUrl = "https://www.gov.cn/zhengce/zuixin/ZUIXINZHENGCE.json";
  const payload = JSON.parse(await fetchText(sourceUrl));
  if (!Array.isArray(payload)) throw new Error("政策列表格式无法识别");
  const rows = payload.slice(0, 80);
  return {
    fetched: rows.length,
    records: rows.map((item: any) => ({
      sourceCode: "gov_policy",
      sourceName: "中国政府网最新政策",
      sourceCategory: "policy" as const,
      sourceType: "政府正式文件",
      sourceGrade: "S" as const,
      title: cleanTitle(item.TITLE || ""),
      sourceUrl: String(item.URL || "https://www.gov.cn/zhengce/zuixin/"),
      publishedAt: `${String(item.DOCRELPUBTIME || "").slice(0, 10)}T08:00:00.000+08:00`,
      rawText: cleanTitle(item.TITLE || ""),
    })),
  };
}

async function fetchGovernmentProcurement(): Promise<{ records: ExternalRecord[]; fetched: number }> {
  const base = "https://www.ccgp.gov.cn/cggg/zygg/gkzb/";
  const html = await fetchText(base);
  const records: ExternalRecord[] = [];
  const pattern = /<a\s+href="([^"]+)"[^>]*title="([^"]+)"[\s\S]{0,500}?发布时间：<em>([^<]+)<\/em>/gi;
  for (const match of html.matchAll(pattern)) {
    const title = decodeHtml(match[2]);
    if (!title) continue;
    records.push({
      sourceCode: "ccgp_procurement",
      sourceName: "中国政府采购网",
      sourceCategory: "demand",
      sourceType: "政府采购",
      sourceGrade: "A",
      title,
      sourceUrl: new URL(match[1], base).toString(),
      publishedAt: `${match[3].trim().replace(" ", "T")}:00+08:00`,
      rawText: title,
    });
  }
  if (!records.length) throw new Error("采购公告页面可访问，但没有解析到公告列表");
  return { records, fetched: records.length };
}

async function fetchProcurementNegative(): Promise<{ records: ExternalRecord[]; fetched: number }> {
  const base = "https://www.ccgp.gov.cn/cggg/zygg/fblbgg/";
  const html = await fetchText(base);
  const records: ExternalRecord[] = [];
  const pattern = /<a\s+href="([^"]+)"[^>]*title="([^"]+)"[\s\S]{0,500}?发布时间：<em>([^<]+)<\/em>/gi;
  for (const match of html.matchAll(pattern)) {
    const title = decodeHtml(match[2]);
    if (!title) continue;
    records.push({
      sourceCode: "procurement_negative",
      sourceName: "采购取消、流标与延期",
      sourceCategory: "negative_counterevidence",
      sourceType: "公共采购反证",
      sourceGrade: "A",
      title,
      sourceUrl: new URL(match[1], base).toString(),
      publishedAt: `${match[3].trim().replace(" ", "T")}:00+08:00`,
      rawText: title,
    });
  }
  if (!records.length) throw new Error("废标终止公告页面可访问，但没有解析到公告列表");
  return { records, fetched: records.length };
}

async function fetchIndustryStatistics(): Promise<{ records: ExternalRecord[]; fetched: number }> {
  const base = "https://www.stats.gov.cn/sj/zxfb/";
  const html = await fetchText(base, 20000);
  const candidates: Array<{ title: string; url: string; publishedAt: string }> = [];
  const seen = new Set<string>();
  const pattern = /<a[^>]+href="([^"]+)"[^>]+title=['"]([^'"]+)['"][^>]*>/gi;
  for (const match of html.matchAll(pattern)) {
    const url = new URL(match[1], base).toString();
    if (!/\/t\d{8}_\d+\.html/.test(url) || seen.has(url)) continue;
    seen.add(url);
    const dateMatch = url.match(/\/t(\d{4})(\d{2})(\d{2})_/);
    if (!dateMatch) continue;
    candidates.push({
      title: decodeHtml(match[2]),
      url,
      publishedAt: `${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}T08:00:00.000+08:00`,
    });
    if (candidates.length >= 12) break;
  }
  if (!candidates.length) throw new Error("统计发布页面可访问，但没有解析到发布记录");
  const records = await Promise.all(candidates.map(async (item, index) => {
    let rawText = item.title;
    if (index < 6) {
      try {
        const detailHtml = await fetchText(item.url, 10000);
        const article = detailHtml.match(/<div class="detail-text-content mhide">([\s\S]*?)<div class="detail-text-xgfj/i)?.[1];
        rawText = stripHtml(article || detailHtml);
      } catch {
        rawText = item.title;
      }
    }
    return {
      sourceCode: "nbs_industry",
      sourceName: "国家统计局数据发布",
      sourceCategory: "industry" as const,
      sourceType: "官方产业统计",
      sourceGrade: "A" as const,
      title: item.title,
      sourceUrl: item.url,
      publishedAt: item.publishedAt,
      rawText,
    };
  }));
  return { records, fetched: candidates.length };
}

async function fetchIndustryDemandStatistics(): Promise<{ records: ExternalRecord[]; fetched: number }> {
  const payload = await fetchIndustryStatistics();
  const demandTerms = ["产量", "销量", "出货", "装机", "投资", "采购", "资本开支", "建设"];
  return {
    fetched: payload.fetched,
    records: payload.records
      .filter((record) => demandTerms.some((term) => `${record.title} ${record.rawText}`.includes(term)))
      .map((record) => ({
        ...record,
        sourceCode: "industry_demand_statistics",
        sourceName: "行业出货、装机与投资统计",
        sourceCategory: "demand" as const,
        sourceType: "官方行业需求统计",
      })),
  };
}

async function collectExpandedSources(
  client: ReturnType<typeof createClient>,
  sectors: Array<{ id: string; name: string }>,
): Promise<SignalCollectionResult> {
  const result: SignalCollectionResult = {
    attemptedSources: 5,
    successfulSources: 0,
    failedSources: 0,
    attemptedCompanies: 0,
    successfulCompanies: 0,
    failedCompanies: 0,
    fetchedCount: 0,
    dedupedCount: 0,
    rawInsertedCount: 0,
    validSignalCount: 0,
    errors: [],
    sourceStatus: "failed",
    sourceDetails: [],
  };
  const loaders = [
    { code: "gov_policy", name: "中国政府网最新政策", category: "policy", load: fetchGovernmentPolicies },
    { code: "ccgp_procurement", name: "中国政府采购网", category: "demand", load: fetchGovernmentProcurement },
    { code: "nbs_industry", name: "国家统计局数据发布", category: "industry", load: fetchIndustryStatistics },
    { code: "industry_demand_statistics", name: "行业出货、装机与投资统计", category: "demand", load: fetchIndustryDemandStatistics },
    { code: "procurement_negative", name: "采购取消、流标与延期", category: "negative_counterevidence", load: fetchProcurementNegative },
  ];
  const sectorIds = new Map(sectors.map((sector) => [sector.name, sector.id]));
  for (const source of loaders) {
    let fetched = 0;
    let inserted = 0;
    let signals = 0;
    let deduped = 0;
    try {
      const payload = await source.load();
      fetched = payload.fetched;
      result.fetchedCount += fetched;
      for (const record of payload.records) {
        const sectorNames = matchedSectors(`${record.title} ${record.rawText}`);
        if (!sectorNames.length) continue;
        const sectorName = sectorNames[0];
        const publishedAt = new Date(record.publishedAt).toISOString();
        const dedupeKey = await sha256(`${record.sourceCode}:${record.sourceUrl}`);
        const eventKey = await sha256(
          `event:${publishedAt.slice(0, 10)}:${record.title.replace(/[^\p{L}\p{N}]/gu, "")}`,
        );
        const { data: existing, error: lookupError } = await client
          .from("raw_clues").select("id").eq("dedupe_key", dedupeKey).maybeSingle();
        if (lookupError) throw lookupError;
        if (existing) {
          deduped += 1;
          result.dedupedCount += 1;
          continue;
        }
        const polarity = record.sourceCategory === "negative_counterevidence"
          ? "negative"
          : record.sourceCategory === "industry"
          ? classifyRelevantPolarity(`${record.title} ${record.rawText}`, sectorNames)
          : classifyPolarity(`${record.title} ${record.rawText}`);
        const realChange = isExternalRealChange(record, `${record.title} ${record.rawText}`);
        const summary = realChange
          ? `${record.sourceName}发布“${record.title}”，已识别为与${sectorName}有关的${record.sourceType}变化，仍需核对原文中的数量、金额和影响范围。`
          : `${record.sourceName}发布“${record.title}”，与${sectorName}有关，但目前只作为待验证线索。`;
        const { data: raw, error: rawError } = await client.from("raw_clues").insert({
          occurred_on: publishedAt.slice(0, 10),
          published_at: publishedAt,
          available_at: publishedAt,
          sector_id: sectorIds.get(sectorName),
          source_type: record.sourceType,
          source_name: record.sourceName,
          source_url: record.sourceUrl,
          source_code: record.sourceCode,
          source_category: record.sourceCategory,
          source_grade: record.sourceGrade,
          title: record.title,
          original_title: record.title,
          summary,
          raw_text: record.rawText.slice(0, 12000),
          clue_type: record.sourceCategory === "demand" ? "真实采购" : record.sourceCategory === "policy" ? "政策变化" : record.sourceCategory === "negative_counterevidence" ? "负面反证" : record.sourceCategory === "supply_chain" ? "供应链变化" : "产业数据",
          novelty_score: realChange ? 8 : 5,
          reliability_score: record.sourceGrade === "S" ? 10 : 9,
          is_duplicate: false,
          screening_status: realChange ? "high_value" : "watch",
          rejection_reason: realChange ? null : "来源可靠，但当前内容还不足以证明形成了可进入机会判断的真实变化。",
          verification_needed: "核对原文中的数量、金额、时间范围、执行主体和负面条件。",
          company_names: [],
          opportunity_keywords: Array.from(new Set(Object.values(sectorKeywords).flat().filter((k) => `${record.title} ${record.rawText}`.toUpperCase().includes(k.toUpperCase())))),
          evidence_level: record.sourceGrade,
          sentiment: polarity,
          positive_negative_neutral: polarity,
          dedupe_key: dedupeKey,
          underlying_event_id: eventKey,
          historical_availability: "A",
          availability_risk: "官方公开入口稳定，系统实际采集时间已记录。",
          metadata: {
            collector: "v43-daily-pipeline",
            version: "V4.4.2",
            source_code: record.sourceCode,
            sectors: sectorNames,
            is_real_change: realChange,
            polarity,
          },
        }).select("id,discovered_at").single();
        if (rawError) throw rawError;
        inserted += 1;
        result.rawInsertedCount += 1;
        if (!realChange) continue;
        const sourceId = `AUTO-${record.sourceCode.toUpperCase()}-${dedupeKey.slice(0, 20)}`;
        const { error: docError } = await client.from("source_documents").upsert({
          source_id: sourceId,
          source_date: publishedAt.slice(0, 10),
          source_grade: record.sourceGrade,
          title: record.title,
          source_url: record.sourceUrl,
          supports: summary,
          notes: "自动采集到原始层并去重后，才进入变化发现；不代表机会已经成立。",
        }, { onConflict: "source_id", ignoreDuplicates: true });
        if (docError) throw docError;
        const { error: signalError } = await client.from("signals").insert({
          sector_id: sectorIds.get(sectorName),
          raw_clue_id: raw.id,
          signal_date: publishedAt.slice(0, 10),
          title: record.title,
          change_description: summary,
          transmission_logic: record.sourceCategory === "demand"
            ? "先验证采购主体和数量，再判断需求能否传导到具体公司。"
            : record.sourceCategory === "policy"
            ? "政策只证明方向变化，仍需需求、产业或公司证据交叉验证。"
            : record.sourceCategory === "negative_counterevidence"
            ? "负面记录用于主动破坏原假设；没有命中不能解释为没有风险。"
            : record.sourceCategory === "supply_chain"
            ? "必须同时核对供应商、客户和竞争对手，重复事件只算一次。"
            : "行业数据只证明产业变化，仍需公司映射和利润传导验证。",
          affected_chain: sectorName,
          duration_hypothesis: "待后续数据连续性验证",
          score: polarity === "negative" ? 8 : 7,
          status: "pending",
          verification_needed: "至少寻找另一类独立来源进行交叉验证。",
          external_id: `AUTO-SIGNAL-${dedupeKey.slice(0, 20)}`,
          signal_type: record.sourceCategory === "demand" ? "需求验证" : record.sourceCategory === "policy" ? "政策变化" : record.sourceCategory === "negative_counterevidence" ? "负面反证" : record.sourceCategory === "supply_chain" ? "供应链验证" : "产业变化",
          source_url: record.sourceUrl,
          source_grade: record.sourceGrade,
          source_code: record.sourceCode,
          source_name: record.sourceName,
          source_category: record.sourceCategory,
          published_at: publishedAt,
          discovered_at: raw.discovered_at,
          historical_availability: "A",
          availability_risk: "官方公开入口稳定，系统实际采集时间已记录。",
          original_title: record.title,
          underlying_event_id: eventKey,
          positive_negative_neutral: polarity,
          is_official: true,
          consensus_level: "待验证",
          traded_status: "待判断",
          action: "进入机会确认",
          metadata: {
            source_document_id: sourceId,
            direction: polarity,
            fact_class: record.sourceType,
            dedupe_key: dedupeKey,
          },
        });
        if (signalError && signalError.code !== "23505") throw signalError;
        signals += 1;
        result.validSignalCount += 1;
      }
      result.successfulSources += 1;
      const status = inserted === 0 ? "healthy_no_new_data" : "healthy";
      const message = inserted === 0
        ? `成功检查，取回${fetched}条，三大赛道本次0条新增。`
        : `成功检查，取回${fetched}条，新写入${inserted}条，形成有效信号${signals}条。`;
      await updateSourceHealth(client, source.code, source.name, source.category, status, null, {
        fetched_count: fetched,
        deduped_count: deduped,
        raw_inserted_count: inserted,
        valid_signal_count: signals,
        message,
      });
      result.sourceDetails?.push({
        sourceCode: source.code, status, fetchedCount: fetched,
        rawInsertedCount: inserted, validSignalCount: signals, message,
      });
    } catch (error) {
      result.failedSources += 1;
      const message = errorMessage(error);
      result.errors.push({ company: source.name, error: message });
      await updateSourceHealth(client, source.code, source.name, source.category, "failed", message, {
        fetched_count: fetched,
        raw_inserted_count: inserted,
        valid_signal_count: signals,
        message: `抓取失败：${message}`,
      });
      result.sourceDetails?.push({
        sourceCode: source.code, status: "failed", fetchedCount: fetched,
        rawInsertedCount: inserted, validSignalCount: signals, message,
      });
    }
  }
  result.sourceStatus = result.failedSources === 0
    ? "healthy"
    : result.successfulSources > 0 ? "degraded" : "failed";
  return result;
}

function mergeSignalResults(...items: SignalCollectionResult[]): SignalCollectionResult {
  const merged: SignalCollectionResult = {
    attemptedSources: 0, successfulSources: 0, failedSources: 0,
    attemptedCompanies: 0, successfulCompanies: 0, failedCompanies: 0,
    fetchedCount: 0, dedupedCount: 0, rawInsertedCount: 0, validSignalCount: 0,
    errors: [], sourceStatus: "failed", sourceDetails: [],
  };
  for (const item of items) {
    merged.attemptedSources += item.attemptedSources;
    merged.successfulSources += item.successfulSources;
    merged.failedSources += item.failedSources;
    merged.attemptedCompanies += item.attemptedCompanies;
    merged.successfulCompanies += item.successfulCompanies;
    merged.failedCompanies += item.failedCompanies;
    merged.fetchedCount += item.fetchedCount;
    merged.dedupedCount += item.dedupedCount;
    merged.rawInsertedCount += item.rawInsertedCount;
    merged.validSignalCount += item.validSignalCount;
    merged.errors.push(...item.errors);
    merged.sourceDetails?.push(...(item.sourceDetails || []));
  }
  merged.sourceStatus = merged.failedSources === 0
    ? "healthy"
    : merged.successfulSources > 0 ? "degraded" : "failed";
  return merged;
}

async function writeSourceCoverage(
  client: ReturnType<typeof createClient>,
  runId: string,
  runDate: string,
  sectors: Array<{ id: string; name: string }>,
) {
  const categories = [
    "company", "policy", "demand", "industry", "supply_chain", "market", "negative_counterevidence",
  ];
  const {start_at:dayStart,end_at:dayEnd} = windowFor(runDate);
  const [{ data: registry, error: registryError }, { data: health, error: healthError }, { data: raw, error: rawError }, { data: signals, error: signalError }] = await Promise.all([
    client.from("source_registry").select("source_code,source_category,sector_scope,automation_enabled,operational_status,historical_strict_available"),
    client.from("source_health").select("source_code,status,last_checked_at"),
    client.from("raw_clues").select("sector_id,source_code,source_category,sentiment,screening_status").gte("discovered_at", dayStart).lt("discovered_at", dayEnd),
    client.from("signals").select("sector_id,source_category,status").gte("discovered_at", dayStart).lt("discovered_at", dayEnd),
  ]);
  if (registryError || healthError || rawError || signalError) {
    throw registryError || healthError || rawError || signalError;
  }
  const healthByCode = new Map((health || []).map((item: any) => [item.source_code, item]));
  const rows = sectors.flatMap((sector) => categories.map((category) => {
    const registered = (registry || []).filter((item: any) =>
      item.source_category === category && (item.sector_scope || []).includes(sector.name)
    );
    const automated = registered.filter((item: any) => item.automation_enabled);
    const automatedActive = registered.filter((item: any) => item.operational_status === "automated_active");
    const manualAvailable = registered.filter((item: any) => item.operational_status === "manual_available");
    const unconfigured = registered.filter((item: any) => item.operational_status === "registered_unconfigured");
    const historicalStrict = registered.filter((item: any) => item.historical_strict_available);
    const attempted = automated.filter((item: any) => {
      const itemHealth = healthByCode.get(item.source_code) as any;
      return itemHealth?.last_checked_at?.slice(0, 10) === runDate;
    });
    const healthy = attempted.filter((item: any) => {
      const status = (healthByCode.get(item.source_code) as any)?.status;
      return ["healthy", "healthy_no_new_data", "healthy_no_new_trade"].includes(status);
    });
    const rawCount = (raw || []).filter((item: any) =>
      item.sector_id === sector.id && item.source_category === category && item.screening_status !== "rejected"
    ).length;
    const signalCount = (signals || []).filter((item: any) =>
      item.sector_id === sector.id && item.source_category === category && item.status !== "invalid"
    ).length;
    const negativeCount = (raw || []).filter((item: any) =>
      item.sector_id === sector.id && item.source_category === category && item.screening_status !== "rejected" && item.sentiment === "negative"
    ).length;
    const registeredCodes = new Set(registered.map((item: any) => item.source_code));
    const effectiveSourceCount = new Set((raw || []).filter((item: any) =>
      item.sector_id === sector.id && item.source_category === category && item.screening_status !== "rejected" && item.source_code && registeredCodes.has(item.source_code)
    ).map((item: any) => item.source_code)).size;
    const integrationRate = registered.length
      ? Math.round((automatedActive.length / registered.length) * 100)
      : 0;
    const collectionSuccessRate = attempted.length ? Math.round((healthy.length / attempted.length) * 100) : 0;
    const effectiveCoverageRate = attempted.length ? Math.round((effectiveSourceCount / attempted.length) * 100) : 0;
    const historicalStrictRate = registered.length ? Math.round((historicalStrict.length / registered.length) * 100) : 0;
    const status = healthy.length === 0 ? "missing" : rawCount > 0 ? "covered" : "partial";
    return {
      coverage_date: runDate,
      sector_id: sector.id,
      source_category: category,
      registered_source_count: registered.length,
      automated_source_count: automated.length,
      manual_available_source_count: manualAvailable.length,
      unconfigured_source_count: unconfigured.length,
      attempted_source_count: attempted.length,
      healthy_source_count: healthy.length,
      planned_source_count: automated.length,
      successful_source_count: healthy.length,
      effective_source_count: effectiveSourceCount,
      historical_strict_source_count: historicalStrict.length,
      raw_record_count: rawCount,
      signal_count: signalCount,
      negative_record_count: negativeCount,
      coverage_pct: effectiveCoverageRate,
      integration_rate_pct: integrationRate,
      collection_success_rate_pct: collectionSuccessRate,
      effective_data_coverage_pct: effectiveCoverageRate,
      historical_strict_availability_pct: historicalStrictRate,
      coverage_status: status,
      notes: status === "covered"
        ? `已成功检查并取得真实记录；接入率${integrationRate}%，采集成功率${collectionSuccessRate}%，有效数据覆盖率${effectiveCoverageRate}%。`
        : status === "partial"
        ? `来源已成功检查但今天没有该赛道新增；接入率${integrationRate}%，不能解释成产业没有变化。`
        : automated.length
        ? "自动来源未成功检查，当前覆盖不足。"
        : "这一层尚未配置自动来源。",
      automation_run_id: runId,
    };
  }));
  const { error } = await client.from("source_category_coverage_daily").upsert(rows, {
    onConflict: "coverage_date,sector_id,source_category",
  });
  if (error) throw error;
  return rows;
}

function eastmoneyId(stockCode: string) {
  const code = stockCode.split(".")[0];
  const market = stockCode.endsWith(".SH") ? "1" : "0";
  return `${market}.${code}`;
}

async function fetchQuote(stockCode: string): Promise<Quote> {
  const secid = eastmoneyId(stockCode);
  const sourceUrl = `https://push2.eastmoney.com/api/qt/stock/get?secid=${secid}&fields=f43,f57,f58,f84,f86,f116`;
  let lastError = "行情接口没有返回";
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await fetch(sourceUrl, {
        headers: { "user-agent": "Mozilla/5.0 research-data-check/1.0" },
      });
      if (!response.ok) throw new Error(`行情接口返回 ${response.status}`);
      const payload = await response.json();
      const data = payload?.data;
      if (!data || !data.f43 || !data.f84 || !data.f116 || !data.f86) {
        throw new Error("行情接口缺少价格、股本、市值或交易时间");
      }
      const tradeDate = new Date(Number(data.f86) * 1000).toISOString().slice(0, 10);
      return {
        code: data.f57,
        name: data.f58,
        tradeDate,
        closePrice: Number(data.f43) / 100,
        sharesOutstanding: Number(data.f84) / 100000000,
        marketCap: Number(data.f116) / 100000000,
        sourceUrl,
      };
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
      if (attempt < 3) await sleep(attempt * 400);
    }
  }
  throw new Error(`${lastError}；重试3次仍失败`);
}


async function threeSectorJob(client: any, run: any, runDate: string) {
    const { data: companies, error: companyError } = await client
      .from("companies")
      .select("id,name,stock_code,company_role,sector_id")
      .eq("company_role", "investable_candidate")
      .not("stock_code", "is", null);
    if (companyError) throw companyError;
    const { data: sectors, error: sectorError } = await client
      .from("sectors")
      .select("id,name");
    if (sectorError) throw sectorError;
    const sectorNames = new Map((sectors || []).map((sector: { id: string; name: string }) => [sector.id, sector.name]));
    const eligibleCompanies = (companies || [])
      .filter((company: ResearchCompany) => /\.(SH|SZ)$/.test(company.stock_code))
      .map((company: ResearchCompany) => ({
        ...company,
        sectors: { name: company.sector_id ? sectorNames.get(company.sector_id) : "" },
      })) as ResearchCompany[];

    const companySignalResult = await collectOfficialSignals(client, eligibleCompanies, runDate);
    const expandedSignalResult = await collectExpandedSources(client, sectors || []);
    const watchTargetResult = await collectWatchTargetDisclosures(client, runDate, sectors || []);
    const signalResult = mergeSignalResults(companySignalResult, expandedSignalResult, watchTargetResult);
    const signalSucceeded =
      signalResult.successfulSources === signalResult.attemptedSources &&
      signalResult.failedSources === 0;
    const aggregateStatus = signalSucceeded
      ? signalResult.rawInsertedCount > 0 ? "healthy" : "healthy_no_new_data"
      : signalResult.successfulSources > 0 ? "degraded" : "failed";
    await updateSourceHealth(
      client,
      "external_signal_sources",
      "外部研究信号来源",
      "signal",
      aggregateStatus,
      signalResult.errors.length ? JSON.stringify(signalResult.errors) : null,
      {
        aggregate: true,
        configured_sources: signalResult.attemptedSources,
        successful_sources: signalResult.successfulSources,
        failed_sources: signalResult.failedSources,
        fetched_count: signalResult.fetchedCount,
        deduped_count: signalResult.dedupedCount,
        raw_inserted_count: signalResult.rawInsertedCount,
        valid_signal_count: signalResult.validSignalCount,
        message: signalSucceeded
          ? "所有已配置来源均已真实尝试并记录健康状态。"
          : "至少一个已配置来源抓取失败，不能把0条结果当成没有新信息。",
      },
    );
    const { error: signalStepError } = await client.from("automation_run_steps").insert({
      run_id: run.id,
      step_code: "signal_collection",
      step_name: "更新信号",
      status: signalSucceeded ? "succeeded" : "failed",
      processed_count: signalResult.rawInsertedCount,
      message: signalSucceeded
        ? `已真实检查${signalResult.attemptedSources}个自动来源，取回${signalResult.fetchedCount}条，去重${signalResult.dedupedCount}条，新写入原始记录${signalResult.rawInsertedCount}条，形成有效信号${signalResult.validSignalCount}条。`
        : `已尝试${signalResult.attemptedSources}个自动来源，但有${signalResult.failedSources}个失败；不能标记为全部成功。`,
      metadata: signalResult,
    });
    if (signalStepError) throw signalStepError;

    let priceSuccess = 0;
    let priceFailed = 0;
    const priceErrors: Array<{ company: string; error: string }> = [];
    const priceWarnings: Array<{ company: string; warning: string }> = [];
    const runDay = new Date(`${runDate}T00:00:00Z`).getUTCDay();
    const isWeekend = runDay === 0 || runDay === 6;
    await Promise.all(eligibleCompanies.map(async (company) => {
      try {
        if (isWeekend) {
          const { data: cached, error: cachedError } = await client
            .from("price_snapshots")
            .select("trade_date")
            .eq("company_id", company.id)
            .order("trade_date", { ascending: false })
            .limit(1)
            .maybeSingle();
          if (cachedError || !cached?.trade_date) {
            throw cachedError || new Error("没有可沿用的最近交易日价格");
          }
          priceSuccess += 1;
          priceWarnings.push({ company: company.name, warning: `非交易日沿用最近交易日 ${cached.trade_date} 的已验证快照。` });
          return;
        }
        const quote = await fetchQuote(company.stock_code);
        const { data: existing } = await client
          .from("price_snapshots")
          .select("id")
          .eq("company_id", company.id)
          .eq("trade_date", quote.tradeDate)
          .eq("source_name", "东方财富实时行情接口")
          .maybeSingle();
        if (!existing) {
          const { error } = await client.from("price_snapshots").insert({
            company_id: company.id,
            trade_date: quote.tradeDate,
            close_price: quote.closePrice,
            shares_outstanding: quote.sharesOutstanding,
            market_cap: quote.marketCap,
            source_name: "东方财富实时行情接口",
            source_url: quote.sourceUrl,
            source_published_at: quote.tradeDate,
            evidence_grade: "B",
            metadata: { unit: "元/亿股/亿元", fetched_by: "v43-daily-pipeline", quote_name: quote.name },
          });
          if (error) throw error;
        }
        priceSuccess += 1;
      } catch (error) {
        priceFailed += 1;
        priceErrors.push({
          company: company.name,
          error: errorMessage(error),
        });
      }
    }));

    const priceStatus = priceFailed > 0
      ? priceSuccess > 0 ? "degraded" : "failed"
      : isWeekend ? "healthy_no_new_trade" : "healthy";
    await updateSourceHealth(
      client,
      "eastmoney_quote",
      "东方财富行情",
      "price",
      priceStatus,
      priceErrors.length ? JSON.stringify(priceErrors) : null,
      {
        success_count: priceSuccess,
        failed_count: priceFailed,
        fallback_count: priceWarnings.length,
        no_new_trade: isWeekend,
        message: isWeekend ? "非交易日，沿用最近交易日已验证快照，不视为故障。" : null,
      },
    );
    const coverageRows = await writeSourceCoverage(client, run.id, runDate, sectors || []);

    const { data: result, error: pipelineError } = await client.rpc(
      "complete_v43_daily_run",
      {
        p_run_id: run.id,
        p_run_date: runDate,
        p_price_success: priceSuccess,
        p_price_failed: priceFailed,
        p_price_errors: { errors: priceErrors, warnings: priceWarnings },
      },
    );
    if (pipelineError) throw pipelineError;

    return {status: result?.status || "failed", result, signal_collection:signalResult, price_success:priceSuccess, price_failed:priceFailed};
}
async function checked(query: any) {
  const {data,error}=await query;
  if(error) throw new Error(error.message);
  return data;
}
Deno.serve(async (request) => {
  if(request.method !== "POST") return json({error:"只接受POST请求"},405);
  const supabaseUrl=Deno.env.get("SUPABASE_URL");
  const serviceKey=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if(!supabaseUrl || !serviceKey) return json({error:"运行环境缺少数据库配置"},500);
  const client=createClient(supabaseUrl,serviceKey,{auth:{persistSession:false},global:{fetch}});
  const body=await request.json().catch(()=>({}));
  const runDate=typeof body.run_date==="string" ? body.run_date : businessDate();
  let window;
  try {window=windowFor(runDate);} catch(error) {return json({error:String(error)},400);}
  const triggerType=body.trigger_type==="scheduled" ? "scheduled" : "manual";
  let runId: string|null=null;
  const loggingErrors: any[]=[];
  let previousSuccessAt: string|null=null;
  const recordStep=async (row: any) => {
    try {await checked(client.from("automation_run_steps").insert(row));}
    catch(error) {loggingErrors.push({job:row.step_code,error:String(error)});}
  };
  try {
    await checked(client.rpc("close_stale_automation_runs",{p_timeout:"30 minutes"}));
    const existing=await checked(client.from("automation_runs").select("id,status").eq("job_code","daily_research_pipeline").eq("run_date",runDate).contains("metadata",{daily_pipeline_version:"17:00-v1"}).in("status",["running","succeeded"]).limit(1));
    if(existing.length) return json({status:"skipped",reason:"already_running_or_completed",pipeline_run_id:existing[0].id});
    const run=await checked(client.from("automation_runs").insert({job_code:"daily_research_pipeline",run_date:runDate,trigger_type:triggerType,status:"running",metadata:{daily_pipeline_version:"17:00-v1",...window}}).select("id").single());
    runId=run.id;
    const context={...window,pipeline_run_id:run.id};
    const jobs: any={};
    // Business modules never share a transaction. Failure is contained per job.
    jobs.mainline_job=await independently("mainline_job",async(signal)=>{
      let calendar: boolean|null=null;
      try {
        const status=await execution.run({...context,signal},()=>checked(client.rpc("get_mainline_status_v2")));
        previousSuccessAt=status?.daily_pipeline?.three_sector?.latest_success_at || null;
        if(status?.daily_pipeline?.trading_calendar?.business_date===runDate) calendar=status.daily_pipeline.trading_calendar.is_open;
      } catch(error) {
        return {...mainlineDecision(null),calendar_error:String(error),provider_status:"pending_provider"};
      }
      return {...mainlineDecision(calendar),provider_status:"pending_provider"};
    },10000);
    // Persist immediately; later three-sector failure cannot erase this result.
    await recordStep({run_id:run.id,step_code:"mainline_job",step_name:"A股主线每日任务（禁用占位）",status:jobs.mainline_job.status,started_at:jobs.mainline_job.started_at,finished_at:jobs.mainline_job.finished_at,message:jobs.mainline_job.reason || jobs.mainline_job.error,metadata:jobs.mainline_job});
    jobs.three_sector_daily_job=await independently("three_sector_daily_job",async(signal)=>execution.run({...context,signal},()=>threeSectorJob(client,run,runDate)),90000);
    const sector=jobs.three_sector_daily_job;
    await recordStep({run_id:run.id,step_code:"three_sector_daily_job",step_name:"三大赛道日终研究",status:sector.status==="succeeded" ? "succeeded" : "failed",started_at:sector.started_at,finished_at:sector.finished_at,message:sector.error || sector.status,metadata:{module_status:sector.status,result:sector.result,signal_collection:sector.signal_collection}});
    let successful_report: any=null;
    jobs.publish_job=await independently("publish_job",async(signal)=>execution.run({...context,signal},async()=>{
      if(sector.status!=="succeeded") return {status:"skipped",reason:"retain_previous_success"};
      const version=await checked(client.from("daily_report_versions").select("*").eq("report_date",runDate).eq("version_number",sector.result.report_version).single());
      const row=await checked(client.from("daily_reports").select("*").eq("id",version.report_id).single());
      successful_report={...row,frozen_snapshot:{...version.frozen_snapshot,report_definition:window.definition,information_window:window,pipeline_run_id:run.id},generated_at:version.generated_at,report_version:version.report_version};
      return {status:"succeeded",report_id:row.id,report_version_id:version.id,latest_success_at:version.generated_at};
    }),10000);
    await recordStep({run_id:run.id,step_code:"publish_job",step_name:"发布最近成功业务结果",status:jobs.publish_job.status,started_at:jobs.publish_job.started_at,finished_at:jobs.publish_job.finished_at,message:jobs.publish_job.reason || jobs.publish_job.error || "success",metadata:jobs.publish_job});
    let sourceHealth: any[]=[];
    try {sourceHealth=await checked(client.from("source_health").select("source_code,status,last_checked_at").gte("last_checked_at",window.start_at));} catch(error) {loggingErrors.push({job:"health_check",error:String(error)});}
    const error_summary=[...loggingErrors,...Object.values(jobs).filter((x:any)=>["failed","partial"].includes(x.status)).map((x:any)=>({job:x.name,error:x.error || x.result || x.status}))];
    const metadata={daily_pipeline_version:"17:00-v1",pipeline_run_id:run.id,...window,jobs,error_summary,source_health_summary:sourceHealth,latest_success_at:jobs.publish_job.latest_success_at || previousSuccessAt,...(successful_report ? {successful_report}:{})};
    const status=loggingErrors.length && overallStatus(Object.values(jobs))==="succeeded" ? "partial" : overallStatus(Object.values(jobs));
    const finished_at=new Date().toISOString();
    await checked(client.from("automation_runs").update({status,finished_at,metadata,error_message:error_summary.length?JSON.stringify(error_summary):null}).eq("id",run.id));
    await checked(client.from("automation_jobs").update({last_run_at:finished_at,last_status:status,...(status==="succeeded"?{last_success_at:finished_at}:{}),last_error:error_summary.length?JSON.stringify(error_summary):null,updated_at:finished_at}).eq("job_code","daily_research_pipeline"));
    return json({pipeline_run_id:run.id,status,...metadata});
  } catch(error) {
    const message=String(error?.message || error);
    if(runId) await client.from("automation_runs").update({status:"failed",finished_at:new Date().toISOString(),error_message:message}).eq("id",runId);
    return json({pipeline_run_id:runId,error:message},500);
  }
});
