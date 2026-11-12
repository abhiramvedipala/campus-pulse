"""Read raw Scorecard/IPEDS text, clean sentinel strings, write parquet and load DuckDB.

Usage: python -m campuspulse.load [--fixture]
Idempotent: every table is dropped and rebuilt from the same inputs, parquet writes are deterministic.
"""
import argparse
import io
import os
import time
import zipfile
import duckdb
import pandas as pd
from . import config as C

SENTINELS = ("NULL", "PrivacySuppressed")
IPEDS_COLS = {"hd": C.IPEDS_HD_COLS, "sfa": C.IPEDS_SFA_COLS, "drvgr": C.IPEDS_DRVGR_COLS,
              "drvef": C.IPEDS_DRVEF_COLS, "drvc": C.IPEDS_DRVC_COLS}


def db_path(fixture: bool):
    return C.Path(os.environ["CAMPUSPULSE_DB"]) if "CAMPUSPULSE_DB" in os.environ else (
        C.FIXTURE_WAREHOUSE if fixture else C.WAREHOUSE)


def _read_text(fh, cols) -> pd.DataFrame:
    """All columns as text, only the wanted ones that exist; BOM and padding stripped from headers."""
    df = pd.read_csv(fh, dtype=str, keep_default_na=False, encoding="latin1",
                     usecols=lambda c: c.strip().lstrip("ï»¿").lstrip("﻿") in cols)
    df.columns = [c.strip().lstrip("ï»¿").lstrip("﻿") for c in df.columns]
    return df


def read_scorecard_release(release: str, fixture: bool, zf: zipfile.ZipFile | None = None) -> pd.DataFrame:
    if fixture:
        return pd.read_csv(C.FIXTURES / f"scorecard_{release}.csv", dtype=str, keep_default_na=False)
    with zf.open(f"MERGED{release}_PP.csv") as fh:
        df = _read_text(fh, set(C.SCORECARD_COLS))
    missing = set(C.SCORECARD_COLS) - set(df.columns)
    if missing:  # a renamed/removed field must be recorded in dbt/seeds/column_map.csv, never guessed
        raise RuntimeError(f"{release}: columns missing from release: {sorted(missing)}")
    return df[C.SCORECARD_COLS]


def read_ipeds(kind: str, year: int, fixture: bool) -> pd.DataFrame | None:
    stem = C.ipeds_files(year)[kind]
    if fixture:
        p = C.FIXTURES / f"ipeds_{kind}_{year}.csv"
        return pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else None
    zp = C.RAW / "ipeds" / f"{stem}.zip"
    if not zp.exists():
        return None
    with zipfile.ZipFile(zp) as z:
        name = next(n for n in z.namelist() if n.lower() == f"{stem.lower()}.csv")  # skip *_rv revisions
        with z.open(name) as fh:
            return _read_text(fh, set(IPEDS_COLS[kind]))


def clean_scorecard(df: pd.DataFrame, release: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (cleaned frame with sentinels -> NULL, per-column suppression stats)."""
    rows = []
    for col in df.columns:
        s = df[col]
        rows.append({"release": release, "column_name": col, "n_rows": len(s),
                     "n_suppressed": int((s == "PrivacySuppressed").sum()),
                     "n_null_literal": int((s == "NULL").sum()) + int((s == "").sum()),
                     "n_nonnull": int((~s.isin(SENTINELS) & (s != "")).sum())})
    out = df.replace({"": None, "NULL": None, "PrivacySuppressed": None})
    return out, pd.DataFrame(rows)


def run(fixture: bool = False) -> dict:
    t0 = time.time()
    C.STAGING.mkdir(parents=True, exist_ok=True)
    stage = C.STAGING / ("fixture" if fixture else "real")
    stage.mkdir(exist_ok=True)
    zf = None if fixture else zipfile.ZipFile(C.RAW / "College_Scorecard_Raw_Data.zip")
    sc, supp, log = [], [], []
    for rel in C.RELEASES:
        raw = read_scorecard_release(rel, fixture, zf)
        clean, stats = clean_scorecard(raw, rel)
        clean.insert(0, "release", rel)
        clean.to_parquet(stage / f"scorecard_{rel}.parquet", index=False)
        sc.append(clean)
        supp.append(stats)
        log.append({"source": f"scorecard_{rel}", "status": "loaded", "rows": len(clean)})
    ip = {k: [] for k in IPEDS_COLS}
    for year in sorted(set(C.IPEDS_YEARS.values())):
        for kind in IPEDS_COLS:
            df = read_ipeds(kind, year, fixture)
            stem = C.ipeds_files(year)[kind]
            if df is None:  # newest/derived files may not exist: log and continue
                log.append({"source": stem, "status": "missing", "rows": 0})
                continue
            df.insert(0, "ipeds_year", year)
            df.to_parquet(stage / f"ipeds_{kind}_{year}.parquet", index=False)
            ip[kind].append(df)
            log.append({"source": stem, "status": "loaded", "rows": len(df)})
    path = db_path(fixture)
    con = duckdb.connect(str(path))
    con.execute("PRAGMA memory_limit='4GB'; PRAGMA threads=4; CREATE SCHEMA IF NOT EXISTS raw;")
    frames = {"scorecard": pd.concat(sc, ignore_index=True), "suppression": pd.concat(supp, ignore_index=True),
              "load_log": pd.DataFrame(log)}
    for k, parts in ip.items():
        if parts:
            frames[f"ipeds_{k}"] = pd.concat(parts, ignore_index=True)
    con.execute("BEGIN")
    for old in con.execute("select table_name from information_schema.tables where table_schema='raw'").fetchall():
        con.execute(f'DROP TABLE raw."{old[0]}"')
    for name, df in frames.items():
        con.register("df_", df)
        con.execute(f"CREATE TABLE raw.{name} AS SELECT * FROM df_")
        con.unregister("df_")
    con.execute("COMMIT")
    n = {t: con.execute(f"select count(*) from raw.{t}").fetchone()[0] for t in frames}
    con.close()
    secs = round(time.time() - t0, 1)
    print(f"loaded into {path.name} in {secs}s: {n}")
    return {"seconds": secs, "rows": n}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true")
    run(ap.parse_args().fixture)
