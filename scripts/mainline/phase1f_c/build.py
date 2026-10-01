"""Offline, allowlisted distribution builder. Never copies unrelated modules."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = Path(__file__).resolve().parent
BASE = "6391737d3398479f70e21d7eb4d8f12dbe1ddb1a"
SOURCE_FILES = [
    "src/mainline/__init__.py", "src/mainline/metrics/__init__.py", "src/mainline/metrics/sector.py",
    "src/mainline/providers/__init__.py", "src/mainline/providers/sws_history.py",
    "src/mainline/providers/base.py", "src/mainline/providers/fallback.py",
    "src/mainline/providers/tushare.py", "src/mainline/providers/akshare.py",
    "src/mainline/providers/eastmoney_window.py", "src/mainline/providers/phase1f_free.py",
    "src/mainline/poc/__init__.py", "src/mainline/poc/phase1f_c.py",
    "config/parameter_profile_industry_trend_v1.json",
    "tests/mainline/test_phase1f_c.py",
    "scripts/mainline/phase1f_d1_run.py",
]


def build():
    files = SOURCE_FILES + [str(p.relative_to(ROOT)) for p in BUNDLE.iterdir()
        if p.is_file() and p.name not in ["integrity.json"]]
    hashes = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(files)}
    payload = {"base_commit":BASE,"branch":"mainline-phase1e","files":hashes,
        "status":"execution_package_only; real_provider_POC_NOT_STARTED",
        "note":"source files copied verbatim, frozen formulas unchanged"}
    (BUNDLE/"integrity.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    out = ROOT/"artifacts"/"phase1f_c_package"
    out.mkdir(parents=True,exist_ok=True)
    path = out/"mainline_phase1f_c_external_poc.zip"
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as z:
        for f in sorted(files+[str((BUNDLE/"integrity.json").relative_to(ROOT))]):
            z.write(ROOT/f,"mainline_phase1f_c/"+f)
    print(path)
    print("SHA256",hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    build()
