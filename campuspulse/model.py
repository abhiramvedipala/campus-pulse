"""Earnings models: OLS (robust SE), ridge/lasso/elastic net, gradient boosting; honest validation; SHAP; residuals.

Usage: python -m campuspulse.model [--fixture]
Target: log of MD_EARN_WNE_P10 (dollars reported too). Nominal dollars, release-year fixed effects.
"""

import os

os.environ.setdefault("OMP_NUM_THREADS", "4")  # keep the machine light: model threads capped at 4
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")

import argparse  # noqa: E402
import json  # noqa: E402
import warnings  # noqa: E402

import duckdb  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shap  # noqa: E402
import statsmodels.api as sm  # noqa: E402
from scipy import stats as sps  # noqa: E402
from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
from sklearn.linear_model import ElasticNetCV, LassoCV, LinearRegression, RidgeCV  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler  # noqa: E402
from statsmodels.stats.diagnostic import het_breuschpagan  # noqa: E402
from statsmodels.stats.outliers_influence import variance_inflation_factor  # noqa: E402
from threadpoolctl import threadpool_limits  # noqa: E402

from . import config as cfg  # noqa: E402
from . import load  # noqa: E402
from . import stats as S  # noqa: E402

warnings.filterwarnings("ignore", message="Found unknown categories")  # expected: handle_unknown encodes them as all zeros
TARGET = "log_median_earnings_p10"
NUM = ["net_price", "pct_pell", "admission_rate", "enrollment", "completion_rate", "retention_rate"]
CAT = ["sector", "carnegie_group", "state", "release_year"]
FEATURES = NUM + CAT
# Earnings-derived or earnings-containing fields that must never be features (see tests/test_leakage.py).
EXCLUDED = {
    "median_earnings_p10": "the target itself",
    "log_median_earnings_p10": "the target itself",
    "mean_earnings_p10": "same Treasury earnings measurement as the target",
    "earnings_cohort_size": "count behind the target's own measurement",
    "median_earnings_p6": "earnings of the same students 4 years earlier; correlated with the target by construction",
    "median_earnings_p8": "earnings of the same students 2 years earlier; correlated with the target by construction",
    "debt_to_earnings": "contains the target in its denominator",
}
SECTORS = ["public", "private nonprofit", "private for-profit"]
COLORS = {"public": "#1f77b4", "private nonprofit": "#2ca02c", "private for-profit": "#d62728"}
N_FOLDS = 5
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False, "font.size": 9})


# ------------------------------------------------------------------ data and design
def load_data(fixture: bool) -> pd.DataFrame:
    con = duckdb.connect(str(load.db_path(fixture)), read_only=True)
    df = con.sql("select * from marts.mart_model_input order by unitid, release_year").df()
    df["release_year"] = df.release_year.astype(str)
    df["enrollment"] = np.log1p(df.enrollment)  # enrollment is heavy-tailed; log for all models
    return df.reset_index(drop=True)


def fold_ids(unitid: pd.Series, seed: int = S.SEED) -> np.ndarray:
    """Institution-grouped folds: every row of an institution lands in the same fold."""
    ids = unitid.unique()
    rng = np.random.default_rng(seed)
    assign = dict(zip(ids, rng.permutation(len(ids)) % N_FOLDS, strict=True))
    return unitid.map(assign).to_numpy()


def linear_pre() -> ColumnTransformer:
    num = Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)), ("sc", StandardScaler())])
    cat = OneHotEncoder(drop="first", handle_unknown="ignore", min_frequency=30, sparse_output=False)
    return ColumnTransformer([("num", num, NUM), ("cat", cat, CAT)])


def tree_pre() -> ColumnTransformer:
    enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=np.nan, encoded_missing_value=np.nan)
    return ColumnTransformer([("num", "passthrough", NUM), ("cat", enc, CAT)])


