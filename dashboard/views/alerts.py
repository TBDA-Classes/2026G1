import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import data_loader as dl
import metrics
import ui
import why

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
ui.page_header("Alerts", f"{period} · {len(sel)} alerts from the model (notebook 03) · sorted by severity, then €",
               None if all_months else dl.month_coverage(src, f["month"]))

# --- How the severity levels were calibrated (EXP-12) -------------------------------
cal, _ = dl.load_calibration()
counts = sel["severity"].value_counts()
c1, c2, c3, c4 = st.columns(4)
for col, level in zip((c1, c2, c3), ("High", "Medium", "Low")):
    with col.container(border=True):
        st.markdown(f"{ui.severity_pill(level)}", unsafe_allow_html=True)
        st.metric(f"{level} alerts", int(counts.get(level, 0)))
        if cal and level.lower() in cal.get("result", {}):
            r = cal["result"][level.lower()]
            st.caption(f"all history: {r['per_week']:.1f} a week · {r['share_of_eur']:.0%} of the € at stake")
with c4.container(border=True):
    if cal and "high" in cal.get("result", {}):
        h = cal["result"]["high"]
        st.metric("Handle the High ones first", f"{h['share_of_eur']:.0%} of €")
        st.caption(f"≈ {h['per_week']:.1f} High alerts a week for the whole floor (EXP-12)")
    else:
        st.metric("€ at stake (selection)", ui.eur(sel["eur_all_in"].sum()))
        st.caption("all-in price")

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
            "Hours": df["hours"], "€ all-in": df["eur_all_in"].round(2), "Excess kWh": df["excess_kWh"].round(1),
            "Status": df["status"]})
        event = st.dataframe(table, hide_index=True, height=440, on_select="rerun",
                             selection_mode="single-row", key=f"table_{key}",
                             column_config={"€ all-in": st.column_config.NumberColumn(format="€ %.2f"),
                                            "Excess kWh": st.column_config.NumberColumn(format="%.1f")})
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
        win = hourly[hourly["timestamp_local"].between(t0, t1)].groupby("timestamp_local")
        w = win[col].mean() / 1000
        temp = win["wx_temp_c"].mean() if "wx_temp_c" in hourly else None
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
        if temp is not None and temp.notna().any():
            fig.add_scatter(x=temp.index, y=temp.values, name="Outdoor °C", yaxis="y2",
                            line=dict(color="#2563EB", width=1, dash="dot"))
            fig.update_layout(yaxis2=dict(overlaying="y", side="right", title="°C", showgrid=False))
        fig.update_layout(height=240, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="kW", hovermode="x unified",
                          legend=dict(orientation="h", y=1.15, font=dict(size=11)))
        st.plotly_chart(fig, key=f"chart_{key}")
        if temp is not None and temp.notna().any():
            st.caption(f"Outside during the alert: {temp.loc[a['start']:a['end']].mean():.1f} °C on average "
                       f"(blue dotted line). Shaded = the alert; 24 h before and after for comparison.")
        why.explain_alert(src, a)          # which factors raised or lowered the expected use (extension 7.2)

        new = st.radio("Status", dl.STATUSES, horizontal=True, index=dl.STATUSES.index(a["status"]),
                       key=f"radio_{key}_{a['alert_id']}")
        if new != a["status"]:
            dl.save_status(a["alert_id"], new)
            st.rerun()
        hist = dl.status_history(a["alert_id"])
        if len(hist):
            st.caption("History: " + " · ".join(f"{s} ({d})" if d else s for d, s in zip(hist["changed_at"], hist["status"])))
        st.caption("\"This was normal\" turns the manager's feedback into labels for tuning the alerts later (KAN-150).")


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

st.caption(f"{metrics.severity_rule_text(P)} An alert = hours far above the model's expectation, "
           f"≥ {P['anomaly']['min_event_hours']} h and ≥ {P['anomaly']['min_event_kwh']} kWh (params.yaml).")
