import pandas as pd
import streamlit as st

import config
import data_loader as dl
import metrics

hourly, src = dl.load_hourly()
P, _ = dl.load_params()
kmap, _ = dl.load_anomaly_k()
standby = dl.load_standby(src)

st.title("Method")
st.caption("How the numbers are made · why they can be trusted · what is still open")

st.markdown(
    "For each of the 9 focus circuits, a **LightGBM** model learns how much electricity is *normally* used at "
    "each hour, from the calendar, the weather and the circuit's own use 1 day to 2 weeks earlier. "
    "When the real use is far above that, an **alert** is raised (signal 1). When the building is in off-hours "
    "and use stays above the circuit's **standby level**, the excess is counted as **chronic waste** (signal 2). "
    "Both get a value in € and CO₂.")

left, right = st.columns(2)
with left.container(border=True):
    st.markdown("**The model**")
    st.markdown(f"""
| | |
|---|---|
| Predicts | energy per hour per circuit, one day ahead |
| Trained on | Jun 2020 – Aug 2022 (lockdown left out) |
| Settings chosen on | Sep – Dec 2022 |
| Tested once on | Jan – Feb 2023, then checked on Aug – Oct 2025 |
| Never uses | same-hour measurements, indoor sensors, anything across the 2023–25 gap |
| Compared with | last week, 4-week median, day-type profile, Ridge, Prophet |
| Main metric | MAE in kWh (the unit the client thinks in) |
""")
with right.container(border=True):
    st.markdown("**The alerts**")
    st.markdown(f"""
- Flag an hour when *actual − expected* > median + k × MAD, per circuit and per hour type (working / off-hours).
- Merge flagged hours ≤ 1 h apart; keep events ≥ {P['anomaly']['min_event_hours']} h and \
≥ {P['anomaly']['min_event_kwh']} kWh.
- **k is chosen per circuit for about one alert per week**, so the manager is not flooded.
- Tested with 40 fake "forgotten devices": 98–100 % found on 7 of 9 circuits; on NW Plugs one heater \
(1 kW) is found 32 % of the time, 2 kW 85 %.
""")

with st.container(border=True):
    st.markdown("**Settings per circuit**")
    rows = []
    for c in config.FOCUS:
        s = metrics.short(c)
        rows.append({"Circuit": s, "Alarm k": (kmap or {}).get(s),
                     "Standby level (W)": round(float(standby.get(s, float("nan"))), 0)})
    st.dataframe(pd.DataFrame(rows), hide_index=True)

FIGURES = [("model_04_skill_heatmap.png", "Model vs baselines per circuit (notebook 02)"),
           ("anom_01_tradeoff.png", "Alerts per week vs fake loads found (notebook 03)"),
           ("anom_02_top_events.png", "The three largest events (notebook 03)"),
           ("eda_05_temperature.png", "NW plugs rise when it gets cold: heaters (notebook 01)"),
           ("eda_04_day_types.png", "Use by type of day (notebook 01)")]
found = [(f, t) for f, t in FIGURES if (config.FIGURES_DIR / f).exists()]
if found:
    st.markdown("**Evidence from the notebooks**")
    tabs = st.tabs([t.split(" (")[0] for _, t in found])
    for tab, (fname, title) in zip(tabs, found):
        with tab:
            st.image(str(config.FIGURES_DIR / fname), caption=title)

with st.container(border=True):
    st.markdown("**Honest limits**")
    st.markdown(
        "- No list of confirmed waste exists: the detector is validated with fake loads and a manual check.\n"
        "- Hour by hour, the error is above the ASHRAE 30 % target on most circuits (people are hard to predict).\n"
        "- Calendar assumptions (Christmas break, all of August) look wrong in places.\n"
        "- The CO₂ factor and the all-in price are placeholders to confirm.\n"
        "- The building is used differently in 2025: retrain on recent data before going live.")

st.markdown("**Data sources of this dashboard**")
st.dataframe(dl.sources(), hide_index=True)
st.caption("Details: docs/METHODOLOGY.md, docs/PIPELINE_MODEL_DETECTION.md, docs/EXPERIMENT_LOG.md.")
