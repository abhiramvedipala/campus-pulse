import duckdb
import pandas as pd

from campuspulse import config as C
from campuspulse import load


def snapshot(path):
    con = duckdb.connect(str(path), read_only=True)
    out = {}
    for (t,) in con.execute("select table_name from information_schema.tables where table_schema='raw' order by 1").fetchall():
        out[t] = con.execute(f"select md5(string_agg(cast(r as varchar), '|' order by cast(r as varchar))) from raw.{t} r").fetchone()[0]
    con.close()
    return out


def test_clean_turns_sentinels_into_null_and_counts_them():
    df = pd.DataFrame({"A": ["1", "NULL", "PrivacySuppressed", "PS", "NA", ""], "B": ["x", "y", "z", "w", "v", "u"]})
    clean, stats = load.clean_scorecard(df, "r")
    assert clean.A.isna().tolist() == [False, True, True, True, True, True]
    a = stats[stats.column_name == "A"].iloc[0]
    assert (a.n_suppressed, a.n_null_literal, a.n_nonnull) == (2, 3, 1)


def test_load_is_idempotent():
    load.run(fixture=True)
    first = snapshot(load.db_path(True))
    load.run(fixture=True)
    assert snapshot(load.db_path(True)) == first


def test_no_sentinel_strings_survive_in_warehouse():
    load.run(fixture=True)
    con = duckdb.connect(str(load.db_path(True)), read_only=True)
    bad = con.execute("select count(*) from raw.scorecard where MD_EARN_WNE_P10 in ('NULL','PrivacySuppressed','PS','','NA')").fetchone()[0]
    assert bad == 0
    assert {r for (r,) in con.execute("select distinct release from raw.scorecard").fetchall()} == set(C.RELEASES)
