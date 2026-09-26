import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json; charset=utf-8" },
});

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function secid(stockCode: string) {
  const code = stockCode.split(".")[0];
  return `${stockCode.endsWith(".SH") ? "1" : "0"}.${code}`;
}

async function fetchQuote(stockCode: string) {
  const sourceUrl = `https://push2.eastmoney.com/api/qt/stock/get?secid=${secid(stockCode)}&fields=f43,f57,f58,f84,f86,f116`;
  let lastError = "行情接口没有返回";
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await fetch(sourceUrl, { headers: { "user-agent": "Mozilla/5.0 close-recalc/1.0" } });
      if (!response.ok) throw new Error(`行情接口返回 ${response.status}`);
      const data = (await response.json())?.data;
      if (!data?.f43 || !data?.f84 || !data?.f116 || !data?.f86) throw new Error("缺少价格、股本、市值或交易时间");
      return {
        tradeDate: new Date(Number(data.f86) * 1000).toISOString().slice(0, 10),
        closePrice: Number(data.f43) / 100,
        sharesOutstanding: Number(data.f84) / 100000000,
        marketCap: Number(data.f116) / 100000000,
        name: String(data.f58 || ""),
        sourceUrl,
      };
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
      if (attempt < 3) await sleep(attempt * 500);
    }
  }
  throw new Error(`${lastError}；重试3次仍失败`);
}

Deno.serve(async (request: Request) => {
  if (request.method !== "POST") return json({ error: "POST required" }, 405);
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceKey) return json({ error: "Supabase runtime configuration missing" }, 500);
  const client = createClient(supabaseUrl, serviceKey, { auth: { persistSession: false } });
  const body = await request.json().catch(() => ({}));
  const runDate = typeof body.run_date === "string" ? body.run_date : new Date().toISOString().slice(0, 10);
  const { data: companies, error } = await client.from("companies")
    .select("id,name,stock_code,sector_id,research_pool_status,company_role,listing_status")
    .eq("company_role", "investable_candidate")
    .eq("listing_status", "listed")
    .in("research_pool_status", ["research", "shadow", "high_expected_return"])
    .not("stock_code", "is", null);
  if (error) return json({ error: error.message }, 500);

  const results = await Promise.all((companies || []).map(async (company: any) => {
    try {
      const quote = await fetchQuote(company.stock_code);
      if (quote.tradeDate !== runDate) throw new Error(`来源最新交易日为${quote.tradeDate}，不是${runDate}，拒绝写成今日收盘价`);
      const { error: writeError } = await client.from("price_snapshots").upsert({
        company_id: company.id,
        trade_date: quote.tradeDate,
        close_price: quote.closePrice,
        shares_outstanding: quote.sharesOutstanding,
        market_cap: quote.marketCap,
        source_name: "东方财富实时行情接口",
        source_url: quote.sourceUrl,
        source_published_at: quote.tradeDate,
        evidence_grade: "B",
        metadata: { unit: "元/亿股/亿元", fetched_by: "v4-close-recalc", quote_name: quote.name, exact_trade_date_verified: true },
      }, { onConflict: "company_id,trade_date,source_name" });
      if (writeError) throw writeError;
      return { company: company.name, status: "updated", trade_date: quote.tradeDate, close_price: quote.closePrice, market_cap: quote.marketCap };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      const title = `${runDate} 收盘价待核实：${company.name}`;
      const { data: existing } = await client.from("research_tasks").select("id").eq("company_id", company.id).eq("title", title).maybeSingle();
      if (!existing) await client.from("research_tasks").insert({
        company_id: company.id, sector_id: company.sector_id, title,
        task_type: "price_verification", priority: "high", status: "pending", due_date: runDate,
        result: `自动行情未能核实当日收盘价：${message}。禁止沿用旧价冒充今日价格。`,
      });
      return { company: company.name, status: "failed", error: message };
    }
  }));
  return json({ run_date: runDate, updated: results.filter((r) => r.status === "updated").length, failed: results.filter((r) => r.status === "failed").length, results });
});