def hgb() -> Pipeline:
    # Categoricals are ordinal-coded and treated as numeric: shap's TreeExplainer mis-attributes sklearn's native categorical
    # splits (additivity error ~1.6 log points measured), so the model I explain is the one I score.
    return Pipeline(
        [
            ("pre", tree_pre()),
            (
                "m",
                HistGradientBoostingRegressor(
                    max_iter=400,
                    learning_rate=0.05,
                    max_leaf_nodes=15,
                    min_samples_leaf=40,
                    l2_regularization=1.0,
                    early_stopping=False,
                    random_state=S.SEED,
                ),
            ),
        ]
    )


def inner_splits(folds: np.ndarray, train_mask: np.ndarray):
    """Penalty selection inside a training set: leave one of its own institution-folds out at a time."""
    idx = np.flatnonzero(train_mask)
    f = folds[idx]
    return [(idx[f != k] - 0, idx[f == k]) for k in np.unique(f)]


def make_models(folds, train_mask):
    cv = [
        (np.searchsorted(np.flatnonzero(train_mask), a), np.searchsorted(np.flatnonzero(train_mask), b))
        for a, b in inner_splits(folds, train_mask)
    ]
    return {
        "OLS": Pipeline([("pre", linear_pre()), ("m", LinearRegression())]),
        "Ridge": Pipeline([("pre", linear_pre()), ("m", RidgeCV(alphas=np.logspace(-2, 3, 20), cv=cv))]),
        "Lasso": Pipeline([("pre", linear_pre()), ("m", LassoCV(alphas=40, cv=cv, random_state=S.SEED, max_iter=5000))]),
        "ElasticNet": Pipeline(
            [("pre", linear_pre()), ("m", ElasticNetCV(l1_ratio=[0.2, 0.5, 0.8], alphas=30, cv=cv, random_state=S.SEED, max_iter=5000))]
        ),
        "GradientBoosting": hgb(),
    }


# ------------------------------------------------------------------ baselines
class Baseline:
    """Median log earnings by (sector[, state]) within release year; falls back to coarser cells. Fit on training rows only."""

    def __init__(self, by_state: bool):
        self.by_state = by_state

    def fit(self, d: pd.DataFrame):
        y = d[TARGET]
        self.t_state = y.groupby([d.sector, d.state, d.release_year]).median()
        self.t_sec_year = y.groupby([d.sector, d.release_year]).median()
        self.t_sec = y.groupby(d.sector).median()
        return self

    def predict(self, d: pd.DataFrame, year_override: str | None = None) -> np.ndarray:
        out = []
        for sec, st, yr in zip(d.sector, d.state, d.release_year if year_override is None else [year_override] * len(d), strict=True):
            if self.by_state and (sec, st, yr) in self.t_state.index:
                out.append(self.t_state[(sec, st, yr)])
            elif (sec, yr) in self.t_sec_year.index:
                out.append(self.t_sec_year[(sec, yr)])
            else:
                out.append(self.t_sec[sec])
        return np.array(out)


# ------------------------------------------------------------------ validation
def grouped_cv(df, folds):
    """Out-of-fold log predictions for every model and both baselines; the model never sees the scored institution."""
    names = ["Baseline: sector median", "Baseline: sector x state median", "OLS", "Ridge", "Lasso", "ElasticNet", "GradientBoosting"]
    pred = {n: np.full(len(df), np.nan) for n in names}
    chosen = {}
    for k in range(N_FOLDS):
        te, tr = folds == k, folds != k
        pred["Baseline: sector median"][te] = Baseline(False).fit(df[tr]).predict(df[te])
        pred["Baseline: sector x state median"][te] = Baseline(True).fit(df[tr]).predict(df[te])
        for name, m in make_models(folds, tr).items():
            m.fit(df.loc[tr, FEATURES], df.loc[tr, TARGET])
            pred[name][te] = m.predict(df.loc[te, FEATURES])
            if name in ("Ridge", "Lasso", "ElasticNet"):
                chosen.setdefault(name, []).append(float(m.named_steps["m"].alpha_))
    return pred, chosen


