// Display-only explanations, certified against the frozen profile and engine.
// Never evaluate market rules here: today's outcome comes from persisted evidence.
export const COPY_VERSION = {rule:'mainline_v2.2.1_state_completion_v1',profile:'industry_trend_v221_state_completion_v1'};
export const limits = {candidate:3,candidateValid:4,rs5Rank:.2,rs10Rank:.3,win5Candidate:.6,win5Confirm:.8,win10Confirm:.7,turnoverIntensity:1,turnoverPercentile:.6,ma20:.6,breadthConfirm:2,enhancers:2,confirmDays:2,weakenGroups:2,weakenDays:2,dwell:3,retireGroups:2,retireDays:3,retireRank:.5,recoverDays:2,slopeWindow:5,slopeValid:4,breadthLag:3,breadthDeclines:3,medianWindow:20,freezeGap:3,e4High:.9};
export const labels:Record<string,string>={S0:'暂未形成',S1:'正在形成',S2:'主线已确认',S3:'主线转弱',S4:'主线退潮',Frozen:'暂缓判断'};
export const meanings:Record<string,string>={S0:'目前还没有形成足够的主线迹象。',S1:'已经出现主线迹象，但证据还不够确认。',S2:'进入确认时，强度、持续性、成交和板块扩散已达到主线标准。',S3:'主线还没有结束，但已经出现持续转弱信号。',S4:'本轮主线已经明显退潮，旧生命周期关闭。',Frozen:'今天的数据不足，系统暂时沿用上一可信状态。'};
export const pct=(v:any)=>v==null?'—':Number.isFinite(Number(v))?`${(Number(v)*100).toFixed(1)}%`:'数据不足';
export const show=(v:any)=>v==null?'—':String(v);
export const number=(v:any)=>v==null?'—':Number.isFinite(Number(v))?Number(v).toFixed(2):'数据不足';
export function compatible(rule?:string,profile?:string){return rule===COPY_VERSION.rule&&profile===COPY_VERSION.profile;}
export const VERSION_WARNING='当前规则版本已变化，请更新规则说明';
const L=limits;
export const standards:Record<string,string[]>={
 S0:['当前未达到候选标准，或此前候选条件已失效，回到暂未形成。仅表示未形成系统定义的候选。'],
 S1:[`5组候选条件至少${L.candidate}组通过，同时至少${L.candidateValid}组数据有效。`,`5日相对强度进入行业前${pct(L.rs5Rank)}。`,'10日相对强度大于0，跑赢全A等权基准。',`最近5个有效交易日至少${pct(L.win5Candidate)}跑赢基准。`,`成交额占比高于自身20日均值，或成交活跃度大于${L.turnoverIntensity}。`,'上涨家数占比或站上20日线占比，高于全A对应值。'],
 S2:[`强度、持续性、成交、板块广度、增强条件5组全部成立，连续${L.confirmDays}个有效交易日，从正在形成进入确认。`,`强度：10日相对强度大于0，且行业排名在前${pct(L.rs10Rank)}。`,`持续性：5日胜率至少${pct(L.win5Confirm)}，或10日胜率至少${pct(L.win10Confirm)}。`,`成交：成交额占比在自身60日历史中的分位至少${pct(L.turnoverPercentile)}，且没有连续3个有效交易日下降。`,`广度3项至少${L.breadthConfirm}项：上涨占比高于全A、站上20日线占比至少${pct(L.ma20)}、创60日新高占比高于3个交易日前。`,`至少${L.enhancers}项可用增强条件：20日相对强度大于0、站上60日线占比改善、创60日新高占比改善、头部成交集中度历史分位低于${pct(L.e4High)}。集中度过高时所需增强证据暂未启用，不强行判断。`,`转弱后恢复确认，必须重新满足完整确认条件，连续${L.recoverDays}个有效交易日。`],
 S3:[`3类转弱信号至少${L.weakenGroups}类成立，连续${L.weakenDays}个有效交易日；确认后至少停留${L.dwell}个交易日。`,`短期强度下降：最近${L.slopeWindow}个交易日5日相对强度的线性趋势斜率小于0，至少${L.slopeValid}个有效观察值。`,'相对排名连续变差：10日强度分位连续3个有效交易日变大。0最强、1最弱，数值变大才代表变差。',`广度恶化：上涨、站上20日线、站上60日线、创60日新高4项占比，至少${L.breadthDeclines}项低于${L.breadthLag}个交易日前。`,`恢复须完整确认条件连续${L.recoverDays}日，不能仅靠一天反弹。`],
 S4:[`3类退潮信号至少${L.retireGroups}类成立，从转弱状态连续${L.retireDays}个有效交易日。`,'相对收益：10日和20日相对强度均小于0。',`相对排名：10日强度分位大于${pct(L.retireRank)}，落到行业后半区。`,`板块广度：4项广度至少${L.breadthDeclines}项低于各自最近${L.medianWindow}个有效交易日的中位数。`,'旧生命周期关闭；未来走强须从正在形成重新进入，开启新生命周期，不能直接跳到确认或转弱。'],
 Frozen:['沿用上一可信状态，不升级、不降级；连续条件计数暂停。缺失值不当作未满足。','数据恢复后的首个有效交易日不能直接触发硬状态跳转。',`缺口不超过${L.freezeGap}个交易日且中间证据完整可验证，允许恢复原计数；否则重置计数，保留上一可信状态。`,'状态持续天数包含暂缓期间；连续条件计数与状态持续天数是两个不同概念。'],
};
export const events:Record<string,string>={candidate:'新进入候选',candidate_failed:'候选失效',confirm:'主线确认',weaken:'主线转弱',recover:'重新确认主线',retire:'进入退潮',new_lifecycle_reentry:'新一轮重新进入候选'};
export const modes:Record<string,string>={production:'正式生产数据',production_simulation:'历史演练数据',backfill:'历史回填数据',production_validation:'生产验证数据'};
export function mode(v?:string){return modes[v||'']||'数据类型待核验';}
export function status(v?:string|null){return ({success:'运行成功',succeeded:'运行成功',partial:'部分完成',failed:'运行失败',skipped:'已跳过',skipped_non_trading_day:'非交易日，已跳过',running:'正在运行',dispatched:'已发出运行请求',pending:'等待运行',queued:'等待运行',cancelled:'已取消'} as Record<string,string>)[v?.toLowerCase()||'']||'状态待核验';}
export function event(v?:string){return events[v||'']||'状态变化';}
const reasons:Record<string,string>={rule_evidence_unavailable:'规则证据不足',enhancement_evidence_deferred:'增强证据暂未启用，不参与硬判断',no_legal_transition_triggered:'尚未达到下一状态的转换要求，沿用当前状态',freeze_recovery_first_session_no_transition:'数据恢复首日，保留状态，暂不跳转',recover_requires_two_or_retire_requires_three_sessions:'恢复或退潮条件尚需满足连续交易日要求',confirmed_date_missing:'确认日期证据缺失',required_metric_coverage_unavailable:'关键指标完整度不足',critical_data_unavailable:'关键数据不足',cross_section_coverage_unavailable:'市场横截面数据完整度不足',insufficient_evidence:'可用证据不足',threshold_not_met:'尚未达到标准',passed:'满足标准',paused:'连续条件计数暂停',resumed:'已恢复原连续计数',reset_after_unverifiable_gap:'缺口证据无法完整验证，连续计数重置'};
export function reason(v:any):string{
 if(v==null||v==='')return '无';
 if(Array.isArray(v))return v.map(reason).join('；')||'无';
 const raw=String(v);const key=raw.split(':')[0];
 if(events[key])return events[key];
 if(reasons[key])return reasons[key];
 if(raw.includes('enhancement_evidence_deferred'))return reasons.enhancement_evidence_deferred;
 if(raw.includes('coverage'))return '数据完整度不足，详见技术记录';
 if(/missing|unavailable|insufficient|invalid|freeze/.test(raw))return '所需数据或规则证据不足，详见技术记录';
 return /[\u4e00-\u9fff]/.test(raw)?raw:'详见技术记录';
}
export const fields=[
 {key:'rs_5',label:'5日相对强度',help:'行业近5日相对全A等权基准的强度，大于0表示跑赢基准。'},
 {key:'rs_10',label:'10日相对强度',help:'行业近10日相对全A等权基准的强度，大于0表示跑赢基准。'},
 {key:'rs_20',label:'20日相对强度',help:'行业近20日相对全A等权基准的强度，大于0表示跑赢基准。'},
 {key:'rs_10_pct',label:'10日强度排名',help:'0最强、1最弱。0.20（20%）代表处于行业前20%；数值越小越强。'},
 {key:'turnover_share',label:'成交额占比',help:'板块成交额占全A成交额的比例。'},
 {key:'turnover_intensity',label:'成交活跃度',help:'相对自身常态的成交活跃程度，大于1表示高于自身常态。'},
 {key:'up_ratio',label:'上涨家数占比',help:'板块成员中当日上涨的家数比例，观察上涨是否扩散。'},
 {key:'above_ma20',label:'站上20日线占比',help:'板块成员价格站上自身20日均线的比例。'},
 {key:'above_ma60',label:'站上60日线占比',help:'板块成员价格站上自身60日均线的比例。'},
 {key:'new_high_60',label:'创60日新高占比',help:'板块成员创出60日新高的比例，观察新高是否扩散。'},
];
export const ruleNames:Record<string,string>={C1:'5日相对强度排名',C2:'10日相对收益',C3:'5日持续占优',C4:'成交活跃',C5:'候选板块扩散','C4.mean20':'成交额占比高于自身常态','C4.intensity':'成交活跃度','C5.up':'上涨占比领先市场','C5.ma20':'站上20日线比例领先市场',candidate:'候选条件汇总',A:'强度与市场排名','A.return':'10日相对收益','A.rank':'10日强度排名',B:'持续性','B.win5':'5日持续占优','B.win10':'10日持续占优',C:'成交确认','C.percentile':'60日成交额占比分位','C.trend':'成交额占比没有连续下降',D:'板块广度','D.up':'上涨占比领先市场','D.ma20':'站上20日线占比','D.newhigh':'新高扩散改善',E1:'20日相对强度',E2:'60日线广度改善',E3:'新高扩散改善',E4:'头部成交集中度',E5:'活跃子主题',enhancers:'可用增强条件',confirm:'完整确认条件','weaken.slope':'短期强度下降','weaken.rank':'相对排名连续恶化','weaken.breadth':'板块广度恶化',weaken:'转弱条件汇总','retire.returns':'10日及20日相对收益转负','retire.rs10':'10日相对收益转负','retire.rs20':'20日相对收益转负','retire.rank':'相对排名落入后半区','retire.breadth':'广度低于自身常态',retire:'退潮条件汇总',recover:'重新确认条件'};
export function ruleName(id:string){if(ruleNames[id])return ruleNames[id];const metric=fields.find(f=>id.endsWith('.'+f.key));return metric?`${metric.label} ${id.startsWith('retire.')?'低于常态':'低于3日前'}`:'其他规则（技术记录可查）';}
export const groups:Record<string,string[]>={S0:['C1','C2','C3','C4','C5'],S1:['A','B','C','D','enhancers'],S2:['A','B','C','D','enhancers'],S3:['weaken.slope','weaken.rank','weaken.breadth'],S4:['retire.returns','retire.rank','retire.breadth']};
export function groupEvidence(rules:any[],state:string){return (groups[state]||[]).map(id=>({id,name:ruleName(id),value:rules.find(q=>q.rule_id===id)?.passed??null}));}
export function evidenceSummary(rules:any[],state:string){const items=groupEvidence(rules,state);return {passed:items.filter(q=>q.value===true),failed:items.filter(q=>q.value===false),unknown:items.filter(q=>q.value===null),total:items.length};}
export function remaining(state:any,rules:any[],isCompatible:boolean){
 if(!isCompatible)return VERSION_WARNING;
 if(state.stage_frozen)return '沿用上一可信状态；等待数据恢复，连续条件计数暂停。';
 const s=state.state;const checks=evidenceSummary(rules,s);const count=state.consecutive_days||state.checkpoint?.consecutive||{};
 if(s==='S4')return '重新达到候选标准后，从正在形成开启新一轮；不能直接跳到确认。';
 if(s==='S0')return '候选需至少3组通过、至少4组数据有效；当天结果见下方证据。';
 if(s==='S1')return `完整确认条件需连续${L.confirmDays}个有效交易日；当前连续记录 ${show(count.confirm)} 日。${checks.unknown.length?'部分证据不足，暂不按失败处理。':''}`;
 if(s==='S2')return `转弱须至少2类信号连续${L.weakenDays}日，并满足确认后的最短停留；当前转弱连续记录 ${show(count.weaken)} 日。`;
 return `恢复确认需完整确认条件连续${L.recoverDays}日（当前 ${show(count.recover)} 日）；退潮需至少2类信号连续${L.retireDays}日（当前 ${show(count.retire)} 日）。`;
}
export function readable(v:any,q:any):string{
 if(v==null)return '数据不足 / 暂未启用';
 if(typeof v==='boolean')return v?'是':'否';
 if(Array.isArray(v))return v.map((item,index)=>`${index+1}：${item==null?'数据不足':typeof item==='boolean'?(item?'满足':'未满足'):readable(item,q)}`).join('；');
 if(typeof v==='object')return Object.entries(v).map(([k,value])=>`${({count:'通过组数',valid_min:'最低有效组数',pass_min:'最低通过组数'} as Record<string,string>)[k]||ruleName(k)}：${readable(value,{operator:'COUNT'})}`).join('；');
 if(typeof v==='number'){
  if(q.rule_id==='weaken.slope')return Number(v).toPrecision(5);
  if(q.rule_id==='E4'||q.rule_id==='E4.not_high')return pct(v);
  return /^(COUNT|AND|OR|CONFIRM_CONSECUTIVE_KERNEL)$/.test(q.operator||'')||q.rule_id==='C4.intensity'?number(v):pct(v);
 }
 return reason(v);
}
export function operator(v:string){return ({'<=':'≤','>=':'≥','<':'<','>':'>','==':'等于',AND:'全部满足',OR:'任一满足',COUNT:'至少通过',DEFERRED:'暂未启用',NOT_HIGH_OR_ENHANCEMENT:'集中度不过高或增强证据可用',recover_to_confirmed:'重新达到完整确认标准'} as Record<string,string>)[v]||'组合条件';}
export function lifecycleOf(detail:any,state:any){return {...(state.checkpoint?.lifecycle||{}),...(detail?.lifecycle_payload||{}),...(detail||{})};}
export function coverageName(key:string){return fields.find(f=>f.key===key)?.label||({rs_3:'3日相对强度',win_5:'5日胜率',win_10:'10日胜率',amount:'成交额',benchmark:'市场基准',sector_return:'行业收益',turnover_pct_60:'60日成交占比分位',turnover_pct_250:'250日成交占比分位'} as Record<string,string>)[key]||'其他指标';}
