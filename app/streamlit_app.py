"""Campus Pulse dashboard: four pages. Run: streamlit run app/streamlit_app.py"""

import sys
from pathlib import Path

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

st.set_page_config(page_title="Campus Pulse", layout="wide")


def overview():
    st.title("Campus Pulse: Overview")
    df = c.filters(c.institutions())
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Institutions", f"{df.unitid.nunique():,}")
    k2.metric("Release years", df.release_year.nunique())
    k3.metric("Institution-years", f"{len(df):,}")
    k4.metric("With 10-yr earnings", f"{df.earnings.notna().sum():,}")
    med = (
        df.groupby(["sector", "release_year"])
        .agg(
            n=("unitid", "size"),
            earnings=("earnings", "median"),
            net_price=("net_price", "median"),
            completion=("completion_rate", "median"),
            debt_to_earnings=("debt_to_earnings", "median"),
        )
        .reset_index()
    )
    metric = st.radio(
        "Trend metric (median across institutions)", ["earnings", "net_price", "completion", "debt_to_earnings"], horizontal=True
    )
    fig = px.line(med, x="release_year", y=metric, color="sector", markers=True, color_discrete_map=c.COLORS)
    fig.update_xaxes(type="category", title="Scorecard release year (the six releases with 10-year earnings; not consecutive)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Level shifts between releases (notably 2014 to 2020) mix real change with Scorecard re-basing each release's dollars to a different year; "
        "values are nominal as published, so compare sectors within a release, not levels across releases."
    )
    st.subheader("Sector medians, latest selected release")
    last = med[med.release_year == med.release_year.max()]
    st.dataframe(last.round(3), hide_index=True, use_container_width=True)
    c.caveat()


def price():
    st.title("Price vs earnings")
    df = c.filters(c.institutions())
    d = df.dropna(subset=["net_price", "earnings"])
    st.write(
        f"Each dot is an institution-year ({d.unitid.nunique():,} institutions). Line: ordinary least squares fit with a 95% band for the mean."
    )
    fig = px.scatter(
        d, x="net_price", y="earnings", color="sector", opacity=0.35, color_discrete_map=c.COLORS, hover_name="institution_name"
    )
    if len(d) > 30:
        x = d.net_price.to_numpy()
        y = d.earnings.to_numpy()
        b, a = np.polyfit(x, y, 1)
        xs = np.linspace(x.min(), np.percentile(x, 99), 60)
        resid = y - (a + b * x)
        se = np.sqrt(resid.var(ddof=2) * (1 / len(x) + (xs - x.mean()) ** 2 / ((x - x.mean()) ** 2).sum()))
        fig.add_trace(go.Scatter(x=xs, y=a + b * xs, mode="lines", line=dict(color="black"), name="OLS fit"))
        fig.add_trace(
            go.Scatter(
                x=np.r_[xs, xs[::-1]],
                y=np.r_[a + b * xs + 1.96 * se, (a + b * xs - 1.96 * se)[::-1]],
                fill="toself",
                fillcolor="rgba(0,0,0,0.15)",
                line=dict(width=0),
                name="95% band",
                hoverinfo="skip",
            )
        )
    fig.update_layout(xaxis_title="Average net price ($)", yaxis_title="Median earnings 10 years after entry ($)")
    st.plotly_chart(fig, use_container_width=True)
    st.subheader("After accounting for who enrolls")
    q1 = c.table("q1_price_vs_earnings.csv")
    q1 = q1[q1.skipped.isna() | (q1.skipped.astype(str) == "")]
    t = q1[q1.cut.isin(["all", "sector"])][
        [
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
        ]
    ]
    st.dataframe(t.round(2), hide_index=True, use_container_width=True)
    st.caption(
        "Residualised = after Pell share, admission rate, state and release year. Intervals are institution-clustered bootstrap (Spearman) and clustered OLS (percent per $10,000). Filters above do not change this table."
    )
    c.caveat()


def florida():
    st.title("Florida public universities vs public peers")
    gaps = c.table("q3_florida_gaps.csv")
    years = sorted(gaps.release_year.unique())
    year = st.sidebar.selectbox("Release year", years, index=len(years) - 1)
    g = gaps[gaps.release_year == year]
    for grp in ["Florida public 4-year", "Florida public community college"]:
        st.subheader(grp)
        d = g[g.fl_group == grp][["metric", "n_fl", "n_peers", "fl_median", "peer_median", "gap", "ci_lo", "ci_hi"]]
        st.dataframe(d.round(3), hide_index=True, use_container_width=True)
    st.image(
        str(c.CHARTS / "q3_florida_gaps.png"),
        caption="Gap vs non-Florida public peers, latest release (95% bootstrap CI). Filters on the sidebar apply to the tables above only through the year.",
    )
    st.subheader("Rank table, latest release (public 4-year earnings rank within Florida)")
    st.dataframe(c.table("q3_florida_rank_table.csv").round(2), hide_index=True, use_container_width=True)
    st.subheader("Over- and under-performers: actual vs what the model predicts for similar institutions")
    ou = c.table("florida_over_under.csv")
    st.dataframe(ou.round(1), hide_index=True, use_container_width=True)
    st.caption(
        "mean_resid_pct = average out-of-fold residual across releases. Typical residual is about 23%, so small differences are noise. Florida groups are small (n=12 universities)."
    )
    c.caveat()


def model():
    st.title("Models: how well can earnings be predicted?")
    met = c.table("model_metrics.csv")
    st.info(
        "How to read this: each model is scored on institutions it never saw (grouped validation) and, separately, on the newest release after training on older ones (temporal). "
        "MAE is the typical dollar miss; lower is better. A model is useful only if it beats the baseline medians. SHAP shows which inputs move predictions; it does not show causes."
    )
    for v in met.validation.unique():
        t = met[(met.validation == v) & (met.metric.isin(["R2_log", "MAE_dollars", "MdAPE_pct"]))]
        piv = t.pivot(index="model", columns="metric", values="estimate").round(3)
        lo = t.pivot(index="model", columns="metric", values="ci_lo").round(3).add_suffix(" lo")
        hi = t.pivot(index="model", columns="metric", values="ci_hi").round(3).add_suffix(" hi")
        st.subheader(v)
        st.dataframe(piv.join(lo).join(hi), use_container_width=True)
    a, b = st.columns(2)
    a.image(str(c.CHARTS / "shap_summary.png"), caption="SHAP summary (gradient boosting)")
    b.image(str(c.CHARTS / "shap_dependence_net_price.png"), caption="Net price dependence")
    st.image(str(c.CHARTS / "shap_top_drivers_by_sector.png"), caption="Top drivers by sector")
    st.image(str(c.CHARTS / "residual_diagnostics.png"), caption="Residuals vs fitted, enrollment, sector, state")
    st.warning(
        "Limits: association is not causation; earnings reflect who enrolls; suppression removes small and some for-profit institutions; "
        "earnings describe a cohort about a decade old; release year is a dollar-base effect, not an institution trait."
    )
    c.caveat()


pages = [
    st.Page(overview, title="Overview", url_path="overview", default=True),
    st.Page(price, title="Price vs earnings", url_path="price"),
    st.Page(florida, title="Florida", url_path="florida"),
    st.Page(model, title="Model", url_path="model"),
]
st.navigation(pages).run()