def temporal_holdout(df, folds):
    """Train on releases before the latest, score the latest. Unseen year -> encoded as the latest training release
    (2020_21), whose dollars Scorecard re-bases to 2022, the same base I assume for 2022_23."""
    last = sorted(df.release_year.unique())[-1]
    tr, te = (df.release_year != last).to_numpy(), (df.release_year == last).to_numpy()
    prev = sorted(df.release_year.unique())[-2]
    test = df[te].assign(release_year=prev)
    pred = {
        n: np.full(len(df), np.nan)
        for n in ["Baseline: sector median", "Baseline: sector x state median", "OLS", "Ridge", "Lasso", "ElasticNet", "GradientBoosting"]
    }
    pred["Baseline: sector median"][te] = Baseline(False).fit(df[tr]).predict(test)
    pred["Baseline: sector x state median"][te] = Baseline(True).fit(df[tr]).predict(test)
    for name, m in make_models(folds, tr).items():
        m.fit(df.loc[tr, FEATURES], df.loc[tr, TARGET])
        pred[name][te] = m.predict(test[FEATURES])
    return pred, te, last, prev


def metrics_fn(y_log, p_log):
    y, p = np.exp(y_log), np.exp(p_log)
    return {
        "R2_log": 1 - np.sum((y_log - p_log) ** 2) / np.sum((y_log - y_log.mean()) ** 2),
        "R2_dollars": 1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2),
        "MAE_dollars": np.mean(np.abs(y - p)),
        "MdAPE_pct": np.median(np.abs(y - p) / y) * 100,
    }


def evaluate(df, pred, mask, label, reps, notes_rows):
    """Point estimates plus institution-clustered bootstrap CIs; MAE improvement vs both baselines (paired draws)."""
    d = df[mask].reset_index(drop=True)
    y = d[TARGET].to_numpy()
    P = {n: p[mask] for n, p in pred.items()}
    groups = S.unit_groups(d.unitid)
    rng = S.rng_for(f"eval-{label}")
    base = ["Baseline: sector median", "Baseline: sector x state median"]
    boot = {n: {m: np.empty(reps) for m in ["R2_log", "R2_dollars", "MAE_dollars", "MdAPE_pct"]} for n in P}
    for b in range(reps):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        for n in P:
            for m, v in metrics_fn(y[idx], P[n][idx]).items():
                boot[n][m][b] = v
    for n in P:
        pt = metrics_fn(y, P[n])
        for m, v in pt.items():
            lo, hi = S.ci(boot[n][m])
            row = {
                "validation": label,
                "model": n,
                "metric": m,
                "estimate": v,
                "ci_lo": lo,
                "ci_hi": hi,
                "n_rows": len(d),
                "n_institutions": d.unitid.nunique(),
            }
            for bn in base:
                if n not in base and m == "MAE_dollars":
                    diff = boot[bn][m] - boot[n][m]
                    row[f"mae_saving_vs_{'sector' if bn == base[0] else 'sector_state'}"] = float(
                        np.mean(np.abs(np.exp(y) - np.exp(P[bn]))) - v
                    )
                    row[f"mae_saving_vs_{'sector' if bn == base[0] else 'sector_state'}_ci"] = f"{S.ci(diff)[0]:.0f} to {S.ci(diff)[1]:.0f}"
            notes_rows.append(row)


