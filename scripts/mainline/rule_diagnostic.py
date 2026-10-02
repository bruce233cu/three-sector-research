"""Read frozen archived evidence; never call a provider, engine or production writer.

All outputs are DIAGNOSTIC_ONLY. Rates describe these correlated development
cases, not independent predictive accuracy. Nulls are retained separately.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOK = ROOT / 'reports/milestone-d-baseline-v1/casebook.json'
RUN = ROOT / 'reports/milestone-d-baseline-v1/runs/historical-blind-v1-20261002-diagnostic-v2'
GROUPS = ['A', 'B', 'C', 'D', 'enhancers']
CHILDREN = {'A': ['A.return', 'A.rank'], 'B': ['B.win5', 'B.win10'],
            'C': ['C.percentile', 'C.trend'], 'D': ['D.up', 'D.ma20', 'D.newhigh'],
            'enhancers': ['E1', 'E2', 'E3', 'E4']}
METRICS = ['sector_return', 'benchmark_return', 'rs_5', 'rs_10', 'rs_20',
           'win_5', 'win_10', 'turnover_share', 'turnover_intensity', 'turnover_pct_60',
           'up_ratio', 'above_ma20', 'above_ma60', 'new_high_60',
           'top3_turnover_share', 'top3_turnover_pct_250']


def read(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write(path, data):
    raw = (json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)


def csv_write(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fields, lineterminator='\n'); writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False, separators=(',', ':'))
                         if isinstance(v, (list, dict)) else v for k, v in row.items()})
    raw = stream.getvalue().encode('utf-8')
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)


def average(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def rules(row):
    return {v['rule_id']: v for v in row['rules']}


def date(row):
    return row['snapshot']['as_of_date']


def margin(rule):
    a, b = rule['actual_value'], rule['threshold']
    if isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float)) and not isinstance(b, bool):
        if rule['operator'] in ('>', '>='): return a - b
        if rule['operator'] in ('<', '<='): return b - a
    return None


def edge_tolerance(rule, row):
    """Descriptive sensitivity bands, never substitute for frozen thresholds.

    Rank/win: one observed grid step; return: 50bp; breadth: 2pp;
    new-high: one member; turnover share: 10% of the comparison mean;
    intensity: 0.1; turnover percentile: one valid observation (floor .025).
    Boolean and unavailable rules have no numeric edge classification.
    """
    metric = rule['metric']; snap = row['snapshot']
    if metric in ('rs_5_pct', 'rs_10_pct'): return 1 / 30
    if metric == 'win_5': return .2
    if metric == 'win_10': return .1
    if metric.startswith('rs_') or metric == 'rs5_slope': return .005
    if metric == 'new_high_60': return 1 / max(snap['member_count'], 1)
    if metric in ('up_ratio', 'above_ma20', 'above_ma60'): return .02
    if metric == 'turnover_share':
        return abs(rule['threshold']) * .1 if isinstance(rule['threshold'], (int, float)) else None
    if metric == 'turnover_intensity': return .1
    if metric == 'turnover_pct_60':
        valid = snap.get('metric_coverage_json', {}).get(metric, 0) * 60
        return max(.025, 1 / valid) if valid else None
    if metric == 'top3_turnover_pct_250': return 1 / max(snap.get('metric_diagnostics', {}).get(metric, {}).get('valid', 1), 1)
    return None


def edge(rule, row, scale=1):
    m, tol = margin(rule), edge_tolerance(rule, row)
    return rule['passed'] is False and m is not None and tol is not None and m >= -tol * scale - 1e-12


def streak(flags):
    best = current = 0
    for flag in flags:
        current = current + 1 if flag else 0; best = max(best, current)
    return best


def transition_sequence(rows):
    if not rows: return []
    seq = [rows[0]['state']['previous_state']]
    for row in rows:
        if row['state']['transition']:
            seq.append(row['state']['state'])
    return seq


def path_count(seq, path):
    return sum(seq[i:i + len(path)] == path for i in range(len(seq) - len(path) + 1))


def evidence_at(row):
    r = rules(row)
    return {'date': date(row), 'state': row['state']['state'],
            'previous_state': row['state']['previous_state'],
            'transition': row['state']['transition'],
            'consecutive': row['state']['consecutive_days'],
            'frozen': row['state']['stage_frozen'], 'reason': row['state']['reason'],
            'groups': {g: r[g]['passed'] for g in GROUPS},
            'atoms': [{**r[i], 'signed_margin': margin(r[i]),
                       'edge_failure': edge(r[i], row), 'edge_band': edge_tolerance(r[i], row)}
                      for g in GROUPS for i in CHILDREN[g]],
            'snapshot': {k: row['snapshot'].get(k) for k in METRICS}}


def persistence(history, anchor):
    index = next(i for i, row in enumerate(history) if date(row) == anchor)
    output = {'anchor': evidence_at(history[index]), 'prior': {}, 'forward': {}}
    for n in [1, 3, 5, 10, 20]:
        # Excludes confirmation date: only information available before entry.
        rows = history[max(0, index - n):index]
        item = {'requested_days': n, 'observed_days': len(rows), 'complete': len(rows) == n,
                'start': date(rows[0]) if rows else None, 'end': date(rows[-1]) if rows else None,
                'metrics': {}, 'group_pass_frequencies': {}}
        for k in METRICS:
            values = [row['snapshot'].get(k) for row in rows]
            known = [v for v in values if v is not None]
            item['metrics'][k] = {'known': len(known), 'null': len(values) - len(known),
                                 'mean': average(known), 'min': min(known) if known else None,
                                 'max': max(known) if known else None,
                                 'first_to_last': known[-1] - known[0] if len(known) >= 2 else None}
        for k in GROUPS + ['confirm', 'candidate', 'E1', 'E2', 'E3', 'D.newhigh', 'C.percentile', 'C.trend', 'B.win5', 'B.win10']:
            values = [rules(row)[k]['passed'] for row in rows]
            item['group_pass_frequencies'][k] = {'pass': values.count(True), 'false': values.count(False),
                                                'null': values.count(None), 'all_days_rate': values.count(True) / len(values) if values else None}
        item['daily_relative_win_rate'] = average([int(row['snapshot']['sector_return'] > row['snapshot']['benchmark_return'])
                                                  for row in rows if row['snapshot']['sector_return'] is not None and row['snapshot']['benchmark_return'] is not None])
        output['prior'][str(n)] = item
        forward = history[index + 1:index + 1 + n]
        output['forward'][str(n)] = {'observed_days': len(forward), 'complete': len(forward) == n,
            'metrics_mean': {k: average([row['snapshot'].get(k) for row in forward]) for k in METRICS},
            'last_vs_anchor': {k: forward[-1]['snapshot'][k] - history[index]['snapshot'][k]
                               if forward and forward[-1]['snapshot'].get(k) is not None and history[index]['snapshot'].get(k) is not None else None for k in METRICS},
            'state_path': [row['state']['state'] for row in forward]}
    exits = []
    for offset, row in enumerate(history[index + 1:], 1):
        transition = row['state']['transition']
        if transition and transition['to_state'] in ('S3', 'S4', 'S1'):
            exits.append({'sessions_after_anchor': offset, **evidence_at(row)})
            if len(exits) == 3: break
    output['first_exit_events'] = exits
    output['S2_contiguous_sessions_from_anchor'] = next((j for j, row in enumerate(history[index:]) if row['state']['state'] != 'S2'), len(history) - index)
    return output


def build(output, production_membership=None):
    output.mkdir(parents=True, exist_ok=True)
    book = read(BOOK); metric_list = read(RUN / 'case_metrics.json'); metrics_by_id = {m['case_id']: m for m in metric_list}
    context = read(RUN / 'causal_context.json.gz'); history_by_object = defaultdict(list)
    for row in context['rows']: history_by_object[row['snapshot']['object_id']].append(row)
    for rows in history_by_object.values(): rows.sort(key=date)
    atoms = []; blockers = []; details = []; matrix_values = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    source_checks = {}; event_labels = defaultdict(set); group_states = Counter(); frozen_hashes = {}
    for case in book['cases']:
        cid = case['case_id']; kind = case['case_type']; archive = read(RUN / (cid + '.json.gz'))
        rows = archive['rows']; event = [r for r in rows if case['start_date'] <= date(r) <= case['end_date']]
        m = metrics_by_id[cid]; source_checks[cid] = hashlib.sha256((RUN / (cid + '.json.gz')).read_bytes()).hexdigest()
        frozen_hashes.update(archive['manifest']['frozen_code_file_hashes'])
        for row in event:
            event_labels[(row['snapshot']['object_id'], date(row))].add(kind)
            rr = rules(row)
            for rule in row['rules']:
                rid = rule['rule_id']; matrix_values[rid][kind][cid].append((rule['passed'], edge(rule, row)))
        for row in rows:
            rr = rules(row); in_event = row in event
            for rule in row['rules']:
                atoms.append({'case_id': cid, 'case_type': kind, 'trade_date': date(row), 'event': in_event,
                    'industry': case['sector'], 'state': row['state']['state'], 'previous_state': row['state']['previous_state'],
                    'frozen': row['state']['stage_frozen'], 'rule_id': rule['rule_id'], 'metric': rule['metric'],
                    'actual_value': rule['actual_value'], 'threshold': rule['threshold'], 'operator': rule['operator'],
                    'passed': rule['passed'], 'reason': rule['reason'], 'signed_margin': margin(rule),
                    'edge_band': edge_tolerance(rule, row), 'edge_failure': edge(rule, row)})
            if not in_event: continue
            passed = [g for g in GROUPS if rr[g]['passed'] is True]
            failed = [g for g in GROUPS if rr[g]['passed'] is False]
            unknown = [g for g in GROUPS if rr[g]['passed'] is None]
            missing = failed + unknown
            eligible = row['state']['previous_state'] == 'S1' and not row['state']['stage_frozen'] and row['state']['reason'] != 'freeze_recovery_first_session_no_transition'
            if row['state']['state'] != 'S2':
                failures = [rr[i] for g in missing for i in CHILDREN[g] if rr[i]['passed'] is False]
                blockers.append({'case_id': cid, 'case_type': kind, 'trade_date': date(row),
                    'industry': case['sector'], 'state': row['state']['state'], 'eligible_S1': eligible,
                    'frozen': row['state']['stage_frozen'], 'pass_count': len(passed), 'passed_groups': passed,
                    'failed_groups': failed, 'null_groups': unknown, 'last_blocker': missing[0] if len(missing) == 1 else None,
                    'last_blocker_status': rr[missing[0]]['passed'] if len(missing) == 1 else None,
                    'near_miss': len(passed) == 4 and bool(failures) and all(edge(r, row) for r in failures) and not unknown,
                    'near_miss_half_band': len(passed) == 4 and bool(failures) and all(edge(r, row, .5) for r in failures) and not unknown,
                    'near_miss_double_band': len(passed) == 4 and bool(failures) and all(edge(r, row, 2) for r in failures) and not unknown,
                    'confirm': rr['confirm']['passed'], 'consecutive': row['state']['consecutive_days'], 'state_reason': row['state']['reason'],
                    'atomic_false': [{'rule_id': r['rule_id'], 'actual': r['actual_value'], 'threshold': r['threshold'], 'margin': margin(r), 'edge': edge(r, row)} for r in failures]})
        own = [b for b in blockers if b['case_id'] == cid]
        group_info = {}
        for g in GROUPS:
            values = [rules(row)[g]['passed'] for row in event]
            group_info[g] = {'pass_days': values.count(True), 'false_days': values.count(False), 'null_days': values.count(None),
                'false_longest_streak': streak([v is False for v in values]),
                'first_pass_in_event': next((date(row) for row in event if rules(row)[g]['passed'] is True), None),
                'sole_blocker_nonS2_days': sum(b['last_blocker'] == g for b in own),
                'sole_blocker_eligible_S1_days': sum(b['last_blocker'] == g and b['eligible_S1'] for b in own),
                'blocker_frequency_all_event_days': (values.count(False) + values.count(None)) / len(values),
                'sole_blocker_frequency_nonS2_days': sum(b['last_blocker'] == g for b in own) / len(own) if own else None}
        atomic_info = {}
        for rid in [i for g in GROUPS for i in CHILDREN[g]]:
            failed_rows = [row for row in event if rules(row)[rid]['passed'] is False]
            numeric_rows = [row for row in failed_rows if margin(rules(row)[rid]) is not None]
            margins = [margin(rules(row)[rid]) for row in numeric_rows]
            example = max(numeric_rows, key=lambda row: margin(rules(row)[rid])) if numeric_rows else (failed_rows[0] if failed_rows else None)
            atomic_info[rid] = {'false_days': len(failed_rows), 'null_days': sum(rules(row)[rid]['passed'] is None for row in event),
                'edge_days': sum(edge(rules(row)[rid], row) for row in failed_rows),
                'severe_numeric_days': sum(margin(rules(row)[rid]) is not None and not edge(rules(row)[rid], row) for row in failed_rows),
                'false_longest_streak': streak([rules(row)[rid]['passed'] is False for row in event]),
                'median_failure_margin': statistics.median(margins) if margins else None,
                'closest_failure': {'date': date(example), 'actual': rules(example)[rid]['actual_value'],
                    'threshold': rules(example)[rid]['threshold'], 'margin': margin(rules(example)[rid]), 'edge': edge(rules(example)[rid], example)} if example else None}
        seq = transition_sequence(rows)
        patterns = {'S0→S1→S0': path_count(seq, ['S0', 'S1', 'S0']),
                    'S1→S2→S3→S2': path_count(seq, ['S1', 'S2', 'S3', 'S2']),
                    'S2→S3→S2→S3': path_count(seq, ['S2', 'S3', 'S2', 'S3']),
                    'S4→S1': path_count(seq, ['S4', 'S1'])}
        transition_evidence = []
        history = history_by_object[case['object_id']]
        history_index = {date(row): i for i, row in enumerate(history)}
        for row in rows:
            tr = row['state']['transition']
            if tr:
                rr = rules(row)
                index = history_index[date(row)]
                prior_rules = rules(history[index - 1]) if index else {}
                transition_evidence.append({'date': date(row), **tr,
                    'true_rules': [k for k, v in rr.items() if v['passed'] is True],
                    'false_rules': [k for k, v in rr.items() if v['passed'] is False],
                    'null_rules': [k for k, v in rr.items() if v['passed'] is None],
                    'candidate_groups': {g: rr[g]['passed'] for g in ['C1', 'C2', 'C3', 'C4', 'C5']},
                    'candidate_group_count': sum(rr[g]['passed'] is True for g in ['C1', 'C2', 'C3', 'C4', 'C5']),
                    'candidate_groups_changed_to_false': [g for g in ['C1', 'C2', 'C3', 'C4', 'C5'] if prior_rules.get(g, {}).get('passed') is True and rr[g]['passed'] is False],
                    'candidate_atomic_changed_to_false': [g for g in ['C1', 'C2', 'C3', 'C4.mean20', 'C4.intensity', 'C5.up', 'C5.ma20'] if prior_rules.get(g, {}).get('passed') is True and rr[g]['passed'] is False],
                    'prior_session': evidence_at(history[index - 1]) if index and tr['to_state'] in ('S2', 'S3', 'S4') else None,
                    'consecutive': row['state']['consecutive_days']})
        history = history_by_object[case['object_id']]
        anchors = []
        if m['first_S2_date']:
            observed = next(row for row in rows if date(row) == m['first_S2_date'])
            confirmed_at = observed['state']['checkpoint'].get('lifecycle', {}).get('confirmed_at')
            # An observed S2 at a left boundary is not a new confirmation.
            anchors.append(confirmed_at or m['first_S2_date'])
        for row in event:
            tr = row['state']['transition']
            if tr and tr['to_state'] == 'S2' and date(row) not in anchors: anchors.append(date(row))
        confirm_days = [row for row in event if rules(row)['confirm']['passed'] is True]
        detail = {'case': case, 'metrics': {k: v for k, v in m.items() if k not in ('timeline', 'post_confirmation_diagnostics')},
            'groups': group_info, 'atomic_blockers': atomic_info,
            'nonS2_event_days': len(own), 'eligible_S1_nonS2_days': sum(b['eligible_S1'] for b in own),
            'pass4_nonS2_days': sum(b['pass_count'] == 4 for b in own),
            'pass3_nonS2_days': sum(b['pass_count'] == 3 for b in own),
            'pass4_eligible_S1_days': sum(b['pass_count'] == 4 and b['eligible_S1'] for b in own),
            'near_miss_days': sum(b['near_miss'] for b in own),
            'near_miss_band_sensitivity': {str(s): sum(b[k] for b in own) for s, k in [(0.5, 'near_miss_half_band'), (1, 'near_miss'), (2, 'near_miss_double_band')]},
            'confirm_true_event_days': len(confirm_days),
            'confirm_true_nonS2_evidence': [evidence_at(row) for row in confirm_days if row['state']['state'] != 'S2'],
            'first_all_groups_pass_in_event': date(confirm_days[0]) if confirm_days else None,
            'first_group_pass_in_case_window': {g: next((date(row) for row in rows if rules(row)[g]['passed'] is True), None) for g in GROUPS},
            'first_all_groups_pass_in_case_window': next((date(row) for row in rows if rules(row)['confirm']['passed'] is True), None),
            'confirm_event_longest_calendar_session_streak': streak([rules(row)['confirm']['passed'] is True for row in event]),
            'patterns': patterns, 'transition_evidence': transition_evidence,
            'event_state_days': dict(Counter(row['state']['state'] for row in event)),
            'persistence_at_S2': [persistence(history, anchor) for anchor in anchors]}
        details.append(detail)
    matrix = []
    for rid, by_type in matrix_values.items():
        row = {'rule_id': rid}
        for kind in ['positive', 'negative', 'ambiguous']:
            by_case = by_type[kind]; values = [v for vals in by_case.values() for v, e in vals]
            known = len(values) - values.count(None)
            rates = [sum(v is True for v, e in vals) / len(vals) for vals in by_case.values()]
            known_rates = [sum(v is True for v, e in vals) / sum(v is not None for v, e in vals) for vals in by_case.values() if any(v is not None for v, e in vals)]
            row.update({kind + '_cases': len(by_case), kind + '_days': len(values), kind + '_pass': values.count(True),
                kind + '_false': values.count(False), kind + '_null': values.count(None), kind + '_known': known,
                kind + '_case_equal_pass_rate_all_days': average(rates),
                kind + '_case_equal_pass_rate_known_days': average(known_rates), kind + '_cases_with_known': len(known_rates),
                kind + '_pooled_pass_rate_all_days': values.count(True) / len(values) if values else None,
                kind + '_pooled_pass_rate_known_days': values.count(True) / known if known else None,
                kind + '_edge_failures': sum(e for vals in by_case.values() for v, e in vals)})
        row['positive_negative_difference_all_days'] = row['positive_case_equal_pass_rate_all_days'] - row['negative_case_equal_pass_rate_all_days']
        pr, nr = row['positive_case_equal_pass_rate_known_days'], row['negative_case_equal_pass_rate_known_days']
        row['positive_negative_difference_known_days'] = pr - nr if pr is not None and nr is not None else None
        positive_rates = [sum(v is True for v, e in vals) / len(vals) for vals in by_type['positive'].values()]
        negative_rates = [sum(v is True for v, e in vals) / len(vals) for vals in by_type['negative'].values()]
        leave_one = [average(positive_rates[:i] + positive_rates[i + 1:]) - average(negative_rates) for i in range(len(positive_rates))]
        leave_one += [average(positive_rates) - average(negative_rates[:i] + negative_rates[i + 1:]) for i in range(len(negative_rates))]
        row['leave_one_case_gap_min'] = min(leave_one)
        row['leave_one_case_gap_max'] = max(leave_one)
        row['positive_sole_blocker_days'] = sum(b['case_type'] == 'positive' and b['last_blocker'] == rid for b in blockers)
        row['positive_sole_blocker_case_count'] = len({b['case_id'] for b in blockers if b['case_type'] == 'positive' and b['last_blocker'] == rid})
        matrix.append(row)
    # Historical membership: no present-day sector lookup and no price reacquisition.
    membership = read(ROOT / 'reports/milestone-d-baseline-v1/data/daily_memberships.json.gz')
    if production_membership:
        import zipfile
        with zipfile.ZipFile(production_membership) as z: membership.update(json.loads(z.read('real_memberships.json')))
    failures = read(ROOT / 'reports/milestone-d-warmup-resume/evidence/failed_items_classified.json')
    impact = []
    for fail in failures:
        sid = fail['security_id']; mapping = defaultdict(list)
        for d, member in sorted(membership.items()):
            if not '2024-05-06' <= d <= '2025-06-30': continue
            for oid, securities in member['members'].items():
                if sid in securities: mapping[oid].append(d)
        for oid, dates in mapping.items():
            cases = [c for c in book['cases'] if c['object_id'] == oid]
            counts = [len(membership[d]['members'][oid]) for d in dates if '2024-05-06' <= d <= '2024-08-30']
            impact.append({'security_id': sid, 'object_id': oid,
                'industry': next((c['sector'] for c in cases), history_by_object[oid][0]['snapshot']['industry_name'] if oid in history_by_object else oid),
                'first_membership_date': min(dates), 'last_membership_date': max(dates),
                'warmup_member_days': sum('2024-05-06' <= d <= '2024-08-30' for d in dates),
                'warmup_member_count_min': min(counts) if counts else None,
                'max_one_security_weight_equal_member': 1 / min(counts) if counts else None,
                'related_cases': [c['case_id'] for c in cases], 'status': 'WARMUP_SENSITIVE' if cases else 'BENCHMARK_INDIRECT_SENSITIVE',
                'effect_size': None, 'effect_size_reason': 'Missing certified prices/amount; membership share is not price/turnover impact.'})
    for d in details:
        related = [x for x in impact if d['case']['case_id'] in x['related_cases']]
        d['missing_warmup_security_ids'] = [x['security_id'] for x in related]
        # Snapshot margins can be verified, but every archived state path inherits
        # a cold checkpoint. Do not certify later cases as warmup-independent.
        d['confidence'] = 'WARMUP_SENSITIVE'
        d['data_sensitivity'] = {'direct_sector_missing_warmup': bool(related),
            'all_cases_missing_84_day_initialization': True,
            'E4_history_count_at_event_start': next(row for row in history_by_object[d['case']['object_id']] if date(row) == d['case']['start_date'])['snapshot'].get('metric_diagnostics', {}).get('top3_turnover_pct_250'),
            'causal_effect_of_13_or_84_days': 'NOT_IDENTIFIABLE_WITHOUT_CERTIFIED_FULL_WARMUP'}
    overlaps = [{'object_id': oid, 'trade_date': day, 'labels': sorted(labels)} for (oid, day), labels in event_labels.items() if len(labels) > 1]
    matrix_no_overlap = []
    for rid in matrix_values:
        out = {'rule_id': rid}
        for kind in ['positive', 'negative', 'ambiguous']:
            case_rates = []
            for detail in details:
                if detail['case']['case_type'] != kind: continue
                case = detail['case']; vals = [rules(row)[rid]['passed'] for row in history_by_object[case['object_id']]
                    if case['start_date'] <= date(row) <= case['end_date'] and len(event_labels[(case['object_id'], date(row))]) == 1]
                if vals: case_rates.append(vals.count(True) / len(vals))
            out[kind + '_case_equal_pass_rate_all_days'] = average(case_rates)
        out['positive_negative_difference'] = out['positive_case_equal_pass_rate_all_days'] - out['negative_case_equal_pass_rate_all_days']
        matrix_no_overlap.append(out)
    checks = []
    for path, expected in frozen_hashes.items():
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        checks.append({'path': path, 'expected': expected, 'actual': actual, 'unchanged': actual == expected})
    assert all(c['unchanged'] for c in checks), 'Frozen business implementation differs from archived manifest'
    assert len(details) == 25 and Counter(d['case']['case_type'] for d in details) == {'positive': 10, 'negative': 10, 'ambiguous': 5}
    assert len(context['rows']) == 197 * 31
    assert all(len({date(r) for r in rows}) == len(rows) for rows in history_by_object.values())
    assert all(row['positive_pass'] + row['positive_false'] + row['positive_null'] == row['positive_days'] for row in matrix)
    summary = {'status': 'DIAGNOSTIC_ONLY', 'set_role': 'DEVELOPMENT / DIAGNOSTIC SET',
        'start_sha': '95ba63c6dbc6b1cad82e84a9c3403f7dc353fc35', 'casebook_version': book['casebook_version'],
        'casebook_checksum': book['checksum'], 'rule_version': book['rule_version'], 'parameter_profile': book['parameter_profile'],
        'source_run': RUN.name, 'source_case_checksums': source_checks, 'aggregate': read(RUN / 'aggregate_metrics.json'),
        'matrix_scope': 'event windows only; case-equal TRUE/all event days primary, known-only and pooled secondary; NULL never silently excluded',
        'edge_bands': edge_tolerance.__doc__, 'overlapping_cross_label_sector_days': overlaps,
        'event_case_days': dict(Counter(b['case_type'] for case in book['cases'] for b in [{'case_type': case['case_type']}] for row in history_by_object[case['object_id']] if case['start_date'] <= date(row) <= case['end_date'])),
        'production_writes': 0, 'G1': 'PASS', 'G2': 'PASS', 'G3': 'PASS', 'G4': 'PASS', 'G5': 'FAIL',
        'pit_level': 'effective_pit', 'knowledge_time_unverified': True, 'rules_recalculated': False,
        'warmup_certified_requests': 5369, 'warmup_total_requests': 5382, 'warmup_coverage': 5369 / 5382,
        'frozen_code_checks': checks, 'context_source_sha256': hashlib.sha256((RUN / 'causal_context.json.gz').read_bytes()).hexdigest(),
        'new_holdout_run': False, 'calibration_executed': False}
    csv_write(output / 'atomic_daily_evidence.csv.gz', atoms)
    csv_write(output / 'event_blockers.csv', blockers)
    csv_write(output / 'rule_discrimination_matrix.csv', matrix)
    csv_write(output / 'rule_matrix_overlap_sensitivity.csv', matrix_no_overlap)
    csv_write(output / 'warmup_security_membership_impact.csv', impact)
    write(output / 'case_diagnostics.json.gz', details)
    write(output / 'diagnostic_summary.json', summary)
    return summary, details, matrix, impact


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/milestone-d-rule-diagnostic')
    parser.add_argument('--production-membership-zip', type=Path)
    args = parser.parse_args()
    summary, _, _, _ = build(args.output, args.production_membership_zip)
    print(json.dumps({'status': summary['status'], 'cases': 25, 'production_writes': 0, 'summary_checksum': digest(summary)}, ensure_ascii=False))
