#!/usr/bin/env bash
# Lint + tests + load + dbt build + analyses/models. `--fixture` runs offline on data/fixtures/.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"; [ -x "$PY" ] || PY=python
FIX=""; if [ "${1:-}" = "--fixture" ]; then FIX="--fixture"; fi

"$PY" -m ruff check .
"$PY" -m pytest -q

if [ -n "$FIX" ]; then
  export CAMPUSPULSE_DB="$PWD/data/warehouse_fixture.duckdb" CP_ROW_FLOOR=250
else
  "$PY" -m campuspulse.download
fi
"$PY" -m campuspulse.load $FIX
(cd dbt && "$PY" -m dbt.cli.main build --profiles-dir .)

# Later phases append their steps here (analyses, models, charts).
for mod in analyses model; do
  if [ -f "campuspulse/$mod.py" ]; then "$PY" -m "campuspulse.$mod" $FIX; fi
done
echo "check.sh OK ${FIX:-(real data)}"
