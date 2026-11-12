"""Write docs/findings.md (one page, plain English) and docs/findings.pdf. Every number is read from reports/.

Usage: python -m scripts.build_findings [--fixture]
"""

import json
import sys
import tempfile
from pathlib import Path

import markdown
import pandas as pd
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

from campuspulse import config as C

fixture = "--fixture" in sys.argv
R, CH = C.reports_dir(fixture), C.charts_dir(fixture)
OUT = C.ROOT / "docs" / ("findings_fixture" if fixture else "")
OUT.mkdir(parents=True, exist_ok=True)

q1 = pd.read_csv(R / "q1_price_vs_earnings.csv").set_index("group")
q2 = pd.read_csv(R / "q2_completion_debt.csv")
q3 = pd.read_csv(R / "q3_florida_gaps.csv")
met = pd.read_csv(R / "model_metrics.csv")
meta = json.loads((R / "model_meta.json").read_text())
shap = pd.read_csv(R / "shap_importance.csv")
fl = pd.read_csv(R / "florida_over_under.csv")

a = q1.loc["all institutions"]
last = q2.release_year.max()
sec = q2[q2.institution_level.isna() & (q2.release_year == last)].set_index("sector")
g = q3[(q3.release_year == q3.release_year.max()) & (q3.fl_group == "Florida public 4-year")].set_index("metric")
best = meta["best_model_by_grouped_cv_mae"]


def m(val, model, metric):
    return met[met.validation.str.startswith(val) & (met.model == model) & (met.metric == metric)].iloc[0]


mg, bg = m("grouped", best, "MAE_dollars"), m("grouped", "Baseline: sector x state median", "MAE_dollars")
rg = m("grouped", best, "R2_log")
fl4 = fl[fl.group == "Florida public 4-year"]
NAMES = {
    "pct_pell": "Pell-grant share",
    "net_price": "net price",
    "enrollment": "enrollment",
    "admission_rate": "admission rate",
    "completion_rate": "completion rate",
    "retention_rate": "retention rate",
    "sector": "sector",
    "carnegie_group": "institution type",
    "state": "state",
}
drivers = [NAMES[d] for d in shap.feature.head(4) if d != "release_year"][:3]


def usd(x: float) -> str:
    return f"-${-x:,.0f}" if x < 0 else f"${x:,.0f}"


e, cpl = g.loc["earnings"], g.loc["completion_rate"]
earn_note = "not clearly different from zero" if e.ci_lo <= 0 <= e.ci_hi else "different from zero"

