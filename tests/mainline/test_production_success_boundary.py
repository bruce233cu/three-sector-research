"""Cached simulation data must not be promoted to a production success."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.parametrize("run_type,latest_success,reuse", [
    ("production", None, False),
    ("production", "2026-09-29", False),
    ("production", "2026-09-30", True),
    ("production_simulation", None, True),
])
def test_cached_success_requires_production_manifest(monkeypatch, tmp_path, run_type, latest_success, reuse):
    spec = importlib.util.spec_from_file_location("production_boundary", ROOT / "scripts/mainline/production_run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "OUT", tmp_path / "output")
    monkeypatch.setenv("MAINLINE_RUN_TYPE", run_type)
    monkeypatch.setenv("MAINLINE_TARGET_DATE", "2026-09-30")
    monkeypatch.setenv("CODE_COMMIT", "test-sha")
    monkeypatch.setenv("MAINLINE_PIPELINE_RUN_ID", "parent-test")
    context = {"calendar": ["2026-09-29", "2026-09-30"], "enabled": True,
               "existing_target": [{} for _ in range(31)], "latest_success": latest_success}
    calls = []
    def gateway(operation, **kwargs):
        calls.append((operation, kwargs))
        return context if operation == "context" else {}
    monkeypatch.setattr(module, "gateway", gateway)
    input_dir = tmp_path / "temporary_g3_input"
    input_dir.mkdir()
    for name in ("temporary_universe_intervals.json", "source_snapshots.json"):
        (input_dir / name).write_text("[]")
    profile = module.read(ROOT / "config/parameter_profile_industry_trend_v221_state_completion_v1.json")
    monkeypatch.setattr(module, "read", lambda _: profile)
    monkeypatch.setattr(module, "select_seed", lambda *a, **k: {"bootstrap_source": "database_checkpoint", "date": "2026-09-29"})
    def collector(*a, **k):
        raise RuntimeError("collector reached; no data was computed")
    monkeypatch.setattr(module.subprocess, "run", collector)
    if reuse:
        module.main()
    else:
        with pytest.raises(RuntimeError, match="collector reached"):
            module.main()
    succeeded = [args for op, args in calls if op == "attempt" and args["payload"]["phase"] == "succeeded"]
    assert bool(succeeded) == (reuse and run_type == "production")
