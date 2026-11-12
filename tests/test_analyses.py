"""SQL analyses on the fixture must equal an independent pandas recomputation from the raw fixture CSVs."""

import os
import subprocess
import sys

import duckdb
import numpy as np
import pandas as pd
import pytest

from campuspulse import analyses, load
from campuspulse import config as C
from campuspulse import stats as S


@pytest.fixture(scope="module")
def con():
    os.environ["CP_ROW_FLOOR"] = "250"
    load.run(fixture=True)
    subprocess.run(
        [sys.executable, "-m", "dbt.cli.main", "build", "--profiles-dir", ".", "-q"], cwd=C.ROOT / "dbt", check=True, env=os.environ
    )
    return duckdb.connect(str(load.db_path(True)), read_only=True)


@pytest.fixture(scope="module")
def raw():
    """Fixture CSVs -> typed pandas frame with the same business rules, written independently of the dbt SQL."""
    frames = []
    for rel in C.RELEASES:
        d = pd.read_csv(C.FIXTURES / f"scorecard_{rel}.csv", dtype=str, keep_default_na=False)
        d["release_year"] = int(rel[:4])
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    num = lambda c: pd.to_numeric(d[c], errors="coerce")  # noqa: E731
    np_ = num("NPT4_PUB").fillna(num("NPT4_PRIV"))
    out = pd.DataFrame(
        {
            "unitid": num("UNITID").astype(int),
            "release_year": d.release_year,
            "state": d.STABBR.where(d.STABBR != ""),
            "sector": num("CONTROL").map({1: "public", 2: "private nonprofit", 3: "private for-profit"}),
            "level": num("PREDDEG").map({3: "4-year", 2: "2-year"}),
            "net_price": np_.where(np_.between(0, 100000)),
            "earnings": num("MD_EARN_WNE_P10"),
            "completion": num("C150_4").fillna(num("C150_L4")),
            "debt": num("GRAD_DEBT_MDN"),
        }
    )
    out["d2e"] = out.debt / out.earnings
    return out


def test_q1_rows_and_mean_earnings(con, raw):
    sql = analyses.sql(con, "01_price_vs_earnings.sql")
    exp = raw[raw.net_price.notna() & raw.earnings.notna() & raw.sector.notna() & raw.state.notna()]
    assert len(sql) == len(exp)
    assert sql.earnings.mean() == pytest.approx(exp.earnings.mean())
    assert sql.net_price.median() == pytest.approx(exp.net_price.median())


def test_q2_sector_year_medians(con, raw):
    sql = analyses.sql(con, "02_completion_debt.sql")
    s = sql[sql.institution_level.isna()].set_index(["sector", "release_year"])
    exp = raw[raw.sector.notna()].groupby(["sector", "release_year"])
    for key in [("public", 2022), ("private nonprofit", 2011), ("private for-profit", 2020)]:
        g = exp.get_group(key)
        assert s.loc[key, "completion_unweighted_median"] == pytest.approx(g.completion.median())
        assert s.loc[key, "median_debt_to_earnings"] == pytest.approx(g.d2e.median())
        assert s.loc[key, "n_institutions"] == len(g)


def test_q3_florida_group_and_peer_counts(con, raw):
    sql = analyses.sql(con, "03_florida.sql")
    pub = raw[(raw.sector == "public") & raw.level.isin(["4-year", "2-year"])]
    assert len(sql) == len(pub)
    fl4 = sql[(sql.fl_group == "Florida public 4-year") & (sql.release_year == 2022)]
    exp = pub[(pub.state == "FL") & (pub.level == "4-year") & (pub.release_year == 2022)]
    assert len(fl4) == len(exp) and fl4.earnings.median() == pytest.approx(exp.earnings.median())


def test_q4_one_row_per_institution_and_metric_latest_release(con, raw):
    sql = analyses.sql(con, "04_sector_differences.sql")
    assert not sql.duplicated(["unitid", "metric"]).any()
    e = raw[raw.earnings.notna() & raw.sector.notna()].sort_values("release_year").groupby("unitid").tail(1)
    got = sql[sql.metric == "earnings"].set_index("unitid")
    assert len(got) == len(e)
    assert (got.loc[e.unitid, "release_year"].to_numpy() == e.release_year.to_numpy()).all()


def test_bootstrap_is_seeded_and_reproducible():
    df = pd.DataFrame({"unitid": np.repeat(np.arange(40), 3), "x": np.random.default_rng(1).normal(size=120)})
    g = S.unit_groups(df.unitid)
    f = lambda i: df.x.to_numpy()[i].mean()  # noqa: E731
    a = S.cluster_boot(g, f, 50, S.rng_for("t"))
    b = S.cluster_boot(g, f, 50, S.rng_for("t"))
    assert np.array_equal(a, b)
    assert not np.array_equal(a, S.cluster_boot(g, f, 50, S.rng_for("other")))
    r1 = analyses._gap(np.arange(20.0), np.arange(40.0), 50, S.rng_for("g"))
    r2 = analyses._gap(np.arange(20.0), np.arange(40.0), 50, S.rng_for("g"))
    assert r1 == r2
