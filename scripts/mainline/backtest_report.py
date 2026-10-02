"""Versioned Chinese report first, calibration candidates second; no rule edits."""
import argparse,sys,json,csv,subprocess
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
from statistics import mean,median
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from mainline.backtest.runner import read,write,BASE_SHA
from mainline.engine.replay import digest

def stamp():return datetime.now(timezone.utc).isoformat()
def md(path,lines):
    if path.exists():raise ValueError('immutable report exists')
    path.write_text('\n'.join(lines)+'\n')
def val(x):return 'NULL' if x is None else str(x)
def why(case,business,metric,kind):
    rows=[r for r in business['rows'] if case['start_date']<=r['snapshot']['as_of_date']<=case['end_date']]
    blocked=Counter(x['rule_id'] for r in rows if r['state']['previous_state']=='S1'
        for x in r['rules'] if x['rule_id'] in ['A','B','C','D','enhancers'] and x['passed'] is False)
    if kind=='false_positive':
        if metric['false_confirmation_count']:
            text='发生新增S1→S2确认，冻结确认规则当时满足，后续行情未持续；属于持续性与样本定义需复核的问题。单个新误报不足以单独调参。'
        else:text='事件期S2来自此前确认；重点看退出时效和标签边界，不能称为新增确认误报。'
    elif kind=='miss':
        text='窗口内从未S2；出现候选但确认条件未连续同时满足。A=相对收益/截面，B=赢基准比例，C=成交持续性，D=广度。'
    elif kind=='lag':
        text='这是首次观察S2与事件起点的交易日差；前窗可能属于此前生命周期，后窗可能属于新事件，不能直接推断因果。'
    else:text='多次候选进入、失效或生命周期重开；转换遵循冻结规则，频次需跨案例验证后才可考虑防抖。'
    return text+' S1阶段失败组频次：'+str(dict(blocked))+'；冻结'+str(metric['freeze_days'])+'日。'

