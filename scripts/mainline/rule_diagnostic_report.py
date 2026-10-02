"""Presentation of archived-rule diagnostics; contains no calibration or replay."""
import csv
import gzip
import json
import statistics
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'reports/milestone-d-rule-diagnostic'
TITLE = 'A股主线识别系统 V2.2.1 — RULE DIAGNOSTIC REPORT'
START = '95ba63c6dbc6b1cad82e84a9c3403f7dc353fc35'
CASES = json.loads(gzip.decompress((D / 'case_diagnostics.json.gz').read_bytes()))
SUMMARY = json.loads((D / 'diagnostic_summary.json').read_text())
MATRIX = list(csv.DictReader((D / 'rule_discrimination_matrix.csv').open()))
MATRIX_BY_ID = {r['rule_id']: r for r in MATRIX}
IMPACT = list(csv.DictReader((D / 'warmup_security_membership_impact.csv').open()))
BLOCKERS = list(csv.DictReader((D / 'event_blockers.csv').open()))
SOURCE = 'https://github.com/bruce233cu/three-sector-research/blob/mainline-phase1e/'


def pct(value):
    return 'NULL' if value is None or value == '' else f'{float(value)*100:.1f}%'


def num(value):
    if value is None: return 'NULL'
    if isinstance(value, bool): return '通过' if value else '未通过'
    if isinstance(value, (int, float)): return f'{value:.6g}'
    return str(value)


def mdtable(headers, rows):
    clean = lambda v: num(v).replace('|', '/').replace('\n', '；')
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '|' + '|'.join(['---']*len(headers)) + '|'] +
                     ['| ' + ' | '.join(clean(v) for v in row) + ' |' for row in rows])


LABELS = {'candidate': 'S1 合计', 'C1': 'S1 短期相对排名', 'C2': 'S1 十日相对收益',
          'C3': 'S1 五日胜率', 'C4': 'S1 成交', 'C5': 'S1 广度',
          'A': 'A 相对强度', 'B': 'B 高胜率', 'C': 'C 成交确认', 'D': 'D 广度确认',
          'enhancers': '增强证据', 'confirm': '五组同时满足'}
CLASSIFICATIONS = {
    'candidate': ('B', '发现能力有用；单日失守立刻退出造成候选反复'),
    'C1': ('A', '正负差28.0个百分点；保留短期相对排名信息'),
    'C2': ('A', '正负差25.5个百分点；与A.return完全重复，保留信息不重复计票'),
    'C3': ('A', '候选层有区分；与确认层高胜率门槛应分开研究'),
    'C4': ('C', '正负差仅6.4个百分点；单日放量易通过，需研究持续性'),
    'C4.mean20': ('C', '高于短期成交均值不等于稳定增量，按多日持续研究'),
    'C4.intensity': ('C', '强度大于1可被短时放量触发，不能单独证明持续流入'),
    'C5': ('B', '正负差22.4个百分点；候选退出时翻转频繁'),
    'A': ('B', '正负差16.4个百分点；绝对相对收益与横截面排名不同约束'),
    'A.return': ('A', '相对收益为正有区分，不能重复当独立证据'),
    'A.rank': ('B', '排名门槛可研究，但不少失败远离阈值，单调放宽不能解释全部'),
    'B': ('D', '正例通过仅33.0%；7例25个非S2日唯一阻塞，优先研究否决结构'),
    'B.win5': ('D', '五日≥4次跑赢，离散高门槛；也过滤负例，不能直接放宽'),
    'B.win10': ('D', '十日≥7次跑赢，对间歇领涨严格；也过滤负例'),
    'C': ('B', '有19.9个百分点差异，早期存在NULL；持续成交比单日分位更值得研究'),
    'C.percentile': ('B', '成交活跃有用，但不等于持续净流入；早期40个有效观测门槛敏感'),
    'C.trend': ('C', '未连降三日不是持续上升；单日反弹即可恢复，结构需研究'),
    'D': ('A', '组差34.7个百分点且事件窗口无NULL，当前较有价值的确认组'),
    'D.up': ('B', '单日比全A上涨家数多，正负差18.3个百分点'),
    'D.ma20': ('A', '正负差26.3个百分点；保留广度存量信息'),
    'D.newhigh': ('A', '正负差34.0个百分点；新高扩散信息有用'),
    'enhancers': ('B', '组差37.4个百分点但受NULL与时间分布影响，不能整体视为高可信'),
    'E1': ('C', '正负差8.8个百分点，确认当天四个误报相关案例全部为正'),
    'E2': ('A', '正负差31.6个百分点；严格增加在100%饱和时须另研究'),
    'E3': ('C', '与D.newhigh完全相同；信息有用，跨组重复计票不提供独立证据'),
    'E4': ('C', '负样本事件窗口全NULL，不能比较判别力；DATA_LIMITATION'),
    'E4.not_high': ('C', '长期分位在负样本无已知观测，不可据表面差异校准'),
    'E5': ('C', '冻结为deferred且不计增强票数，不是正式阻塞项'),
    'weaken': ('B', '退化方向负例触发更多，但无独立退潮日期，不判早退晚退'),
    'retire': ('B', '退化规则有方向信息；窗口相关性与迟延参考缺失'),
}


def classification(rid):
    return CLASSIFICATIONS.get(rid, ('B', '仅描述当前发展集，不据本表直接修改阈值'))


def persistence_rows():
    rows = []
    for kind in ['positive', 'negative']:
        selected = [d for d in CASES if d['case']['case_type'] == kind and d['metrics']['event_confirmed_days'] > 0]
        for n in [1, 3, 5, 10, 20]:
            row = {'cohort': '正样本事件期S2' if kind == 'positive' else '负样本事件期S2', 'window': n, 'cases': len(selected),
                   'case_ids': ','.join(d['case']['case_id'] for d in selected), 'primary_anchor': 'first actual lifecycle confirmation associated with observed S2'}
            avg = lambda values: statistics.mean(v for v in values if v is not None)
            row['daily_relative_win_rate'] = avg(d['persistence_at_S2'][0]['prior'][str(n)]['daily_relative_win_rate'] for d in selected)
            for metric in ['rs_5', 'rs_10', 'rs_20', 'win_5', 'win_10', 'turnover_intensity', 'turnover_pct_60',
                           'up_ratio', 'above_ma20', 'above_ma60', 'new_high_60', 'top3_turnover_share']:
                row[metric] = avg(d['persistence_at_S2'][0]['prior'][str(n)]['metrics'][metric]['mean'] for d in selected)
            for group in ['B', 'C', 'D', 'enhancers', 'E1', 'E2', 'E3']:
                row[group + '_pass_frequency'] = avg(d['persistence_at_S2'][0]['prior'][str(n)]['group_pass_frequencies'][group]['all_days_rate'] for d in selected)
            rows.append(row)
    return rows


PERSISTENCE = persistence_rows()
sections = []


def section(title, body):
    sections.append(('## ' + title, body))


