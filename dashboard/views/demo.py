"""
Live demo (backlog F6.3, KAN-167): the 2025 data (period B) are replayed hour by hour as if they arrived live.
The chart grows, the counters go up and every alert pops up with its cost and severity when it ends.
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
events, _ = dl.load_events()
daily, _ = dl.load_daily_waste()

B = hourly[hourly["Regime"] == "B"] if "Regime" in hourly else hourly[hourly["timestamp_local"].dt.year >= 2025]
st.title("Live demo · 2025 replayed as if live")
if B.empty or events is None:
    st.info("The demo needs the 2025 data (period B) and reports/anomaly_events.csv.")
    st.stop()

t_start, t_end = B["timestamp_local"].min().floor("h"), B["timestamp_local"].max().floor("h")
first_view = t_start + pd.Timedelta(days=7)            # start with one week of history on screen
ss = st.session_state
ss.setdefault("demo_t", first_view)
ss.setdefault("demo_play", False)
ss.setdefault("demo_seen", [])
st.caption(f"Data of {t_start:%d %b} – {t_end:%d %b %Y}, played back as the building manager would see them "
           "arrive. The LightGBM line here is a real forecast: the model was trained only on 2020 – Feb 2023 and "
           "predicts one day ahead, 2.5 years later. Press ▶ Play.")

# --- Controls (outside the auto-refreshing part) ---------------------------------
names = [metrics.short(c) for c in config.FOCUS]


def _toggle():
    ss.demo_play = not ss.demo_play


def _restart():
    ss.demo_t, ss.demo_seen, ss.demo_play = first_view, [], False


def _jump():   # storyline: SE Lighting on all weekend, 26–29 Sep 2025
    ss.demo_t, ss.demo_play = max(pd.Timestamp("2025-09-26 12:00"), first_view), True


c1, c2, c3, c4, c5, c6 = st.columns([1.8, 1.8, 1.2, 1, 1, 1.3])
circuit = c1.selectbox("Circuit on the chart", names,
                       index=names.index(config.DEMO_CIRCUIT) if config.DEMO_CIRCUIT in names else 0)
methods = dl.methods_covering(src, circuit, t_start, t_end) or ["B2 · 4-week median"]
method = c2.selectbox("Expected line", methods, help="Prediction method drawn as the dashed line. LightGBM "
                      "appears here once expected_hourly.parquet exists (tools/export_expected.py).")
speed = c3.selectbox("Speed", list(config.DEMO_SPEEDS), index=1)
c4.button("⏸ Pause" if ss.demo_play else "▶ Play", on_click=_toggle, type="primary")
c5.button("⏮ Restart", on_click=_restart)
c6.button("⏭ Jump to 26 Sep", on_click=_jump, help="The weekend of the largest 2025 alert")

frame = dl.demo_frame(src, circuit, method)
exp_label = config.LGB_LABELS["Out-of-time 2025"][0] if method.startswith("LightGBM") else method
ev25 = events[(events["start"] >= t_start) & (events["start"] <= t_end)]
daily25 = daily[(daily["date"] >= t_start.normalize())] if daily is not None else None
# small steps, twice a second: smoother than one big jump per second
step = pd.Timedelta(hours=config.DEMO_SPEEDS[speed] * config.DEMO_TICK_S)


def replay():
    if ss.demo_play:
        ss.demo_t = min(ss.demo_t + step, t_end)
        if ss.demo_t >= t_end:
            ss.demo_play = False
    now = ss.demo_t

    # new alerts since the last tick -> pop-up (at most 3 per tick at high speed)
    ended = ev25[ev25["end"] <= now]
    new = ended[~ended["alert_id"].isin(ss.demo_seen)].sort_values("end")
    icons = {"High": "🔴", "Medium": "🟠", "Low": "🔵"}
    for _, a in new.tail(2).iterrows():
        st.toast(f"**{a['severity']} alert** · {a['circuit']} · {ui.eur(a['eur_all_in'])} · "
                 f"{a['hours']} h, +{a['excess_kWh']:.0f} kWh", icon=icons.get(a["severity"], "⚠️"))
    ss.demo_seen = ss.demo_seen + list(new["alert_id"])

    # clock
    row = frame.loc[:now].iloc[-1] if len(frame.loc[:now]) else None
    closed = bool(row["off"]) if row is not None else False
    pill = ("<span class='pill' style='background:#1F2937;color:#F9FAFB'>Building closed</span>" if closed
            else "<span class='pill' style='background:#DCFCE7;color:#166534'>Working hours</span>")
    live = "<span class='pill' style='background:#FEE2E2;color:#991B1B'>● LIVE</span>" if ss.demo_play else ""
    st.markdown(f"<div style='display:flex;gap:16px;align-items:center;margin:.2rem 0 .6rem'>"
                f"<span class='big-number clock'>{now:%a %d %b %Y · %H:00}</span>"
                f"{pill}{live}</div>", unsafe_allow_html=True)

    # running counters since the start of the replay
    used = float(frame["focus_cum"].asof(now)) if len(frame.loc[:now]) else 0.0
    waste = daily25[daily25["date"] < now.normalize()] if daily25 is not None else None
    k1, k2, k3, k4 = st.columns(4)
    with k1.container(border=True):
        st.metric("Electricity used", f"{used:,.0f} kWh")
        st.caption("9 focus circuits, since the start of the replay")
    with k2.container(border=True):
        st.metric("Off-hours waste so far",
                  ui.eur_range(metrics.eur_range(waste["eur_omie"].sum(), waste["eur_all_in"].sum()))
                  if waste is not None else "–")
        st.caption(f"{waste['excess_kWh'].sum():,.0f} kWh · {waste['kg_co2'].sum():,.0f} kg CO₂"
                   if waste is not None else "")
    by_sev = ended["severity"].value_counts()
    with k3.container(border=True):
        st.metric("Alerts raised", len(ended))
        st.markdown(" ".join(f"{ui.severity_pill(s)} {by_sev.get(s, 0)}" for s in ["High", "Medium", "Low"]),
                    unsafe_allow_html=True)
    with k4.container(border=True):
        st.metric("€ at stake in alerts", ui.eur_range(metrics.eur_range(ended["eur_omie"].sum(), ended["eur_all_in"].sum())))
        st.caption("handle the High ones first")

    # chart: last 7 days, and the next 24 h of expected use (known one day ahead)
    left, right = st.columns([3, 2])
    with left.container(border=True):
        # fixed window = the current week (Mon → Mon): the axes stay still, only the line grows
        a0 = (now - pd.Timedelta(days=now.dayofweek)).normalize()
        a1 = a0 + pd.Timedelta(days=7)
        st.markdown(f"**{circuit}** · week of {a0:%d %b %Y} · actual vs expected")
        w = frame.loc[a0:a1]
        past = w.loc[:now]
        fig = go.Figure()
        off = w["off"]
        blocks = (off != off.shift()).cumsum()[off]
        for _, b in blocks.groupby(blocks):
            fig.add_vrect(x0=b.index[0], x1=b.index[-1] + pd.Timedelta("1h"), fillcolor=config.COLOR_OFF,
                          line_width=0, layer="below")
        for _, a in ev25[(ev25["circuit"] == circuit) & (ev25["start"] <= now) & (ev25["end"] >= a0)].iterrows():
            fig.add_vrect(x0=max(a["start"], a0), x1=min(a["end"], now), fillcolor="rgba(185,28,28,0.12)",
                          line=dict(color=config.COLOR_THRESHOLD, width=1, dash="dot"),
                          annotation_text=f"{a['severity']} · {ui.eur(a['eur_all_in'])}",
                          annotation_position="top left", annotation_font_size=11)
        if "upper_kwh" in w:
            fig.add_scatter(x=w.index, y=w["upper_kwh"], line=dict(width=0), showlegend=False, hoverinfo="skip")
            fig.add_scatter(x=w.index, y=w["lower_kwh"], line=dict(width=0), fill="tonexty",
                            fillcolor="rgba(107,114,128,0.16)", name="90 % band")
        ahead = w.loc[:now + pd.Timedelta(hours=24)]          # expected use is known one day ahead
        fig.add_scatter(x=ahead.index, y=ahead["expected"], name=exp_label,
                        line=dict(color=config.METHODS[method][0], dash="dash"))
        fig.add_scatter(x=past.index, y=past["actual"], name="Actual", line=dict(color=config.COLOR_ACTUAL, width=2.5))
        fig.add_vline(x=now, line_color=config.COLOR_EXPECTED, line_width=1.5)
        # y scale fixed for the whole week, so the chart does not jump at every step
        y_top = pd.concat([w[c] for c in ("actual", "expected", "upper_kwh") if c in w]).max()
        y_top = float(y_top) * 1.15 if pd.notna(y_top) and y_top > 0 else 1.0
        fig.update_layout(height=340, yaxis_title="kWh per hour (= kW)", hovermode="x unified",
                          legend=dict(orientation="h", y=1.12), xaxis=dict(range=[a0, a1]),
                          yaxis=dict(range=[0, y_top]), transition=dict(duration=0))
        st.plotly_chart(fig, key="demo_chart", config={"displayModeBar": False, "staticPlot": ss.demo_play})
        st.caption(f"Grey = building closed · red = alert · dashed = {exp_label}, shown up to 24 h ahead.")

    with right.container(border=True):
        st.markdown("**Alert feed**")
        feed = ev25[ev25["start"] <= now].sort_values("start", ascending=False).head(6)
        if feed.empty:
            st.caption("No alert yet. Keep playing…")
        for _, a in feed.iterrows():
            ongoing = a["end"] > now
            st.markdown(
                f"{ui.severity_pill(a['severity'])} **{a['circuit']}** · "
                f"{'<b style=color:#B91C1C>ongoing</b>' if ongoing else ui.eur(a['eur_all_in'])}  \n"
                f"<span style='color:{config.COLOR_MUTED};font-size:.85rem'>{a['start']:%a %d %b %H:%M} · "
                f"{a['day_type']} · {a['message']}</span>", unsafe_allow_html=True)
        st.page_link("views/alerts.py", label="Open the alert list →")


run_every = config.DEMO_TICK_S if ss.demo_play else None
if hasattr(st, "fragment"):
    st.fragment(run_every=run_every)(replay)()     # only this part refreshes every second
else:
    replay()
    st.caption("Auto-play needs Streamlit ≥ 1.37; with this version, press Play again to step forward.")

ui.footnote(P)