def main(results):
    base=ROOT/'reports/milestone-d-baseline-v1'
    book=read(base/'casebook.json');index=read(results/'run_index.json')
    metrics=read(results/'case_metrics.json');agg=read(results/'aggregate_metrics.json')
    leak=read(results/'future_leakage_checks.json');rerun=read(results/'deterministic_rerun.json')
    manifests=read(results/'run_manifests.json');context=read(results/'causal_context.json.gz')
    cases={c['case_id']:c for c in book['cases']}
    businesses={c:read(results/(c+'.json.gz')) for c in cases}
    full=index['baseline_equivalence_status']=='FULL_CERTIFIED_WARMUP_RESTORED'
    wp=manifests[0].get('warmup_provenance') or {}
    checks={
      'casebook先冻结':book['selection_frozen_at']<index['started_at'] and all(m['casebook_checksum']==book['checksum'] for m in manifests),
      '正样本存在':sum(c['case_type']=='positive' for c in cases.values())>=8,
      '负样本存在':sum(c['case_type']=='negative' for c in cases.values())>=8,
      '模糊样本存在':sum(c['case_type']=='ambiguous' for c in cases.values())>=4,
      'PIT无明显执行层前视':not leak['future_leakage_detected'],
      'Baseline完整预热运行':full and wp.get('original_raw_response_checksum_matching') is True and len(wp.get('warm_benchmark_checks',[]))==84,
      'detection可统计':len(metrics)==25,
      'miss可统计':all('MISS' in r for r in metrics),
      'false positive可统计':all('false_S2_days' in r for r in metrics),
      'lag可统计':all('S2_lag_observed' in r for r in metrics),
      'churn可统计':all('transition_count' in r for r in metrics),
      'lifecycle可统计':all('lifecycle_count' in r for r in metrics),
      'Freeze可统计':all('freeze_days' in r for r in metrics) and not agg['overall']['freeze_transition_violations'],
      'coverage可统计':all('coverage' in r for r in metrics),
      'deterministic rerun通过':len(rerun)>=5 and all(r['components_equal'] and r['full_anchor_replayed'] for r in rerun),
      '失败案例完整展示':len(metrics)==len(cases),
      '没有边测边调参':all(m['code_sha']==BASE_SHA and m['rule_version']==book['rule_version'] and m['parameter_profile']==book['parameter_profile'] for m in manifests),
      '所有结果可追溯':all(m['checksum']==r['checksum'] for m,r in zip(manifests,metrics)),
      '结果版本化':all(m['backtest_run_id'].startswith(index['backtest_run_id']) for m in manifests)}
    blockers=[]
    if not full:blockers.append('缺少原认证84日预热输入，冷启动结果不能作为完整Baseline验收。')
    if leak['future_leakage_detected']:blockers.append('时点检查发现前视或历史输入重算不一致。')
    if not all(checks.values()) and not blockers:blockers.append('盲测合同存在未通过项目，见逐项检查。')
    gate='PASS' if all(checks.values()) else 'FAIL'
    o=agg['overall'];pos=[r for r in metrics if r['case_type']=='positive'];neg=[r for r in metrics if r['case_type']=='negative']
    fp=sorted([r for r in neg if r['false_S2_days']>0],key=lambda r:(-r['false_S2_days'],-r['false_confirmation_count'],r['case_id']))[:5]
    misses=sorted([r for r in pos if r['MISS']],key=lambda r:(-r['event_days'],r['case_id']))[:5]
    lag=sorted([r for r in pos if r['S2_lag_observed'] is not None],key=lambda r:(-r['S2_lag_observed'],r['case_id']))[:5]
    churn=sorted(metrics,key=lambda r:(-r['short_interval_reversal_count'],-r['transition_count'],r['case_id']))[:5]
    failed={'false_positive':fp,'miss':misses,'lag':lag,'churn':churn}
    write(results/'failure_cases.json',{k:[{**r,'analysis':why(cases[r['case_id']],businesses[r['case_id']],r,k)} for r in rs] for k,rs in failed.items()})
    # A CSV preserves NULL explicitly; authoritative types stay in the JSON.
    fields=['case_id','case_name','case_type','first_S1_date','first_S2_date','event_first_S1_date','event_first_S2_date',
       'S1_lag_observed','S2_lag_observed','S1_detected','S2_detected','event_S2_detected','MISS','miss_category',
       'confirmed_duration','false_S2_days','false_confirmation_count','inherited_S2_at_event_start',
       'transition_count','reversal_count','short_interval_reversal_count','lifecycle_count','reentry_count','retired_state_reentry_count','freeze_days']
    with (results/'case_metrics.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in metrics:w.writerow({k:val(r.get(k)) for k in fields})
    with (results/'daily_state_timelines.csv').open('w',newline='') as f:
        fs=['case_id','date','state','frozen','reason','lifecycle_id','transition','backtest_run_id']
        w=csv.DictWriter(f,fieldnames=fs);w.writeheader()
        for r in metrics:
            for t in r['timeline']:w.writerow({**{k:val(t.get(k)) for k in fs if k not in ['case_id','backtest_run_id','transition']},
              'case_id':r['case_id'],'backtest_run_id':businesses[r['case_id']]['manifest']['backtest_run_id'],
              'transition':json.dumps(t['transition'],ensure_ascii=False) if t['transition'] else 'NULL'})
    report_at=stamp();execution_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    first_days=[r['snapshot']['as_of_date'] for r in context['rows']]
    debts=['知识时间未验证，strict PIT覆盖0%，不能称strict PIT。','此前工程验收接触该窗口汇总结果，本轮为独立标签的校准样本，非最终未接触保留盲测。',
      '公开申万加权指数、细分主题与有效成分等权行业/全A等权基准存在代理差异。','个股未复权、停牌真实性及知识时间仍受既有认证限制。',
      '相同事件、多行业和重叠窗口相关，不能把25例当成25个独立样本。',
      'N01-N03前窗为19交易日，保留冻结的截断边界；部分确认后60日收益右截断。',
      '缺独立结构恶化参考日期，退潮滞后保持NULL，不能武断判早退或晚退。']
    coverage={k:min(r['coverage'][k] for r in metrics) for k in ['membership_resolution','benchmark','core_metric','rule_evidence_records','source']}
    freeze_reasons=Counter()
    for r in metrics:freeze_reasons.update(r['freeze_reason'])
    output={'title':'A股主线识别系统 V2.2.1 — MILESTONE D HISTORICAL BLIND TEST REPORT',
        'baseline':'Baseline V1','start_sha':BASE_SHA,'execution_code_sha':execution_sha,
        'final_repository_sha':'报告归档提交和交付消息为准；运行代码SHA独立记录。',
        'casebook_version':book['casebook_version'],'casebook_checksum':book['checksum'],
        'case_count':len(metrics),'positive_count':len(pos),'negative_count':len(neg),'ambiguous_count':sum(r['case_type']=='ambiguous' for r in metrics),
        'run_id':index['backtest_run_id'],'data_snapshot_version':index['data_snapshot_version'],
        'rule_version':book['rule_version'],'parameter_profile':book['parameter_profile'],'code_sha':BASE_SHA,
        'window_start':min(first_days),'window_end':max(first_days),'warmup_days':84 if full else 0,
        'pit_level':'effective_pit','knowledge_time_unverified':True,'overall':o,'coverage_minimum':coverage,
        'freeze_reasons':dict(freeze_reasons),'rerun_cases':[r['case_id'] for r in rerun],
        'future_leakage_detected':leak['future_leakage_detected'],'checks':checks,'G5':gate,'blocking_issues':blockers[:3],
        'technical_debt':debts,'report_completed_at':report_at,'rules_modified':False,
        'production_database_writes':0,'milestone_d':'BASELINE BLIND TEST CLOSED' if gate=='PASS' else 'OPEN'}
    write(results/'G5_FINAL_GATE.json',output)
    L=['# '+output['title'],'',f'G5 = {gate}。这是盲测体系的验收，不等于规则准确或优化完成。',
      '',f'本轮{"完整预热Baseline" if full else "冷启动诊断"}结果：正例全窗口S2 {o["positive_full_window_S2"]}/{len(pos)}，事件期S2 {o["positive_event_window_S2"]}/{len(pos)}，全窗口漏报{o["MISS"]}例。',
      f'负例事件期存在S2 {o["negative_any_event_S2_cases"]}/{len(neg)}，稳定至少3日{o["negative_stable_S2_cases"]}例，新增确认{o["negative_new_confirmation_cases"]}例；事件期S2合计{o["negative_false_S2_days"]}个案例行业日。',
      '', 'False Positive（误报）、Miss（漏报）、Lag（识别滞后）、Churn（状态反复）、PIT（时点真实性）均按冻结统计合同解释。状态和窗口相关，以下不是总体准确率或交易收益承诺。',
      '', '## 交付37项','',
      '| 项目 | 证据与结果 |','|---|---|',
      f'| 1. 起始SHA | {BASE_SHA} |',
      f'| 2. 最终SHA | 本报告归档提交及交付消息；运行代码提交 {execution_sha} |',
      f'| 3. Casebook | {book["casebook_version"]}；校验 {book["checksum"]}；冻结于 {book["selection_frozen_at"]} |',
      f'| 4–7. 样本数 | 共{len(metrics)}；正{len(pos)}，负{len(neg)}，模糊{sum(r["case_type"]=="ambiguous" for r in metrics)} |',
      '| 8. 选择原则 | 公开复盘与白名单行业收益/成交/广度，标签未进入引擎；不按状态删改case。 |',
      f'| 9. 时间范围 | 重放{min(first_days)}至{max(first_days)}；{"另有2024-05-06至2024-08-30共84日预热" if full else "预热缺失，明确冷启动"} |',
      '| 10–11. 时点等级 | effective_pit；knowledge_time_unverified=true；strict覆盖0% |',
      '| 12. 数据来源 | 复用认证板块与每日成分；原Sina、SWS、已认证历史股票池和日历。未建立长期个股库。 |',
      f'| 13. 规则 | {book["rule_version"]} |', f'| 14. 参数 | {book["parameter_profile"]} |',f'| 15. code_sha | {BASE_SHA}；7个冻结文件逐字节核对 |',
      '| 16. Runner | scripts/mainline/backtest_runner.py；31行业逐日截面；首日S0初始化、之后合法前日checkpoint；复用同一冻结引擎。 |',
      '| 17. Evaluator | scripts/mainline/backtest_evaluate.py；统计合同见docs/MAINLINE_BLIND_TEST_CONTRACT.md |',
      f'| 18. Manifests | {index["backtest_run_id"]}；run_manifests.json含25例独立ID、源、日期、版本、checksum |',
      '| 19. 时间线 | daily_state_timelines.csv及同名case压缩JSON；包含每日state、Freeze、rule evidence、checkpoint和lifecycle |',
      '| 20–21. 首次S1/S2 | 下表及case_metrics.csv；左截断、事件内首次与继承确认分开 |',
      f'| 22. Detection | 全窗S1 {o["positive_full_window_S1"]}/{len(pos)}；全窗S2 {o["positive_full_window_S2"]}/{len(pos)}；事件期{o["positive_event_window_S2"]}/{len(pos)} |',
      f'| 23. Miss | 全窗口{o["MISS"]}例；类别{o["miss_categories"]}；事件外确认另列 |',
      f'| 24. 误报 | 事件S2 {o["negative_any_event_S2_cases"]}例；稳定{o["negative_stable_S2_cases"]}例；新增{o["negative_new_confirmation_cases"]}例；{o["negative_false_S2_days"]}日 |',
      f'| 25. 滞后 | 已观察S2正例中位{o["S2_lag_observed_median"]}交易日；有负值/继承，不含从未确认者，不能单独评价快慢 |',
      f'| 26. 反复 | 跨case观察转换{o["transitions"]}，重访{o["reversals"]}，5日内{o["short_reversals"]}；重叠窗可能重复计数 |',
      f'| 27. Lifecycle | case ID去重重复{o["duplicate_lifecycles"]}；重开与S4重入分列；右截断开放周期保留 |',
      f'| 28. Freeze | {o["freeze_days"]}/{o["case_days"]}案例日；冻期转换违规{o["freeze_transition_violations"]}；理由和恢复方式见明细 |',
      f'| 29. Coverage | 最小覆盖{coverage}；未知和递延保持NULL，成分有效价格比例/基准截面比例另列 |',
      f'| 30. 重跑 | {len(rerun)}例：{",".join(r["case_id"] for r in rerun)}；从起点完整重放，state/rules/checkpoint/lifecycle/checksum一致 |',
      f'| 31. 泄漏检查 | 9类未来扰动；历史RS重算{leak["past_only_core_RS_checks"]}次，差异{leak["past_only_core_RS_mismatches"]}；检测前视={leak["future_leakage_detected"]} |',
      '| 32. 严重失败 | 下列误报、漏报、滞后与反复各最多5例，不足5全部列出 |',
      '| 33. 边界案例 | 5个模糊case下文逐一展示，不给对错评分 |',
      '| 34. 总体表现 | 能输出候选和部分确认；确认缺失、事件外确认及候选反复是候选研究方向，不能据单个案例立即调参。 |',
      f'| 35. G5 | {gate} |',f'| 36. Blocking Issues | {blockers[:3] if blockers else "无"} |',
      '| 37. Technical debt | 下文保留知识时间、主题代理、相关样本、窗口截断和结构恶化参考缺口 |','',
      '## 每例检测与滞后','',
      '| Case | 类型/行业 | 首次观察S1 | 首次观察S2 | 事件S2日 | S2观察滞后 | 漏报 | 转换/短反复 | Freeze |',
      '|---|---|---|---|---:|---:|---|---|---:|']
    for r in metrics:L.append(f'| {r["case_id"]} | {r["case_type"]}/{cases[r["case_id"]]["sector"]} | {val(r["first_S1_date"])} | {val(r["first_S2_date"])} | {r["event_confirmed_days"]} | {val(r["S2_lag_observed"])} | {r["MISS"]} | {r["transition_count"]}/{r["short_interval_reversal_count"]} | {r["freeze_days"]} |')
    L+=['','## 最严重失败及原因','']
    for kind,title in [('false_positive','误报（含继承确认，按事件S2日排序）'),('miss','漏报（全窗没有S2）'),('lag','最长观察滞后（前窗或后窗均不剪裁）'),('churn','最多短间隔状态反复')]:
        L+=['### '+title,'']
        for r in failed[kind]:L+=[f'- {r["case_id"]} {r["case_name"]}：事件S2 {r["event_confirmed_days"]}日；新增确认{val(r["false_confirmation_count"])}；滞后{val(r["S2_lag_observed"])}；转换{r["transition_count"]}、短反复{r["short_interval_reversal_count"]}。',why(cases[r['case_id']],businesses[r['case_id']],r,kind)]
        if not failed[kind]:L+=['本类没有符合定义的案例。']
        L+=['']
    L+=['## 模糊与边界案例','']
    for r in metrics:
        if r['case_type']=='ambiguous':L.append(f'- {r["case_id"]} {r["case_name"]}：事件S2{r["event_confirmed_days"]}日，短反复{r["short_interval_reversal_count"]}次。{cases[r["case_id"]]["selection_reason"]}')
    L+=['','## 分层结果','']
    for dimension,groups in agg['strata'].items():
        L+=['### '+dimension,'','| 分层 | 例数 | 正例事件S2/正例 | 正例漏报 | 负例事件S2/负例 | 新确认误报例 | 短反复 |','|---|---:|---|---:|---|---:|---:|']
        for k,a in groups.items():L.append(f'| {k} | {a["cases"]} | {a["positive_event_window_S2"]}/{a["positive_cases"]} | {a["MISS"]} | {a["negative_any_event_S2_cases"]}/{a["negative_cases"]} | {a["negative_new_confirmation_cases"]} | {a["short_reversals"]} |')
        L+=['']
    L+=['## Gate逐项','']+[f'- [{"x" if passed else " "}] {name}' for name,passed in checks.items()]
    L+=['','## 技术债与真实性边界','']+['- '+d for d in debts]
    L+=['','## 生产保护','',
       '本轮runner/evaluator/补数作业不连接数据库，没有production写入口。mainline_job不在本轮修改范围，原17:00调度继续；Sites仍为v41，MANUAL_UI_CHECK_REQUIRED保留。外部数据库计数与checksum由交付时再次核验。',
       '', 'G1–G4沿用PASS，没有重跑、重开。参数、状态规则、circ_mv约定、Provider、Universe、three-sector业务均未改变。',
       '', f'报告先完成于{report_at}。下面的校准清单另文生成；本轮停止于Baseline和候选清单。']
    md(results/'BASELINE_BLIND_TEST_REPORT.md',L)
    # Only after the report is persisted are research candidates written.
    bounce=[r['case_id'] for r in metrics if r['short_interval_reversal_count']>=5]
    confirm=[r['case_id'] for r in pos if (r['MISS'] or not r['event_S2_detected']) and r['top_confirm_blockers'].get('B',0)>=5]
    inherited=[r['case_id'] for r in neg if r['false_S2_days']>0 and r['inherited_S2_at_event_start']]
    candidate=[
     {'id':'C1','problem':'候选状态频繁开关/生命周期重开','cases':bounce,'frequency':len(bounce),
      'possible_cause':'候选进入和失效使用即时条件，缺少候选层面的滞回；需排除标签窗及数据影响。','direction':'先诊断候选保持条件、滞回或连续性的新版本实验，不在本轮改参数。','risk':'初期强行情确认可能变慢。','positive_effect':'可能降低反复，但也可能漏掉短而有效行情。','negative_effect':'可能减少热闹导致的短候选，不能保证减少S2。','overfit':'中等；须在事件簇和时间隔离样本重复验证。','next_stage':len(bounce)>=2},
     {'id':'C2','problem':'部分正样本有相对趋势但确认赢率组反复不满足','cases':confirm,'frequency':len(confirm),
      'possible_cause':'中期累计相对收益与短期日度赢率不是同一维度，且行业等权/主题标签有差异。','direction':'先拆解A/B/C/D共同失败及行业代理差异，再设计新profile的持久性实验，不直接放宽S2。','risk':'普涨、脉冲和防御切换可能更容易被确认。','positive_effect':'可能改善慢趋势的覆盖，需多风格验证。','negative_effect':'可能增加误报，必须同时检验全部负例。','overfit':'较高，不能只针对银行或一个主题调参。','next_stage':len(confirm)>=2},
     {'id':'C3','problem':'负窗中的S2常为前一周期继承','cases':inherited,'frequency':len(inherited),
      'possible_cause':'合法驻留/连续转弱/退潮与市场窗口定义共同影响。','direction':'先在新标注版本冻结独立结构恶化参考，评价退潮滞后；不据继承S2直接缩短weaken/retire。','risk':'过早退出会损害恢复行情。','positive_effect':'应保护S3恢复和完整生命周期。','negative_effect':'有望更准确区分退出慢与新增误报。','overfit':'较高，当前缺少独立结构日期。','next_stage':len(inherited)>=2},
     {'id':'C4','problem':'加权行业、主题与等权一级行业标签存在代理差异','cases':['P01','P03','P08','P10','A02','A03','A04'],'frequency':7,
      'possible_cause':'龙头主题或大盘行业指数强，不等于广泛等权行业持续赢全A等权。','direction':'下一版独立Casebook先固定目标和标签依据，保留Baseline标签；不重做正式benchmark、Universe或Provider。','risk':'后验重标会制造漂亮结果，因此旧case不可改删。','positive_effect':'更可信地界定真实检出和漏报。','negative_effect':'更可信地区分龙头脉冲与板块扩散。','overfit':'高，必须先冻结新Casebook再看新系统输出。','next_stage':True},
     {'id':'C5','problem':'当前为校准Casebook，尚非最终未接触保留样本','cases':list(cases),'frequency':len(cases),
      'possible_cause':'同事件多行业相关且工程阶段接触过本窗口汇总状态。','direction':'按时间划分校准/保留区间，保留样本规则输出不可参与选择和调参。','risk':'若多次窥视保留集，将失去最终检验意义。','positive_effect':'验证跨阶段识别能力。','negative_effect':'验证新规则是否只是对已知脉冲过拟合。','overfit':'必须控制。','next_stage':True}]
    for c in candidate:
        if c['frequency']<2:c['next_stage']=False;c['direction']='样本不足，不作为调参建议；先增加独立案例。'
    calibration={'created_after_report':stamp(),'baseline_report_completed_at':report_at,'G5':gate,'rules_modified':False,
       'candidates':candidate,'single_new_false_confirmation_policy':'新增误报不足多个独立案例时，不建议为单例新增S2过滤器。'}
    write(results/'RULE_CALIBRATION_CANDIDATE_LIST.json',calibration)
    C=['# RULE CALIBRATION CANDIDATE LIST','', '只列研究候选，不执行。先完成Baseline报告，再生成本清单。G5='+gate+'。']
    if gate!='PASS':C+=['','当前Gate未通过，任何规则调整均待阻塞解决后再讨论。']
    for c in candidate:
        C+=['','## '+c['id']+' '+c['problem'],'',
           f'涉及case：{",".join(c["cases"])}；出现频次：{c["frequency"]}个案例观察（可能相关）。',
           '可能根因：'+c['possible_cause'],'建议方向：'+c['direction'],'风险：'+c['risk'],
           '对正例：'+c['positive_effect'],'对负例：'+c['negative_effect'],'过拟合：'+c['overfit'],
           '值得下一阶段测试：'+str(c['next_stage'])+'；不是规则有效性的结论。']
    C+=['','单个新增误报只列观察事项，不能据此单案例调参。']
    md(results/'RULE_CALIBRATION_CANDIDATE_LIST.md',C)
    N=['# 下一阶段开工清单（不自动开始）','']
    if gate=='PASS':
        N+=['- 冻结新的规则版本和参数版本，保留Baseline V1代码、Casebook与结果。','- 先锁定少量多案例支持的假设，再设置正负例共同验收目标，不创建总评分。',
          '- 划分时间独立、未接触的保留窗口，先冻结独立标签和结构转弱参考，再看输出。',
          '- 对每个候选新版本运行相同Casebook及保留集，比较检出、漏报、误报、滞后、反复和Freeze。',
          '- 保留5例以上完整确定性重跑、时点检查、production隔离及版本化结果。',
          '- 不自动发布新规则，不在本轮进入MILESTONE E。']
    else:N+=['先解决G5阻塞，保持规则冻结，不开始规则校准。']
    md(results/'NEXT_PHASE_CHECKLIST.md',N)
    if not (results/'README.md').exists():md(results/'README.md',['# '+index['backtest_run_id'],'','完整交付见BASELINE_BLIND_TEST_REPORT.md；Gate见G5_FINAL_GATE.json。','',
      'case_metrics.csv和daily_state_timelines.csv便于阅读；同名case压缩JSON包含完整rule evidence和checkpoint。causal_context.json.gz为31行业连续历史轨迹。',
      '原冷启动诊断run -01保留；完整预热版本使用单独ID、数据快照和manifest，不覆盖旧结果。'])
    print(json.dumps({'run_id':index['backtest_run_id'],'G5':gate,'overall':o,'blockers':blockers[:3],'report_completed_at':report_at},ensure_ascii=False),flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--results',type=Path,required=True);main(a.parse_args().results)
