"""One-off survey: per release, row count and non-null counts of key fields."""

import pathlib
import re
import sys
import zipfile

import pandas as pd

Z = sys.argv[1]
KEY = [
    "UNITID",
    "MD_EARN_WNE_P10",
    "NPT4_PUB",
    "NPT4_PRIV",
    "C150_4",
    "C150_L4",
    "GRAD_DEBT_MDN",
    "DEBT_MDN",
    "RET_FT4",
    "RET_FTL4",
    "PCTPELL",
    "ADM_RATE",
    "UGDS",
    "CCBASIC",
    "PREDDEG",
    "CONTROL",
    "STABBR",
]
with zipfile.ZipFile(Z) as z:
    names = sorted(n for n in z.namelist() if re.match(r"MERGED\d{4}_\d\d_PP\.csv$", n))
    rows = []
    for n in names[-20:]:
        with z.open(n) as f:
            hdr = pd.read_csv(f, nrows=0).columns
        cols = [c for c in KEY if c in hdr]
        with z.open(n) as f:
            df = pd.read_csv(f, usecols=cols, dtype=str, na_values=["NULL", "PrivacySuppressed", "PS", "NA"])
        miss = [c for c in KEY if c not in hdr]
        print(n, len(df), "ncols", len(hdr), "missing", miss)
        counts = {c: int(df[c].notna().sum()) for c in cols if c != "UNITID"}
        print("   ", counts)
        rows.append({"release": n[6:13], "rows": len(df), **{f"nonnull_{k}": v for k, v in counts.items()}})
    out = pathlib.Path(__file__).resolve().parent.parent / "reports" / "release_survey.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