section('大白话成绩单 · Executive Summary', '''**一句话结论：当前更像“把某几天很强当成持续主线”，同时用高胜率一票否决间歇领涨；不能靠把门槛统一调松解决。**

- **真主线漏在哪里：发现不是首要问题，升级才是。** 10例都曾进入候选S1，只有6例全窗到过S2、5例事件期处于S2。B组高胜率最值得研究：7个正例出现过其余4组满足、B独自阻塞，共25个非S2案例日；其中真正可升级的S1日只有8日、4例。早期电子、电力设备还混有成交分位历史不足。
- **假主线为何进：同一天很强不足以证明以后持续。** 4个负例事件期有S2，但只有房地产N10在事件期新确认；传媒、社会服务、通信沿用旧S2。四个相关首次确认均五组满足，中期相对收益当天也都为正。确认前5日跑赢频率，负例相关组85%、正例组76%；“只加强短期胜率”没有证据能解决误报。
- **最大三个问题：升级否决权失衡、时间持续性不足、状态开关太容易反复。** B正例通过率33.0%、负例18.1%；候选成交组正负差只有6.4个百分点。全窗有117次S0→S1→S0模式，候选失败138次，58%的失败日仍有2票，离3票候选门槛只差1票。这里的次数含相关和重叠窗口，不是独立错误数。
- **保留广度信息，优先测试结构。** D广度组正负差34.7个百分点，新高扩散34.0个百分点，相对有价值。最可疑的是B的绝对否决、单日成交开关、D与E重复的新高证据。下一步值得研究多日成交/中期积累、证据去重和候选/恢复滞回；本轮没有执行调参，也没有证明任何候选有效。

所有结论均为 **DIAGNOSTIC_ONLY**。25例从本轮起只作 **DEVELOPMENT / DIAGNOSTIC SET**。G5仍FAIL；当前不进入正式Rule Calibration。''')

section('先把两类错误分开：漏掉升级，还是旧状态退出慢', '''正样本全窗漏报4例：P01电子、P02电力设备、P03银行、P09有色金属；P10军工是事件期未确认、事后才确认。P04/P05事件内新确认；P06/P07/P08在事件开始前已确认，事件内仍有S2，不能把其负滞后解释为预测能力。

负样本事件期S2为N05、N07、N09、N10，共11个案例行业日；稳定至少3日有2例。事件内新S1→S2只有N10一次；没有事件内S3→S2误恢复。N02、N06在其事件外曾到S2，不能按本次负窗口记成误报。模糊样本不纳入召回/误确认的分母。

本文主判别力口径是**每个案例事件期TRUE天数/事件期总天数，然后10个正例、10个负例或5个模糊例等权平均**；NULL留在分母。另存已知日分母和 pooled 案例日口径。正/负/模糊事件天数分别244/88/118，全窗共1,631案例日。通过频率不是“该规则导致的漏报概率”。没有替换规则重放，所以不能把阻塞天数写成可避免的漏报数。

存在11个行业日跨标签重叠：P05/N07社会服务在2024-12-16共享同一S2日；A01/N05传媒重叠10日。案例也共享行情及行业，不能当25个独立试验。保留原标签，另做移除跨标签重叠日、逐一留出案例的敏感性检查。''')

core_ids = ['candidate', 'C1', 'C2', 'C3', 'C4', 'C5', 'A', 'B', 'C', 'D', 'enhancers', 'confirm']
display_matrix = []
for rid in core_ids:
    r = MATRIX_BY_ID[rid]; cls, why = classification(rid)
    display_matrix.append({'rule_id': rid, 'rule': LABELS[rid],
        'positive_rate': float(r['positive_case_equal_pass_rate_all_days']), 'negative_rate': float(r['negative_case_equal_pass_rate_all_days']),
        'ambiguous_rate': float(r['ambiguous_case_equal_pass_rate_all_days']), 'gap': float(r['positive_negative_difference_all_days']), 'gap_pp':100*float(r['positive_negative_difference_all_days']),
        'positive_failures': int(r['positive_false']), 'negative_passes': int(r['negative_pass']),
        'positive_nulls': int(r['positive_null']), 'negative_nulls': int(r['negative_null']),
        'sole_blocker_days': int(r['positive_sole_blocker_days']), 'edge_failures': int(r['positive_edge_failures']),
        'class': cls, 'judgment': why})
section('规则判别力：广度有价值，高胜率否决更可疑', '''下表比的是固定事件窗口里的规则满足频率，差值为正例减负例。广度D的差异较大且没有NULL；B虽然过滤负例，也让真主线很难连续升级。成交C4大多数真假窗口都能满足，区分度弱。增强组差异更大，但时间分布与可用性混杂，不能直接宣布它最有效。

“真主线漏报风险”用实际FALSE天数与唯一阻塞日呈现；“负例放行”是负例TRUE天数，并不等于整个系统误确认次数。组规则无统一数值边缘距离，边缘失败只能在下层原子规则统计。

''' + mdtable(['规则组', '正例通过', '负例通过', '模糊通过', '正负差', '正例FALSE', '负例TRUE', '正/负NULL', '正例唯一阻塞日', '诊断类'],
    [[r['rule'], pct(r['positive_rate']), pct(r['negative_rate']), pct(r['ambiguous_rate']), f"{r['gap']*100:+.1f}pp", r['positive_failures'], r['negative_passes'], f"{r['positive_nulls']}/{r['negative_nulls']}", r['sole_blocker_days'], r['class']] for r in display_matrix]))

positive_rows = []
ROOT_CAUSE = {
    'P01': ('C历史不足 / B', 'A排名', '成交分位12日NULL，五组仅11月11日齐全，随后失配；不能归因纯规则'),
    'P02': ('C历史不足 / B', 'A排名', '12日成交分位NULL；11月11日五组通过但由S0入S1，次日不连续'),
    'P03': ('B高胜率', 'C成交 / A排名', 'B失败27/32日；三次单日全组通过没有形成有效连续'),
    'P04': ('D / 增强早期不足', 'B', '11月27日首次事件期齐全，28日升级；两日规则只增加一个有效交易日'),
    'P05': ('B高胜率', 'A排名', 'B连续失败12日，12月12日齐全、13日升级，14日滞后主要来自证据晚齐'),
    'P06': ('B / D（退出及再入）', 'C / A', '首个S2在事件前；事件内退出后再成为候选，未能再确认'),
    'P07': ('C成交', 'B（恢复）', '事件内处于S2/S3；B唯一阻塞4日均非S1，属恢复限制'),
    'P08': ('B（恢复）', 'C成交', '事件前已确认；B失败25/30日，唯一阻塞6日均为非S1'),
    'P09': ('B高胜率', 'A排名 / C成交', 'B失败24日，A22日、C21日，很多失败远离阈值，6月12日单日齐全'),
    'P10': ('B高胜率', 'D / A', '事件期B 28/28日失败；不是少一天，6月27日事后升级')}
for d in CASES:
    if d['case']['case_type'] != 'positive': continue
    c = d['case']; m = d['metrics']; primary, secondary, reason = ROOT_CAUSE[c['case_id']]
    atom_id = 'C.percentile' if c['case_id'] in ['P01', 'P02'] else 'B.win10'
    atom = d['atomic_blockers'][atom_id]; example = atom['closest_failure']
    positive_rows.append({'case_id': c['case_id'], 'industry': c['sector'], 'first_S1': m['first_S1_date'], 'first_S2': m['first_S2_date'],
        'event_S2_days': m['event_confirmed_days'], 'S2_lag': m['S2_lag_observed'], 'primary_blocker': primary,
        'secondary_blocker': secondary, 'margin_example': f"{atom_id}: {num(example['actual'])} vs {num(example['threshold'])}; margin={num(example['margin'])}" if example else 'NULL/没有数值失败',
        'blocker_days': ';'.join(f"{g}:{d['groups'][g]['false_days']}F/{d['groups'][g]['null_days']}NULL" for g in ['A', 'B', 'C', 'D', 'enhancers']),
        'near_miss_days': d['near_miss_days'], 'reason': reason})
section('真主线漏报表：10例都发现过，5例未在事件期确认', '''以下“首日”为存档窗口内首次观察，左截断候选不能视作真正首次发现。S2滞后按全窗首次观察相对事件开始的交易日距离，负值表示事件前已有S2；漏报时NULL。首要阻塞是证据排序，不是反事实因果结论。

''' + mdtable(['案例 / 行业', 'S1首日', 'S2首日', '事件S2天', 'S2滞后', '首要 / 次要阻塞', '近似通过日', '初步根因'],
[[r['case_id']+' '+r['industry'], r['first_S1'], r['first_S2'], r['event_S2_days'], r['S2_lag'], r['primary_blocker']+'；'+r['secondary_blocker'], r['near_miss_days'], r['reason']] for r in positive_rows]))

