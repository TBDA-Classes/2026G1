import pandas as pd
import streamlit as st

import config
import data_loader as dl
import metrics

hourly, src = dl.load_hourly()
P, _ = dl.load_params()
kmap, _ = dl.load_anomaly_k()
standby = dl.load_standby(src)
card, card_src = dl.load_model_card()
comp, _ = dl.load_model_comparison()
final, final_src = dl.load_final_settings()


def wins(period: str) -> str:
    """'7 of 9': circuits where LightGBM beats the best simple baseline (MAE, reports/model_comparison.csv)."""
    if comp is None:
        return "?"
    x = comp[comp["period"] == period].pivot_table(index="circuit", columns="model", values="MAE_kWh")
    base = [c for c in x if c.startswith("B")]
    if "LightGBM_forecast" not in x or not base:
        return "?"
    return f"{int((x['LightGBM_forecast'] < x[base].min(axis=1)).sum())} of {len(x)}"

st.title("Method & model card")
st.caption("How the numbers are made · why they can be trusted · what is still open")

st.markdown(
    "For each of the 9 focus circuits, a **LightGBM** model learns how much electricity is *normally* used at "
    "each hour, from the calendar, the weather and the circuit's own use 1 day to 2 weeks earlier. "
    "When the real use is far above that, an **alert** is raised (signal 1). When the building is closed and "
    "use stays above the circuit's **standby level**, the excess is counted as **waste** (signal 2). "
    "Both get a value in € and CO₂, and alerts are ranked by € and duration.")

tab_card, tab_periods, tab_model, tab_detect, tab_fig, tab_docs = st.tabs(
    ["Model card", "Periods: forecast or afterwards?", "Model & alerts", "Detection test", "Evidence",
     "Documents & sources"])

with tab_periods:
    st.markdown("**Model evaluation (notebook 02).** Each model predicts one day ahead: every hour is predicted only "
                "with information at least 24 hours old.")
    st.dataframe(pd.DataFrame([{"Phase": n, "Period (local time)": f"{pd.Timestamp(a):%d %b %Y} – {pd.Timestamp(b):%d %b %Y}",
                                "What happens": d} for n, a, b, _, d in config.PHASES if n != "No data"]),
                 hide_index=True)
    st.markdown("""
**Two kinds of LightGBM line in this dashboard**

| Where | File | What it is | How to read it |
|---|---|---|---|
| Jan – Feb 2023 | `reports/test_predictions.parquet` | model retrained up to 31 Dec 2022, predicted once | **honest test**: judge the model here |
| Aug – Oct 2025 | `expected_hourly.parquet` | model trained only on 2020 – Feb 2023 | **real forecast**, 2.5 years later: used in the live demo |
| Jun 2020 – Dec 2022 | `expected_hourly.parquet` | each quarter predicted by a model trained on the other quarters, later ones included (cross-fitting) | **expected afterwards**: fine for a historical report and for finding past waste, but not a forecast |

The alerts of 2020 – 2023 were computed on the cross-fitted line (notebook 03): every hour is judged by a model that
never saw that hour, but that did see later months. Honest accuracy figures are those of the test months and of 2025
(page *Expected vs actual*, accuracy table).
""")

with tab_card:
    if card:
        st.markdown(card)
        st.caption(f"Source: {card_src}")
    else:
        st.info("The model card is not in the repository yet (backlog F3.3, branch KAN-162). "
                "When `docs/MODEL_CARD.md` exists, it is shown here automatically.")

with tab_model:
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
| Data | the zone files of the data-cleaning group (`data/zone_*_hourly`), joined by `src/zones.py` |
| Compared with | last week, 4-week median, day-type profile, Ridge, Prophet (scores only) |
| Model search (EXP-13) | 7 model types × 4 input sets, then month by month: LightGBM best (9 of 15 months) |
| Result | beats the best simple baseline on {wins("val")} circuits (validation), {wins("test")} (test), \
{wins("regime_b")} (2025) |
""")
        if final:
            st.caption("Final settings, the same for all circuits (" + final_src + "): " +
                       ", ".join(f"{k} = {v}" for k, v in final.items()))
    with right.container(border=True):
        st.markdown("**The alerts**")
        st.markdown(f"""
