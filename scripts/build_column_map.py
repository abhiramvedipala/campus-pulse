"""Write dbt/seeds/column_map.csv: per kept field and release, the source column, whether the
release has data for it, and the Scorecard cohort note from Institution_Cohort_Map."""

import duckdb
import pandas as pd

from campuspulse import config as C
from campuspulse import load

cm = pd.read_excel(C.RAW / "dict.xlsx", sheet_name="Institution_Cohort_Map", index_col=0)
con = duckdb.connect(str(load.db_path(False)), read_only=True)
rows = []
for rel in C.RELEASES:
    col = f"MERGED_{rel[:4]}-{rel[5:]} datafile"
    for f in C.SCORECARD_COLS:
        n = con.execute(f'select count("{f}") from raw.scorecard where release=?', [rel]).fetchone()[0]
        note = cm.at[f, col] if f in cm.index and col in cm.columns else None
        rows.append(
            {
                "field": f,
                "release": rel,
                "source_column": f,
                "renamed": False,
                "nonnull_rows": n,
                "cohort_note": "" if pd.isna(note) else str(note).replace("\n", " "),
            }
        )
pd.DataFrame(rows).to_csv(C.ROOT / "dbt/seeds/column_map.csv", index=False)
print(len(rows), "rows")
