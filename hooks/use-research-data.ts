"use client";
import { useEffect, useState } from "react";

export function useResearchData(initialFirms: any[], initialSigs: any[]) {
  const [data, setData] = useState({
    firms: [] as any[],
    sigs: [] as any[],
    reports: [] as any[],
    opportunities: [] as any[],
    profitModels: [] as any[],
    valuations: [] as any[],
    sources: [] as any[],
    sourceRegistry: [] as any[],
    sourceHealth: [] as any[],
    sourceCoverageDaily: [] as any[],
    sourceCategoryStatusSummary: [] as any[],
    sourceGaps: [] as any[],
    sourceWatchTargets: [] as any[],
    supplyChainEntities: [] as any[],
    supplyChainRelationships: [] as any[],
    snapshots: [] as any[],
    rawClues: [] as any[],
    sectorReviews: [] as any[],
    opportunityReviews: [] as any[],
    opportunityCompanies: [] as any[],
    researchTasks: [] as any[],
    modelParameters: [] as any[],
    probabilities: [] as any[],
    probabilityChanges: [] as any[],
    prices: [] as any[],
    expectedReturns: [] as any[],
    reverseValuations: [] as any[],
    sensitivities: [] as any[],
    predictionValidations: [] as any[],
    modelChanges: [] as any[],
    timelineEvents: [] as any[],
    dailySnapshots: [] as any[],
    investmentThresholds: [] as any[],
    investmentAssessments: [] as any[],
    stateTransitions: [] as any[],
    validationEvents: [] as any[],
    screeningDecisions: [] as any[],
    opportunitySignalLinks: [] as any[],
    optimizationRecords: [] as any[],
    historicalRuns: [] as any[],
    historicalDays: [] as any[],
    historicalRawRecords: [] as any[],
    historicalAvailableRecords: [] as any[],
    historicalSignals: [] as any[],
    historicalOpportunities: [] as any[],
    historicalCompanies: [] as any[],
    historicalModels: [] as any[],
    historicalAssessments: [] as any[],
    historicalDecisions: [] as any[],
    historicalLeakChecks: [] as any[],
    historicalLeakCheckCorrections: [] as any[],
    historicalSourceCoverage: [] as any[],
    historicalSourceCategoryCoverage: [] as any[],
    historicalSearchLogs: [] as any[],
    updatedAt: "",
  });
  const [live, setLive] = useState(false);
  useEffect(() => {
    let active = true;
    fetch("/api/research", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error("Database unavailable");
        return response.json();
      })
      .then((next) => {
        if (active && Array.isArray(next.firms) && Array.isArray(next.sigs)) {
          setData(next);
          setLive(true);
        }
      })
      .catch(() => setLive(false));
    return () => {
      active = false;
    };
  }, []);
  return { ...data, live };
}
