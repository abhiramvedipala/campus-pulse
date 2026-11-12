"""Run analysis/*.sql against the warehouse, add statistics, write reports/*.csv, docs/charts/*.png, findings_auto.md.

Usage: python -m campuspulse.analyses [--fixture]
"""

import argparse
import json

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.formula.api as smf  # noqa: E402
from scipy import stats as sps  # noqa: E402
from statsmodels.stats.multitest import multipletests  # noqa: E402

from . import config as cfg  # noqa: E402
from . import load  # noqa: E402
from . import stats as S  # noqa: E402

SQL_DIR = cfg.ROOT / "analysis"
MIN_N = 30  # minimum institutions in a group before I report a statistic for it
MIN_N_FL = 8  # Florida groups are small by nature; reported with n and flagged below this
SECTORS = ["public", "private nonprofit", "private for-profit"]
COLORS = {"public": "#1f77b4", "private nonprofit": "#2ca02c", "private for-profit": "#d62728"}
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False, "font.size": 9})


def fmt_p(p: float) -> str:
    return "p < 1e-300" if p < 1e-300 else f"p = {p:.1e}"


def verdict(lo: float, hi: float) -> str:
    return (
        "the interval includes zero, so this is not distinguishable from no difference" if lo <= 0 <= hi else "the interval excludes zero"
    )


def sql(con, name: str) -> pd.DataFrame:
    return con.sql((SQL_DIR / name).read_text()).df()


def design(df: pd.DataFrame) -> np.ndarray:
    """Controls for Q1: Pell share, admission rate (+ missing flag), state and release-year fixed effects."""
    adm = df.admission_rate
    base = pd.DataFrame(
        {"const": 1.0, "pell": df.pct_pell.fillna(df.pct_pell.median()), "adm": adm.fillna(0.0), "adm_missing": adm.isna().astype(float)},
        index=df.index,
    )
    fe = pd.get_dummies(df[["state", "release_year"]].astype(str), drop_first=True).astype(float)
    return pd.concat([base, fe], axis=1).to_numpy()


