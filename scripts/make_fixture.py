"""Build the small committed fixture in data/fixtures/ from the real raw data (seeded, stratified)."""

import zipfile

import numpy as np
import pandas as pd

from campuspulse import config as C
from campuspulse import load

SEED, PER_SECTOR = 20, 125
C.FIXTURES.mkdir(parents=True, exist_ok=True)
zf = zipfile.ZipFile(C.RAW / "College_Scorecard_Raw_Data.zip")
raw = {r: load.read_scorecard_release(r, False, zf) for r in C.RELEASES}
allr = pd.concat([d.assign(release=r) for r, d in raw.items()])
has_earn = allr[~allr.MD_EARN_WNE_P10.isin(["NULL", "PrivacySuppressed"])].UNITID.unique()
latest = raw[C.RELEASES[-1]].drop_duplicates("UNITID").set_index("UNITID")
fl_pub4 = allr[(allr.STABBR == "FL") & (allr.CONTROL == "1") & (allr.PREDDEG == "3")].UNITID.unique()
fl_cc = allr[(allr.STABBR == "FL") & (allr.CONTROL == "1") & (allr.PREDDEG == "2")].UNITID.unique()
rng = np.random.default_rng(SEED)
keep = set(fl_pub4) | set(rng.choice(sorted(fl_cc), 8, replace=False))
pool = allr[allr.UNITID.isin(has_earn) & ~allr.UNITID.isin(keep)].drop_duplicates("UNITID")
for _, g in pool.groupby("CONTROL"):
    keep |= set(rng.choice(sorted(g.UNITID), min(PER_SECTOR, len(g)), replace=False))
keep = sorted(keep)
for r, d in raw.items():
    d[d.UNITID.isin(keep)].to_csv(C.FIXTURES / f"scorecard_{r}.csv", index=False)
for year in sorted(set(C.IPEDS_YEARS.values())):
    for kind in load.IPEDS_COLS:
        df = load.read_ipeds(kind, year, False)
        if df is not None:
            df[df.UNITID.isin(keep)].to_csv(C.FIXTURES / f"ipeds_{kind}_{year}.csv", index=False)
print(len(keep), "institutions;", sum(p.stat().st_size for p in C.FIXTURES.iterdir()) // 1024, "KB")
