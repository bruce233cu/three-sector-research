import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const page = readFileSync("app/mainline/page.tsx", "utf8");
const shell = readFileSync("app/research-ui.tsx", "utf8");
const api = readFileSync("app/api/mainline/route.ts", "utf8");

test("mainline is a first-level market navigation entry", () => {
  assert.match(shell, /\["市场", \[\["A股主线", "\/mainline"/);
});

test("mainline anchor reads a dedicated real-data endpoint", () => {
  assert.match(page, /fetch\("\/api\/mainline"/);
  assert.match(api, /functions\/v1\/mainline-status/);
});

test("mainline anchor states the company-research boundary", () => {
  assert.match(page, /公司利润、估值、赔率和投资价值/);
  assert.doesNotMatch(page, /S2主线|15\s*\/\s*15成功/);
});
