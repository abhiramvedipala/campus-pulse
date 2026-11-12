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
