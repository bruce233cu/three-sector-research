import { NextResponse } from "next/server";
import {readDailyPipeline, successfulReports} from "../../../lib/daily-result";

async function readTable(path: string) {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key)
    throw new Error("Supabase runtime configuration is missing");
  const response = await fetch(`${url}/rest/v1/${path}`, {
    headers: { apikey: key, Authorization: `Bearer ${key}` },
    cache: "no-store",
  });
  if (!response.ok)
    throw new Error(`Supabase request failed: ${response.status}`);
  return response.json();
}

export async function GET() {
  try {
    const dailyPipeline = await readDailyPipeline();
    const [
      companyRows,
      signalRows,
      reportRows,
      opportunityRows,
      profitRows,
      valuationRows,
      sourceRows,
      sourceRegistry,
      sourceHealth,
      sourceCoverageDaily,
      snapshotRows,
      clueRows,
      sectorReviewRows,
      opportunityReviewRows,
      mappingRows,
      taskRows,
      parameterRows,
      probabilityRows,
      probabilityChangeRows,
      priceRows,
      expectedRows,
      reverseRows,
      sensitivityRows,
      validationRows,
      modelChangeRows,
      timelineRows,
      dailySnapshotRows,
      thresholdRows,
      assessmentRows,
      transitionRows,
      validationEventRows,
      decisionRows,
      opportunitySignalRows,
      optimizationRows,
      expectedReturnCorrectionRows,
      opportunitySignalCorrectionRows,
      historicalRuns,
      historicalDays,
      historicalRawRecords,
      historicalAvailableRecords,
      historicalSignals,
      historicalOpportunities,
      historicalCompanies,
      historicalModels,
      historicalAssessments,
      historicalDecisions,
      historicalLeakChecks,
      historicalLeakCheckCorrections,
      historicalSourceCoverage,
      historicalSourceCategoryCoverage,
      historicalSearchLogs,
      sourceCategoryStatusSummary,
      sourceGaps,
      sourceWatchTargets,
      supplyChainEntities,
      supplyChainRelationships,
    ] = await Promise.all([
      readTable(
        "companies?select=id,external_code,stock_code,name,status,odds_note,profit_note,rank,score,market_cap,pool_reason,industry_chain_position,core_business,key_assumptions,listing_status,accounting_status,accounting_blocker,company_role,research_pool_status,valuation_status,investment_assessment_status,shadow_stage,shadow_reason,reactivation_condition,transition_reason,last_transition_at,last_validation_at,next_validation_at,metadata,updated_at,sectors(name)&order=score.desc.nullslast",
      ),
      readTable(
        "signals?select=id,external_id,signal_date,title,change_description,signal_type,company_name,source_url,source_grade,source_code,source_name,source_category,published_at,discovered_at,historical_availability,availability_risk,original_title,underlying_event_id,positive_negative_neutral,is_official,score,status,verification_needed,action,previous_status,traded_status,metadata,sectors(name)&order=signal_date.desc,score.desc&limit=500",
      ),
      readTable("daily_reports?select=*&order=report_date.desc&limit=30"),
      readTable(
        "opportunities?select=*,sectors(name)&order=composite_score.desc.nullslast",
      ),
      readTable(
        "profit_models?select=*,companies(external_code,name)&order=fiscal_year.desc,scenario",
      ),
      readTable(
        "valuation_scenarios?select=*,companies(external_code,name)&order=valuation_date.desc",
      ),
      readTable("source_documents?select=*&order=source_date.desc"),
      readTable("source_registry?select=*&order=source_category,priority,source_name"),
      readTable("source_health?select=*&order=source_name"),
      readTable("source_category_coverage_daily?select=*,sectors(name)&order=coverage_date.desc,source_category&limit=500"),
      readTable(
        "research_snapshots?select=*,companies(external_code,name)&order=snapshot_date.desc",
      ),
      readTable(
        "raw_clues?select=*,sectors(name)&order=occurred_on.desc,discovered_at.desc&limit=1000",
      ),
      readTable(
        "daily_sector_reviews?select=*,sectors(name)&order=report_date.desc",
      ),
      readTable("daily_opportunity_reviews?select=*&order=report_date.desc"),
      readTable(
        "opportunity_companies?select=*,companies(external_code,name,stock_code,accounting_status),opportunities(external_id,name,stage)&order=created_at",
      ),
      readTable(
        "research_tasks?select=*,companies(name,stock_code)&order=priority,status,created_at.desc",
      ),
      readTable(
        "model_parameters?select=*,profit_models(company_id,scenario,fiscal_year,model_type,companies(external_code,name))&order=parameter_name",
      ),
      readTable(
        "probability_assessments?select=*,companies(external_code,name)&superseded_at=is.null&order=effective_at.desc",
      ),
      readTable(
        "probability_changes?select=*,companies(external_code,name)&order=changed_at.desc&limit=500",
      ),
      readTable(
        "price_snapshots?select=*,companies(external_code,name)&order=trade_date.desc,captured_at.desc&limit=1000",
      ),
      readTable("latest_expected_returns?select=*&order=expected_return.desc"),
      readTable(
        "reverse_valuation_requirements?select=*&order=company_name,target_multiple,pe_multiple",
      ),
      readTable(
        "sensitivity_results?select=*,companies(external_code,name)&order=calculated_at.desc&limit=1000",
      ),
      readTable(
        "prediction_validations?select=*,companies(external_code,name)&order=first_qualified_at.desc",
      ),
      readTable(
        "model_change_log?select=*,companies(external_code,name)&order=changed_at.desc&limit=1000",
      ),
      readTable(
        "company_timeline_events?select=*,companies(external_code,name,stock_code)&order=event_at.desc&limit=1000",
      ),
      readTable(
        "company_daily_snapshots?select=*,companies(external_code,name,stock_code)&order=trade_date.desc,created_at.desc&limit=2000",
      ),
      readTable(
        "investment_thresholds?select=*&is_active=eq.true&order=effective_from.desc",
      ),
      readTable(
        "investment_assessments?select=*,companies(external_code,name,stock_code)&order=assessed_at.desc",
      ),
      readTable(
        "company_state_transitions?select=*,companies(external_code,name,stock_code)&order=created_at.desc&limit=2000",
      ),
      readTable(
        "company_validation_events?select=*,companies(external_code,name,stock_code)&order=validation_date.desc,created_at.desc&limit=2000",
      ),
      readTable(
        "screening_decisions?select=*&order=evaluated_at.desc&limit=3000",
      ),
      readTable(
        "active_opportunity_signal_links?select=*,signals(external_id,title),opportunities(external_id,name)&order=linked_at",
      ),
      readTable(
        "system_optimization_records?select=*&order=record_date.desc,created_at.desc",
      ),
      readTable("expected_return_corrections?select=*&order=corrected_at.desc"),
      readTable(
        "opportunity_signal_link_corrections?select=link_id,is_valid,reason&order=corrected_at.desc",
      ),
      readTable(
        "historical_validation_runs?select=*&order=created_at.desc",
      ),
      readTable(
        "historical_validation_days?select=*&order=simulation_date.desc",
      ),
      readTable(
        "historical_raw_records?select=*&order=published_at.desc.nullslast,event_date.desc&limit=2000",
      ),
      readTable(
        "historical_available_records?select=*&order=created_at&limit=5000",
      ),
      readTable("historical_signals?select=*&order=created_at"),
      readTable("historical_opportunities?select=*&order=created_at"),
      readTable("historical_companies?select=*&order=created_at"),
      readTable("historical_models?select=*&order=frozen_at"),
      readTable("historical_assessments?select=*&order=decision_time"),
      readTable("historical_decisions?select=*&order=decision_time"),
      readTable(
        "historical_leak_checks?select=*&order=severity,check_code",
      ),
      readTable(
        "historical_leak_check_corrections?select=*&order=created_at",
      ),
      readTable(
        "historical_source_coverage?select=*&order=source_type",
      ),
      readTable(
        "historical_source_category_coverage?select=*&order=source_category",
      ),
      readTable(
        "historical_search_logs?select=*&order=simulation_date,created_at",
      ),
      readTable("source_category_status_summary?select=*&order=source_category"),
      readTable("source_gap_register?select=*&order=priority,sector_name,source_category"),
      readTable("source_watch_targets?select=*&order=target_role,priority,entity_name"),
      readTable("supply_chain_entities?select=*&order=entity_name"),
      readTable("supply_chain_relationships?select=*&order=effective_from.desc.nullslast,created_at.desc"),
    ]);
    const invalidOpportunitySignalLinkIds = new Set(
      opportunitySignalCorrectionRows
        .filter((row: any) => row.is_valid === false)
        .map((row: any) => row.link_id),
    );
    const expectedCorrectionBySnapshot = new Map(
      expectedReturnCorrectionRows.map((row: any) => [row.snapshot_id, row]),
    );
    const applyExpectedCorrection = (row: any) => {
      const correction = expectedCorrectionBySnapshot.get(
        row.expected_return_snapshot_id || row.current_snapshot_id || row.id,
      ) as any;
      if (!correction) return row;
      return {
        ...row,
        change_driver: correction.corrected_change_driver,
        change_reason: correction.corrected_change_reason,
        correction_note: correction.correction_reason,
        ...(row.current_snapshot_id
          ? {
              event_type:
                correction.corrected_change_driver === "price"
                  ? "price_change"
                  : "validation",
              title:
                correction.corrected_change_driver === "price"
                  ? "价格驱动的赔率变化（系统更正）"
                  : "系统更正：本次没有新的基本面变化",
              description: correction.corrected_change_reason,
            }
          : {}),
      };
    };
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
      marketCap:
        row.market_cap == null ? "待核算" : `${Number(row.market_cap)}亿`,
      reason: row.pool_reason || "待补充入池依据",
      chain: row.industry_chain_position || "待映射",
      coreBusiness: row.core_business || "待补充",
      keyAssumptions: row.key_assumptions || "待验证",
      listingStatus: row.listing_status,
      accountingStatus: row.accounting_status,
      accountingBlocker: row.accounting_blocker,
      companyRole: row.company_role,
      researchPoolStatus: row.research_pool_status,
      valuationStatus: row.valuation_status,
      investmentAssessmentStatus: row.investment_assessment_status,
      shadowStage: row.shadow_stage,
      shadowReason: row.shadow_reason,
      reactivationCondition: row.reactivation_condition,
      transitionReason: row.transition_reason,
      lastTransitionAt: row.last_transition_at,
      lastValidationAt: row.last_validation_at,
      nextValidationAt: row.next_validation_at,
      metadata: row.metadata || {},
      updatedAt: row.updated_at,
    }));
    const sigs = signalRows.map((row: any) => ({
      uuid: row.id,
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
      sourceCode: row.source_code,
      sourceName: row.source_name,
      sourceCategory: row.source_category,
      sourceGrade: row.source_grade,
      publishedAt: row.published_at,
      discoveredAt: row.discovered_at,
      historicalAvailability: row.historical_availability,
      availabilityRisk: row.availability_risk,
      originalTitle: row.original_title,
      underlyingEventId: row.underlying_event_id,
      polarity: row.positive_negative_neutral,
      isOfficial: row.is_official,
      metadata: row.metadata || {},
    }));
    const opportunities = opportunityRows.map((row: any) => ({
      ...row,
      code: row.external_id,
      track: row.sectors?.name || "待分类",
      company: row.core_company || "待映射",
    }));
    const profitModels = profitRows.map((row: any) => ({
      ...row,
      companyCode: row.companies?.external_code,
      companyName: row.companies?.name,
    }));
    const valuations = valuationRows.map((row: any) => ({
      ...row,
      companyCode: row.companies?.external_code,
      companyName: row.companies?.name,
    }));
    const snapshots = snapshotRows.map((row: any) => ({
      ...row,
      companyCode: row.companies?.external_code,
      companyName: row.companies?.name,
    }));
    const rawClues = clueRows.map((row: any) => ({
      ...row,
      track: row.sectors?.name || "待分类",
    }));
    const sectorReviews = sectorReviewRows.map((row: any) => ({
      ...row,
      track: row.sectors?.name || "待分类",
    }));
    return NextResponse.json({
      firms,
      sigs,
      reports: successfulReports(reportRows, dailyPipeline),
      daily_pipeline: dailyPipeline,
      opportunities,
      profitModels,
      valuations,
      sources: sourceRows,
      sourceRegistry,
      sourceHealth,
      sourceCoverageDaily,
      snapshots,
      rawClues,
      sectorReviews,
      opportunityReviews: opportunityReviewRows,
      opportunityCompanies: mappingRows,
      researchTasks: taskRows,
      modelParameters: parameterRows,
      probabilities: probabilityRows,
      probabilityChanges: probabilityChangeRows,
      prices: priceRows,
      expectedReturns: expectedRows.map(applyExpectedCorrection),
      reverseValuations: reverseRows,
      sensitivities: sensitivityRows,
      predictionValidations: validationRows,
      modelChanges: modelChangeRows,
      timelineEvents: timelineRows.map(applyExpectedCorrection),
      dailySnapshots: dailySnapshotRows.map(applyExpectedCorrection),
      investmentThresholds: thresholdRows,
      investmentAssessments: assessmentRows,
      stateTransitions: transitionRows,
      validationEvents: validationEventRows,
      screeningDecisions: decisionRows,
      opportunitySignalLinks: opportunitySignalRows.filter(
        (row: any) => !invalidOpportunitySignalLinkIds.has(row.id),
      ),
      optimizationRecords: optimizationRows,
      historicalRuns,
      historicalDays,
      historicalRawRecords,
      historicalAvailableRecords,
      historicalSignals,
      historicalOpportunities,
      historicalCompanies,
      historicalModels,
      historicalAssessments,
      historicalDecisions,
      historicalLeakChecks,
      historicalLeakCheckCorrections,
      historicalSourceCoverage,
      historicalSourceCategoryCoverage,
      historicalSearchLogs,
      sourceCategoryStatusSummary,
      sourceGaps,
      sourceWatchTargets,
      supplyChainEntities,
      supplyChainRelationships,
      updatedAt: new Date().toISOString(),
    });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Unknown error" },
      { status: 503 },
    );
  }
}