# ------------------------------------------------------------------ inference
def ols_inference(df, rep):
    pre = linear_pre()
    X = pre.fit_transform(df[FEATURES])
    names = [n.split("__", 1)[1] for n in pre.get_feature_names_out()]
    Xd = sm.add_constant(pd.DataFrame(X, columns=names))
    y = df[TARGET].to_numpy()
    res = sm.OLS(y, Xd).fit(cov_type="HC3")
    cl = sm.OLS(y, Xd).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(df.unitid)[0]})
    ci_ = res.conf_int()
    coef = pd.DataFrame(
        {
            "term": res.params.index,
            "coef": res.params.values,
            "ci_lo": ci_[0].values,
            "ci_hi": ci_[1].values,
            "se_hc3": res.bse.values,
            "se_cluster": cl.bse.values,
            "p_hc3": res.pvalues.values,
        }
    )
    coef["pct_effect_per_unit"] = np.expm1(coef.coef) * 100
    coef.to_csv(rep / "ols_coefficients.csv", index=False)
    bp = het_breuschpagan(res.resid, Xd)
    numeric_idx = [i for i, n in enumerate(Xd.columns) if n in NUM]
    vif = {Xd.columns[i]: float(variance_inflation_factor(Xd.to_numpy(), i)) for i in numeric_idx}
    diag = {
        "n": int(res.nobs),
        "r2": float(res.rsquared),
        "adj_r2": float(res.rsquared_adj),
        "cov_type": "HC3",
        "breusch_pagan_lm_p": float(bp[1]),
        "jarque_bera_p": float(sps.jarque_bera(res.resid).pvalue),
        "residual_skew": float(sps.skew(res.resid)),
        "condition_number": float(res.condition_number),
        "max_leverage": float(res.get_influence().hat_matrix_diag.max()),
        "vif_numeric": vif,
        "note": "HC3 robust SEs reported; cluster-by-institution SEs are in the se_cluster column and are larger when repeated releases correlate.",
    }
    (rep / "ols_diagnostics.json").write_text(json.dumps(diag, indent=2))
    return coef, diag, res


def lasso_table(df, folds, rep):
    m = make_models(folds, np.ones(len(df), bool))["Lasso"].fit(df[FEATURES], df[TARGET])
    pre = m.named_steps["pre"]
    names = [n.split("__", 1)[1] for n in pre.get_feature_names_out()]
    t = pd.DataFrame({"term": names, "coef": m.named_steps["m"].coef_})
    t["dropped"] = t.coef == 0
    t.to_csv(rep / "lasso_coefficients.csv", index=False)
    # importance per original feature: mean absolute deviation of that feature's total contribution to the linear predictor
    X = pre.transform(df[FEATURES])
    imp = {}
    for f in FEATURES:
        cols = [i for i, term in enumerate(names) if feature_of(term) == f]
        contrib = X[:, cols] @ t.coef.to_numpy()[cols] if cols else np.zeros(len(df))
        imp[f] = float(np.mean(np.abs(contrib - contrib.mean())))
    return t, float(m.named_steps["m"].alpha_), imp


def feature_of(term: str) -> str:
    for c in CAT:
        if term.startswith(c + "_"):
            return c
    return term.replace("missingindicator_", "").split("_")[0] if term.startswith("missingindicator_") else term


