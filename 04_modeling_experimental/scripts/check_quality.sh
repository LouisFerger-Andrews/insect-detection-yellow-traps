#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "[1/3] Python compile checks"
cd "$REPO_ROOT"
python3 -m compileall 03_application/backend/app 04_modeling_experimental/src

echo "[2/3] Frontend build checks"
cd "$REPO_ROOT/03_application/frontend"
npm run build

echo "[3/3] Backend pytest checks"
cd "$REPO_ROOT/03_application/backend"
if [[ -x ".venv/bin/python" ]]; then
  if .venv/bin/python -c "import pytest" >/dev/null 2>&1; then
    .venv/bin/python -m pytest -q
  else
    echo "Skipping backend pytest: pytest is not installed in 03_application/backend/.venv"
  fi
else
  echo "Skipping backend pytest: 03_application/backend/.venv/bin/python not found"
fi

echo "Quality checks completed."
