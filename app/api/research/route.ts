import { NextResponse } from "next/server";

async function readTable(path: string) {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) throw new Error("Supabase runtime configuration is missing");
  const response = await fetch(`${url}/rest/v1/${path}`, {
    headers: { apikey: key, Authorization: `Bearer ${key}` },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Supabase request failed: ${response.status}`);
  return response.json();
}

export async function GET() {
  try {
    const [companyRows, signalRows, reportRows, opportunityRows, profitRows, valuationRows, sourceRows, snapshotRows, clueRows, sectorReviewRows, opportunityReviewRows, mappingRows, taskRows, parameterRows, probabilityRows, probabilityChangeRows, priceRows, expectedRows, reverseRows, sensitivityRows, validationRows, modelChangeRows, timelineRows, dailySnapshotRows] = await Promise.all([
      readTable("companies?select=id,external_code,stock_code,name,status,odds_note,profit_note,rank,score,market_cap,pool_reason,industry_chain_position,core_business,key_assumptions,listing_status,accounting_status,accounting_blocker,metadata,updated_at,sectors(name)&order=score.desc.nullslast"),
      readTable("signals?select=external_id,signal_date,title,change_description,signal_type,company_name,source_url,source_grade,score,status,verification_needed,action,previous_status,traded_status,metadata,sectors(name)&order=signal_date.desc,score.desc&limit=500"),
      readTable("daily_reports?select=*&order=report_date.desc&limit=30"),
      readTable("opportunities?select=*,sectors(name)&order=composite_score.desc.nullslast"),
      readTable("profit_models?select=*,companies(external_code,name)&order=fiscal_year.desc,scenario"),
      readTable("valuation_scenarios?select=*,companies(external_code,name)&order=valuation_date.desc"),
      readTable("source_documents?select=*&order=source_date.desc"),
      readTable("research_snapshots?select=*,companies(external_code,name)&order=snapshot_date.desc"),
      readTable("raw_clues?select=*,sectors(name)&order=occurred_on.desc,discovered_at.desc&limit=1000"),
      readTable("daily_sector_reviews?select=*,sectors(name)&order=report_date.desc"),
      readTable("daily_opportunity_reviews?select=*&order=report_date.desc"),
      readTable("opportunity_companies?select=*,companies(name,stock_code,accounting_status),opportunities(external_id,name,stage)&order=created_at"),
      readTable("research_tasks?select=*,companies(name,stock_code)&order=priority,status,created_at.desc"),
      readTable("model_parameters?select=*,profit_models(company_id,scenario,fiscal_year,model_type,companies(external_code,name))&order=parameter_name"),
      readTable("probability_assessments?select=*,companies(external_code,name)&superseded_at=is.null&order=effective_at.desc"),
      readTable("probability_changes?select=*,companies(external_code,name)&order=changed_at.desc&limit=500"),
      readTable("price_snapshots?select=*,companies(external_code,name)&order=trade_date.desc,captured_at.desc&limit=1000"),
      readTable("latest_expected_returns?select=*&order=expected_return.desc"),
      readTable("reverse_valuation_requirements?select=*&order=company_name,target_multiple,pe_multiple"),
      readTable("sensitivity_results?select=*,companies(external_code,name)&order=calculated_at.desc&limit=1000"),
      readTable("prediction_validations?select=*,companies(external_code,name)&order=first_qualified_at.desc"),
      readTable("model_change_log?select=*,companies(external_code,name)&order=changed_at.desc&limit=1000"),
      readTable("company_timeline_events?select=*,companies(external_code,name,stock_code)&order=event_at.desc&limit=1000"),
      readTable("company_daily_snapshots?select=*,companies(external_code,name,stock_code)&order=trade_date.desc,created_at.desc&limit=2000"),
    ]);
    const firms = companyRows.map((row: any) => ({
      id: row.id,
      code: row.external_code,
      stockCode: row.stock_code,
      name: row.name,
      track: row.sectors?.name || "待分类",
      stage: row.status,
      odds: row.odds_note || "待核算",
      profit: row.profit_note || "待核算",
      rank: row.rank || "B",
      score: Number(row.score || 0),
      marketCap: row.market_cap == null ? "待核算" : `${Number(row.market_cap)}亿`,
      reason: row.pool_reason || "待补充入池依据",
      chain: row.industry_chain_position || "待映射",
      coreBusiness: row.core_business || "待补充",
      keyAssumptions: row.key_assumptions || "待验证",
      listingStatus: row.listing_status,
      accountingStatus: row.accounting_status,
      accountingBlocker: row.accounting_blocker,
      metadata: row.metadata || {},
      updatedAt: row.updated_at,
    }));
    const sigs = signalRows.map((row: any) => ({
      id: row.external_id,
      date: row.signal_date,
      track: row.sectors?.name || "待分类",
      type: row.signal_type || "待分类",
      company: row.company_name || "待映射",
      title: row.title,
      score: (Number(row.score || 0) / 2).toFixed(1),
      state: row.action || row.status,
      source: row.source_url || "",
      change: row.change_description || "待补充变化说明",
      verify: row.verification_needed || "待补充验证节点",
      previousStatus: row.previous_status || "待补充",
      tradedStatus: row.traded_status || "待判断",
      metadata: row.metadata || {},
    }));
    const opportunities = opportunityRows.map((row: any) => ({ ...row, code: row.external_id, track: row.sectors?.name || "待分类", company: row.core_company || "待映射" }));
    const profitModels = profitRows.map((row: any) => ({ ...row, companyCode: row.companies?.external_code, companyName: row.companies?.name }));
    const valuations = valuationRows.map((row: any) => ({ ...row, companyCode: row.companies?.external_code, companyName: row.companies?.name }));
    const snapshots = snapshotRows.map((row: any) => ({ ...row, companyCode: row.companies?.external_code, companyName: row.companies?.name }));
    const rawClues = clueRows.map((row: any) => ({ ...row, track: row.sectors?.name || "待分类" }));
    const sectorReviews = sectorReviewRows.map((row: any) => ({ ...row, track: row.sectors?.name || "待分类" }));
    return NextResponse.json({ firms, sigs, reports: reportRows, opportunities, profitModels, valuations, sources: sourceRows, snapshots, rawClues, sectorReviews, opportunityReviews: opportunityReviewRows, opportunityCompanies: mappingRows, researchTasks: taskRows, modelParameters: parameterRows, probabilities: probabilityRows, probabilityChanges: probabilityChangeRows, prices: priceRows, expectedReturns: expectedRows, reverseValuations: reverseRows, sensitivities: sensitivityRows, predictionValidations: validationRows, modelChanges: modelChangeRows, timelineEvents: timelineRows, dailySnapshots: dailySnapshotRows, updatedAt: new Date().toISOString() });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "Unknown error" }, { status: 503 });
  }
}