# ------------------------------------------------------------------ SHAP, residuals
def shap_section(df, lasso_imp, rep, ch, fixture):
    m = hgb().fit(df[FEATURES], df[TARGET])
    pre, est = m.named_steps["pre"], m.named_steps["m"]
    Xt = pd.DataFrame(pre.transform(df[FEATURES]), columns=FEATURES)
    n = min(len(Xt), 1500 if fixture else 4000)
    samp = Xt.sample(n, random_state=S.SEED)
    expl = shap.TreeExplainer(est)
    sv = expl.shap_values(samp)
    err = float(np.abs(sv.sum(axis=1) + expl.expected_value - est.predict(samp.to_numpy())).max())
    assert err < 1e-6, f"SHAP additivity violated: {err}"
    imp = pd.DataFrame({"feature": FEATURES, "mean_abs_shap": np.abs(sv).mean(axis=0)}).sort_values("mean_abs_shap", ascending=False)
    imp["shap_rank"] = np.arange(1, len(imp) + 1)
    imp.to_csv(rep / "shap_importance.csv", index=False)
    # display copy with readable category labels for the beeswarm
    disp = samp.copy()
    plt.figure(figsize=(7, 4.2))
    shap.summary_plot(sv, disp, show=False, plot_size=None)
    plt.title("SHAP summary: drivers of log median earnings")
    plt.tight_layout()
    plt.savefig(ch / "shap_summary.png")
    plt.close()
    # top drivers by sector
    sec = df.loc[samp.index, "sector"].to_numpy()
    rows = [
        {"sector": s, "feature": f, "mean_abs_shap": float(np.abs(sv[sec == s, j]).mean())}
        for s in SECTORS
        for j, f in enumerate(FEATURES)
        if (sec == s).sum() > 0
    ]
    bys = pd.DataFrame(rows)
    bys.to_csv(rep / "shap_by_sector.csv", index=False)
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.4), sharex=True)
    for ax, s in zip(axes, SECTORS, strict=True):
        t = bys[bys.sector == s].sort_values("mean_abs_shap").tail(6)
        ax.barh(t.feature, t.mean_abs_shap, color=COLORS[s])
        ax.set_title(s)
    axes[1].set_xlabel("mean |SHAP| (log earnings)")
    fig.tight_layout()
    fig.savefig(ch / "shap_top_drivers_by_sector.png")
    plt.close(fig)
    j = FEATURES.index("net_price")
    plt.figure(figsize=(6, 4))
    shap.dependence_plot(j, sv, samp, interaction_index=FEATURES.index("pct_pell"), show=False)
    plt.title("SHAP dependence: net price (colour = Pell share)")
    plt.tight_layout()
    plt.savefig(ch / "shap_dependence_net_price.png")
    plt.close()
    # compare with lasso: importance = mean |contribution| of each feature to the lasso prediction (same log-earnings units as SHAP)
    li = pd.DataFrame({"feature": FEATURES, "lasso_importance": [lasso_imp[f] for f in FEATURES]})
    li["lasso_rank"] = li.lasso_importance.rank(ascending=False, method="min").astype(int)
    cmp = imp.merge(li, on="feature")
    cmp["rank_gap"] = (cmp.shap_rank - cmp.lasso_rank).abs()
    cmp.to_csv(rep / "shap_vs_lasso.csv", index=False)
    rho = float(sps.spearmanr(cmp.shap_rank, cmp.lasso_rank).statistic)
    return imp, cmp, rho