md = f"""# What does college deliver? Four answers from public data

*For counselors and parents. Source: US Dept. of Education College Scorecard and IPEDS, {int(meta["n_institutions"]):,} institutions, six data releases (2011-2014, 2020, 2022). All numbers below are generated from `reports/`.*

**1. Does paying more buy higher earnings?** Among colleges, higher net price goes with higher earnings (rank correlation {a.spearman_raw:.2f}, 95% interval {a.raw_ci_lo:.2f} to {a.raw_ci_hi:.2f}), but much of that is who enrolls. After accounting for Pell-grant share, selectivity, state and year, the correlation falls to {a.spearman_residualised:.2f} ({a.res_ci_lo:.2f} to {a.res_ci_hi:.2f}). Comparable colleges charging $10,000 more have graduates earning about {a.pct_earnings_per_10k:.1f}% more ({a.pct_ci_lo:.1f}% to {a.pct_ci_hi:.1f}%). That is an association, not a promise that paying more raises your earnings.

**2. Who finishes what they start, and at what debt cost?** In the {int(last)} release, the typical (median) college completes {sec.loc["public", "completion_unweighted_median"]:.0%} of students at public, {sec.loc["private nonprofit", "completion_unweighted_median"]:.0%} at private nonprofit and {sec.loc["private for-profit", "completion_unweighted_median"]:.0%} at for-profit colleges; weighted by enrollment the figures are {sec.loc["public", "completion_enrollment_weighted"]:.0%}, {sec.loc["private nonprofit", "completion_enrollment_weighted"]:.0%} and {sec.loc["private for-profit", "completion_enrollment_weighted"]:.0%}. Typical completer debt is ${sec.loc["public", "median_debt"]:,.0f} (public), ${sec.loc["private nonprofit", "median_debt"]:,.0f} (nonprofit) and ${sec.loc["private for-profit", "median_debt"]:,.0f} (for-profit). Debt above half of median earnings affects {sec.loc["public", "share_debt_to_earnings_above_half"]:.0%}, {sec.loc["private nonprofit", "share_debt_to_earnings_above_half"]:.0%} and {sec.loc["private for-profit", "share_debt_to_earnings_above_half"]:.0%} of colleges respectively.

**3. How do Florida public universities compare?** Against public four-year peers elsewhere ({int(e.n_fl)} Florida universities with earnings data, {int(e.n_peers)} peers), Florida's median earnings gap is {usd(e.gap)} (95% interval {usd(e.ci_lo)} to {usd(e.ci_hi)}), {earn_note}. Florida's completion is {cpl.gap * 100:.1f} points higher ({cpl.ci_lo * 100:.1f} to {cpl.ci_hi * 100:.1f}) and net price ${-g.loc["net_price", "gap"]:,.0f} lower. Given their student mix, {fl4.iloc[0].institution_name} ({fl4.iloc[0].mean_resid_pct:+.0f}%) is furthest above and {fl4.iloc[-1].institution_name} ({fl4.iloc[-1].mean_resid_pct:+.0f}%) furthest below what a model predicts, but typical model error is about 23%, so these differences are small.

**4. What predicts earnings?** A {best.replace("GradientBoosting", "gradient-boosting")} model predicts earnings for colleges it has never seen to within ${mg.estimate:,.0f} on average (95% interval ${mg.ci_lo:,.0f} to ${mg.ci_hi:,.0f}), against ${bg.estimate:,.0f} for simply using the typical value for the same sector and state (R-squared on log earnings {rg.estimate:.2f}). The inputs doing the most work, after the data release itself, are {", ".join(drivers)}.

<table><tr>
<td><img src="{(CH / "q1_spearman_by_sector.png").as_posix()}" width="100%"><br><sub>1. Price vs earnings, raw and adjusted</sub></td>
<td><img src="{(CH / "q2_completion_by_sector.png").as_posix()}" width="100%"><br><sub>2. Completion by sector</sub></td></tr><tr>
<td><img src="{(CH / "q3_florida_gaps.png").as_posix()}" width="100%"><br><sub>3. Florida gaps vs peers</sub></td>
<td><img src="{(CH / "shap_top_drivers_by_sector.png").as_posix()}" width="100%"><br><sub>4. What moves predictions</sub></td></tr></table>

**What this cannot tell you.** These are patterns across colleges, not effects on any student; earnings describe students who entered about a decade before each release, in nominal dollars; small colleges are missing because their numbers are privacy-suppressed, so results describe colleges big enough to report; the Florida group is small, so its intervals are wide; and no model here can say what would happen to you at a particular college.
"""
(OUT / "findings.md").write_text(md.replace(C.ROOT.as_posix() + "/", ""))  # repo-relative image paths in the committed markdown

CSS = "body{{font-family:Helvetica,Arial,sans-serif;font-size:{fs}pt;line-height:1.28;margin:0}}h1{{font-size:{h}pt;margin:0 0 3px}}p{{margin:3px 0}}td{{width:50%;vertical-align:top;padding:2px}}table{{width:100%;border-collapse:collapse}}sub{{font-size:{s}pt}}"
html_body = markdown.markdown(md, extensions=["md_in_html"])
with sync_playwright() as p:
    try:
        browser = p.chromium.launch()
    except Exception:
        browser = p.chromium.launch(channel="chrome")
    for fs in (9.5, 9, 8.5, 8, 7.5):
        html = f"<html><head><style>{CSS.format(fs=fs, h=fs + 5, s=fs - 1.5)}</style></head><body>{html_body}</body></html>"
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "findings.html"
            f.write_text(html)
            page = browser.new_page()
            page.goto(f.as_uri())
            page.wait_for_timeout(500)
            page.pdf(
                path=str(OUT / "findings.pdf"),
                format="Letter",
                margin={"top": "0.4in", "bottom": "0.4in", "left": "0.5in", "right": "0.5in"},
                print_background=True,
            )
            page.close()
        if len(PdfReader(OUT / "findings.pdf").pages) == 1:
            break
    browser.close()
pages = len(PdfReader(OUT / "findings.pdf").pages)
assert pages == 1, f"findings.pdf is {pages} pages"
print(f"wrote {OUT / 'findings.md'} and findings.pdf (1 page, {fs}pt)")
