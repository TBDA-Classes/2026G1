"""
Storey 1 energy dashboard — CeDInt · UPM (TBDA 2026, Group 1)

Shows the results of the modelling notebooks (reports/) on top of the frozen
hourly dataset. Run from the repository root or from this folder:
    streamlit run dashboard/app.py
"""
import streamlit as st

import data_loader as dl

st.set_page_config(page_title="Storey 1 energy", page_icon="⚡", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebar"] {background-color: #111827;}
[data-testid="stSidebar"] * {color: #E5E7EB;}
[data-testid="stSidebar"] [data-baseweb="select"] * {color: #111827;}
[data-testid="stMetricValue"] {font-family: ui-monospace, monospace;}
.block-container {padding-top: 2rem;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Storey 1 energy\nCeDInt · UPM")

pages = [
    st.Page("views/overview.py", title="Overview", icon=":material/dashboard:", default=True),
    st.Page("views/off_hours.py", title="Off-hours use", icon=":material/nightlight:"),
    st.Page("views/expected_vs_actual.py", title="Expected vs actual", icon=":material/show_chart:"),
    st.Page("views/alerts.py", title="Alerts", icon=":material/notifications:"),
    st.Page("views/savings.py", title="Savings report", icon=":material/savings:"),
    st.Page("views/data_quality.py", title="Data quality", icon=":material/fact_check:"),
    st.Page("views/method.py", title="Method", icon=":material/science:"),
]
nav = st.navigation(pages)

# Loaded once (cache); the filters live in the sidebar so every page shares them
hourly, source = dl.load_hourly()
dl.sidebar_filters(hourly)
with st.sidebar:
    st.caption(f"Data: {source}")

nav.run()