section('AND与最后阻塞：有否决失衡，但不能把35日都算作漏报', '''正例事件期非S2日中，4/5组满足35日、3/5组满足43日。唯一缺口为B 25日（7例）、C 7日（5例）、A 2日（2例）、Enhancer 1日（1例）、D 0日。C的7日中含4日早期NULL，不能当作阈值太严。

限定“上一日S1、当天未Freeze且非恢复保护日”的可升级机会后：B唯一阻塞8日（P03 2、P05 1、P09 1、P10 4）；C 2日（P03/P09各1）；A 1日（P06）。其余大量4/5日发生在S0/S3/S4，必须先满足合法状态入口或恢复计数，不能说移除一个条件就会升级。

**B否决权值得研究，放宽效果尚未验证。** B全正例失败170/244案例日，且会过滤69/88负例案例日；N08煤炭也有B唯一阻塞1个可升级日。贸然放松可能把已拦住的负例放进来。''' )

for d in CASES:
    if d['case']['case_type'] != 'positive': continue
    c = d['case']; m = d['metrics']; primary, secondary, reason = ROOT_CAUSE[c['case_id']]
    group_table = mdtable(['组', '通过 / FALSE / NULL', '阻塞频率（事件总日）', '最长连续FALSE', '事件首次满足', '唯一阻塞日 / 可升级S1日'],
        [[g, f"{v['pass_days']}/{v['false_days']}/{v['null_days']}", pct(v['blocker_frequency_all_event_days']), v['false_longest_streak'], v['first_pass_in_event'], f"{v['sole_blocker_nonS2_days']}/{v['sole_blocker_eligible_S1_days']}"] for g, v in d['groups'].items()])
    atom_table = mdtable(['原子规则', 'FALSE / 边缘 / 严重数值 / NULL', '最长FALSE', '失败margin中位', '最近失败的日期:实际 vs 阈值'],
        [[rid, f"{v['false_days']}/{v['edge_days']}/{v['severe_numeric_days']}/{v['null_days']}", v['false_longest_streak'], v['median_failure_margin'],
          (v['closest_failure']['date']+': '+num(v['closest_failure']['actual'])+' vs '+num(v['closest_failure']['threshold'])) if v['closest_failure'] else '无数值失败/NULL'] for rid, v in d['atomic_blockers'].items()])
    true_not = '; '.join(f"{r['date']}，前态{r['previous_state']}，确认计数{r['consecutive']['confirm']}，{r['reason']}" for r in d['confirm_true_nonS2_evidence']) or '事件期不存在全组通过但未S2的日'
    section(c['case_id']+' '+c['sector']+'：'+primary, f"**{reason}。** 事件期{c['start_date']}至{c['end_date']}共{m['event_days']}日；S1首次观察{m['first_S1_date']}，滞后{m['S1_lag_observed']}日；S2 {m['first_S2_date'] or '未确认'}。{d['confidence']}。\n\n{group_table}\n\n{atom_table}\n\n五组通过但未S2：{true_not}。4/5={d['pass4_nonS2_days']}日、3/5={d['pass3_nonS2_days']}日；近似数值失败{d['near_miss_days']}日，边缘带减半/标准/加倍分别{d['near_miss_band_sensitivity']}。这些不是替代阈值重放。")

negative_rows = []
for d in CASES:
    if d['case']['case_type'] != 'negative': continue
    c = d['case']; m = d['metrics']; p = d['persistence_at_S2'][0] if d['persistence_at_S2'] else None
    negative_rows.append({'case_id': c['case_id'], 'industry': c['sector'], 'first_S1': m['first_S1_date'], 'first_observed_S2': m['first_S2_date'],
        'event_S2_date': m['event_first_S2_date'], 'event_S2_days': m['event_confirmed_days'],
        'new_false_confirmations': m['false_confirmation_count'], 'inherited_S2': m['inherited_S2_at_event_start'],
        'full_window_S2_days': m['confirmed_duration'], 'entry_groups': '5/5通过' if p and all(p['anchor']['groups'].values()) else '不适用/入口未完整已知',
        'anchor_date': p['anchor']['date'] if p else None, 'continuous_S2_sessions': p['S2_contiguous_sessions_from_anchor'] if p else 0,
        'first_S3': next((e['date'] for e in p['first_exit_events'] if e['state'] == 'S3'), None) if p else None,
        'first_S4': next((e['date'] for e in p['first_exit_events'] if e['state'] == 'S4'), None) if p else None})
section('假主线误报表：1次新确认，3例旧状态延续', '''表中全窗S2日和事件S2日分列。N02、N06事件外的S2不记为事件误报。N05/N07/N09在事件开始已处S2，诊断其原确认证据与后来退出，但不能认定事件开始当日五组仍全部通过。

''' + mdtable(['案例 / 行业', 'S1首日', 'S2首次观察', '事件首个S2', '事件S2天', '事件新确认 / 沿用', '原确认五组', '首次S3 / S4'],
 [[r['case_id']+' '+r['industry'], r['first_S1'], r['first_observed_S2'], r['event_S2_date'], r['event_S2_days'], str(r['new_false_confirmations'])+' / '+('是' if r['inherited_S2'] else '否'), r['entry_groups'], str(r['first_S3'])+' / '+str(r['first_S4'])] for r in negative_rows]))

FP_INTERPRETATION = {
 'N05': '传媒确认前10日RS20均值为-3.28%，当天转为+3.54%；但确认后5日广度与成交继续改善，不能说它立即整体衰败。负标签窗口后段才走弱，原确认是否错误与持有状态失效须分开。',
 'N07': '社会服务确认前5日C持续性很强（4/5日），当天RS20为+4.19%；它正是P05的同一次确认。确认后5日MA20广度下降40.3个百分点、新高下降19.7个百分点，5日后进S3。标签跨相邻窗口，不能要求同一日同时判真假。',
 'N09': '通信确认前5日全部跑赢，C也5/5日通过，不能用“缺乏5日持续性”解释它。确认后5日win5从1.0降至0.2、MA20广度降26.5个百分点，8日后进S3。更长持续性与退出可能有价值，尚未证明能预先拦截。',
 'N10': '房地产是唯一事件内新误确认。确认当天RS20为+12.21%、win5/win10均0.8、MA20/MA60广度100%、新高74%，并非中期RS不足或小范围龙头独涨。此前20日C仅1/20日通过；确认后5日新高降71个百分点，3日后进S3。早期C分位也受warmup影响。'}
for d in CASES:
    cid = d['case']['case_id']
    if cid not in FP_INTERPRETATION: continue
    p = d['persistence_at_S2'][0]
    table = mdtable(['规则', '实际', '阈值', '判定', 'margin'], [[a['rule_id'], a['actual_value'], a['threshold'], a['passed'], a['signed_margin']] for a in p['anchor']['atoms']])
    section(cid+' '+d['case']['sector']+'：原确认满足，后续表现不同', f"**{FP_INTERPRETATION[cid]}**\n\n原确认{p['anchor']['date']}，连续S2 {p['S2_contiguous_sessions_from_anchor']}交易日（从原确认计，不是事件内日数）；事件内S2 {d['metrics']['event_confirmed_days']}日。原五组均TRUE。\n\n{table}\n\n原子规则有FALSE不代表组FALSE：B为OR、D与Enhancer为计票；E4未知仍可由E1/E2/E3足够票数通过。原确认前1/3/5/10/20日与后续同窗口全部保留在案例证据，后续变化只用于诊断，未回填到确认时点。")

