## What it built
Download + load + DuckDB warehouse + dbt (staging, intermediate, 5 marts) + data dictionary + `scripts/check.sh` + CI (fixture mode).

## How it was tested
- `pytest` (5 tests: link scraping, sentinel cleaning, idempotent load, release coverage).
- `dbt build`: 10 models + seed, 18 data tests, all pass on real data and on the fixture.
- `scripts/check.sh --fixture` offline; `scripts/check.sh` on the real data.

## Numbers produced (see RESULTS.md)
6 releases; 9,536 distinct institutions; 44,408 institution-years; 35,270 with earnings; IPEDS match 94.2%; load 2.6 s.

## Open questions
- Years are 2011-2014, 2020, 2022: only releases with populated 10-year earnings (DECISIONS D-02).
- GitHub repo creation was blocked, so this PR was merged locally (see PROGRESS.md, Needs me).
