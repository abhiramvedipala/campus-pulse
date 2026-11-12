# Progress

## Done
- Phase 1: ingestion, DuckDB warehouse, dbt models/tests, data dictionary, check.sh, CI (branch `phase-1-ingest-warehouse`).

- Phase 2: SQL analyses, tests, charts, auto findings (branch `phase-2-sql-analyses`).
- Phase 3: models, validation, SHAP, residuals (branch `phase-3-modeling`).
- Phase 4: dashboard, screenshots, one-page brief + PDF, `make refresh` (branch `phase-4-dashboard-refresh`).

## Next
- Nothing: Definition of done reached except the items under Needs me.

## Needs me
- Create the GitHub repo and push: `gh repo create abhiramvedipala/campus-pulse` was blocked by a permission prompt in the build session.
  Run `gh repo create abhiramvedipala/campus-pulse --private --source=. --remote=origin --push`, then `git push --all`.
  Until then every phase is merged locally with a merge commit (same history shape as PRs).
- Streamlit Community Cloud deploy (needs your account): steps will be in the README after phase 4.
