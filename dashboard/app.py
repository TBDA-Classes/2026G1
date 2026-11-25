"""
Storey 1 energy dashboard — CeDInt · UPM (TBDA 2026, Group 1)

Shows the results of the modelling notebooks (reports/) on top of the zone
files of the data-cleaning group (data/zone_*_hourly). Run from the repository root:
    streamlit run dashboard/app.py
"""
import time

import streamlit as st

import data_loader as dl
import ui

t0 = time.perf_counter()
st.set_page_config(page_title="Storey 1 energy · CeDInt", page_icon="⚡", layout="wide")

with st.sidebar:
    st.markdown("### ⚡ Storey 1 energy\nCeDInt · UPM · TBDA Group 1")
dark = ui.theme_switch()          # light / dark button at the top of the sidebar
ui.apply_style(dark)

pages = {
    "Monitor": [
        st.Page("views/overview.py", title="Overview", icon=":material/dashboard:", default=True),
        st.Page("views/demo.py", title="Live demo (2025 replay)", icon=":material/play_circle:"),
        st.Page("views/alerts.py", title="Alerts", icon=":material/notifications:"),
    ],
    "Analyse": [
        st.Page("views/off_hours.py", title="Off-hours use", icon=":material/nightlight:"),
        st.Page("views/expected_vs_actual.py", title="Expected vs actual", icon=":material/show_chart:"),
        st.Page("views/savings.py", title="Savings report", icon=":material/savings:"),
    ],
    "Act": [
        st.Page("views/planner.py", title="Action planner", icon=":material/task_alt:"),
    ],
    "Trust": [
        st.Page("views/data_quality.py", title="Data quality", icon=":material/fact_check:"),
        st.Page("views/method.py", title="Method & model card", icon=":material/science:"),
        st.Page("views/guide.py", title="How to use", icon=":material/help:"),
    ],
}
nav = st.navigation(pages)

# Loaded once (cache); the filters live in the sidebar so every page shares them
hourly, source = dl.load_hourly()
dl.sidebar_filters(hourly)

nav.run()

with st.sidebar:
    st.divider()
    st.caption(f"Data: {source}")
    # Quality requirement Q4: every page should load in under 3 s
    st.caption(f"Page built in {time.perf_counter() - t0:.2f} s")
