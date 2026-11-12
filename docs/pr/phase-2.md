## What it built
Four SQL analyses with bootstrap intervals, tests and effect sizes; CSV outputs, charts and auto-generated findings.

## How it was tested
`pytest` (10 tests: SQL vs pandas for four queries, bootstrap reproducibility); `scripts/check.sh --fixture`; `python -m campuspulse.analyses` on the real data (about 60 s).

## Numbers produced (RESULTS.md, phase 2)
Net price vs earnings: rho 0.30, partial 0.17, 8.7% per $10k. Florida public 4-year earnings gap $3,004 (CI crosses zero, n=12). Sector earnings differences: epsilon-squared 0.34.

## Open questions
Florida groups are small; UF-Online duplicates UF's earnings record (D-10).
