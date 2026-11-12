# Interview notes

## Phase 1: ingestion, warehouse, data dictionary

**What it built**
- A resumable downloader that scrapes the dated Scorecard zip link, records SHA-256 and size, and tolerates missing IPEDS files.
- A loader that streams the 560 MB zip member by member (never extracted), keeps 50 of 3,379 columns as text, turns the four
  missing-value strings into NULL, counts suppression, and rebuilds the DuckDB `raw` schema in one transaction (idempotent).
- A dbt project: 4 staging models, 1 intermediate (`int_institution_year`), 5 marts, 18 tests, a column-map seed.
- A data dictionary generated from dbt metadata, plus a seeded 399-institution fixture so CI runs offline.

**Key decisions (and "why not X?")**
- *Why those six releases?* I counted non-null 10-year earnings per file. Only 8 of 20 recent files have any. "Six newest" would have
  given me no target variable. See D-02.
- *Why DuckDB + dbt, not pandas scripts?* The grain, joins and tests are the product; dbt makes the lineage and tests reviewable.
  DuckDB reads Parquet/pandas directly and needs no server.
- *Why text-first loading?* The files mix numbers with `PS`, `NA`, `NULL`; casting on read would silently drop or fail on them.
- *Why not a Docker Postgres?* Not needed at 44k rows and it would compete with another project for the shared Docker daemon.
- *Why a 0.85 IPEDS match threshold?* See D-05: observed minimum is 91.7%; the test is there to catch a broken join, not churn.

**Hardest problem**
Non-null counts equalled row counts. Three causes stacked: the files use `NA` and `PS`, not just the strings the spec named;
`DataFrame.replace` with `None` pads instead of nulling; and dbt's `try_cast` was hiding it downstream. I found it when the column-map
seed showed 0 empty columns for a field I knew was empty, then fixed the sentinel set and added a test.

**Likely questions**
1. *How do you know the load is idempotent?* A test loads the fixture twice and compares per-table md5 checksums of every row.
2. *What does suppression do to your analysis?* About 11% of earnings and 18% of completer-debt values are `PS`; it removes small
   institutions, so results describe institutions big enough to report, not all of them.
3. *How would you handle a Scorecard column rename?* `config.SCORECARD_COLS` and `column_map.csv`; the loader raises if a kept column is missing.
4. *Why a custom IPEDS match test?* To fail loudly on a bad join year, with the threshold justified from measured rates.
5. *Why are the years not consecutive?* Treasury only refreshed the earnings cohort in some releases; the newest four have none.

**Files to open**: `campuspulse/load.py`, `campuspulse/download.py`, `dbt/models/intermediate/int_institution_year.sql`,
`dbt/models/marts/schema.yml`, `dbt/tests/generic/`, `DECISIONS.md`, `docs/data-dictionary.md`.

## Phase 2: SQL analyses and statistical tests

**What it built**
- Four committed `.sql` files (price vs earnings, completion/debt, Florida, sector differences) run by `campuspulse/analyses.py`.
- Institution-clustered, seeded bootstrap intervals; partial Spearman (controls: Pell, admission rate, state, year) and a clustered OLS.
- Kruskal-Wallis plus Holm-corrected Mann-Whitney with epsilon-squared and rank-biserial effect sizes.
- CSVs in `reports/`, six charts in `docs/charts/`, and `findings_auto.md` whose sentences are generated from the numbers.

**Key decisions (and "why not X?")**
- *Why cluster the bootstrap by institution?* Each institution appears in up to six releases with overlapping cohorts; a row bootstrap would give intervals that are too narrow.
- *Why a partial Spearman and not just OLS?* Earnings and net price are skewed; ranks are robust. I report the OLS percent-per-$10k beside it so the effect has a unit.
- *Why latest-release-per-institution for rank tests?* Rank tests assume independent observations.
- *Why not a causal estimate for price?* Observational, selection on who enrolls; controls are proxies. The text says association throughout.

**Hardest problem**
Making the controls honest. Admission rate is missing for most 2-year and for-profit schools, so dropping missing rows would silently turn "all institutions" into "selective 4-year schools".
I fill with 0 plus a missing flag, which keeps all rows, and recompute the residualisation inside every bootstrap draw so the interval reflects it. A second bug: my config alias `C` shadowed patsy's `C()` in the formula.

**Likely questions**
1. *Net price vs earnings: what did you find?* Raw rho 0.30 (0.28 to 0.32), 0.17 (0.15 to 0.19) after controls; about 8.7% higher earnings per $10k of net price (7.7% to 9.6%). Still an association.
2. *Why do for-profits stay at 0.47 after controls?* I do not know; plausible explanations (programme mix, price tracking certificate length) are not tested here, so I only report it.
3. *How do you know the SQL is right?* Four tests recompute the same quantities from the raw fixture CSVs in pandas.
4. *Is Florida different?* Earnings gap is $3,004 (CI -$3,779 to $8,601): not distinguishable from zero with 12 universities; completion and net price gaps are clear.
5. *What is the minimum cell rule?* 30 institutions for sector/Carnegie groups, 8 for Florida with a small-n flag.

**Files to open**: `analysis/*.sql`, `campuspulse/analyses.py`, `campuspulse/stats.py`, `tests/test_analyses.py`, `reports/findings_auto.md`.
