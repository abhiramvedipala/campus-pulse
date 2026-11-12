"""Shared loading and layout helpers. The app reads only committed outputs in reports/ and docs/charts/."""

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from campuspulse import config as cfg  # noqa: E402

FIXTURE = os.environ.get("CAMPUSPULSE_FIXTURE") == "1"
REPORTS = cfg.reports_dir(FIXTURE)
CHARTS = cfg.charts_dir(FIXTURE)
SECTORS = ["public", "private nonprofit", "private for-profit"]
COLORS = {"public": "#1f77b4", "private nonprofit": "#2ca02c", "private for-profit": "#d62728"}
DOLLAR_NOTE = "Dollars are nominal as published. Earnings describe a cohort that entered about a decade before the release year."


@st.cache_data
def table(name: str) -> pd.DataFrame:
    return pd.read_csv(REPORTS / name)


@st.cache_data
def institutions() -> pd.DataFrame:
    return pd.read_csv(REPORTS / "institution_year_slim.csv.gz")


def filters(df: pd.DataFrame) -> pd.DataFrame:
    """Sidebar filters by sector, state and release year; applied to institution-year data."""
    st.sidebar.header("Filters")
    sectors = st.sidebar.multiselect("Sector", SECTORS, default=SECTORS)
    states = st.sidebar.multiselect("State (empty = all)", sorted(df.state.dropna().unique()))
    years = st.sidebar.multiselect("Release year", sorted(df.release_year.unique()), default=sorted(df.release_year.unique()))
    out = df[df.sector.isin(sectors) & df.release_year.isin(years)]
    if states:
        out = out[out.state.isin(states)]
    st.sidebar.caption(f"{out.unitid.nunique():,} institutions, {len(out):,} institution-years selected")
    return out


def caveat() -> None:
    st.caption(DOLLAR_NOTE + " Results are associations between institutions, not effects of attending one.")
