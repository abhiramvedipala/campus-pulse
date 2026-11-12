# Automatic findings

Generated from the CSVs in this folder by `python -m campuspulse.analyses`; never edited by hand.

**Q1 price vs earnings.** Across 6,927 institutions (31,233 institution-years), net price and earnings have Spearman rho = 0.30 (95% CI 0.28 to 0.32); after controlling for Pell share, admission rate, state and release year the partial rho is 0.17 (0.15 to 0.19). Each extra $10,000 of net price is associated with 8.7% higher earnings (7.7% to 9.6%, SEs clustered by institution); within public institutions the partial rho is 0.27 (n=1,980). This is an association among institutions, not the effect of paying more.

**Q2 completion and debt, 2022 release.** public: completion 40% (median, n=1,868) / 49% (enrollment-weighted), median completer debt $12,000, debt-to-earnings 0.24 with 2% above 0.5 (n=1,582); private nonprofit: completion 58% (median, n=1,433) / 64% (enrollment-weighted), median completer debt $22,500, debt-to-earnings 0.39 with 15% above 0.5 (n=1,372); private for-profit: completion 64% (median, n=2,058) / 48% (enrollment-weighted), median completer debt $9,500, debt-to-earnings 0.28 with 11% above 0.5 (n=1,772). Debt-to-earnings is a ratio of two institution medians, and the earnings cohort is about a decade old.

**Q3 Florida, 2022 release.** Florida public 4-year institutions (n=12) have median earnings $62,272 vs $59,268 for public 4-year peers elsewhere (n=579): gap $3,004 (95% bootstrap CI $-3,779 to $8,601); completion gap 15.9 points (7.6 to 24.1). The Florida group includes state colleges that award mostly bachelor's degrees; community colleges are compared separately in q3_florida_gaps.csv.

**Q4 sector differences.** Earnings differ across sectors (Kruskal-Wallis H = 2,748, p = 0.0e+00, epsilon-squared = 0.34, 95% CI 0.32 to 0.36, n = 7,998 institutions, latest release each). Largest pairwise gap: public vs private nonprofit, rank-biserial -0.23 (-0.26 to -0.19), Holm-adjusted p = 9.4e-36. Groups with fewer than 30 institutions are dropped from a test. Rank tests compare distributions, not causes.
