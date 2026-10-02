import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from mainline.backtest.runner import read,write,baseline_profile,load_inputs
from mainline.backtest.evaluator import evaluate_case,aggregate
from mainline.backtest.leak_checker import audit
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);a=p.parse_args()
    d=ROOT/'reports/milestone-d-baseline-v1';book=read(d/'casebook.json');profile,_=baseline_profile(ROOT)
    panel,members,dates,prov=load_inputs(d,profile)
    results=[evaluate_case(c,read(a.results/(c['case_id']+'.json.gz')),dates,
              book['expected_negative_stable_s2_min_sessions'],book['short_reversal_max_sessions']) for c in book['cases']]
    write(a.results/'case_metrics.json',results);write(a.results/'aggregate_metrics.json',aggregate(results))
    checks=audit(panel,members,dates,profile,read(a.results/'causal_context.json.gz'))
    write(a.results/'future_leakage_checks.json',checks)
    print('case metrics and temporal audit saved',flush=True)
