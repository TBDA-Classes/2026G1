"""Energy dashboard skeleton (KAN-118).

Run from the repo root:
    streamlit run dashboard/app.py

Pages are added sprint by sprint (KAN-128 overview, KAN-26 actual vs expected,
KAN-154 warnings, KAN-167 demo mode). This file only proves the stack runs and
can read the combined table.
"""
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
COMBINED = ROOT / "data" / "processed" / "combined.parquet"

st.set_page_config(page_title="Storey 1 energy dashboard", layout="wide")


@st.cache_data
def load_combined() -> pd.DataFrame:
    return pd.read_parquet(COMBINED)


st.title("Storey 1 energy dashboard")
st.caption("Skeleton (KAN-118). Pages arrive sprint by sprint.")

with st.sidebar:
    st.header("Filters")
    st.write("Zone and date filters land in KAN-140.")

if not COMBINED.exists():
    st.warning(
        "Combined table not found. Build it first:\n\n"
        "`python -m src.data.combine`"
    )
    st.stop()

df = load_combined()

c1, c2, c3 = st.columns(3)
c1.metric("Rows", f"{len(df):,}")
c2.metric("Zones", df["zone"].nunique())
c3.metric("Period", f"{df['timestamp'].min():%Y-%m-%d} to {df['timestamp'].max():%Y-%m-%d}")

st.subheader("Rows per zone and circuit")
st.dataframe(df.groupby(["zone", "circuit"]).size().rename("rows").reset_index(),
             use_container_width=True, hide_index=True)

st.subheader("Sample of the combined table")
st.dataframe(df.head(20), use_container_width=True, hide_index=True)
