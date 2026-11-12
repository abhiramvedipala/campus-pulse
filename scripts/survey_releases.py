"""One-off survey: per release, row count and non-null counts of key fields."""
import sys, zipfile, re
import pandas as pd
Z = sys.argv[1]
KEY = ["UNITID","MD_EARN_WNE_P10","NPT4_PUB","NPT4_PRIV","C150_4","C150_L4","GRAD_DEBT_MDN","DEBT_MDN","RET_FT4","RET_FTL4","PCTPELL","ADM_RATE","UGDS","CCBASIC","PREDDEG","CONTROL","STABBR"]
with zipfile.ZipFile(Z) as z:
    names = sorted(n for n in z.namelist() if re.match(r"MERGED\d{4}_\d\d_PP\.csv$", n))
    for n in names[-14:]:
        with z.open(n) as f:
            hdr = pd.read_csv(f, nrows=0).columns
        cols = [c for c in KEY if c in hdr]
        with z.open(n) as f:
            df = pd.read_csv(f, usecols=cols, dtype=str, na_values=["NULL","PrivacySuppressed"])
        miss = [c for c in KEY if c not in hdr]
        print(n, len(df), "ncols", len(hdr), "missing", miss)
        print("   ", {c: int(df[c].notna().sum()) for c in cols if c not in ("UNITID","INSTNM")})
