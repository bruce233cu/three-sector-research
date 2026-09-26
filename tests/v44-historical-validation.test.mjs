import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

test("keeps V4.4 records isolated from live research tables", async () => {
  const sql = await readFile(new URL("supabase/schema_v44_historical_validation.sql", root), "utf8");
  for (const table of [
    "historical_validation_runs",
    "historical_validation_days",
    "historical_raw_records",
    "historical_available_records",
    "historical_signals",
    "historical_opportunities",
    "historical_companies",
    "historical_models",
    "historical_assessments",
    "historical_decisions",
    "historical_leak_checks",
    "historical_source_coverage",
    "historical_search_logs",
  ]) {
    assert.match(sql, new RegExp(`create table if not exists public\\.${table}`));
  }
  assert.match(sql, /locked historical validation runs cannot be changed/);
  assert.match(sql, /version or date boundary changed; create a new test run/);
});

test("pre-fixes three equal windows and invalidates biased reconstruction", async () => {
  const sql = await readFile(new URL("supabase/data_v44_historical_validation_runs.sql", root), "utf8");
  assert.match(sql, /'V44-ROB-20260901'/);
  assert.match(sql, /'V44-SPACE-20260901'/);
  assert.match(sql, /'V44-AI-20260901'/);
  assert.match(sql, /'2026-08-25','2026-09-01','2026-09-08'/);
  assert.match(sql, /'dataset_construction_bias','资料库构建偏差','P0','failed'/);
  assert.match(sql, /set status='invalid'/);
  assert.match(sql, /gpt_external_knowledge_allowed',false/);
  assert.match(sql, /free_web_search_allowed',false/);
});

test("serves a historical validation module without adding return rankings", async () => {
  const page = await readFile(new URL("app/[module]/page.tsx", root), "utf8");
  const api = await readFile(new URL("app/api/research/route.ts", root), "utf8");
  assert.match(page, /function HistoricalValidation/);
  assert.match(page, /本模块只验信息，不验收益/);
  assert.match(page, /查看被排除资料/);
  assert.match(api, /historical_validation_runs\?select=\*/);
  assert.match(api, /historical_leak_checks\?select=\*/);
  assert.match(api, /historical_leak_check_corrections\?select=\*/);
});
