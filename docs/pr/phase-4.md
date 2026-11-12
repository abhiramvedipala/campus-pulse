## What it built
Four-page Streamlit dashboard, per-page screenshots, one-page findings brief (Markdown + PDF, numbers generated), and a one-command refresh (`make refresh`, `make refresh FIXTURE=1`). README and interview notes completed.

## How it was tested
`scripts/check.sh --fixture` (17 pytest tests, 18 dbt tests); `make refresh FIXTURE=1` (40 s offline); `make refresh` on the real data (163 s).

## Numbers produced (RESULTS.md)
Refresh wall time 163 s; models and analyses unchanged between two full runs.

## Open questions
Streamlit Cloud deploy needs the owner's account (README has the steps).