section('持续性比较：短期更猛不能可靠区分，成交与中期积累值得研究', '''主比较取事件期有S2的5个正例（P04—P08）和4个负例（N05/N07/N09/N10），均回看关联生命周期的首次真实确认。排除P10事件外才确认。前N日不包含确认日，只使用当时已经发生的数据，案例等权，不按行业成交绝对大小加权。

**并未找到“真主线一定连续更强”的稳定定律。** 前5日真实日收益跑赢比例，正例76%、负例85%；前10日64%与65%；前20日52%与55%。广度存量和成交强度的负例均值也可能更高。前10日RS20滚动值均值为正例+1.03%、负例-1.28%，C持续满足频率52%与37.5%；这是值得测试的方向，远不是证明。

N07与P05共用原确认，五个正例与四个负例只是8个不同的行业确认；还有三例负窗口的原确认在事件外。严格限定事件内新确认，正例只有P04/P05两次，负例只有N10一次，不能据此建立可靠阈值。原始字段的不同尺度分别比较，成交占比不跨行业直接解释为资金吸引力。'''
 + '\n\n' + mdtable(['前窗口', '分组 / 案例数', '实际日跑赢', '滚动RS20均值', 'B持续通过', 'C持续通过', 'D持续通过', '成交强度均值'],
 [[r['window'], r['cohort']+' / '+str(r['cases']), pct(r['daily_relative_win_rate']), pct(r['rs_20']), pct(r['B_pass_frequency']), pct(r['C_pass_frequency']), pct(r['D_pass_frequency']), num(r['turnover_intensity'])] for r in PERSISTENCE if r['window'] in [5,10,20]]))

section('广度、成交与集中度：存量高不等于扩散能维持', '''前5日，负例相关组MA20广度均值75.6%、正例53.7%；新高13.8%与7.1%。因此广度阈值更高未必过滤误报。更有价值的是新增广度的变化与能否维持：D.newhigh/E2事件期正负差34.0/31.6个百分点，但并非所有负例确认后都立即衰减，N05就是反例。

成交C.percentile衡量过去60日的相对活跃位置；C.trend只要求“不是连续3个有效日下降”，单日回升即可满足，它没有证明净资金流入或较长趋势持续。负例N09前5日C每天通过，N07也4/5日通过；简单再加5日成交持续要求仍可能放行它们。N10前10/20日C通过仅10%/5%，N05为30%/15%，较长成交持续性有研究价值，但早期分位NULL会污染比较。

Top3成交占比前10日均值正例19.3%、负例23.8%，不同产业天然集中度不同，不能把4.5个百分点均值差当普适阈值。**四个负例原确认的250日Top3历史分位全部NULL**；所有负例事件期88日也全NULL，不能证明“龙头过度集中导致误报”。这是DATA_LIMITATION。增强E4的条件是历史分位<0.90，不是Top3成交占比<90%，两者不能混用。''')

lag_rows = []
for d in CASES:
    if d['case']['case_type'] != 'positive': continue
    m = d['metrics']; lag_rows.append([d['case']['case_id'], m['S1_lag_observed'], m['S2_lag_observed'],
        *[d['groups'][g]['first_pass_in_event'] for g in ['A','B','C','D','enhancers']], d['first_all_groups_pass_in_event'], m['first_S2_date']])
section('滞后拆解：证据不连续，比固定多等一天更关键', '''各组分别第一次通过，不代表它们曾同时通过。下表把“各组首次满足”“五组首次同时满足”和最终确认分开；完整案例证据也有pre/post全窗首次满足日期。

P04五组事件期11月27日齐全、28日确认；P05 12月12日齐全、13日确认；P06 1月24日齐全、27日确认；P07 1月21日/22日；P08 1月9日/10日，已确认正例最终有效两日常只增加一个交易日。P10 6月19日首次齐全，6月27日才确认，中间条件失配，不能算固定“两日要求延迟6日”。

但P01/P03/P09都出现单日全组通过而次日断开，连续要求确实阻止了升级；P02 11月11日是S0→S1日，不能同时升级S2。是否应取消连续要求尚无证据，N08煤炭也曾只有单日全组通过而被拦住。

''' + mdtable(['案例', 'S1滞后', 'S2滞后', 'A首满足', 'B首满足', 'C首满足', 'D首满足', '增强首满足', '事件首次五组齐', '全窗首S2'], lag_rows))

churn_rows = []
churn_details = {}
for kind, label in [('positive','正例'),('negative','负例'),('ambiguous','模糊')]:
    selected = [d for d in CASES if d['case']['case_type'] == kind]
    counts = Counter(); counts.update({key:0 for key in ['S0→S1→S0','S1→S2→S3→S2','S2→S3→S2→S3','S4→S1']})
    for d in selected: counts.update(d['patterns'])
    exits = [t for d in selected for t in d['transition_evidence'] if t['to_state']=='S0']
    toggles = Counter(g for t in exits for g in t['candidate_groups_changed_to_false'])
    churn_details[kind] = {'patterns':dict(counts), 'candidate_failed':len(exits), 'exit_at_two_pass_groups':sum(t['candidate_group_count']==2 for t in exits), 'changed_group_counts':dict(toggles)}
    churn_rows.append([label,*[counts[key] for key in ['S0→S1→S0','S1→S2→S3→S2','S2→S3→S2→S3','S4→S1']],len(exits),sum(t['candidate_group_count']==2 for t in exits)])
section('状态反复：主要发生在候选，少数确认后反复恢复', '''全窗统计沿用同一版评估器：341次转换、276次反复、174次短反复、63个Freeze日。下表模式按压缩的实际转移序列计数，可重叠，不等于转换总数；窗口首日用存档previous_state接入，不漏掉首日转移。

''' + mdtable(['类型','S0→S1→S0','S1→S2→S3→S2','S2→S3→S2→S3','S4→S1','候选失败关闭','失败时仍2票'],churn_rows) + '''

**候选来回占主体。** 138次候选失败中80次仍有2/5票（58.0%），单日跌破3票立即退出。按前一交易日到失败日的TRUE→FALSE翻转，C5广度出现78次、C4成交50次、C3胜率48次、C2相对收益46次、C1短期排名32次；一次退出可能多组变化，不能相加当退出数。C5还有全A基准动态比较，不宜仅归因自身广度崩溃。

确认后的S2→S3→S2→S3集中在P04、P07、P08（合计4个模式）。退出用短期RS斜率、排名恶化、三日广度下降的2/3条件；恢复重新要求五组确认2日，存在同类短期信息两头切换。候选单日退出与确认恢复应分别研究滞回，而非统一把所有等待天数加长。''')

section('S3/S4：能纠正负窗口S2，无法宣称退潮时机准确', '''从原确认计，N10连续S2 3日、N07 5日、N09 8日、N05 9日；随后分别第3/5/8/9个交易日进入S3，第6/9/11/15日进入S4。若从各自负事件开始计，首次S3需5/4/2/2日；不能把事件内2日S2误说成原确认后2日就退出。当前没有“错误S2连续20日”的负例证据。

正例也可能快速进入S3：P04原确认后5日、P05后5日，P06/P07后11日，P08后19日；P04/P07/P08出现恢复后再转弱。它们提示短期回撤容易触发转弱，但**缺少独立、冻结的结构转弱参考日，不能断言S3或S4过早/过晚**，也不能量化Retirement Timing优劣。

每次S3/S4触发的true/false/null原子证据及此前一天计数已归档。S3至少确认驻留3日且弱化连续2日；S4在S3内退潮连续3日，恢复需确认连续2日。错误确认后有纠正能力不代表确认质量合格；较慢S4也可能来自防抖，不应凭事后曲线直接缩短等待。''')

