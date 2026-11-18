import plotly.graph_objects as go
import streamlit as st

import config
import data_loader as dl
import metrics
import ui

hourly, src = dl.load_hourly()
P, _ = dl.load_params()
f = dl.get_filters()
cur = dl.apply_filters(dl.load_long(src), f, month=True)
daily, _ = dl.load_daily_waste()
night = P["off_hours"]["night_hours"]

hours = hourly[hourly["month"] == f["month"]]
n_off, n_all = int(hours["is_off_hours"].sum()), len(hours)
ui.page_header("Off-hours use",
               f"{f['month'].strftime('%B %Y')} · the building was in off-hours {n_off} of {n_all} hours "
               f"({n_off / max(n_all, 1):.0%})", dl.month_coverage(src, f["month"]))


def split_chart(col: str, title: str):
    t = metrics.open_off_split(cur, col)
    fig = go.Figure()
    fig.add_bar(y=t[col], x=t["Working hours"], name="Working hours", orientation="h",
                marker_color=config.COLOR_OPEN)
    fig.add_bar(y=t[col], x=t["Off-hours"], name="Off-hours", orientation="h", marker_color=config.COLOR_WASTE,
                text=[f"{p:.0f} % off-hours" for p in t["off_pct"].fillna(0)], textposition="outside")
    fig.update_layout(barmode="stack", height=40 + 34 * max(len(t), 3), plot_bgcolor="white",
                      margin=dict(l=0, r=0, t=10, b=0), yaxis=dict(autorange="reversed"),
                      xaxis_title="kWh", legend=dict(orientation="h", y=-0.3))
    st.markdown(f"**{title}**")
    st.plotly_chart(fig)
    return t


left, right = st.columns(2)
with left.container(border=True):
    split_chart("zone", "Per zone: working hours vs off-hours (kWh)")
with right.container(border=True):
    t = split_chart("circuit", "Per circuit (kWh)")
    if len(t) and t["Off-hours"].sum() > 0:
        a = t.iloc[0]
        st.caption(f"{a['circuit']} carries the largest off-hours use: {a['Off-hours']:,.0f} kWh "
                   f"({a['off_pct']:.0f} % of its energy).")

# --- Weekday x hour ------------------------------------------------------------
with st.container(border=True):
    st.markdown("**Average power by weekday and hour (kW, selection)**")
    prof = metrics.weekday_hour_profile(cur)
    if prof.empty:
        st.info("No data for this selection.")
    else:
        fig = go.Figure(go.Heatmap(z=prof.values, x=[f"{h:02d}" for h in prof.columns], y=prof.index,
                                   colorscale=[[0, "#FFF7ED"], [1, config.COLOR_WASTE]],
                                   hovertemplate="%{y} %{x}:00 → %{z:.2f} kW<extra></extra>",
                                   colorbar=dict(title="kW")))
        fig.add_shape(type="rect", x0=night[1] - 0.5, x1=night[0] - 0.5, y0=-0.5, y1=4.5,
                      line=dict(color="#111827", width=2))
        fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig)
        st.caption(f"Outlined: working hours (Mon–Fri {night[1]:02d}:00–{night[0]}:00, team definition). "
                   "Holidays and breaks inside the box also count as off-hours.")

# --- Chronic waste over time + standby levels ---------------------------------
left, right = st.columns([2, 1])
with left.container(border=True):
    st.markdown("**Chronic off-hours waste per circuit and month (kWh above standby)**")
    if daily is None:
        ui.missing("This chart", "reports/offhours_waste_daily.csv")
    else:
        hm = metrics.chronic_heatmap(dl.apply_filters(daily, f))
        fig = go.Figure(go.Heatmap(z=hm.values, x=[m.strftime("%b %Y") for m in hm.columns], y=hm.index,
                                   colorscale="Reds", colorbar=dict(title="kWh"),
                                   hovertemplate="%{y} · %{x}: %{z:.0f} kWh<extra></extra>"))
        fig.update_layout(height=60 + 28 * len(hm), margin=dict(l=0, r=0, t=10, b=0),
                          xaxis=dict(type="category"))
        st.plotly_chart(fig)
        st.caption("A dark stripe that comes back every winter is waste that repeats: heaters, lights on a timer.")
with right.container(border=True):
    st.markdown("**Standby level per circuit**")
    sb = dl.load_standby(src).rename("Standby (W)").round(0).reset_index().rename(columns={"index": "Circuit"})
    st.dataframe(sb, hide_index=True)
    st.caption(f"P{P['off_hours']['standby_percentile']} of night use on the training period "
               "(Jun 2020 – Aug 2022). Use above this level in off-hours counts as chronic waste.")

ui.footnote(P)
