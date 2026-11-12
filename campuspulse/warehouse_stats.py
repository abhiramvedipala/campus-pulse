"""Phase 1 measurements: coverage, suppression, IPEDS match rate and dbt test counts -> reports/."""

import argparse
import json

import duckdb

from . import config as C
from . import load


def run(fixture: bool = False) -> dict:
    out = C.reports_dir(fixture)
    con = duckdb.connect(str(load.db_path(fixture)), read_only=True)
    con.sql("""
        select release_label, release_year, count(*) as institutions,
               round(avg((median_earnings_p10 is not null)::int), 4) as share_earnings,
               round(avg((net_price is not null)::int), 4) as share_net_price,
               round(avg((completion_rate is not null)::int), 4) as share_completion,
               round(avg((median_grad_debt is not null)::int), 4) as share_grad_debt,
               round(avg(ipeds_matched::int), 4) as ipeds_match_rate
        from marts.fct_institution_year group by 1, 2 order by 2
    """).df().to_csv(out / "coverage_by_release.csv", index=False)
    con.sql("""
        select release, column_name, n_rows, n_suppressed, n_null_literal, n_nonnull,
               round(n_suppressed::double / n_rows, 4) as suppressed_share,
               round(1 - n_nonnull::double / n_rows, 4) as missing_share
        from raw.suppression order by column_name, release
    """).df().to_csv(out / "suppression_by_column.csv", index=False)
    # Slim exports so the dashboard runs from committed files alone (no warehouse needed).
    con.sql("select * from marts.mart_sector_year order by sector, release_year").df().to_csv(out / "sector_year.csv", index=False)
    con.sql("""
        select unitid, release_year, institution_name, state, sector, institution_level, carnegie_group,
               net_price, median_earnings_p10 as earnings, pct_pell, admission_rate, enrollment, completion_rate,
               median_grad_debt, debt_to_earnings
        from marts.fct_institution_year where sector is not null order by unitid, release_year
    """).df().round(4).to_csv(out / "institution_year_slim.csv.gz", index=False)
    one = lambda q: con.execute(q).fetchone()[0]  # noqa: E731
    stats = {
        "releases_loaded": one("select count(distinct release_year) from marts.fct_institution_year"),
        "distinct_institutions": one("select count(distinct unitid) from marts.fct_institution_year"),
        "rows_fct_institution_year": one("select count(*) from marts.fct_institution_year"),
        "rows_with_earnings": one("select count(*) from marts.fct_institution_year where has_earnings"),
        "ipeds_match_rate": round(one("select avg(ipeds_matched::int) from marts.fct_institution_year"), 4),
        "net_price_nulled_out_of_range": one(
            "select count(*) from marts.fct_institution_year where net_price_raw is not null and net_price is null"
        ),
        "ipeds_files_missing": [r[0] for r in con.execute("select source from raw.load_log where status='missing'").fetchall()],
    }
    rr = C.ROOT / "dbt" / "target" / "run_results.json"
    if rr.exists():
        res = json.loads(rr.read_text())["results"]
        tests = [r for r in res if r["unique_id"].startswith("test.")]
        stats["dbt_tests"] = len(tests)
        stats["dbt_tests_passed"] = sum(r["status"] == "pass" for r in tests)
        stats["dbt_models_built"] = sum(r["unique_id"].startswith("model.") and r["status"] == "success" for r in res)
    (out / "warehouse_stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats))
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true")
    run(ap.parse_args().fixture)
