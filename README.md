# Campus Pulse

Higher-education outcomes analytics on free US government data: College Scorecard and IPEDS in a DuckDB warehouse modeled with dbt,
SQL analyses with proper statistics, earnings models with SHAP, and a four-page Streamlit dashboard.

*Phase 4 (dashboard, brief, one-command refresh) is still to come; this README is updated after each phase.*

## Problem
Families choose colleges with sticker prices and rankings, but the question is what a school delivers for students like theirs:
earnings, completion and debt. The Scorecard publishes this for thousands of institutions, but in files with 3,000+ columns, mixed
missing-value codes and changing layouts. This project makes it queryable and tests four questions:
1. Does paying more buy higher earnings?
2. Which sectors finish what they start, and at what debt cost?
3. How do Florida public universities compare with peers, and who over- or under-performs?
4. What predicts earnings, and how well for institutions the model has never seen?

## Architecture
```mermaid
flowchart LR
  A[Scorecard zip + IPEDS files] --> B[download.py<br/>manifest + sha256]
  B --> C[load.py<br/>text -> NULL cleaning -> parquet]
  C --> D[(DuckDB raw schema)]
  D --> E[dbt staging -> intermediate -> marts<br/>18 tests]
  E --> F[analyses + models<br/>phases 2-3]
```
Raw files are read as text, cleaned in one place, loaded to DuckDB and modeled by dbt at institution-year grain.

## Tech stack
| Tool | Used for | Why |
|---|---|---|
| Python 3.12, pandas | download and load | streaming zip reads, simple text cleaning |
| DuckDB | warehouse | file database, fast analytics SQL, no server or container |
| dbt-duckdb | modeling and tests | lineage, documented columns, tests as code |
| pytest, ruff | quality | fast checks on every commit |
| GitHub Actions | CI | runs the offline fixture check |

## Quick start
Prerequisites: Python 3.12, `uv`. About 600 MB of downloads.
```bash
uv venv --python 3.12 && uv pip install -r requirements.txt
./scripts/check.sh --fixture   # offline, uses data/fixtures
./scripts/check.sh             # real data (downloads once)
```

## Results
Full tables in [RESULTS.md](RESULTS.md) (generated, each number with its command).

| Question | Finding (real data) | Command |
|---|---|---|
| Warehouse | 6 releases, 9,536 institutions, 44,408 institution-years | `python -m campuspulse.warehouse_stats` |
| 1. Price vs earnings | Spearman 0.30 (0.28 to 0.32); 0.17 (0.15 to 0.19) after controls; +8.7% earnings per $10k net price (7.7% to 9.6%) | `python -m campuspulse.analyses` |
| 2. Completion and debt | 2022 release, median completion public 40%, nonprofit 58%, for-profit 64%; enrollment-weighted 49%, 64%, 48% | `python -m campuspulse.analyses` |
| 3. Florida | public 4-year earnings gap $3,004 (CI -$3,779 to $8,601, n=12); completion +15.9 points | `python -m campuspulse.analyses` |
| 4. What predicts earnings | grouped-CV R2(log) 0.74, MAE $5,438 (5,284 to 5,593) vs $8,503 sector-by-state baseline; 2022 holdout MAE $7,784 vs $10,665 | `python -m campuspulse.model` |
| Sector differences | Kruskal-Wallis on earnings epsilon-squared 0.34 (0.32 to 0.36), n=7,998 | `python -m campuspulse.analyses` |

## How it works
- **Release choice by measurement.** Only some Scorecard releases populate 10-year earnings; I counted them (DECISIONS D-02).
- **Missing-value strings.** `NULL`, `PrivacySuppressed`, `PS`, `NA` all become NULL and suppression is counted per column.
- **Idempotent load.** Tables rebuild in one transaction; a test compares checksums across two runs.
- **Clustered bootstrap.** Institutions appear in several releases, so intervals resample whole institutions (seeded).
- **Honest validation.** Institution-grouped folds and a 2022 temporal holdout against same-year baselines; a leakage test and a permuted-target test.
- **SHAP that adds up.** SHAP additivity is asserted (native categorical splits were mis-attributed, DECISIONS D-11).
- **Honest controls.** Admission rate is missing for most 2-year and for-profit schools; I use a missing flag instead of dropping them.

## Testing
`pytest` (17 tests: load, download, SQL vs pandas recomputation, bootstrap, leakage, fold integrity, SHAP additivity) and `dbt build` (18 data tests). `scripts/check.sh --fixture` runs both offline.

## Design decisions and trade-offs
See [DECISIONS.md](DECISIONS.md). Top three: earnings releases are not the newest ones; Carnegie comes from IPEDS because Scorecard's
is empty; no Power BI/Tableau (Windows-only / account), Streamlit instead.

## Known limits and next steps
Earnings describe a cohort that entered about a decade before the release. Dollars are nominal. Suppression removes small institutions.

## Project structure
```
campuspulse/  download, load, config, warehouse_stats, analyses, stats, model, results
analysis/     four SQL analyses
reports/      CSV outputs and findings_auto.md

dbt/          models (staging, intermediate, marts), seeds, custom tests
scripts/      check.sh, refresh.sh, build_dictionary.py, make_fixture.py
data/fixtures committed 399-institution sample
docs/         data-dictionary.md, INTERVIEW-NOTES.md, pr/
```
