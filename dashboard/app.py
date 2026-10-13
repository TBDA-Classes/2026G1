# KAN-118 dashboard skeleton
# run from repo root: streamlit run dashboard/app.py
# for now this just checks that the app starts and can read the combined table,
# actual pages come in later sprints (7.3a overview, 7.4 chart, 7.14 warnings)

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
COMBINED = ROOT / "data" / "processed" / "combined.parquet"

st.set_page_config(page_title="Storey 1 energy", layout="wide")


@st.cache_data
def load_data():
    return pd.read_parquet(COMBINED)


st.title("Storey 1 energy dashboard")

with st.sidebar:
    st.header("Filters")
    st.write("zone/date filters coming in 7.17")

if not COMBINED.exists():
    st.warning("No combined table yet, run `python -m src.data.combine` first")
    st.stop()

df = load_data()

col1, col2, col3 = st.columns(3)
col1.metric("Rows", f"{len(df):,}")
col2.metric("Zones", df["zone"].nunique())
col3.metric("Period", f"{df['timestamp'].min():%Y-%m-%d} to {df['timestamp'].max():%Y-%m-%d}")

st.subheader("Rows per zone and circuit")
counts = df.groupby(["zone", "circuit"]).size().rename("rows").reset_index()
st.dataframe(counts, width="stretch", hide_index=True)

st.subheader("First rows")
st.dataframe(df.head(20), width="stretch", hide_index=True)
