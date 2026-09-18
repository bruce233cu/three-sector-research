"use client";
import { useEffect, useState } from "react";

export function useResearchData(initialFirms: any[], initialSigs: any[]) {
  const [data, setData] = useState({
    firms: initialFirms, sigs: initialSigs, reports: [] as any[], opportunities: [] as any[],
    profitModels: [] as any[], valuations: [] as any[], sources: [] as any[], snapshots: [] as any[],
    rawClues: [] as any[], sectorReviews: [] as any[], opportunityReviews: [] as any[],
    opportunityCompanies: [] as any[], researchTasks: [] as any[], modelParameters: [] as any[],
    probabilities: [] as any[], probabilityChanges: [] as any[], prices: [] as any[],
    expectedReturns: [] as any[], reverseValuations: [] as any[], sensitivities: [] as any[],
    predictionValidations: [] as any[], modelChanges: [] as any[], timelineEvents: [] as any[],
    dailySnapshots: [] as any[], investmentThresholds: [] as any[], investmentAssessments: [] as any[],
    stateTransitions: [] as any[], validationEvents: [] as any[], updatedAt: ""
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
    return () => { active = false; };
  }, []);
  return { ...data, live };
}