atomic_ids = ['C4.mean20','C4.intensity','C5.up','C5.ma20','A.return','A.rank','B.win5','B.win10','C.percentile','C.trend','D.up','D.ma20','D.newhigh','E1','E2','E3','E4.not_high','E4','E5']
atomic_display = []
for rid in atomic_ids:
    r=MATRIX_BY_ID[rid]; cl,why=classification(rid)
    atomic_display.append([rid,pct(r['positive_case_equal_pass_rate_all_days']),pct(r['negative_case_equal_pass_rate_all_days']),pct(r['ambiguous_case_equal_pass_rate_all_days']),
        f"{float(r['positive_negative_difference_all_days'])*100:+.1f}pp",r['positive_false'],r['negative_pass'],r['positive_edge_failures'],r['positive_null']+'/'+r['negative_null'],cl,why])
section('原子规则分级：保留信息价值，研究重复计票和饱和', '''A类是当前发展集中相对高区分信息，B类有作用但需研究阈值或时间结构，C类弱区分/证据不足/结构需重看，D类反复造成升级阻塞、优先研究。均为DIAGNOSTIC CLASSIFICATION，不是正式删除或调整名单；D类不等于已证明净损害。

**确认结构有重复信息。** D.newhigh与E3的实际字段、比较对象及布尔判定在全部450事件案例日完全相同；C2与A.return也重复。增强票数不能当独立证据件数。E2严格“大于三日前”在广度100%时必然失败，正例P01/P03/P04共13个饱和FALSE日；但不少由E1+E3补足，不能把这13日直接算作漏报。

E4正例仅53/244日有已知历史分位，负例0/88日，差异被历史长度和事件日期污染。E5本来不计增强票，保持NULL，不把deferred解释成正式失败。

''' + mdtable(['原子规则','正例通过','负例通过','模糊通过','差值','正例FALSE','负例TRUE','正例边缘','正/负NULL','类','判断'],atomic_display))

CANDIDATES = [
 {'priority':1,'name':'重审B高胜率的一票否决，保留强度但研究多日积累',
  'cases':'P03/P05/P09/P10；恢复另见P06/P07/P08；风险反例N08',
  'count':'7正例25个非S2日；真正可升级8日/4例；P10事件28/28日B失败',
  'current':'win5≥0.8 OR win10≥0.7，作为S2全部AND中的强制组',
  'interpretation':'短胜率门槛过滤波动型领涨，区分差仅14.9pp却有绝对否决权；不是每次TRUE都持续',
  'direction':'候选研究：以更长相对强势/广度持续证据补充B；比较保留硬门槛、分层确认或证据组合。先写有限方案，不直接设新数值',
  'improve':'间歇领涨的召回及确认滞后', 'worsen':'更多煤炭等短脉冲被放行；降低确认稳定性',
  'risk':'已用25例发现方向，具体阈值很容易迎合P10；必须新holdout检验'},
 {'priority':2,'name':'用成交历史持续性区分当前放量与积累，研究两阶段确认',
  'cases':'N05/N07/N09/N10；对照P04/P05/P06/P07/P08',
  'count':'4负例相关原确认；仅N10为事件内新误确认。前10日C频率正52%/负37.5%；N09前5日仍100%',
  'current':'成交分位≥0.6 AND 非连续三日下降，只检查当前；candidate C4为均值或强度OR',
  'interpretation':'候选成交组正负差6.4pp；未三日连降并不等于长期持续；5日简单持续也可能无效',
  'direction':'研究S1证据积累→S2确认，成交分位/广度/中期RS的多日联合持续；不把当天RS20>0当充分中期证据',
  'improve':'减少一次共振造成的确认，提高稳定性', 'worsen':'真主线启动更晚，突然转强的P04等可能漏掉',
  'risk':'前20日部分负例C低受早期NULL污染；P05/N07同一确认，不能据小组均值固定阈值'},
 {'priority':3,'name':'候选进入与退出采用不同确认强度，降低S0/S1横跳',
  'cases':'全部25例；漏报P01/P02/P03/P09，负例N01/N03/N04/N08',
  'count':'117个S0→S1→S0模式；138次候选失败中80次仍2票；C5翻转78次',
  'current':'候选至少3/5票；S1单日candidate FALSE即S0，重新TRUE又开生命周期',
  'interpretation':'3→2票可立刻关闭；相对全A的日广度与成交切换易形成多次生命周期',
  'direction':'研究进入/退出滞回、短观察缓冲或候选证据持续；不增加统一综合分',
  'improve':'候选稳定性、生命周期可读性及少量确认机会', 'worsen':'候选池滞留弱板块，反应变慢',
  'risk':'模式有窗口重复计数，不能以次数最大化减横跳而牺牲失效响应'},
 {'priority':4,'name':'增强证据去重，并研究广度饱和时的趋势保持',
  'cases':'全部25例D.newhigh/E3；饱和正例P01/P03/P04；原确认N05/N07/N09/N10',
  'count':'450事件案例日两条完全相同；正例E2有13个100%→100%失败日；负例E4 88日NULL',
  'current':'D.newhigh与E3同一新高增长；E2要求MA60严格增长；E4至少160观测；E5不计票',
  'interpretation':'五组不是五份独立信息；饱和与低历史可用性使名义增强结构改变',
  'direction':'研究独立证据家族与去重；饱和时区分维持高广度和扩散停止；仅在证据真实可得时使用集中度',
  'improve':'解释可靠性，减少重复证据放行和饱和误拒', 'worsen':'独立证据更少可能严重提高漏报；允许高位保持又可能滞留顶端',
  'risk':'不能按NULL当TRUE；13个饱和日未必实际阻塞，去重净效果未知'},
 {'priority':5,'name':'分开研究转弱、恢复与重新入场，避免短期信号双向切换',
  'cases':'P04/P07/P08；退出对照N05/N07/N09/N10；P05/P06生命周期再入',
  'count':'正例3个S1→S2→S3→S2、4个S2→S3→S2→S3模式；负例原确认后3/5/8/9日S3',
  'current':'弱化2/3组连续2日且驻留≥3；恢复用S2五组连续2日；S4后candidate即可S1',
  'interpretation':'确认和恢复共享高门槛，弱化偏短期；S4后又能单日重开，可能造成阶段与生命周期抖动',
  'direction':'研究恢复专用持续证据、转弱/退潮的幅度与时间分层；先补独立退潮参考日，再比较时机',
  'improve':'减少确认后反复，改善生命周期质量与失效解释', 'worsen':'可能推迟负例退出，或错过二波恢复',
  'risk':'没有早/晚退潮标准答案，不能靠事后最高点拟合退出规则'}]
section('Top 5优化候选：只列实验方向，不执行', '''以下均由多个案例重复证据提出，收益与代价一起保留。没有生成新rule_version，没有重算替代状态路径，也没有把“建议”写进Production。

''' + '\n\n'.join(f"### {c['priority']}. {c['name']}\n\n**问题与证据：** {c['interpretation']}。涉及{c['cases']}；{c['count']}。\n\n**当前条件：** {c['current']}。\n\n**值得测试：** {c['direction']}。\n\n**可能改善：** {c['improve']}。**可能恶化：** {c['worsen']}。\n\n**过拟合/数据风险：** {c['risk']}。" for c in CANDIDATES))

