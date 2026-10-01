import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
const source=stripTypeScriptTypes(readFileSync(new URL('../lib/daily-result.ts',import.meta.url),'utf8'));
const {successfulReports,readDailyPipeline}=await import('data:text/javascript,'+encodeURIComponent(source));
test('failed newest report cannot replace successful frozen report',()=>{
  const p={three_sector:{latest_success_report:{id:'good',report_date:'2026-10-01'}}};
  const rows=[{id:'failed',report_date:'2026-10-02'},{id:'changed',report_date:'2026-10-01'},{id:'history',report_date:'2026-09-30'}];
  assert.deepEqual(successfulReports(rows,p).map(x=>x.id),['good','history']);
});
test('without proven success do not invent latest report',()=>assert.deepEqual(successfulReports([{report_date:'2026-10-01'}],{}),[]));
test('reader uses shared logs, never depends on mainline tables or providers',async()=>{
  const originalFetch=globalThis.fetch;
  const oldURL=process.env.SUPABASE_URL,oldKey=process.env.SUPABASE_PUBLISHABLE_KEY;
  const requested=[];
  process.env.SUPABASE_URL='https://stub.invalid';process.env.SUPABASE_PUBLISHABLE_KEY='stub';
  globalThis.fetch=async(url)=>{
    requested.push(String(url));
    const success={finished_at:'2026-10-01T09:01:00Z',metadata:{successful_report:{id:'good',report_date:'2026-10-01'},jobs:{three_sector_daily_job:{status:'succeeded'}}}};
    const latest={run_date:'2026-10-02',status:'failed',metadata:{jobs:{three_sector_daily_job:{status:'failed'},mainline_job:{status:'skipped',reason:'pending_provider'}}}};
    return new Response(JSON.stringify(String(url).includes('&or=')?[success]:[latest]));
  };
  try {const p=await readDailyPipeline();assert.equal(p.three_sector.latest_success_report.id,'good');assert.equal(p.three_sector.latest_run_status,'failed');assert.equal(p.mainline.reason,'pending_provider');assert.ok(requested.every(x=>x.includes('/automation_runs?')));}
  finally {globalThis.fetch=originalFetch;if(oldURL===undefined)delete process.env.SUPABASE_URL;else process.env.SUPABASE_URL=oldURL;if(oldKey===undefined)delete process.env.SUPABASE_PUBLISHABLE_KEY;else process.env.SUPABASE_PUBLISHABLE_KEY=oldKey;}
});
