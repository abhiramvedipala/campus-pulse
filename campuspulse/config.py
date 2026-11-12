"""Single source of truth for paths, releases and the columns kept from the raw files."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
STAGING = ROOT / "data" / "staging"
FIXTURES = ROOT / "data" / "fixtures"
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
FIXTURE_WAREHOUSE = ROOT / "data" / "warehouse_fixture.duckdb"


def reports_dir(fixture: bool = False) -> Path:
    """Committed outputs live in reports/; fixture runs write to an ignored sibling so they never clobber real numbers."""
    d = ROOT / ("reports_fixture" if fixture else "reports")
    d.mkdir(exist_ok=True)
    return d


def charts_dir(fixture: bool = False) -> Path:
    d = ROOT / "docs" / ("charts_fixture" if fixture else "charts")
    d.mkdir(parents=True, exist_ok=True)
    return d


SCORECARD_PAGE = "https://collegescorecard.ed.gov/data/"
DICT_URL = "https://collegescorecard.ed.gov/assets/CollegeScorecardDataDictionary.xlsx"
IPEDS_BASE = "https://nces.ed.gov/ipeds/datacenter/data/"

# Chosen by measurement (scripts/survey_releases.py, DECISIONS.md D-02): the six most recent
# Scorecard institution-level releases in which MD_EARN_WNE_P10 is populated.
RELEASES = ["2011_12", "2012_13", "2013_14", "2014_15", "2020_21", "2022_23"]
# IPEDS survey year used for a release = first calendar year of the release label.
IPEDS_YEARS = {r: int(r[:4]) for r in RELEASES}

# (logical column, source column in the MERGED file). Names are identical across the six
# releases (verified, see dbt/seeds/column_map.csv); kept as a list so a rename is a one-line edit.
SCORECARD_COLS = [
    # identity / classification
    "UNITID",
    "INSTNM",
    "CITY",
    "STABBR",
    "CONTROL",
    "PREDDEG",
    "HIGHDEG",
    "CCBASIC",
    "LOCALE",
    "REGION",
    "HBCU",
    "MENONLY",
    "WOMENONLY",
    # admissions and enrollment
    "ADM_RATE",
    "SAT_AVG",
    "ACTCMMID",
    "UGDS",
    "UGDS_WHITE",
    "UGDS_BLACK",
    "UGDS_HISP",
    "UGDS_ASIAN",
    "UG25ABV",
    "PCTPELL",
    "PCTFLOAN",
    "PAR_ED_PCT_1STGEN",
    "FEMALE",
    # price and cost
    "NPT4_PUB",
    "NPT4_PRIV",
    "NPT41_PUB",
    "NPT41_PRIV",
    "NPT45_PUB",
    "NPT45_PRIV",
    "COSTT4_A",
    "TUITIONFEE_IN",
    "TUITIONFEE_OUT",
    "TUITFTE",
    "INEXPFTE",
    "AVGFACSAL",
    "PFTFAC",
    # completion and retention
    "C150_4",
    "C150_L4",
    "RET_FT4",
    "RET_FTL4",
    # debt and repayment
    "GRAD_DEBT_MDN",
    "DEBT_MDN",
    "WDRAW_DEBT_MDN",
    "CDR3",
    # earnings (target and earnings-derived fields; the latter are leakage-excluded in models)
    "MD_EARN_WNE_P10",
    "MN_EARN_WNE_P10",
    "COUNT_WNE_P10",
    "MD_EARN_WNE_P6",
    "MD_EARN_WNE_P8",
]

IPEDS_HD_COLS = ["UNITID", "SECTOR", "ICLEVEL", "CONTROL", "HBCU", "LOCALE", "CCBASIC", "C21BASIC", "CYACTIVE"]
IPEDS_SFA_COLS = ["UNITID", "SCUGRAD", "UAGRNTP", "UAGRNTA", "UPGRNTP", "UFLOANP", "UFLOANA"]
IPEDS_DRVGR_COLS = ["UNITID", "GRRTTOT", "BAGR150", "L4GR150"]
IPEDS_DRVEF_COLS = ["UNITID", "ENRTOT", "FTE", "EFUG"]
IPEDS_DRVC_COLS = ["UNITID", "BASDEG", "ASCDEG", "CERT1", "CERT2"]


def ipeds_files(year: int) -> dict[str, str]:
    """IPEDS file stems for a survey year; the derived DRV* files only exist for recent years."""
    sfa = f"SFA{year % 100:02d}{(year + 1) % 100:02d}"
    return {"hd": f"HD{year}", "sfa": sfa, "drvgr": f"DRVGR{year}", "drvef": f"DRVEF{year}", "drvc": f"DRVC{year}"}