section('新Holdout设计：25例已经是练习题，不能再当期末考试', '''**本轮只冻结设计约束，不选最终案例、不运行。** 待候选方案获得单独授权后，在开发集设计有限实验；规则、参数和指标合同全部冻结并保留哈希后，才揭封新holdout输入。

1. 至少10正、10负、5模糊；每类覆盖科技/制造/消费/金融/周期及上涨、震荡、回撤环境。正例兼顾突然启动与缓慢积累，负例包含强脉冲、宽幅反弹、龙头独涨和成交退热，不由新规则输出决定入选。
2. 与当前25例的行业、事件及pre/post窗口不重叠；同一产业链/同一行情阶段的高度相关事件按episode分组隔离。优先使用未参加规则诊断的历史区间，不能换行业名字继续复用同一波行情。保留排除清单与选择理由。
3. 独立标注人只用公开同期行情/产业证据及白名单原始观测，不看S0—S4输出；锁定标签、event/pre/post窗口、expected_behavior、数据版本、PIT与参考退潮日。模糊标签只用于鲁棒性，绝不算命中。
4. 验证同时报告正例事件检测、事件新误确认与继承S2、确认滞后及删失、Churn、生命周期质量、独立参考退潮时机。事先定义可接受权衡与统计分母，不能单看总准确率或综合分。
5. 每例认证完整warmup，缺失保留NULL/Freeze；effective PIT与knowledge未验证状态诚实继承。固定代码和数据后一次运行并至少5例确定性重跑；所有失败都保留。揭封后该holdout不得继续调参再宣称泛化，应另建下一版holdout。

是否值得进入正式Rule Calibration：**研究方向值得立项，当前正式Gate不允许进入。** 本轮完成的是诊断；G5仍FAIL，没有独立验证集结果。''')

impact_rows = [[r['security_id'],r['industry'],r['warmup_member_days'],r['related_cases'],pct(r['max_one_security_weight_equal_member'])] for r in IMPACT]
section('13项影响：集中涉及6例，全球0.242%不能替代局部评估', '''通过已有Production artifact的历史SW2021成员快照逐日映射，13项在84个warmup交易日均属相应行业。8只直接落到当前案例的5个行业、6个案例：P01电子3只，P07机械设备2只，N06纺织服饰1只，P06计算机1只，N05/A01传媒共1只。另5只不在案例行业，但通过全A基准、全市场广度、总成交和横截面排名间接影响所有案例。

电子3只占最小成员数469的0.640%，机械设备2/572为0.350%；纺织服饰1/106为0.943%，传媒1/130为0.769%。这些只是成员权重上界，不是收益或成交影响：成交集中可能更大，价格缺失无法计算真实改变量。未证明影响极小。

''' + mdtable(['证券','历史行业','warmup成员日','相关案例','单只等成员权重最大值'],impact_rows) + '''

这13项是认证响应字节不一致，不是停牌/不存在，也不一定表示指定窗口价格发生变化。**另一个更大的限制是整个早期84日状态预热缺失**：当前报告的cold轨迹没有使用已认证的5369只重新生成完整warmup，所以99.758454%是请求认证覆盖，不是当前状态重放预热覆盖。C60早期缺样本、E4长期分位不足以及冷checkpoint继承不能被小比例掩盖。

以上6例加注直接证券WARMUP_SENSITIVE；P02/P03/P04/P05等无直接13项也可能受84日初始化影响。全部状态路径资格均WARMUP_SENSITIVE，不把后期窗口自动认证为无warmup偏差。没有新provider请求或补值。''')

section('置信度与结构、阈值、数据问题分开处理', '''**HIGH CONFIDENCE DIAGNOSTIC** 指可直接从存档证据验证的机制事实：冻结B门槛、存档25例的满足频率与合法状态资格、D/E3完全重复、E5不计票、候选退出实际票数以及原S2计数。它不表示这些频率可推广，也不表示warmup完整。

**WARMUP_SENSITIVE / LOW CONFIDENCE** 包括：P01/P02的C分位NULL归因、E4组间可用性差异、任何漏报中可被完整预热消除的比例、13项实际数据影响、完整新规则召回/误报收益、S3/S4早晚和小样本持续性差异。

- 结构型：全部AND赋予B绝对否决；D/E3重复；C.trend只排除短连降；候选进入/退出对称单日开关；转弱与恢复共享易波动信息。
- 阈值型：B离散胜率、A横截面排名、C成交分位的边缘与严重失败并存。P10 win10最接近也只有0.5，对0.7差0.2；不能说改一点就能补齐。明确数值margin：大于/大于等于用实际减阈值，小于/小于等于用阈值减实际；0margin在严格比较仍可失败。
- 数据型：缺84日初始化、13项认证字节不可恢复、E4历史长度不齐、deferred结构证据。NULL与FALSE分开，不把NULL填0。

边缘带仅作描述：排名一步1/30、win5一步0.2/win10一步0.1、相对收益50bp、广度2个百分点、新高1个成员、成交占比距均值10%、强度0.1、成交分位一步（至少0.025）。各case保存减半/加倍敏感性，不是推荐新阈值；布尔/组规则没有虚构数字margin。

敏感性核查：去掉跨标签重叠日后，D差34.9pp、新高32.9pp、B16.5pp、C4 6.5pp，主要排序未翻转。逐一留出一个案例，D差32.1—39.3pp，B8.1—19.0pp，C4 0.3—9.9pp；这些区间不是置信区间，不消除行情共因。边缘带减半/标准/加倍，正例近似失败日从0变7再到17，7日中只有3日合法处于可升级S1；不能用“边缘”标签支持统一降阈值。''')

section('模糊样本：保留解释空间，不用来装饰命中率', mdtable(['案例','行业','事件S2日','全窗首S2','主要约束','资格'],
 [[d['case']['case_id'],d['case']['sector'],d['metrics']['event_confirmed_days'],d['metrics']['first_S2_date'],
   max(d['groups'],key=lambda g:d['groups'][g]['false_days']+d['groups'][g]['null_days']),d['confidence']] for d in CASES if d['case']['case_type']=='ambiguous']) + '''

A01传媒事件有9日S2；窗口首个S2在2024-12-16是继承状态，实际生命周期确认更早，已按checkpoint溯源。A02通信只在事件后6月30日确认；A03/A04/A05未确认。A04/A05都有单日五组满足但不能连续升级，说明取消两日要求也会改变模糊集，不能只追求正例成绩漂亮。''')

audit_values = [
 ('起始SHA',START),('最终SHA','最终交付归档提交由FINAL_DELIVERY.json与本报告Git提交定位；不把提交自身SHA写入自身内容'),
 ('Casebook',SUMMARY['casebook_version']+'；'+SUMMARY['casebook_checksum']),('当前覆盖率','5369/5382=99.758454%认证请求；完整warmup资格不存在'),
 ('13项影响','历史映射8只→5行业/6例；另5只影响全A基准；实际幅度未知'),('正样本','S1 10/10；全窗S2 6/10；事件S2 5/10'),
 ('负样本','事件S2 4/10；新误确认1/10；11案例行业日'),('模糊样本','5例；1例事件S2；不计准确率'),
 ('S1判别力','candidate正75.0%/负44.4%，C4仅6.4pp差异'),('A判别力','61.7%/45.3%；16.4pp'),('B判别力','33.0%/18.1%；14.9pp'),
 ('C判别力','49.3%/29.4%；19.9pp；NULL分列'),('D判别力','67.9%/33.2%；34.7pp'),('Enhancer判别力','68.0%/30.6%；37.4pp，时间可用性混杂'),
 ('Atomic判别力','完整矩阵含候选/确认/弱化/退潮，本文主原子逐条解释'),('主要阻塞','B唯一非S2 25日/7例，可升级8日/4例；早期C含NULL'),
 ('主要误报路径','1新确认+3继承；四次相关原确认五组均满足'),('滞后归因','分别列各组首次、同时满足、计数与合法前态；未反事实调参'),
 ('Churn','341转换/276反复/174短反复；117个S0→S1→S0模式'),('S3/S4','负例原确认后3/5/8/9日S3；早晚参考缺失'),
 ('高判别力','D、新高扩散、E2、候选相对强度；发展集描述'),('低判别力','C4、E1；E4无法比较'),('高漏报风险','B否决；冷启动C；E2饱和尚未证实净损害'),
 ('高误报风险','短期共振与缺少持续证据；继承S2退出问题'),('结构问题','AND/重复信息/候选开关/恢复与退出'),('阈值问题','边缘和严重失败分列，不统一降门槛'),
 ('数据问题','84日初始化、13项字节、E4历史长度/deferred'),('Top5候选','B否决、成交积累/两阶段、候选滞回、增强独立/饱和、恢复退出分层'),
 ('候选风险','召回/误报/迟延/滞留/过拟合/证据不足逐项列'),('Holdout','新10正/10负/5模糊，episode及窗口隔离，规则冻结后揭封'),
 ('正式Rule Calibration','当前不进入；诊断方向值得立项，候选净收益未知')]
