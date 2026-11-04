import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import data_loader as dl
import ui

hourly, src = dl.load_hourly()
f = dl.get_filters()
monthly, per_circuit, gaps = dl.coverage_tables(src)
manifest = dl.load_manifest()

ui.page_header("Data quality", "Can I trust these numbers? · frozen dataset of the data team",
               dl.month_coverage(src, f["month"]))

# --- Reliability ----------------------------------------------------------------
counts = per_circuit["status"].value_counts()
cols = st.columns(4)
for col, label, note in zip(cols, ["Reliable", "Use with caution", "Unreliable"],
                            ["≥ 99 % of hours", "90–99 % of hours", "< 90 % of hours"]):
    with col.container(border=True):
        st.metric(label, int(counts.get(label, 0)))
        st.caption(f"of {len(per_circuit)} circuits · {note}")
with cols[3].container(border=True):
    st.metric("Used for waste", int(per_circuit["focus"].sum()))
    st.caption("focus circuits; the others are fixed loads")

# --- Periods ----------------------------------------------------------------------
if manifest:
    r = manifest["regimes"]
    st.markdown(
        f"**Two periods:** A = {r['A']['start_utc'][:10]} → {r['A']['end_utc'][:10]} "
        f"({r['A']['rows']:,} hours, one reading per hour) · B = {r['B']['start_utc'][:10]} → "
        f"{r['B']['end_utc'][:10]} ({r['B']['rows']:,} hours, minute readings averaged). "
        f"{manifest.get('note_gap', '')}")

# --- Monthly coverage ---------------------------------------------------------------
year = f["month"].year
m = monthly[monthly["month"].dt.year == year]
with st.container(border=True):
    st.markdown(f"**Share of hours with data, {year} (16 circuits)**")
    colors = ["#F97316" if v < config.COVERAGE_WARNING else "#0F766E" for v in m["coverage"]]
    fig = go.Figure(go.Bar(x=m["month"].dt.strftime("%b"), y=m["coverage"] * 100, marker_color=colors,
                           text=[f"{v:.0%}" for v in m["coverage"]], textposition="outside"))
    fig.update_layout(height=260, plot_bgcolor="white", margin=dict(l=0, r=0, t=10, b=0),
                      yaxis=dict(range=[0, 112], visible=False), xaxis=dict(type="category"))
    st.plotly_chart(fig)
    st.caption(f"Below {config.COVERAGE_WARNING:.0%} in orange: those months carry a warning on every page. "
               "COVID lockdown hours (until 21 Jun 2020) are left out, as in the models.")

left, right = st.columns(2)
with left.container(border=True):
    st.markdown("**Coverage per circuit**")
    pc = per_circuit.assign(coverage=(per_circuit["coverage"] * 100).round(1),
                            role=per_circuit["focus"].map({True: "focus", False: "fixed load"}))
    st.dataframe(pc[["circuit", "role", "coverage", "status"]], hide_index=True,
                 column_config={"coverage": st.column_config.ProgressColumn(
                     "Hours with data (%)", min_value=0, max_value=100, format="%.1f")})
with right.container(border=True):
    st.markdown("**Largest gaps**")
    st.dataframe(gaps, hide_index=True)
    if "low_coverage" in hourly:
        st.caption(f"{int(hourly['low_coverage'].sum())} hours of 2025 were built from fewer than 30 "
                   "one-minute readings (rule R11): kept, but less precise.")

# --- Cleaning rules -----------------------------------------------------------------
with st.container(border=True):
    st.markdown("**Cleaning rules applied by the data team** (`src/clean.py`)")
    if manifest and "cleaning_rules" in manifest:
        rules = pd.DataFrame(list(manifest["cleaning_rules"].items()), columns=["Rule", "What was done"])
        st.dataframe(rules, hide_index=True)
    st.caption("Principle: a wrong or missing value becomes empty, never invented; the raw files are never "
               "changed. Energy per hour = average power W (the Ea counters reset and are not used). "
               "Details: docs/PIPELINE_MODEL_DETECTION.md.")
