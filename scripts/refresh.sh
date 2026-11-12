#!/usr/bin/env bash
# Phase 1 stub: runs the checks (download -> load -> dbt build). Phase 4 adds analyses, models, charts, screenshots, findings.
set -euo pipefail
cd "$(dirname "$0")/.."
./scripts/check.sh "$@"
