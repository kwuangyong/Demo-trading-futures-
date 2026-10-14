#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements-core.txt
if ! .venv/bin/python -m pip install -r requirements.txt; then
  echo 'Vnstock install failed. Synthetic practice remains available; real-data modes require vnstock.'
fi
exec .venv/bin/python run.py --open "$@"
