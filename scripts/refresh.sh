#!/usr/bin/env bash
# One command, raw data to every table, chart, screenshot and brief:  make refresh   (or make refresh FIXTURE=1)
# download (skipped when the manifest matches) -> load -> dbt build -> stats -> dictionary -> analyses -> models
# -> screenshots -> findings (+PDF) -> RESULTS.md. Fails loudly on any dbt test failure (set -e).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-$PWD/.venv/bin/python}"; [ -x "$PY" ] || PY=python
FIX=""; if [ "${1:-}" = "--fixture" ]; then FIX="--fixture"; export CAMPUSPULSE_DB="$PWD/data/warehouse_fixture.duckdb" CP_ROW_FLOOR=250 CAMPUSPULSE_FIXTURE=1; fi
START=$(date +%s)

[ -z "$FIX" ] && "$PY" -m campuspulse.download
"$PY" -m campuspulse.load $FIX
(cd dbt && "$PY" -m dbt.cli.main build --profiles-dir .)
"$PY" -m campuspulse.warehouse_stats $FIX
"$PY" -m scripts.build_dictionary $FIX
"$PY" -m campuspulse.analyses $FIX
"$PY" -m campuspulse.model $FIX
"$PY" -m scripts.screenshots $FIX

ELAPSED=$(( $(date +%s) - START ))
REPORTS=reports; [ -n "$FIX" ] && REPORTS=reports_fixture
mkdir -p "$REPORTS"
printf '{"wall_seconds": %s, "mode": "%s", "excludes": "final findings and RESULTS.md assembly (about 5 s)"}\n' "$ELAPSED" "${FIX:-real}" > "$REPORTS/refresh_timing.json"
"$PY" -m scripts.build_findings $FIX
"$PY" -m campuspulse.results $FIX
echo "refresh OK in ${ELAPSED}s ${FIX:-(real data)}"