section('31项交付核查与隔离状态', mdtable(['序号','交付项','结果'],[[i+1,k,v] for i,(k,v) in enumerate(audit_values)]) + '''

rule_version = mainline_v2.2.1_state_completion_v1；parameter_profile = industry_trend_v221_state_completion_v1。pit_level=effective_pit；knowledge_time_unverified=true。G1/G2/G3/G4=PASS（沿用未重验），G5=FAIL。

production_writes=0；未修改正式规则、profile、状态机、生产数据、17:00自动化、Sites或UI。新增只读诊断脚本与报告；生产对象前后整表数量和校验对照另存隔离证据，项目优化留痕仅追加独立public记录。

交付核验：关键指标已从原档独立复算；只读诊断重复运行7个输出逐字节一致。可复算笔记已顺序执行Python单元并保留真实输出（当前环境Jupyter内核通信不可用）。HTML通过结构及数据校验；环境无Chromium，浏览器视觉、来源弹窗与交互尚未验证。项目优化记录已追加并查询核实，验收为“部分通过”。

**已经定位重复的阻塞与误确认路径；下一步是测试有限候选，不能宣称规则优化完成。** 剩余待验证问题是：稳定的中期积累/成交特征能否同时减少漏报与误报，且不显著增加确认滞后。''')

lead = sections[0][1].split('\n\n', 1)[0]
sections[0] = (sections[0][0], sections[0][1].split('\n\n', 1)[1])
markdown = '# ' + TITLE + '\n\n' + lead + '\n\n' + '\n\n'.join(header+'\n\n'+body for header,body in sections)+'\n'
(D / 'RULE_DIAGNOSTIC_REPORT.md').write_text(markdown)
(D / 'calibration_candidates.json').write_text(json.dumps(CANDIDATES,ensure_ascii=False,indent=2)+'\n')
(D / 'rule_classification.json').write_text(json.dumps({r['rule_id']:{'class':classification(r['rule_id'])[0],'judgment':classification(r['rule_id'])[1],'status':'DIAGNOSTIC_ONLY'} for r in MATRIX},ensure_ascii=False,indent=2)+'\n')
(D / 'persistence_summary.json').write_text(json.dumps(PERSISTENCE,ensure_ascii=False,indent=2)+'\n')
(D / 'churn_attribution.json').write_text(json.dumps(churn_details,ensure_ascii=False,indent=2)+'\n')

# Canonical report package: one reader; no separate hand-built HTML renderer.
source = {'id':'diagnostic_evidence','label':'冻结25例诊断与逐日规则证据',
          'href':SOURCE+'reports/milestone-d-rule-diagnostic/RULE_DIAGNOSTIC_REPORT.md',
          'query':{'engine':'Python stdlib','language':'python',
            'url':SOURCE+'scripts/mainline/rule_diagnostic.py',
            'description':'仅读取冻结casebook、diagnostic-v2逐日快照/规则/状态/checkpoint与已有历史成员artifact；不重算替代状态、不访问行情provider',
            'tables_used':['casebook_v1_20261002_25','historical-blind-v1-20261002-diagnostic-v2/*.json.gz','causal_context.json.gz','real_memberships.json'],
            'filters':{'population':'10 positive, 10 negative, 5 ambiguous; frozen event windows','rule_matrix':'case-equal mean TRUE/all event sessions; NULL separately','status':'DIAGNOSTIC_ONLY'},
            'metric_definitions':{'pass_rate':'Each case TRUE/event days, then equal mean within frozen label','sole_blocker':'Four groups TRUE and one FALSE/NULL, non-S2; legal S1 eligibility separately','persistence':'Prior N sessions excluding actual lifecycle confirmation; case-equal means'}}}
db = sqlite3.connect(':memory:')
db.execute('create table rule_evidence(case_id text, case_type text, trade_date text, in_event integer, rule_id text, passed integer)')
with gzip.open(D / 'atomic_daily_evidence.csv.gz', 'rt') as stream:
    evidence = list(csv.DictReader(stream))
db.executemany('insert into rule_evidence values(?,?,?,?,?,?)',
    [(r['case_id'],r['case_type'],r['trade_date'],int(r['event']=='True'),r['rule_id'],
      1 if r['passed']=='True' else 0 if r['passed']=='False' else None) for r in evidence])
db.execute('create table context_C(object_id text, session_index integer, trade_date text, passed integer)')
context = json.loads(gzip.decompress((ROOT / 'reports/milestone-d-baseline-v1/runs/historical-blind-v1-20261002-diagnostic-v2/causal_context.json.gz').read_bytes()))
indices = Counter(); context_rows=[]; anchor_index={}
for row in sorted(context['rows'],key=lambda r:(r['snapshot']['object_id'],r['snapshot']['as_of_date'])):
    oid=row['snapshot']['object_id']; day=row['snapshot']['as_of_date']; i=indices[oid]; indices[oid]+=1
    passed=next(r['passed'] for r in row['rules'] if r['rule_id']=='C')
    context_rows.append((oid,i,day,1 if passed is True else 0 if passed is False else None)); anchor_index[(oid,day)]=i
db.executemany('insert into context_C values(?,?,?,?)',context_rows)
db.execute('create table anchors(case_id text, case_type text, object_id text, session_index integer)')
db.executemany('insert into anchors values(?,?,?,?)',[(d['case']['case_id'],d['case']['case_type'],d['case']['object_id'],
    anchor_index[(d['case']['object_id'],d['persistence_at_S2'][0]['anchor']['date'])]) for d in CASES
    if d['case']['case_type'] in ['positive','negative'] and d['metrics']['event_confirmed_days']>0])
