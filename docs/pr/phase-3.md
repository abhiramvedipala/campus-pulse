## What it built
OLS (HC3), ridge/lasso/elastic net, gradient boosting; grouped-CV and temporal validation vs two baselines; SHAP; residual analysis; Florida over/under table.

## How it was tested
`pytest` (17 tests incl. leakage, permuted-target, fold integrity, SHAP additivity); `scripts/check.sh --fixture`; `python -m campuspulse.model` on real data (about 25 s).

## Numbers produced (RESULTS.md, phase 3)
Grouped CV: R2(log) 0.74, MAE $5,438 vs $8,503 baseline. Temporal 2022: MAE $7,784 vs $10,665. SHAP-lasso rank rho 0.75.

## Open questions
Temporal holdout re-uses institutions; release year is a dollar-base effect (D-11).