# ---------------------------------------------------------------- Q1
def q1(con, rep, ch, reps, notes):
    df = sql(con, "01_price_vs_earnings.sql")
    rows = []
    cuts = [("all", "all institutions", df)]
    cuts += [("sector", s, df[df.sector == s]) for s in SECTORS]
    cuts += [("carnegie", g, df[df.carnegie_group == g]) for g in sorted(df.carnegie_group.unique())]
    for kind, name, d in cuts:
        d = d.reset_index(drop=True)
        n_inst = d.unitid.nunique()
        if n_inst < MIN_N:
            rows.append(
                {"cut": kind, "group": name, "n_institutions": n_inst, "n_rows": len(d), "skipped": f"fewer than {MIN_N} institutions"}
            )
            continue
        x, y = d.net_price.to_numpy(), np.log(d.earnings.to_numpy())
        X = design(d)
        groups = S.unit_groups(d.unitid)
        rng = S.rng_for(f"q1-{kind}-{name}")
        raw = S.spearman(x, y)
        b_raw = S.cluster_boot(groups, lambda i: S.spearman(x[i], y[i]), reps, rng)
        res = S.partial_spearman(x, y, X)
        b_res = S.cluster_boot(groups, lambda i: S.partial_spearman(x[i], y[i], X[i]), reps, rng)
        # OLS: % change in earnings per $10k net price, same controls, SEs clustered by institution
        m = smf.ols(
            "np.log(earnings) ~ I(net_price/10000) + pct_pell + admission_rate + C(state) + C(release_year)",
            data=d.assign(admission_rate=d.admission_rate.fillna(0)),
        ).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.unitid)[0]})
        b, (lo, hi) = m.params["I(net_price / 10000)"], m.conf_int().loc["I(net_price / 10000)"]
        rows.append(
            {
                "cut": kind,
                "group": name,
                "n_institutions": n_inst,
                "n_rows": len(d),
                "spearman_raw": raw,
                "raw_ci_lo": S.ci(b_raw)[0],
                "raw_ci_hi": S.ci(b_raw)[1],
                "spearman_residualised": res,
                "res_ci_lo": S.ci(b_res)[0],
                "res_ci_hi": S.ci(b_res)[1],
                "pct_earnings_per_10k": float(np.expm1(b) * 100),
                "pct_ci_lo": float(np.expm1(lo) * 100),
                "pct_ci_hi": float(np.expm1(hi) * 100),
                "skipped": "",
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(rep / "q1_price_vs_earnings.csv", index=False)
    ok = out[out.skipped == ""]
    # chart 1: scatter, pooled, by sector, with fitted line (OLS on log earnings)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for s in SECTORS:
        d = df[df.sector == s]
        ax.scatter(d.net_price / 1000, d.earnings / 1000, s=4, alpha=0.25, color=COLORS[s], label=f"{s} (n={d.unitid.nunique():,})")
        if len(d) > 30:
            k, c = np.polyfit(d.net_price / 1000, d.earnings / 1000, 1)
            xs = np.linspace(0, d.net_price.quantile(0.99) / 1000, 50)
            ax.plot(xs, k * xs + c, color=COLORS[s], lw=2)
    ax.set(
        xlabel="Average net price ($ thousands, nominal)",
        ylabel="Median earnings 10 yrs after entry ($ thousands)",
        title="Net price vs earnings by sector (institution-years)",
    )
    ax.legend(markerscale=3, frameon=False)
    fig.tight_layout()
    fig.savefig(ch / "q1_price_vs_earnings_scatter.png")
    plt.close(fig)
    # chart 2: raw vs residualised Spearman
    sub = ok[ok.cut.isin(["all", "sector"])].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    yy = np.arange(len(sub))
    for off, col, lab, c in [(-0.15, "raw", "raw", "#888"), (0.15, "res", "after controls", "#1f77b4")]:
        val = sub["spearman_raw" if col == "raw" else "spearman_residualised"]
        ax.errorbar(val, yy + off, xerr=[val - sub[f"{col}_ci_lo"], sub[f"{col}_ci_hi"] - val], fmt="o", color=c, label=lab, capsize=2)
    ax.set_yticks(yy, sub.group)
    ax.axvline(0, color="k", lw=0.5)
    ax.set(
        xlabel="Spearman correlation, net price vs log earnings (95% bootstrap CI)", title="Raw vs after Pell, admission rate, state, year"
    )
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(ch / "q1_spearman_by_sector.png")
    plt.close(fig)
    a = ok[ok.group == "all institutions"].iloc[0]
    pubs = ok[ok.group == "public"].iloc[0] if (ok.group == "public").any() else None
    notes.append(
        f"**Q1 price vs earnings.** Across {int(a.n_institutions):,} institutions ({int(a.n_rows):,} institution-years), net price and earnings have Spearman rho = {a.spearman_raw:.2f} "
        f"(95% CI {a.raw_ci_lo:.2f} to {a.raw_ci_hi:.2f}); after controlling for Pell share, admission rate, state and release year the partial rho is {a.spearman_residualised:.2f} "
        f"({a.res_ci_lo:.2f} to {a.res_ci_hi:.2f}). Each extra $10,000 of net price is associated with {a.pct_earnings_per_10k:.1f}% higher earnings "
        f"({a.pct_ci_lo:.1f}% to {a.pct_ci_hi:.1f}%, SEs clustered by institution)"
        + (
            f"; within public institutions the partial rho is {pubs.spearman_residualised:.2f} (n={int(pubs.n_institutions):,})."
            if pubs is not None
            else "."
        )
        + " This is an association among institutions, not the effect of paying more."
    )
    return out


# ---------------------------------------------------------------- Q2
def q2(con, rep, ch, notes):
    df = sql(con, "02_completion_debt.sql")
    df.to_csv(rep / "q2_completion_debt.csv", index=False)
    sec = df[df.institution_level.isna()]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for ax, col, title in [
        (axes[0], "completion_unweighted_median", "Median across institutions (unweighted)"),
        (axes[1], "completion_enrollment_weighted", "Weighted by undergraduate enrollment"),
    ]:
        for s in SECTORS:
            d = sec[sec.sector == s]
            ax.plot(d.release_year, d[col], marker="o", color=COLORS[s], label=s)
        ax.set(title=title, xlabel="Scorecard release year (non-consecutive)")
        ax.set_xticks(sorted(sec.release_year.unique()))
    axes[0].set_ylabel("Completion within 150% of normal time")
    axes[0].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(ch / "q2_completion_by_sector.png")
    plt.close(fig)
    last = sec.release_year.max()
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    d = sec[sec.release_year == last].set_index("sector").loc[SECTORS]
    axes[0].bar(d.index, d.median_debt_to_earnings, color=[COLORS[s] for s in d.index])
    axes[0].set(title=f"Median debt-to-earnings, {last} release (unweighted)", ylabel="completer debt / earnings")
    axes[1].bar(d.index, d.share_debt_to_earnings_above_half * 100, color=[COLORS[s] for s in d.index])
    axes[1].set(title="Share of institutions above 0.5", ylabel="% of institutions")
    for ax in axes:
        ax.tick_params(axis="x", labelrotation=15)
    fig.tight_layout()
    fig.savefig(ch / "q2_debt_to_earnings.png")
    plt.close(fig)
    t = sec[sec.release_year == last].set_index("sector")
    parts = [
        f"{s}: completion {t.loc[s, 'completion_unweighted_median']:.0%} (median, n={int(t.loc[s, 'n_completion']):,}) / {t.loc[s, 'completion_enrollment_weighted']:.0%} (enrollment-weighted), "
        f"median completer debt ${t.loc[s, 'median_debt']:,.0f}, debt-to-earnings {t.loc[s, 'median_debt_to_earnings']:.2f} with {t.loc[s, 'share_debt_to_earnings_above_half']:.0%} above 0.5 (n={int(t.loc[s, 'n_debt_to_earnings']):,})"
        for s in SECTORS
    ]
    notes.append(
        f"**Q2 completion and debt, {last} release.** "
        + "; ".join(parts)
        + ". Debt-to-earnings is a ratio of two institution medians, and the earnings cohort is about a decade old."
    )
    return sec


# ---------------------------------------------------------------- Q3
def _gap(a: np.ndarray, b: np.ndarray, reps, rng):
    """FL median minus peer median with a bootstrap CI (each group resampled separately)."""
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < MIN_N_FL or len(b) < MIN_N:
        return None
    diff = np.median(a) - np.median(b)
    boot = np.array([np.median(rng.choice(a, len(a))) - np.median(rng.choice(b, len(b))) for _ in range(reps)])
    return {
        "n_fl": len(a),
        "n_peers": len(b),
        "fl_median": float(np.median(a)),
        "peer_median": float(np.median(b)),
        "gap": float(diff),
        "ci_lo": S.ci(boot)[0],
        "ci_hi": S.ci(boot)[1],
    }


def q3(con, rep, ch, reps, notes):
    df = sql(con, "03_florida.sql")
    metrics = {
        "earnings": "Earnings ($)",
        "completion_rate": "Completion rate",
        "net_price": "Net price ($)",
        "debt_to_earnings": "Debt-to-earnings",
    }
    rows = []
    for year in sorted(df.release_year.unique()):
        for grp, level in [("Florida public 4-year", "4-year"), ("Florida public community college", "2-year")]:
            d = df[(df.release_year == year) & (df.institution_level == level)]
            fl, peers = d[d.fl_group == grp], d[d.fl_group.isna() & (d.state != "FL")]
            for m in metrics:
                r = _gap(fl[m].to_numpy(float), peers[m].to_numpy(float), reps, S.rng_for(f"q3-{year}-{grp}-{m}"))
                if r:
                    rows.append({"release_year": year, "fl_group": grp, "metric": m, **r, "small_fl_n": r["n_fl"] < 15})
    gaps = pd.DataFrame(rows)
    gaps.to_csv(rep / "q3_florida_gaps.csv", index=False)
    last = df.release_year.max()
    rank = df[(df.release_year == last) & df.fl_group.notna()].copy()
    pub4 = df[(df.release_year == last) & (df.institution_level == "4-year")]
    rank["earnings_rank_in_group"] = rank.groupby("fl_group").earnings.rank(ascending=False, method="min")
    rank["earnings_percentile_vs_public_peers"] = [
        (pub4.earnings.dropna() < e).mean() * 100 if (lv == "4-year" and pd.notna(e)) else np.nan
        for e, lv in zip(rank.earnings, rank.institution_level)
    ]
    rank = rank.sort_values(["fl_group", "earnings_rank_in_group"])[
        [
            "fl_group",
            "institution_name",
            "release_year",
            "earnings",
            "earnings_rank_in_group",
            "earnings_percentile_vs_public_peers",
            "completion_rate",
            "net_price",
            "debt_to_earnings",
            "enrollment",
        ]
    ]
    rank.to_csv(rep / "q3_florida_rank_table.csv", index=False)
    g = gaps[gaps.release_year == last]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    for ax, grp in zip(axes, ["Florida public 4-year", "Florida public community college"]):
        d = g[g.fl_group == grp]
        if d.empty:
            continue
        rel = d.gap / d.peer_median * 100
        lo, hi = d.ci_lo / d.peer_median * 100, d.ci_hi / d.peer_median * 100
        ax.errorbar(rel, range(len(d)), xerr=[rel - lo, hi - rel], fmt="o", capsize=3, color="#1f77b4")
        ax.set_yticks(range(len(d)), [metrics[m] for m in d.metric])
        ax.axvline(0, color="k", lw=0.5)
        ax.set(title=f"{grp} (n={int(d.n_fl.iloc[0])})", xlabel="Gap vs non-Florida public peers (% of peer median)")
    fig.tight_layout()
    fig.savefig(ch / "q3_florida_gaps.png")
    plt.close(fig)
    e = g[(g.fl_group == "Florida public 4-year") & (g.metric == "earnings")]
    c = g[(g.fl_group == "Florida public 4-year") & (g.metric == "completion_rate")]
    if len(e) and len(c):
        e, c = e.iloc[0], c.iloc[0]
        notes.append(
            f"**Q3 Florida, {last} release.** Florida public 4-year institutions (n={int(e.n_fl)}) have median earnings ${e.fl_median:,.0f} vs ${e.peer_median:,.0f} for public 4-year peers elsewhere (n={int(e.n_peers)}): "
            f"gap ${e.gap:,.0f} (95% bootstrap CI ${e.ci_lo:,.0f} to ${e.ci_hi:,.0f}); completion gap {c.gap * 100:.1f} points ({c.ci_lo * 100:.1f} to {c.ci_hi * 100:.1f}). "
            f"For earnings {verdict(e.ci_lo, e.ci_hi)}. Florida groups are small (flagged small_fl_n in q3_florida_gaps.csv), so intervals are wide; University of Florida-Online reports the same earnings figure as the main campus. Community colleges are compared separately."
        )
    return gaps


# ---------------------------------------------------------------- Q4 (sector differences)
def q4(con, rep, ch, reps, notes):
    df = sql(con, "04_sector_differences.sql")
    rows, pair_rows = [], []
    for metric, d in df.groupby("metric"):
        counts = d.sector.value_counts()
        keep = [s for s in SECTORS if counts.get(s, 0) >= MIN_N]
        dropped = [s for s in SECTORS if s not in keep]
        d = d[d.sector.isin(keep)].reset_index(drop=True)
        if len(keep) < 2:
            continue
        arrays = [d[d.sector == s].value.to_numpy() for s in keep]
        h, p = sps.kruskal(*arrays)
        n = len(d)
        rng = S.rng_for(f"q4-{metric}")
        groups = [np.flatnonzero(d.sector.to_numpy() == s) for s in keep]

        def eps(_):
            samp = [rng.choice(g_, len(g_)) for g_ in groups]
            hh = sps.kruskal(*[d.value.to_numpy()[i] for i in samp]).statistic
            return S.epsilon_squared(hh, n)

        boot = np.array([eps(None) for _ in range(reps)])
        rows.append(
            {
                "metric": metric,
                "n": n,
                "groups": ", ".join(f"{s} (n={counts[s]})" for s in keep),
                "dropped_small_groups": ", ".join(dropped),
                "H": h,
                "p_value": p,
                "epsilon_squared": S.epsilon_squared(h, n),
                "eps_ci_lo": S.ci(boot)[0],
                "eps_ci_hi": S.ci(boot)[1],
            }
        )
        pairs = [(a, b) for i, a in enumerate(keep) for b in keep[i + 1 :]]
        pv = [sps.mannwhitneyu(d[d.sector == a].value, d[d.sector == b].value).pvalue for a, b in pairs]
        adj = multipletests(pv, method="holm")[1]
        for (a, b), p0, p1 in zip(pairs, pv, adj):
            xa, xb = d[d.sector == a].value.to_numpy(), d[d.sector == b].value.to_numpy()
            bt = np.array([S.rank_biserial(rng.choice(xa, len(xa)), rng.choice(xb, len(xb))) for _ in range(max(reps // 2, 50))])
            pair_rows.append(
                {
                    "metric": metric,
                    "group_a": a,
                    "group_b": b,
                    "n_a": len(xa),
                    "n_b": len(xb),
                    "median_a": np.median(xa),
                    "median_b": np.median(xb),
                    "p_raw": p0,
                    "p_holm": p1,
                    "rank_biserial": S.rank_biserial(xa, xb),
                    "rb_ci_lo": S.ci(bt)[0],
                    "rb_ci_hi": S.ci(bt)[1],
                }
            )
    kw, pw = pd.DataFrame(rows), pd.DataFrame(pair_rows)
    kw.to_csv(rep / "q4_kruskal_wallis.csv", index=False)
    pw.to_csv(rep / "q4_pairwise_mannwhitney.csv", index=False)
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.6))
    for ax, metric, lab in [
        (axes[0], "earnings", "Median earnings ($)"),
        (axes[1], "completion", "Completion rate"),
        (axes[2], "debt_to_earnings", "Debt-to-earnings"),
    ]:
        d = df[df.metric == metric]
        data = [d[d.sector == s].value.to_numpy() for s in SECTORS]
        bp = ax.boxplot(data, tick_labels=["public", "nonprofit", "for-profit"], showfliers=False, patch_artist=True)
        for patch, s in zip(bp["boxes"], SECTORS):
            patch.set_facecolor(COLORS[s])
            patch.set_alpha(0.5)
        ax.set(title=lab)
    fig.tight_layout()
    fig.savefig(ch / "q4_sector_distributions.png")
    plt.close(fig)
    k = kw[kw.metric == "earnings"].iloc[0]
    pe = pw[(pw.metric == "earnings")].sort_values("rank_biserial")
    top = pe.iloc[0] if len(pe) else None
    notes.append(
        f"**Q4 sector differences.** Earnings differ across sectors (Kruskal-Wallis H = {k.H:,.0f}, {fmt_p(k.p_value)}, epsilon-squared = {k.epsilon_squared:.2f}, 95% CI {k.eps_ci_lo:.2f} to {k.eps_ci_hi:.2f}, n = {int(k.n):,} institutions, latest release each). "
        + (
            f"Largest pairwise gap: {top.group_a} vs {top.group_b}, rank-biserial {top.rank_biserial:.2f} ({top.rb_ci_lo:.2f} to {top.rb_ci_hi:.2f}), Holm-adjusted {fmt_p(top.p_holm)}. "
            if top is not None
            else ""
        )
        + f"Groups with fewer than {MIN_N} institutions are dropped from a test. Rank tests compare distributions, not causes."
    )
    return kw, pw


def run(fixture: bool = False) -> None:
    rep, ch = cfg.reports_dir(fixture), cfg.charts_dir(fixture)
    reps = 100 if fixture else 500
    con = duckdb.connect(str(load.db_path(fixture)), read_only=True)
    notes = []
    q1_df = q1(con, rep, ch, reps, notes)
    q2(con, rep, ch, notes)
    q3_df = q3(con, rep, ch, reps, notes)
    q4_df, _ = q4(con, rep, ch, reps, notes)
    (rep / "findings_auto.md").write_text(
        "# Automatic findings\n\nGenerated from the CSVs in this folder by `python -m campuspulse.analyses`; never edited by hand.\n\n"
        + "\n\n".join(notes)
        + "\n"
    )
    (rep / "analysis_meta.json").write_text(
        json.dumps(
            {
                "bootstrap_reps": reps,
                "min_n": MIN_N,
                "min_n_florida": MIN_N_FL,
                "seed": S.SEED,
                "rows_q1": int(q1_df.n_rows.max()),
                "q3_rows": len(q3_df),
                "q4_rows": len(q4_df),
            },
            indent=2,
        )
    )
    print("\n\n".join(notes))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true")
    run(ap.parse_args().fixture)
