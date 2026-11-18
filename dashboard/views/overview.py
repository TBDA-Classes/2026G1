import plotly.graph_objects as go
import streamlit as st

import config
import data_loader as dl
import metrics
import ui

hourly, src = dl.load_hourly()
P, _ = dl.load_params()
f = dl.get_filters()
long_sel = dl.apply_filters(dl.load_long(src), f)
daily, daily_src = dl.load_daily_waste()
events, events_src = dl.load_events()
daily_sel = dl.apply_filters(daily, f)
events_sel = dl.apply_filters(events, f)

ui.page_header("Overview", f"Storey 1 · {f['month'].strftime('%B %Y')} · historical data",
               dl.month_coverage(src, f["month"]))

if daily is None or events is None:
    ui.missing("The waste figures", "reports/offhours_waste_daily.csv and reports/anomaly_events.csv")
    st.stop()

k = metrics.month_kpis(long_sel, daily_sel, events_sel, f["month"])

# --- KPI cards ----------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
with c1.container(border=True):
    delta = f"{k['used_delta_pct']:+.1f} % vs previous month" if k["used_delta_pct"] is not None else None
    st.metric("Electricity used", f"{k['used_kwh']:,.0f} kWh", delta, delta_color="inverse")
    st.caption("all circuits of the selection")
with c2.container(border=True):
    st.metric("Used during off-hours", f"{k['off_share_pct']:.1f} %")
    st.caption("nights, weekends, holidays, breaks")
with c3.container(border=True):
    st.metric("Chronic off-hours waste", ui.eur_range(k["waste_eur"]))
    prev = f" · {ui.eur(k['waste_eur_prev'])} previous month (all-in)" if k["waste_eur_prev"] is not None else ""
    st.caption(f"{k['waste_kwh']:,.0f} kWh · {k['waste_co2']:,.0f} kg CO₂{prev}")
with c4.container(border=True):
    st.metric("Alerts this month", k["events"])
    st.markdown(" ".join(f"{ui.severity_pill(s)} {k['events_by_sev'].get(s, 0)}"
                         for s in ["High", "Medium", "Low"]), unsafe_allow_html=True)
    st.caption(f"{k['events_kwh']:,.0f} kWh above expected")

# --- Monthly chronic waste + floor map ---------------------------------------
left, right = st.columns([2, 1])
with left.container(border=True):
    st.markdown("**Chronic off-hours waste per month (€, all-in price)**")
    mw = metrics.monthly_waste(daily_sel)
    colors = [config.COLOR_WASTE if m == f["month"] else config.COLOR_WASTE_LIGHT for m in mw["month"]]
    fig = go.Figure(go.Bar(x=mw["label"], y=mw["eur_all_in"], marker_color=colors,
                           customdata=mw[["excess_kWh", "eur_omie"]],
                           hovertemplate="%{x}<br>€ %{y:.0f} all-in · € %{customdata[1]:.0f} OMIE"
                                         "<br>%{customdata[0]:.0f} kWh<extra></extra>"))
    fig.update_layout(height=270, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white",
                      xaxis=dict(type="category"))
    st.plotly_chart(fig)
    st.caption("Selected month highlighted · no data between March 2023 and August 2025")

with right.container(border=True):
    st.markdown("**Where is the waste?**")
    month_daily = dl.apply_filters(daily, {**f, "zone": "All zones"}, month=True)
    by_zone = metrics.waste_by(month_daily, "zone").set_index("zone")["excess_kWh"]
    ui.floor_map({z: float(by_zone.get(z, 0)) for z in config.ZONES})

# --- Top sources + largest alerts ---------------------------------------------
left, right = st.columns(2)
with left.container(border=True):
    st.markdown("**Top waste sources this month (kWh above standby, off-hours)**")
    top = metrics.waste_by(daily_sel[daily_sel["month"] == f["month"]], "circuit").head(5)
    if top["excess_kWh"].sum() == 0:
        st.info("No chronic waste for this selection.")
    else:
        fig = go.Figure(go.Bar(x=top["excess_kWh"], y=top["circuit"], orientation="h",
                               marker_color=config.COLOR_WASTE,
                               text=[f"{k:,.0f} kWh · {ui.eur(e)}" for k, e in zip(top["excess_kWh"], top["eur_all_in"])],
                               textposition="outside"))
        fig.update_layout(height=240, margin=dict(l=0, r=90, t=0, b=0), plot_bgcolor="white",
                          yaxis=dict(autorange="reversed"), xaxis=dict(visible=False))
        st.plotly_chart(fig)

with right.container(border=True):
    st.markdown("**Largest alerts this month**")
    month_ev = metrics.sort_alerts(events_sel[events_sel["month"] == f["month"]])
    if month_ev.empty:
        st.info("No alert for this selection.")
    for _, a in month_ev.head(3).iterrows():
        l, r = st.columns([3, 1])
        l.markdown(f"**{a['circuit']}** · {a['day_type']}  \n"
                   f"{a['start']:%a %d %b %H:%M} → {a['end']:%a %d %b %H:%M}")
        r.markdown(f"{ui.severity_pill(a['severity'])}<br>"
                   f"<b style='font-family:monospace'>+{a['excess_kWh']:.0f} kWh</b>", unsafe_allow_html=True)
    st.page_link("views/alerts.py", label="All alerts →")

ui.footnote(P)
