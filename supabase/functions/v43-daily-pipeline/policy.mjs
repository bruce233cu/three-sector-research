export const TIMEZONE = 'Asia/Shanghai';
export const CRON = '0 9 * * *';
export function businessDate(value = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {timeZone: TIMEZONE, year:'numeric', month:'2-digit', day:'2-digit'}).format(new Date(value));
}
export function windowFor(date) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || businessDate(`${date}T12:00:00+08:00`) !== date) throw new Error('invalid business_date');
  const start = new Date(`${date}T00:00:00+08:00`);
  return { business_date:date, timezone:TIMEZONE, start_at:start.toISOString(), cutoff_at:new Date(`${date}T17:00:00+08:00`).toISOString(), end_at:new Date(start.getTime()+86400000).toISOString(), definition:'截至当日17:00可获得信息形成的日终研究快照；执行中新信息按实际抓取时间标记' };
}
export function mainlineDecision(calendar) {
  if (calendar === false) return {status:'skipped', reason:'skipped_non_trading_day', provider_enabled:false, gate:'G1_NOT_PASSED'};
  if (calendar !== true) return {status:'skipped', reason:'trading_calendar_unknown', provider_enabled:false, provider_status:'pending_provider', gate:'G1_NOT_PASSED'};
  return {status:'skipped', reason:'pending_provider', provider_enabled:false, gate:'G1_NOT_PASSED'};
}
export function overallStatus(jobs) {
  if (jobs.every(j=>['succeeded','skipped'].includes(j.status))) return 'succeeded';
  return jobs.some(j=>j.status==='succeeded') ? 'partial' : 'failed';
}
export async function independently(name, action, timeoutMs=90000) {
  const started_at = new Date().toISOString();
  const controller = new AbortController();
  let timer;
  try {
    const result = await Promise.race([action(controller.signal), new Promise((_,reject)=> {timer=setTimeout(()=>{controller.abort();reject(new Error(`${name}: timeout`));},timeoutMs);})]);
    return {name, ...result, started_at, finished_at:new Date().toISOString()};
  } catch(error) {
    return {name,status:'failed',error:String(error?.message || error),started_at,finished_at:new Date().toISOString()};
  } finally {clearTimeout(timer);}
}
export function stampPayload(payload, context) {
  if (!payload || typeof payload !== 'object') return payload;
  if (Array.isArray(payload)) return payload.map(x=>stampPayload(x,context));
  const fetched_at = new Date().toISOString();
  const source_time = payload.published_at || payload.source_published_at || null;
  const date = source_time && Number.isFinite(Date.parse(source_time)) ? businessDate(source_time) : null;
  if (date && date > context.business_date) throw new Error('future source date rejected');
  const information_window = !date ? 'source_time_unverified' : date < context.business_date ? 'historical_lookback' : Date.parse(source_time)>Date.parse(context.cutoff_at) ? 'after_cutoff' : 'same_day';
  return {...payload, ...(payload.occurred_on && date ? {occurred_on:date}:{}), ...(payload.signal_date && date ? {signal_date:date}:{}), metadata:{...(payload.metadata||{}), pipeline_run_id:context.pipeline_run_id, business_date:context.business_date, timezone:TIMEZONE, source_time, fetched_at, information_window, cutoff_at:context.cutoff_at}};
}
export function latestSuccessful(runs, module='three_sector_daily_job') {
  return [...runs].sort((a,b)=>String(b.finished_at||'').localeCompare(String(a.finished_at||''))).find(r=>r.metadata?.jobs?.[module]?.status==='succeeded' && r.metadata?.successful_report) || null;
}
