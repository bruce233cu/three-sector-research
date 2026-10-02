"""Offline only. Frozen labels are consumed outside the engine input interface."""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'))
from mainline.backtest.runner import run
if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--casebook-dir',type=Path,default=ROOT/'reports/milestone-d-baseline-v1')
    a.add_argument('--output',type=Path,required=True)
    a.add_argument('--run-id',required=True)
    a.add_argument('--warmup-dir',type=Path)
    args=a.parse_args();run(ROOT,args.casebook_dir,args.output,args.run_id,warmup_directory=args.warmup_dir)
