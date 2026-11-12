"""Assemble RESULTS.md from the JSON/CSV files in reports/. Every number carries the command that made it."""

import argparse
import json

import pandas as pd

from . import config as C


def _load(rep, name):
    p = rep / name
    if not p.exists():
        return None
    return json.loads(p.read_text()) if p.suffix == ".json" else pd.read_csv(p)


def phase1(rep) -> list[str]:
    st, lt, cov = _load(rep, "warehouse_stats.json"), _load(rep, "load_timing.json"), _load(rep, "coverage_by_release.csv")
    if st is None:
        return []
    out = ["## Phase 1: warehouse", "", "| Measure | Value | Command |", "|---|---|---|"]
    rows = [
        ("Scorecard releases loaded", st["releases_loaded"], "python -m campuspulse.warehouse_stats"),
        ("Distinct institutions (all releases)", f"{st['distinct_institutions']:,}", "python -m campuspulse.warehouse_stats"),
        ("Rows in fct_institution_year", f"{st['rows_fct_institution_year']:,}", "python -m campuspulse.warehouse_stats"),
        ("Rows with non-suppressed 10-yr earnings", f"{st['rows_with_earnings']:,}", "python -m campuspulse.warehouse_stats"),
        ("IPEDS HD match rate", f"{st['ipeds_match_rate']:.1%}", "python -m campuspulse.warehouse_stats"),
        ("dbt tests (passed / total)", f"{st.get('dbt_tests_passed')} / {st.get('dbt_tests')}", "cd dbt && dbt build --profiles-dir ."),
        ("Net prices nulled (outside 0-100,000)", st["net_price_nulled_out_of_range"], "python -m campuspulse.warehouse_stats"),
        ("IPEDS files missing (404, tolerated)", len(st["ipeds_files_missing"]), "python -m campuspulse.download"),
    ]
    if lt:
        rows += [
            ("Load wall time (s)", lt["seconds"], "python -m campuspulse.load"),
            ("Warehouse size (MB)", lt["warehouse_mb"], "ls -l data/warehouse.duckdb"),
        ]
    out += [f"| {a} | {b} | `{c}` |" for a, b, c in rows]
    if cov is not None:
        out += [
            "",
            "Institutions and non-null share per release (`reports/coverage_by_release.csv`):",
            "",
            cov.to_markdown(index=False),
            "",
        ]
    sup = _load(rep, "suppression_by_column.csv")
    if sup is not None:
        key = ["MD_EARN_WNE_P10", "NPT4_PUB", "NPT4_PRIV", "C150_4", "C150_L4", "GRAD_DEBT_MDN", "ADM_RATE", "PCTPELL", "UGDS"]
        t = sup[sup.column_name.isin(key)].pivot(index="column_name", columns="release", values="suppressed_share")
        m = sup[sup.column_name.isin(key)].pivot(index="column_name", columns="release", values="missing_share")
        out += [
            "Share of rows privacy-suppressed (`PS`) per release (`reports/suppression_by_column.csv`):",
            "",
            t.map("{:.1%}".format).to_markdown(),
            "",
        ]
        out += [
            "Share of rows missing for any reason (suppressed, not available or not reported):",
            "",
            m.map("{:.1%}".format).to_markdown(),
            "",
        ]
    return out


def phase2(rep) -> list[str]:
    q1, q2, q3, kw, pw = (
        _load(rep, f)
        for f in [
            "q1_price_vs_earnings.csv",
            "q2_completion_debt.csv",
            "q3_florida_gaps.csv",
            "q4_kruskal_wallis.csv",
            "q4_pairwise_mannwhitney.csv",
        ]
    )
    if q1 is None:
        return []
    cmd = "`python -m campuspulse.analyses`"
    f = lambda d, cols, nd=3: d[cols].round(nd).to_markdown(index=False)  # noqa: E731
    ok = q1[q1.skipped.isna() | (q1.skipped.astype(str) == "")]
    out = [
        "## Phase 2: SQL analyses and tests",
        "",
        f"Command for every table below: {cmd}. Bootstrap = institution-clustered, seeded; reps in `reports/analysis_meta.json`.",
        "",
    ]
    out += [
        "### Q1 net price vs earnings (n = institutions; partial = after Pell, admission rate, state, year)",
        "",
        f(
            ok,
            [
                "cut",
                "group",
                "n_institutions",
                "spearman_raw",
                "raw_ci_lo",
                "raw_ci_hi",
                "spearman_residualised",
                "res_ci_lo",
                "res_ci_hi",
                "pct_earnings_per_10k",
                "pct_ci_lo",
                "pct_ci_hi",
            ],
            2,
        ),
        "",
    ]
    last = q2.release_year.max()
    t = q2[q2.institution_level.isna() & (q2.release_year == last)]
    out += [
        f"### Q2 completion and debt, {last} release (completion: unweighted median and enrollment-weighted)",
        "",
        f(
            t,
            [
                "sector",
                "n_institutions",
                "n_completion",
                "completion_unweighted_median",
                "completion_enrollment_weighted",
                "n_debt",
                "median_debt",
                "n_debt_to_earnings",
                "median_debt_to_earnings",
                "share_debt_to_earnings_above_half",
            ],
            3,
        ),
        "",
    ]
    g = q3[q3.release_year == q3.release_year.max()]
    out += [
        f"### Q3 Florida public vs non-Florida public peers, {int(g.release_year.max())} release (gap = Florida median minus peer median)",
        "",
        f(g, ["fl_group", "metric", "n_fl", "n_peers", "fl_median", "peer_median", "gap", "ci_lo", "ci_hi"], 3),
        "",
    ]
    out += [
        "### Q4 Kruskal-Wallis across sectors (latest release per institution)",
        "",
        f(kw, ["metric", "n", "H", "p_value", "epsilon_squared", "eps_ci_lo", "eps_ci_hi"], 3),
        "",
        "Pairwise Mann-Whitney with Holm correction and rank-biserial effect size:",
        "",
        f(pw, ["metric", "group_a", "group_b", "n_a", "n_b", "p_holm", "rank_biserial", "rb_ci_lo", "rb_ci_hi"], 3),
        "",
    ]
    return out


