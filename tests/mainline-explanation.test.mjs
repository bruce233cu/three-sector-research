import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {join} from 'node:path';
import * as copy from '../app/mainline/ui-copy.ts';
const page=readFileSync('app/mainline/page.tsx','utf8');
const profilePath=join(process.env.MAINLINE_RULE_SOURCE_ROOT||'.','config/parameter_profile_industry_trend_v221_state_completion_v1.json');
test('Chinese states, events, modes and statuses are complete',()=>{
 assert.deepEqual(Object.values(copy.labels),['暂未形成','正在形成','主线已确认','主线转弱','主线退潮','暂缓判断']);
 assert.deepEqual(Object.values(copy.events),['新进入候选','候选失效','主线确认','主线转弱','重新确认主线','进入退潮','新一轮重新进入候选']);
 for(const v of ['production','production_simulation','production_validation','backfill'])assert.doesNotMatch(copy.mode(v),/[a-z]/i);
 for(const v of ['SUCCESS','PARTIAL','FAILED','SKIPPED','succeeded','skipped_non_trading_day'])assert.doesNotMatch(copy.status(v),/[a-z]/i);
 assert.doesNotMatch(page,/MARKET RADAR|Production not enabled|SIMULATION|BACKFILL|>Frozen</);
});
test('certified standard explanations have a strict version guard',()=>{
 assert.equal(copy.compatible(copy.COPY_VERSION.rule,copy.COPY_VERSION.profile),true);
 assert.equal(copy.compatible('future_rule',copy.COPY_VERSION.profile),false);
 assert.equal(copy.compatible(copy.COPY_VERSION.rule,'future_profile'),false);
 assert.equal(copy.remaining({state:'S1'},[],false),copy.VERSION_WARNING);
 assert.match(page,/ok\?standards\[s\]/);
 assert.match(page,/detailOk\?standards\[current.state.state\]/);
});
test('frozen UI thresholds match the official read-only profile and engine',{skip:!existsSync(profilePath)},()=>{
 const p=JSON.parse(readFileSync(profilePath,'utf8')),L=copy.limits;
 assert.equal(copy.COPY_VERSION.rule,p.rule_version);assert.equal(copy.COPY_VERSION.profile,p.profile_id);
 for(const [k,v] of Object.entries({candidate:p.candidate.candidate_min_pass_count,rs5Rank:p.candidate.rs5_cross_section_pct_max,rs10Rank:p.confirm.rs10_cross_section_pct_max,win5Candidate:p.candidate.win5_min,win5Confirm:p.confirm.win5_min,win10Confirm:p.confirm.win10_min,ma20:p.confirm.above_ma20_min,turnoverIntensity:p.candidate.turnover_intensity_min,turnoverPercentile:p.confirm.turnover_pct60_min,breadthConfirm:p.confirm.breadth_min_pass_count,enhancers:p.confirm.enhancer_min_pass_count,confirmDays:p.confirm.confirm_consecutive_days,weakenGroups:p.weaken.deterioration_group_min,weakenDays:p.weaken.consecutive_days,dwell:p.weaken.min_dwell_days_after_confirm,retireGroups:p.retire.core_deterioration_group_min,retireDays:p.retire.consecutive_days,retireRank:p.state_completion.retire_rank_threshold,recoverDays:p.state_completion.recover_consecutive_days,slopeWindow:p.state_completion.rs5_ols_window,slopeValid:p.state_completion.rs5_ols_minimum,breadthLag:p.state_completion.breadth_deterioration_lag,breadthDeclines:p.state_completion.breadth_pass_minimum,medianWindow:p.state_completion.breadth_median_valid_window,freezeGap:p.state_completion.freeze_short_gap_max,e4High:p.state_completion.e4_high_percentile}))assert.equal(L[k],v,k);
 assert.equal(p.state_completion.freeze_first_resume_day_transition,false);
 const rules=readFileSync(join(process.env.MAINLINE_RULE_SOURCE_ROOT||'.','src/mainline/engine/rules.py'),'utf8');
 assert.match(rules,/candidate_min_pass_count'\],4\)/);assert.equal(L.candidateValid,4);
 assert.match(copy.standards.Frozen.join(' '),/首个有效交易日不能直接/);
 assert.match(copy.standards.S3.join(' '),/0最强、1最弱/);
 assert.match(copy.standards.S4.join(' '),/不能直接跳/);
});
test('today evidence never implies all conditions passed from a held state',()=>{
 const evidence=[{rule_id:'A',passed:true},{rule_id:'B',passed:false},{rule_id:'C',passed:null},{rule_id:'D',passed:true},{rule_id:'enhancers',passed:null}];
 const result=copy.evidenceSummary(evidence,'S2');assert.equal(result.passed.length,2);assert.equal(result.failed.length,1);assert.equal(result.unknown.length,2);assert.equal(result.total,5);
 assert.equal(copy.evidenceSummary([],'S3').unknown.length,3);
 assert.match(page,/sum.passed.length/);assert.doesNotMatch(page,/5 \/ 5组满足/);
});
test('missing/deferred evidence remains distinct from failure; pause counters truthfully',()=>{
 assert.match(copy.reason('enhancement_evidence_deferred'),/不参与硬判断/);
 assert.equal(copy.readable(null,{}),'数据不足 / 暂未启用');
 assert.match(copy.remaining({state:'S1',stage_frozen:true,consecutive_days:{confirm:1}},[],true),/计数暂停/);
 assert.match(copy.remaining({state:'S3',consecutive_days:{recover:1,retire:2}},[],true),/当前 1 日/);
 assert.match(copy.remaining({state:'S3',consecutive_days:{recover:1,retire:2}},[],true),/当前 2 日/);
 assert.match(copy.standards.Frozen.join(' '),/状态持续天数包含暂缓期间/);
});
test('evidence formatting preserves percentages, counts, boolean and fine slope precision',()=>{
 assert.equal(copy.readable(.18,{rule_id:'C1',operator:'<='}),'18.0%');
 assert.equal(copy.readable(.9,{rule_id:'E4',operator:'NOT_HIGH_OR_ENHANCEMENT'}),'90.0%');
 assert.equal(copy.readable(2,{operator:'COUNT'}),'2.00');
 assert.equal(copy.readable(true,{}),'是');
 assert.match(copy.readable([true,false,null],{}),/满足.*未满足.*数据不足/);
 assert.notEqual(copy.readable(-.0001,{rule_id:'weaken.slope'}),'0.00');
 assert.equal(copy.operator('<='),'≤');
 assert.equal(copy.lifecycleOf({lifecycle_payload:{start_date:'2026-09-21',highest_state:'S2'}},{checkpoint:{lifecycle:{candidate_at:'2026-09-21'}}}).start_date,'2026-09-21');
});
test('UI preserves existing fetch contract, audit details and responsive grid counts',()=>{
 assert.match(page,/fetch\('\/api\/mainline',\{cache:'no-store'\}/);
 assert.match(page,/kind=detail&object=\$\{encodeURIComponent\(selected\)\}&date=/);
 for(const label of ['技术规则详情','原始规则证据','生命周期技术详情','完整度技术记录','来源与版本'])assert.ok(page.includes(label));
 assert.match(page,/PopoverTrigger asChild/);assert.match(page,/pointerType==='mouse'/);
 const css=readFileSync('app/globals.css','utf8');assert.match(css,/ml-distribution\{display:grid;grid-template-columns:repeat\(6,1fr\)/);
 assert.match(css,/ml-metrics\{display:grid;grid-template-columns:repeat\(3,1fr\)/);
});
