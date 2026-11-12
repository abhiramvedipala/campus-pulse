# What does college deliver? Four answers from public data

*For counselors and parents. Source: US Dept. of Education College Scorecard and IPEDS, 7,998 institutions, six data releases (2011-2014, 2020, 2022). All numbers below are generated from `reports/`.*

**1. Does paying more buy higher earnings?** Among colleges, higher net price goes with higher earnings (rank correlation 0.30, 95% interval 0.28 to 0.32), but much of that is who enrolls. After accounting for Pell-grant share, selectivity, state and year, the correlation falls to 0.17 (0.15 to 0.19). Comparable colleges charging $10,000 more have graduates earning about 8.7% more (7.7% to 9.6%). That is an association, not a promise that paying more raises your earnings.

**2. Who finishes what they start, and at what debt cost?** In the 2022 release, the typical (median) college completes 40% of students at public, 58% at private nonprofit and 64% at for-profit colleges; weighted by enrollment the figures are 49%, 64% and 48%. Typical completer debt is $12,000 (public), $22,500 (nonprofit) and $9,500 (for-profit). Debt above half of median earnings affects 2%, 15% and 11% of colleges respectively.

**3. How do Florida public universities compare?** Against public four-year peers elsewhere (12 Florida universities with earnings data, 579 peers), Florida's median earnings gap is $3,004 (95% interval -$3,779 to $8,601), not clearly different from zero. Florida's completion is 15.9 points higher (7.6 to 24.1) and net price $5,852 lower. Given their student mix, Florida International University (+12%) is furthest above and Florida State University (-9%) furthest below what a model predicts, but typical model error is about 23%, so these differences are small.

**4. What predicts earnings?** A gradient-boosting model predicts earnings for colleges it has never seen to within $5,438 on average (95% interval $5,284 to $5,593), against $8,503 for simply using the typical value for the same sector and state (R-squared on log earnings 0.74). The inputs doing the most work, after the data release itself, are net price, Pell-grant share, enrollment.

<table><tr>
<td><img src="docs/charts/q1_spearman_by_sector.png" width="100%"><br><sub>1. Price vs earnings, raw and adjusted</sub></td>
<td><img src="docs/charts/q2_completion_by_sector.png" width="100%"><br><sub>2. Completion by sector</sub></td></tr><tr>
<td><img src="docs/charts/q3_florida_gaps.png" width="100%"><br><sub>3. Florida gaps vs peers</sub></td>
<td><img src="docs/charts/shap_top_drivers_by_sector.png" width="100%"><br><sub>4. What moves predictions</sub></td></tr></table>

**What this cannot tell you.** These are patterns across colleges, not effects on any student; earnings describe students who entered about a decade before each release, in nominal dollars; small colleges are missing because their numbers are privacy-suppressed, so results describe colleges big enough to report; the Florida group is small, so its intervals are wide; and no model here can say what would happen to you at a particular college.