def residual_section(df, oof_log, rep, ch, best):
    d = df.copy()
    d["pred_log"], d["resid_log"] = oof_log, d[TARGET] - oof_log
    d["actual"], d["pred"] = np.exp(d[TARGET]), np.exp(oof_log)
    d["resid_pct"] = (np.exp(d.resid_log) - 1) * 100
    d[["unitid", "release_year", "state", "sector", "actual", "pred", "resid_pct"]].round(2).to_csv(
        rep / "oof_predictions.csv", index=False
    )
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    ax = axes[0, 0]
    ax.scatter(d.pred_log, d.resid_log, s=3, alpha=0.2, color="#555")
    ax.axhline(0, color="r", lw=0.8)
    ax.set(xlabel="Fitted log earnings (out-of-fold)", ylabel="Residual (log)", title=f"Residuals vs fitted ({best})")
    ax = axes[0, 1]
    ax.scatter(d.enrollment, d.resid_log, s=3, alpha=0.2, color="#555")
    ax.axhline(0, color="r", lw=0.8)
    ax.set(xlabel="log(1 + undergraduate enrollment)", ylabel="Residual (log)", title="Residuals vs enrollment")
    ax = axes[1, 0]
    ax.boxplot([d[d.sector == s].resid_log for s in SECTORS], tick_labels=["public", "nonprofit", "for-profit"], showfliers=False)
    ax.axhline(0, color="r", lw=0.8)
    ax.set(title="Residuals by sector", ylabel="Residual (log)")
    st = d.groupby("state").resid_log.agg(["mean", "size"])
    st = st[st["size"] >= 30].sort_values("mean")
    ax = axes[1, 1]
    sel = pd.concat([st.head(8), st.tail(8)])
    ax.barh(sel.index, sel["mean"], color=["#d62728" if v < 0 else "#2ca02c" for v in sel["mean"]])
    ax.set(title="Mean residual by state (n >= 30 rows)", xlabel="Mean log residual")
    fig.tight_layout()
    fig.savefig(ch / "residual_diagnostics.png")
    plt.close(fig)
    st.rename(columns={"mean": "mean_log_resid", "size": "n_rows"}).to_csv(rep / "residuals_by_state.csv")
    d.groupby("sector").resid_log.agg(["mean", "std", "size"]).to_csv(rep / "residuals_by_sector.csv")
    # over/under performers: mean out-of-fold residual per institution across its releases
    inst = (
        d.groupby("unitid")
        .agg(
            institution_name=("institution_name", "last"),
            state=("state", "last"),
            sector=("sector", "last"),
            n_releases=("resid_pct", "size"),
            mean_resid_pct=("resid_pct", "mean"),
            actual_last=("actual", "last"),
            pred_last=("pred", "last"),
            fl4=("is_florida_public_4yr", "max"),
            flcc=("is_florida_public_cc", "max"),
        )
        .reset_index()
    )
    sd = float(d.resid_log.std())
    inst["outside_one_sd"] = inst.mean_resid_pct.abs() > (np.exp(sd) - 1) * 100
    big = inst[inst.n_releases >= 2]
    pd.concat(
        [
            big.nlargest(25, "mean_resid_pct").assign(direction="over-performer"),
            big.nsmallest(25, "mean_resid_pct").assign(direction="under-performer"),
        ]
    ).drop(columns=["fl4", "flcc"]).round(2).to_csv(rep / "over_under_performers.csv", index=False)
    fl = (
        # UF-Online reports the Gainesville campus's earnings (shared OPEID): not an independent record, so left out here
        inst[(inst.fl4 | inst.flcc) & ~inst.institution_name.str.contains("Online")]
        .assign(group=lambda x: np.where(x.fl4, "Florida public 4-year", "Florida public community college"))
        .sort_values("mean_resid_pct", ascending=False)
    )
    fl.drop(columns=["fl4", "flcc"]).round(2).to_csv(rep / "florida_over_under.csv", index=False)
    return d, inst, fl, sd