def phase3(rep) -> list[str]:
    met, meta, cmp = (
        _load(rep, "model_metrics.csv"),
        _load(rep, "model_meta.json"),
        _load(rep, "shap_vs_lasso.csv"),
    )
    if met is None:
        return []
    cmd = "`python -m campuspulse.model`"
    out = [
        "## Phase 3: models",
        "",
        f"Command for every table below: {cmd}. Target: log median earnings 10 years after entry (nominal dollars, release-year fixed effects). "
        f"Features: {', '.join(meta['features'])}. Excluded as leakage: {', '.join(meta['excluded_features'])}. Best by grouped-CV MAE: **{meta['best_model_by_grouped_cv_mae']}**.",
        "",
    ]
    for v in met.validation.unique():
        t = met[met.validation == v]
        piv = t.pivot(index="model", columns="metric", values="estimate")
        lo, hi = t.pivot(index="model", columns="metric", values="ci_lo"), t.pivot(index="model", columns="metric", values="ci_hi")
        tab = pd.DataFrame(
            {
                "R2 (log)": [f"{piv.loc[m, 'R2_log']:.3f} ({lo.loc[m, 'R2_log']:.3f}, {hi.loc[m, 'R2_log']:.3f})" for m in piv.index],
                "R2 (dollars)": [f"{piv.loc[m, 'R2_dollars']:.3f}" for m in piv.index],
                "MAE $": [
                    f"{piv.loc[m, 'MAE_dollars']:,.0f} ({lo.loc[m, 'MAE_dollars']:,.0f}, {hi.loc[m, 'MAE_dollars']:,.0f})"
                    for m in piv.index
                ],
                "MdAPE %": [
                    f"{piv.loc[m, 'MdAPE_pct']:.1f} ({lo.loc[m, 'MdAPE_pct']:.1f}, {hi.loc[m, 'MdAPE_pct']:.1f})" for m in piv.index
                ],
            },
            index=piv.index,
        )
        sav = t[t.metric == "MAE_dollars"].set_index("model")
        tab["MAE saving vs sector x state baseline (95% CI)"] = [
            f"{sav.loc[m, 'mae_saving_vs_sector_state']:,.0f} ({sav.loc[m, 'mae_saving_vs_sector_state_ci']})"
            if pd.notna(sav.loc[m, "mae_saving_vs_sector_state"])
            else "baseline"
            for m in tab.index
        ]
        out += [f"### {v} (n = {int(t.n_rows.iloc[0]):,} rows, {int(t.n_institutions.iloc[0]):,} institutions)", "", tab.to_markdown(), ""]
    out += [
        "### SHAP importance (gradient boosting, all data) vs lasso importance",
        "",
        cmp.round(3).to_markdown(index=False),
        "",
        f"SHAP-lasso rank Spearman rho = {meta['shap_lasso_rank_spearman']:.2f}. Lasso dropped: {', '.join(meta['lasso_dropped']) or 'none'}.",
        "",
    ]
    ols, diag = _load(rep, "ols_coefficients.csv"), _load(rep, "ols_diagnostics.json")
    if ols is not None:
        main = ols[~ols.term.str.startswith(("state_", "release_year_", "missingindicator_", "const"))]
        out += [
            "### OLS with HC3 robust standard errors (numeric terms are per 1 SD; categorical terms are vs the omitted level)",
            "",
            main.round(3).to_markdown(index=False),
            "",
            f"Diagnostics: R2 {diag['r2']:.3f}, Breusch-Pagan p = {diag['breusch_pagan_lm_p']:.1e} (heteroskedastic, hence robust SEs), Jarque-Bera p = {diag['jarque_bera_p']:.1e}, "
            f"residual skew {diag['residual_skew']:.2f}, condition number {diag['condition_number']:.0f}, max VIF {max(diag['vif_numeric'].values()):.1f}, max leverage {diag['max_leverage']:.3f}.",
            "",
        ]
    fl = _load(rep, "florida_over_under.csv")
    if fl is not None:
        out += [
            "### Florida over- and under-performers (mean out-of-fold residual %, public 4-year)",
            "",
            fl[fl.group == "Florida public 4-year"][["institution_name", "n_releases", "mean_resid_pct", "actual_last", "pred_last"]]
            .round(1)
            .to_markdown(index=False),
            "",
        ]
    return out


SECTIONS = [phase1, phase2, phase3]


def run(fixture: bool = False) -> None:
    rep = C.reports_dir(fixture)
    lines = ["# Results", "", "Generated by `python -m campuspulse.results` from `reports/`; do not edit by hand.", ""]
    for s in SECTIONS:
        lines += s(rep)
    (C.ROOT / ("RESULTS.md" if not fixture else "reports_fixture/RESULTS.md")).write_text("\n".join(lines) + "\n")
    print("wrote RESULTS.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true")
    run(ap.parse_args().fixture)