matrix_sql = '''WITH per_case AS (
 SELECT case_id, case_type, rule_id,
        SUM(CASE WHEN passed=1 THEN 1 ELSE 0 END)*1.0/COUNT(*) AS rate,
        COUNT(*) AS event_days
 FROM main.rule_evidence
 WHERE in_event=1 AND case_type IN ('positive','negative')
   AND rule_id IN ('C4','A','B','C','D','enhancers')
 GROUP BY case_id,case_type,rule_id
)
SELECT rule_id,case_type,AVG(rate) AS rate,COUNT(*) AS cases,
       SUM(event_days) AS cohort_case_days
FROM per_case GROUP BY rule_id,case_type ORDER BY rule_id,case_type;'''
persistence_sql = '''WITH sizes(n) AS (VALUES(5),(10),(20)), per_case AS (
 SELECT a.case_id,a.case_type,s.n,
        SUM(CASE WHEN r.passed=1 THEN 1 ELSE 0 END)*1.0/COUNT(*) AS rate
 FROM main.anchors a CROSS JOIN sizes s
 JOIN main.context_C r ON r.object_id=a.object_id
  AND r.session_index<a.session_index AND r.session_index>=a.session_index-s.n
 GROUP BY a.case_id,a.case_type,s.n HAVING COUNT(*)=s.n
)
SELECT n,case_type,AVG(rate) AS rate,COUNT(*) AS cases
FROM per_case GROUP BY n,case_type ORDER BY n,case_type;'''
(D / 'diagnostic_queries.sql').write_text('-- SQLite in-memory; imported frozen archives, no production database.\n'+matrix_sql+'\n\n'+persistence_sql+'\n')
matrix_query_results=db.execute(matrix_sql).fetchall()
persistence_query_results=db.execute(persistence_sql).fetchall()
source['query']['url']=SOURCE+'scripts/mainline/rule_diagnostic_report.py'
source['query']['sql']=matrix_sql
source['query']['engine']='SQLite (in-memory imports of frozen file evidence)'
source['query']['language']='sql'
source['query']['tables_used']=['main.rule_evidence']
source['query']['description']+='；诊断表由只读Python读取原始规则/状态与固定案例标注，SQL独立重算图表频率；手工根因解释不属于行情数据'
persistence_source={**source,'id':'persistence_evidence','label':'冻结上下文的确认前成交持续性',
    'query':{**source['query'],'sql':persistence_sql,'tables_used':['main.context_C','main.anchors'],
      'description':'197×31冻结上下文C证据，与5正/4负事件S2案例实际确认锚点联接；只看确认前5/10/20交易日，NULL保留在分母'}}
blocks = [{'id':'title','type':'markdown','body':'# '+TITLE+'\n\n'+lead}]
tables = []
table_specs = {
  2: ('matrix_lookup', '规则判别力表', 'matrix_lookup', display_matrix,
      [('rule','规则组','text'),('positive_rate','正例通过','percent'),('negative_rate','负例通过','percent'),('ambiguous_rate','模糊通过','percent'),('gap_pp','差值（百分点）','number'),('positive_failures','正例FALSE','number'),('negative_passes','负例TRUE','number'),('positive_nulls','正例NULL','number'),('sole_blocker_days','唯一阻塞日','number'),('class','诊断类','text')], 'gap_pp'),
  3: ('positive_lookup','真主线漏报表','positive_lookup',positive_rows,
      [('case_id','案例','text'),('industry','行业','text'),('first_S1','S1首日','text'),('first_S2','S2首日','text'),('event_S2_days','事件S2天','number'),('primary_blocker','首要阻塞','text'),('margin_example','阈值距离例','text'),('near_miss_days','近似失败日','number'),('reason','初步根因','text')], 'case_id'),
  15: ('negative_lookup','假主线误报表','negative_lookup',negative_rows,
      [('case_id','案例','text'),('industry','行业','text'),('event_S2_date','事件首S2','text'),('event_S2_days','事件S2天','number'),('new_false_confirmations','事件新确认','number'),('inherited_S2','继承S2','text'),('anchor_date','原确认','text'),('continuous_S2_sessions','原连续S2日','number'),('entry_groups','原确认五组','text'),('first_S3','首S3','text'),('first_S4','首S4','text')], 'case_id')}
for index,(header,body) in enumerate(sections):
    if index in table_specs:
        tid,title,dataset,data,columns,sort = table_specs[index]
        # Replace the same overview table with the native table, do not duplicate.
        body = body.split('\n\n| ', 1)[0]
        tables.append({'id':tid,'title':title,'dataset':dataset,'sourceId':'diagnostic_evidence',
            'defaultSort':{'field':sort,'direction':'desc' if sort=='gap_pp' else 'asc'},
            'columns':[{'field':field,'label':label,**({'type':'text'} if fmt=='text' else {'format':fmt})} for field,label,fmt in columns]})
    blocks.append({'id':f'section_{index}','type':'markdown','body':header+'\n\n'+body,'sourceId':'diagnostic_evidence'})
    if index in table_specs: blocks.append({'id':'table_block_'+str(index),'type':'table','tableId':table_specs[index][0]})
    if index == 2: blocks.append({'id':'discrimination_chart_block','type':'chart','chartId':'discrimination_chart'})
    if header.startswith('## 持续性比较'): blocks.append({'id':'persistence_chart_block','type':'chart','chartId':'persistence_chart'})
chart_rows = [{'group':LABELS[rid], 'cohort':'正样本' if kind=='positive' else '负样本','rate':rate,
               'cases':cases,'cohort_case_days':days,'case_equal':True}
              for rid,kind,rate,cases,days in matrix_query_results]
persist_chart = [{'lookback':str(n)+'日','cohort':'正样本事件期S2' if kind=='positive' else '负样本事件期S2','rate':rate,'cases':cases}
                for n,kind,rate,cases in persistence_query_results]
for row in chart_rows:
    rid=next(rid for rid,label in LABELS.items() if label==row['group'])
    expected=float(MATRIX_BY_ID[rid][('positive' if row['cohort']=='正样本' else 'negative')+'_case_equal_pass_rate_all_days'])
    assert abs(row['rate']-expected)<1e-12
for row in persist_chart:
    expected=next(r['C_pass_frequency'] for r in PERSISTENCE if str(r['window'])+'日'==row['lookback'] and r['cohort']==row['cohort'])
    assert abs(row['rate']-expected)<1e-12
charts = [
 {'id':'discrimination_chart','title':'事件期规则组满足频率','type':'bar','dataset':'discrimination', 'sourceId':'diagnostic_evidence','valueFormat':'percent',
  'palette':{'kind':'categorical','name':'blue'}, 'encodings':{'x':{'field':'group','type':'nominal','label':'规则组'},'y':{'field':'rate','type':'quantitative','label':'案例等权通过频率'},'color':{'field':'cohort','type':'nominal','label':'冻结标签'}}},
 {'id':'persistence_chart','title':'确认前成交组持续满足频率','type':'bar','dataset':'persistence','sourceId':'persistence_evidence','valueFormat':'percent',
  'palette':{'kind':'categorical','name':'blue'},'encodings':{'x':{'field':'lookback','type':'nominal','label':'确认前窗口'},'y':{'field':'rate','type':'quantitative','label':'C满足比例（案例等权）'},'color':{'field':'cohort','type':'nominal','label':'事件S2组'}}}]
artifact = {'surface':'report','manifest':{'version':1,'surface':'report','title':TITLE,'description':'冻结25例规则体检；DIAGNOSTIC_ONLY；未实施校准',
    'generatedAt':'2026-10-02T15:10:06Z','blocks':blocks,'charts':charts,'tables':tables,'sources':[source,persistence_source]},
    'snapshot':{'version':1,'status':'ready','generatedAt':'2026-10-02T15:10:06Z','datasets':{'discrimination':chart_rows,'persistence':persist_chart,
        **{spec[2]:spec[3] for spec in table_specs.values()}}},'sources':[source,persistence_source]}
(D / 'artifact.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n')
(D / 'report_source_notes.md').write_text('''# Report source and design notes

Audience: product stakeholders. Delivery: portable HTML because user prohibits Sites.
Required structure maps to Chinese scorecard/Executive Summary, findings sections,
Top5 and Holdout next steps, confidence/data caveats and open research question.
Exact rule and case lookup use tables, not charts; atomic daily details use CSV.gz.
Charts: grouped bars, categorical positive/negative label colors, zero-based rate
axes, 12 rule-rate observations and 6 prior-C-rate observations. Same units per
chart. No accuracy score and no causal claim. Adjacent narratives define denominators
and caution on cold warmup, inherited S2, overlapping cases and selected anchors.
All canonical sources resolve to the authorized GitHub branch; no machine paths,
credentials or invented source SQL. All raw data are frozen diagnostic-v2 artifacts.
''')
print(json.dumps({'report_sections':len(sections),'markdown_characters':len(markdown),'charts':2,'status':'DIAGNOSTIC_ONLY'}))
