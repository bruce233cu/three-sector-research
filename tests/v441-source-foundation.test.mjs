import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const read = (path) => readFile(new URL(path, root), "utf8");

test("registers all seven source layers without treating registration as execution", async () => {
  const schema = await read("supabase/schema_v441_source_foundation.sql");
  for (const category of [
    "company", "policy", "demand", "industry", "supply_chain", "market", "negative_counterevidence",
  ]) {
    assert.match(schema, new RegExp(`'${category}'`));
  }
  assert.match(schema, /'not_configured'/);
  assert.match(schema, /等待首次真实运行/);
});

test("collects official policy, procurement and industry sources before making signals", async () => {
  const collector = await read("supabase/functions/v43-daily-pipeline/index.ts");
  assert.match(collector, /gov\.cn\/zhengce\/zuixin\/ZUIXINZHENGCE\.json/);
  assert.match(collector, /ccgp\.gov\.cn\/cggg\/zygg\/gkzb/);
  assert.match(collector, /stats\.gov\.cn\/sj\/zxfb/);
  assert.match(collector, /raw_clues/);
  assert.match(collector, /isExternalRealChange/);
  assert.match(collector, /underlying_event_id/);
  assert.match(collector, /healthy_no_new_data/);
});

test("shows source registry and provenance across research views", async () => {
  const modules = await read("app/[module]/page.tsx");
  const shell = await read("app/research-ui.tsx");
  const signal = await read("app/signals/[id]/page.tsx");
  const company = await read("app/company/[code]/page.tsx");
  assert.match(shell, /href="\/sources"/);
  assert.match(modules, /function SourceRegistryView/);
  assert.match(modules, /historicalSourceCategoryCoverage/);
  assert.match(modules, /当日主要来源/);
  assert.match(signal, /历史可得性/);
  assert.match(company, /来源类型/);
});