def run(fixture: bool = False) -> None:
    rep, ch = cfg.reports_dir(fixture), cfg.charts_dir(fixture)
    reps = 100 if fixture else 300
    df = load_data(fixture)
    folds = fold_ids(df.unitid)
    rows = []
    with threadpool_limits(4):
        pred_cv, chosen = grouped_cv(df, folds)
        evaluate(df, pred_cv, np.ones(len(df), bool), "grouped 5-fold by institution", reps, rows)
        pred_t, te, last, prev = temporal_holdout(df, folds)
        evaluate(df, pred_t, te, f"temporal holdout (train before {last}, test {last})", reps, rows)
        coef, diag, _ = ols_inference(df, rep)
        lasso, lasso_alpha, lasso_imp = lasso_table(df, folds, rep)
        met = pd.DataFrame(rows)
        met.to_csv(rep / "model_metrics.csv", index=False)
        g = met[(met.validation.str.startswith("grouped")) & (met.metric == "MAE_dollars")].set_index("model").estimate
        best = g.drop([i for i in g.index if i.startswith("Baseline")]).idxmin()
        imp, cmp, rho = shap_section(df, lasso_imp, rep, ch, fixture)
        d, inst, fl, sd = residual_section(df, pred_cv[best], rep, ch, best)
    meta = {
        "best_model_by_grouped_cv_mae": best,
        "chosen_penalties": chosen,
        "lasso_alpha_full_fit": lasso_alpha,
        "lasso_dropped": lasso[lasso.dropped].term.tolist(),
        "shap_lasso_rank_spearman": rho,
        "resid_sd_log": sd,
        "temporal_year_encoded_as": prev,
        "bootstrap_reps": reps,
        "n_rows": len(df),
        "n_institutions": int(df.unitid.nunique()),
        "excluded_features": EXCLUDED,
        "features": FEATURES,
    }
    (rep / "model_meta.json").write_text(json.dumps(meta, indent=2, default=float))

    def m_(v, mdl, metric):
        r = met[(met.validation.str.startswith(v)) & (met.model == mdl) & (met.metric == metric)].iloc[0]
        return r

    bg, bt, base2 = (lambda v, k: m_(v, best, k)), None, "Baseline: sector x state median"
    mae_g, r2_g, mae_t, r2_t = (
        bg("grouped", "MAE_dollars"),
        bg("grouped", "R2_log"),
        bg("temporal", "MAE_dollars"),
        bg("temporal", "R2_log"),
    )
    bmae_g, bmae_t = m_("grouped", base2, "MAE_dollars"), m_("temporal", base2, "MAE_dollars")
    top3 = ", ".join(imp.feature.head(3))
    over = fl.head(1).iloc[0]
    under = fl.tail(1).iloc[0]
    fl4 = fl[fl.group == "Florida public 4-year"]
    txt = [
        f"**Q4 prediction.** The best model by institution-grouped 5-fold validation is {best} (n = {len(df):,} institution-years, {meta['n_institutions']:,} institutions): "
        f"R-squared on log earnings {r2_g.estimate:.2f} (95% CI {r2_g.ci_lo:.2f} to {r2_g.ci_hi:.2f}), mean absolute error ${mae_g.estimate:,.0f} ({mae_g.ci_lo:,.0f} to {mae_g.ci_hi:,.0f}) "
        f"versus ${bmae_g.estimate:,.0f} for the sector-by-state median baseline. Scored on the {last} release after training on earlier releases the error is ${mae_t.estimate:,.0f} "
        f"({mae_t.ci_lo:,.0f} to {mae_t.ci_hi:,.0f}) against ${bmae_t.estimate:,.0f} for the baseline; the same institutions appear in both periods, so this is a time test, not an unseen-institution test.",
        f"**What drives the predictions.** Largest mean absolute SHAP values: {top3}. Release year ranks high because dollars are nominal and re-based differently by release, not because of anything about institutions. "
        f"Lasso (penalty chosen by institution-grouped CV) dropped {len(meta['lasso_dropped'])} of its terms; SHAP and lasso importance ranks agree with Spearman rho = {rho:.2f}, "
        f"largest disagreement: {cmp.sort_values('rank_gap').iloc[-1].feature} (rank gap {int(cmp.rank_gap.max())}). Association is not causation.",
        f"**Over- and under-performers, Florida public 4-year.** Institutions are compared with what their student mix and sector predict, using out-of-fold predictions averaged over releases. "
        f"Highest: {fl4.iloc[0].institution_name} ({fl4.iloc[0].mean_resid_pct:+.0f}%); lowest: {fl4.iloc[-1].institution_name} ({fl4.iloc[-1].mean_resid_pct:+.0f}%). "
        f"A typical residual is about {(np.exp(sd) - 1) * 100:.0f}%, so differences smaller than that are within model noise.",
    ]
    (rep / "findings_model_auto.md").write_text(
        "# Automatic model findings\n\nGenerated by `python -m campuspulse.model`; never edited by hand.\n\n" + "\n\n".join(txt) + "\n"
    )
    print(met[met.metric.isin(["R2_log", "MAE_dollars", "MdAPE_pct"])].round(3).to_string(index=False))
    print("best:", best, "| lasso dropped:", len(meta["lasso_dropped"]), "| SHAP-lasso rank rho:", round(rho, 2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true")
    run(ap.parse_args().fixture)
