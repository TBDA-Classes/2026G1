"""
Action planner with verification (customer-value document, extension 7.1).

1. Plan: pick a circuit and a measure, say how much of its waste the measure should remove,
   and see the yearly saving in kWh, € and CO₂ (and the payback time if the cost is known).
2. Verify: give the date the measure was taken; the page compares the off-hours waste before and after
   that date on similar days (working days vs closed days, similar outdoor temperature).
Only results that already exist are used (reports/savings_summary.csv, reports/offhours_waste_daily.csv).
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import data_loader as dl
import metrics
import ui

hourly, src = dl.load_hourly()
P, _ = dl.load_params()
sav, _ = dl.load_savings()
daily, _ = dl.load_daily_waste()

st.title("Action planner")
st.caption("Choose a measure, see what it saves, then check after the fact whether it worked · "
           "the monthly cycle: see → locate → understand → act → verify")
if sav is None or daily is None:
    ui.missing("The planner", "reports/savings_summary.csv and reports/offhours_waste_daily.csv")
    st.stop()

MEASURES = {   # measure -> (suggested share of the waste removed, suitable loads)
    "Switch off heaters at night, weekends and breaks": (0.6, "Plugs & Sockets"),
    "Timer or presence sensor on the lighting": (0.8, "Lighting"),
    "HVAC off at night and at weekends": (0.7, "HVAC"),
    "Lower the heating setpoint at night": (0.3, "HVAC"),
    "Awareness campaign (signs, e-mail)": (0.2, None),
    "Other measure": (0.5, None),
}

sav = sav.rename(columns={"device": "load_type"})
sav["circuit"] = sav["zone"] + " " + sav["load_type"]
per_circuit = sav.groupby("circuit")[["potential_kWh", "eur_omie", "eur_all_in", "kg_co2"]].mean()
names = list(per_circuit.sort_values("potential_kWh", ascending=False).index)

tab_plan, tab_verify = st.tabs(["1 · Plan a measure", "2 · Verify a measure"])

# ---------------------------------------------------------------------------- plan
with tab_plan:
    left, right = st.columns([2, 3])
    with left:
        circuit = st.selectbox("Circuit", names, help="Sorted by waste, largest first")
        load = circuit.split(" ", 1)[1]
        options = [m for m, (_, l) in MEASURES.items() if l in (None, load)]
        measure = st.selectbox("Measure", options)
        share = st.slider("Share of this circuit's off-hours waste it removes", 0, 100,
                          int(MEASURES[measure][0] * 100), 5, format="%d %%") / 100
        cost = st.number_input("Cost of the measure (€, optional)", 0.0, 100000.0, 0.0, 10.0)
    base = per_circuit.loc[circuit]
    kwh = base["potential_kWh"] * share
    eur = metrics.eur_range(base["eur_omie"] * share, base["eur_all_in"] * share)
    with right:
        c1, c2, c3 = st.columns(3)
        with c1.container(border=True):
            st.metric("Energy saved", f"{kwh:,.0f} kWh / yr")
            st.caption(f"of {base['potential_kWh']:,.0f} kWh of waste a year")
        with c2.container(border=True):
            st.metric("Money saved", ui.eur_range(eur) + " / yr")
            st.caption("wholesale price → all-in tariff")
        with c3.container(border=True):
            st.metric("CO₂ avoided", f"{base['kg_co2'] * share:,.0f} kg / yr")
            st.caption(ui.co2_label(P).split(" (")[0])
        if cost > 0 and eur[1] > 0:
            lo_m, hi_m = cost / eur[1] * 12, (cost / eur[0] * 12 if eur[0] > 0 else float("inf"))
            st.success(f"**Payback:** {lo_m:,.0f}–{hi_m:,.0f} months (all-in tariff → wholesale price).")
        elif cost == 0:
            st.info("A behaviour change or a timer setting costs almost nothing: the saving starts immediately.")
        st.caption(f"Baseline: average waste of 2021–22 for {circuit} (notebook 03). "
                   f"{config.PATTERNS.get(circuit, '')}")
        d = st.date_input("Date the measure is (or was) taken", value=pd.Timestamp("2022-02-01"),
                          min_value=hourly["timestamp_local"].min().date(),
                          max_value=hourly["timestamp_local"].max().date())
        if st.button("Log this measure", type="primary"):
            dl.save_action({"circuit": circuit, "measure": measure, "share": share, "cost_eur": cost,
                            "date": str(d), "expected_kWh_per_year": round(kwh)})
            st.toast(f"Logged: {measure} on {circuit} from {d}", icon="✅")
    log = dl.load_actions()
    if len(log):
        st.markdown("**Measures logged**")
        st.dataframe(log, hide_index=True)

# ---------------------------------------------------------------------------- verify
with tab_verify:
    st.markdown("Pick a circuit and the date a measure was taken. The page compares the off-hours waste "
                "**before** and **after** that date, on **similar days** (same type of day, similar outdoor "
                "temperature), so a mild week does not look like a success.")
    log = dl.load_actions()
    c1, c2, c3 = st.columns(3)
    preset = None
    if len(log):
        pick = c1.selectbox("Logged measure", ["—"] + [f"{r.date} · {r.circuit} · {r.measure}" for r in log.itertuples()])
        if pick != "—":
            preset = log.iloc[[f"{r.date} · {r.circuit} · {r.measure}" for r in log.itertuples()].index(pick)]
    # worked example when nothing is logged: SE Plugs & Sockets changed for good on 2 Dec 2021
    example = "SE Plugs & Sockets" if "SE Plugs & Sockets" in names else names[0]
    v_circuit = c2.selectbox("Circuit ", names,
                             index=names.index(preset["circuit"] if preset is not None else example))
    v_date = pd.Timestamp(c3.date_input("Measure taken on", value=pd.Timestamp(preset["date"]) if preset is not None
                                        else pd.Timestamp("2021-12-02")))
    window = st.slider("Days compared on each side", 14, 90, 42, 7)

    days = (hourly.groupby(hourly["timestamp_local"].dt.normalize())
                  .agg(working=("is_working_day", "first"), temp=("wx_temp_c", "mean")))
    d = (daily[daily["circuit"] == v_circuit].set_index("date")[["excess_kWh", "eur_omie", "eur_all_in", "kg_co2"]]
         .join(days, how="left"))
    before = d[(d.index >= v_date - pd.Timedelta(days=window)) & (d.index < v_date)]
    after = d[(d.index >= v_date) & (d.index < v_date + pd.Timedelta(days=window))]
    if before.empty or after.empty:
        st.warning("Not enough data on one side of this date (the data stop in Feb 2023 and restart in Aug 2025).")
        st.stop()

    # similar days: same type of day, and outdoor temperature within the range seen on both sides
    lo_t, hi_t = max(before["temp"].min(), after["temp"].min()), min(before["temp"].max(), after["temp"].max())
    rows = []
    for label, wd in [("Working days", True), ("Closed days (weekends, holidays, breaks)", False)]:
        b = before[(before["working"] == wd) & before["temp"].between(lo_t, hi_t)]
        a = after[(after["working"] == wd) & after["temp"].between(lo_t, hi_t)]
        if len(b) and len(a):
            change = (a["excess_kWh"].mean() / b["excess_kWh"].mean() - 1) * 100 if b["excess_kWh"].mean() else float("nan")
            rows.append({"Days": label, "Before (kWh/day)": b["excess_kWh"].mean(), "After (kWh/day)": a["excess_kWh"].mean(),
                         "Change": change, "Days compared": f"{len(b)} / {len(a)}",
                         "Outside before / after (°C)": f"{b['temp'].mean():.1f} / {a['temp'].mean():.1f}"})
    res = pd.DataFrame(rows)
    k1, k2, k3 = st.columns(3)
    total_b, total_a = before["excess_kWh"].mean(), after["excess_kWh"].mean()
    k1.metric("Waste before", f"{total_b:.1f} kWh/day")
    k2.metric("Waste after", f"{total_a:.1f} kWh/day",
              f"{(total_a / total_b - 1) * 100:+.0f} %" if total_b else None, delta_color="inverse")
    saved = lambda col: max(before[col].mean() - after[col].mean(), 0) * 365
    k3.metric("Saved if it lasts a year", f"{saved('excess_kWh'):,.0f} kWh",
              ui.eur_range(metrics.eur_range(saved("eur_omie"), saved("eur_all_in"))) + " · "
              f"{saved('kg_co2'):,.0f} kg CO₂", delta_color="off")
    if len(res):
        st.dataframe(res, hide_index=True, column_config={
            "Before (kWh/day)": st.column_config.NumberColumn(format="%.2f"),
            "After (kWh/day)": st.column_config.NumberColumn(format="%.2f"),
            "Change": st.column_config.NumberColumn(format="%+.0f %%")})

    fig = go.Figure()
    fig.add_bar(x=d.loc[before.index[0]:after.index[-1]].index, y=d.loc[before.index[0]:after.index[-1], "excess_kWh"],
                marker_color=[config.COLOR_WASTE_LIGHT if t < v_date else config.COLOR_ACTUAL
                              for t in d.loc[before.index[0]:after.index[-1]].index], name="Off-hours waste")
    fig.add_vline(x=v_date, line_color="#111827", line_width=2)
    fig.add_annotation(x=v_date, y=1, yref="paper", text="measure", showarrow=False, xanchor="left", yanchor="top")
    for part, colour in ((before, config.COLOR_WASTE), (after, config.COLOR_ACTUAL)):
        fig.add_scatter(x=[part.index[0], part.index[-1]], y=[part["excess_kWh"].mean()] * 2, mode="lines",
                        line=dict(color=colour, dash="dash"), showlegend=False)
    fig.update_layout(height=300, yaxis_title="kWh above standby per day", showlegend=False)
    st.plotly_chart(fig, key="verify_chart")
    st.caption("Orange = before, teal = after; dashed lines = averages. Compare similar days in the table: "
               "heating waste depends on the cold, so check that the outdoor temperature is close on both sides. "
               "Worked example (default): SE Plugs & Sockets on 2 Dec 2021 — its weekend waste fell from about 9 to "
               "under 1 kWh a day and stayed there (−83 % between 2021 and 2022): something left on was switched off for good.")
