#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/src"
python -m mainline.poc.run_phase1d \
  --output-dir reports/phase1d/runtime \
  --cache-dir .cache/mainline/phase1d