- An hour is flagged when *actual − expected* > median + k × MAD, per circuit and per hour type.
- Flagged hours ≤ 1 h apart form one alert; kept if ≥ {P['anomaly']['min_event_hours']} h and \
≥ {P['anomaly']['min_event_kwh']} kWh.
- **k is chosen per circuit for about one alert a week**, so the manager is not flooded.
- {metrics.severity_rule_text(P)}
""")
    rows = [{"Circuit": metrics.short(c), "Alarm k": (kmap or {}).get(metrics.short(c)),
             "Standby level (W)": round(float(standby.get(metrics.short(c), float("nan"))), 0)} for c in config.FOCUS]
    st.dataframe(pd.DataFrame(rows), hide_index=True)

with tab_detect:
    st.markdown("**Fake loads injected, then searched for** — there is no labelled waste, so the team hid "
                "40 artificial loads per circuit (3–12 h, only while closed, Sep 2022 – Feb 2023) and ran the "
                "detector with the production thresholds.")
    det = pd.DataFrame(config.DETECTION_TEST, columns=["Circuit", "Fake load", "Found (%)", "Other alerts a week"])
    st.dataframe(det, hide_index=True, column_config={"Found (%)": st.column_config.ProgressColumn(
        "Found", min_value=0, max_value=100, format="%d %%")})
    st.caption("All fake loads are found on 7 of 9 circuits. The two noisiest circuits find small loads less often: "
               "NW Lighting (300 W: 15 %) and NW Plugs & Sockets, where one heater is hidden among many people. "
               "\"Other alerts\" are real waste or false alarms: the Alerts page lets the manager mark them, which "
               "creates the missing labels. Source: notebook 03, section 3 (zone data, 25 Nov 2026).")
    st.markdown("**NW Plugs & Sockets: how big must a load be to be found?**")
    st.dataframe(pd.DataFrame(config.DETECTION_SIZES, columns=["Fake load", "Found (%)"]), hide_index=True,
                 column_config={"Found (%)": st.column_config.ProgressColumn("Found", min_value=0, max_value=100,
                                                                            format="%d %%")})
    st.caption("A forgotten 2 kW heater (the usual size) is found 9 times out of 10.")

with tab_fig:
    figures = [("model_04_skill_heatmap.png", "Model vs baselines per circuit (notebook 02)"),
               ("anom_01_tradeoff.png", "Alerts per week vs fake loads found (notebook 03)"),
               ("anom_02_top_events.png", "The three largest events (notebook 03)"),
               ("sev_01_calibration.png", "Severity thresholds: share of € covered (EXP-12)"),
               ("eda_05_temperature.png", "NW plugs rise when it gets cold: heaters (notebook 01)"),
               ("eda_04_day_types.png", "Use by type of day (notebook 01)")]
    found = [(fn, t) for fn, t in figures if (config.FIGURES_DIR / fn).exists()]
    if not found:
        st.info("No figure found in reports/figures/.")
    for fn, title in found:
        st.image(str(config.FIGURES_DIR / fn), caption=title)

with tab_docs:
    st.markdown("**Team documents**  \n" + "  \n".join("- " + dl.doc_link(n) for n in config.DOC_LINKS))
    st.markdown("**Honest limits**")
    st.markdown(
        "- No list of confirmed waste exists: the detector is validated with fake loads and a manual check.\n"
        "- Hour by hour, the error is above the target on most circuits (people are hard to predict).\n"
        "- Some Christmas and August closure days look like working days (calendar to fix, KAN-56).\n"
        "- € are shown as a range: OMIE wholesale price (lower bound) → € 0.142/kWh all-in excl. VAT (upper bound); "
        "CeDInt's own contract is not known.\n"
        "- CO₂ uses the hourly intensity of the Spanish grid (Red Eléctrica); the supplier mix (CNMC) would give "
        "about twice as much. Both are on the Savings page.\n"
        "- In 2025 one lighting circuit is used differently: retrain on recent data before going live.\n"
        "- Savings are a potential, not a guarantee.")
    st.markdown("**Data files used by this dashboard**")
    st.dataframe(dl.sources(), hide_index=True)
