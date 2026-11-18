import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import data_loader as dl
import metrics
import ui

hourly, src = dl.load_hourly()
P, _ = dl.load_params()
f = dl.get_filters()
events, events_src = dl.load_events()
expected, _ = dl.load_expected()
standby = dl.load_standby(src)

if events is None:
    st.title("Alerts")
    ui.missing("The alert list", "reports/anomaly_events.csv")
    st.stop()

all_months = st.toggle("Show every month (not only the selected one)", value=False)
sel = dl.apply_filters(events, f, month=not all_months)
status = dl.load_status()
sel = metrics.sort_alerts(sel.assign(status=sel["alert_id"].map(status).fillna("Open")))
waste = sel[sel["category"] == "Off-hours waste"]
check = sel[sel["category"] == "To investigate"]

period = "all months" if all_months else f["month"].strftime("%B %Y")
ui.page_header("Alerts", f"{period} · {len(sel)} alerts from the model (notebook 03) · sorted by severity, then kWh",
               None if all_months else dl.month_coverage(src, f["month"]))

tab1, tab2, tab3 = st.tabs([f"Off-hours waste · {len(waste)}", f"To investigate (working hours) · {len(check)}",
                            "Data errors"])


def table_and_detail(df: pd.DataFrame, key: str):
    c1, c2 = st.columns(2)
    sev = c1.multiselect("Severity", ["High", "Medium", "Low"], default=["High", "Medium", "Low"], key=f"sev_{key}")
    stat = c2.multiselect("Status", dl.STATUSES, default=dl.STATUSES, key=f"stat_{key}")
    df = df[df["severity"].isin(sev) & df["status"].isin(stat)].reset_index(drop=True)
    if df.empty:
        st.info("No alert for this selection.")
        return

    left, right = st.columns([3, 2])
    with left:
        table = pd.DataFrame({
            "Severity": df["severity"], "Circuit": df["circuit"], "Day": df["day_type"],
            "When": df["start"].dt.strftime("%a %d %b %Y %H:%M") + " → " + df["end"].dt.strftime("%a %d %b %H:%M"),
            "Hours": df["hours"], "Excess kWh": df["excess_kWh"].round(1),
            "€ all-in": df["eur_all_in"].round(2), "Status": df["status"]})
        event = st.dataframe(table, hide_index=True, height=440, on_select="rerun",
                             selection_mode="single-row", key=f"table_{key}")
        st.download_button("Download this list (CSV)", table.to_csv(index=False).encode("utf-8"),
                            file_name=f"alerts_{key}.csv", mime="text/csv", key=f"dl_{key}")
        st.caption(f"Click a row to see its detail · source: {events_src}")
    rows = event.selection.rows
    # a row kept selected from before a filter change may no longer exist
    a = df.iloc[rows[0] if rows and rows[0] < len(df) else 0]

    with right.container(border=True):
        st.markdown(f"**{a['circuit']}** {ui.severity_pill(a['severity'])}", unsafe_allow_html=True)
        st.caption(f"{a['start']:%a %d %b %Y %H:%M} → {a['end']:%a %d %b %H:%M} · {a['hours']} hours · {a['day_type']}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Excess", f"{a['excess_kWh']:.0f} kWh")
        m2.metric("Cost", ui.eur_range(metrics.eur_range(a["eur_omie"], a["eur_all_in"])))
        m3.metric("CO₂", f"{a['kg_co2']:.0f} kg")
        st.markdown("**Why it was flagged**")
        st.write(f"{a['message']} Actual {a['actual_kWh']:.0f} kWh against {a['expected_kWh']:.0f} kWh expected "
                 f"over these {a['hours']} hours.")

        col = next(c for c in config.FOCUS if metrics.short(c) == a["circuit"])
        t0, t1 = a["start"] - pd.Timedelta("24h"), a["end"] + pd.Timedelta("24h")
        w = hourly[hourly["timestamp_local"].between(t0, t1)].groupby("timestamp_local")[col].mean() / 1000
        fig = go.Figure()
        fig.add_vrect(x0=a["start"], x1=a["end"], fillcolor="rgba(185,28,28,.10)", line_width=0)
        fig.add_scatter(x=w.index, y=w.values, name="Actual", line=dict(color=config.COLOR_ACTUAL))
        if expected is not None:
            e = expected[(expected["circuit"] == a["circuit"]) & expected["timestamp_local"].between(t0, t1)]
            if len(e):
                fig.add_scatter(x=e["timestamp_local"], y=e["expected_kwh"], name="Expected",
                                line=dict(color=config.COLOR_EXPECTED, dash="dash"))
        if a["circuit"] in standby:
            fig.add_hline(y=standby[a["circuit"]] / 1000, line_dash="dot", line_color="#6B7280",
                          annotation_text="standby level")
        fig.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white",
                          showlegend=False, yaxis_title="kW")
        st.plotly_chart(fig, key=f"chart_{key}")

        new = st.radio("Status", dl.STATUSES, horizontal=True, index=dl.STATUSES.index(a["status"]),
                       key=f"radio_{key}_{a['alert_id']}")
        if new != a["status"]:
            dl.save_status(a["alert_id"], new)
            st.rerun()
        st.caption("\"This was normal\" turns the manager's feedback into labels for tuning the alerts later.")


with tab1:
    table_and_detail(waste, "waste")
with tab2:
    st.caption("Mostly during working hours: part of this use may be legitimate, so it is not counted as savings.")
    table_and_detail(check, "check")
with tab3:
    st.markdown("**Missing data (largest gaps, all circuits)**")
    _, _, gaps = dl.coverage_tables(src)
    st.dataframe(gaps, hide_index=True)
    if "low_coverage" in hourly:
        n = int(hourly.loc[hourly["month"] == f["month"], "low_coverage"].sum())
        if n:
            st.warning(f"{n} hours this month were built from fewer than 30 one-minute readings (less precise).")
    st.caption("Gaps are not waste: the cleaning (rules R1–R12) leaves wrong values empty instead of guessing.")

sev = P["anomaly"]["severity_kwh"]
st.caption(f"Severity by excess energy per alert: Low < {sev[0]} kWh, Medium {sev[0]}–{sev[1]} kWh, "
           f"High > {sev[1]} kWh (params.yaml). An alert = hours far above the model's expectation, "
           f"≥ {P['anomaly']['min_event_hours']} h and ≥ {P['anomaly']['min_event_kwh']} kWh.")
