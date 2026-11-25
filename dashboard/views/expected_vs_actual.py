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
expected, exp_src = dl.load_expected()
bands, bands_src = dl.load_bands()
events, _ = dl.load_events()
scores, _ = dl.load_model_comparison()

# --- Page selectors: circuit and week -----------------------------------------
names = [metrics.short(c) for c in config.FOCUS]
col_of = dict(zip(names, config.FOCUS))
top_l, top_r = st.columns([3, 2])
with top_r:
    c1, c2 = st.columns(2)
    circuit = c1.selectbox("Circuit", names, index=0)
    col = col_of[circuit]
    ts = hourly.loc[hourly[col].notna(), "timestamp_local"]
    weeks = pd.DatetimeIndex(sorted((ts.dt.normalize() - pd.to_timedelta(ts.dt.dayofweek, unit="D")).unique()))
    first = f["month"].start_time
    default = int(min(weeks.searchsorted(first - pd.Timedelta(days=first.dayofweek)), len(weeks) - 1))
    week = c2.selectbox("Week", weeks, index=default,
                        format_func=lambda d: f"{d:%d} – {d + pd.Timedelta(days=6):%d %b %Y}")
with top_l:
    st.title("Expected vs actual")
    st.caption(f"{circuit} · week of {week:%d %B %Y}")

# --- Series for the week (one value per local hour) ----------------------------
start, end = week, week + pd.Timedelta(days=7)
idx = pd.date_range(start, end - pd.Timedelta("1h"), freq="h")
wk = hourly[(hourly["timestamp_local"] >= start) & (hourly["timestamp_local"] < end)]
by_hour = wk.groupby("timestamp_local")          # the autumn DST hour appears twice: averaged
actual = (by_hour[col].mean() / 1000).reindex(idx)
off = by_hour["is_off_hours"].first().reindex(idx).fillna(False).astype(bool)
temp = by_hour["wx_temp_c"].mean().reindex(idx) if "wx_temp_c" in wk else None
hour_phase = pd.Series(metrics.phase_of(pd.Series(idx)).values, index=idx)
phase = hour_phase.mode().iat[0]

# --- Where is this week in the evaluation? (train / validation / test / 2025) ----
phase_info = {n: (c, d) for n, a, b, c, d in config.PHASES}
strip = go.Figure()
for n, a, b, colour, _ in config.PHASES:
    if n == "No data":
        continue
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    strip.add_shape(type="rect", x0=a, x1=b, y0=0, y1=1, fillcolor=colour, line=dict(width=0), layer="below")
    strip.add_annotation(x=a + (b - a) / 2, y=0.5, text=n, showarrow=False, font=dict(size=11, color="#111827"))
strip.add_shape(type="line", x0=start + pd.Timedelta(days=3.5), x1=start + pd.Timedelta(days=3.5), y0=-0.15, y1=1.15,
                line=dict(color="#DC2626", width=3))
strip.add_scatter(x=[pd.Timestamp("2020-04-02"), pd.Timestamp("2025-10-13")], y=[0.5, 0.5], mode="markers",
                  marker=dict(opacity=0), hoverinfo="skip", showlegend=False)   # gives the axis its range
strip.update_layout(height=70, showlegend=False, margin=dict(l=0, r=0, t=0, b=0),
                    yaxis=dict(visible=False, range=[-0.2, 1.2]),
                    xaxis=dict(type="date", rangebreaks=[dict(bounds=["2023-03-15", "2025-08-01"])]))
st.plotly_chart(strip, config={"displayModeBar": False}, key="phase_strip")
st.markdown(f"<span class='pill' style='background:{phase_info.get(phase, ('#E5E7EB',))[0]};color:#111827'>"
            f"{phase}</span> {phase_info.get(phase, ('', ''))[1]}", unsafe_allow_html=True)

# --- Prediction methods to draw (several can be compared) -------------------------
available = dl.methods_covering(src, circuit, start, end)
default = [m for m in ("LightGBM (team model)",) if m in available] or \
          [m for m in ("B2 · 4-week median",) if m in available]
chosen = st.multiselect("Prediction methods to compare", available, default=default,
                        help="LightGBM and Ridge come from the modelling notebooks; B1–B3 are the team's simple "
                             "baselines, computed here for every hour. Only methods with values for this week are listed.")
missing_methods = [m for m in config.METHODS if m not in available]
preds = {m: dl.method_series(src, circuit, m).reindex(idx) for m in chosen}
alarm = None
if "LightGBM (team model)" in chosen and expected is not None and "alarm_kwh" in expected:
    e = expected[(expected["circuit"] == circuit) & expected["timestamp_local"].between(start, end)]
    if e["alarm_kwh"].notna().sum() > 24:
        alarm = e.groupby("timestamp_local")["alarm_kwh"].mean().reindex(idx)
        # in the test months the line is the honest forecast, the threshold belongs to the cross-fitted line
        alarm[hour_phase == "Test"] = float("nan")

show_temp = st.toggle("Show outdoor temperature", value=False, disabled=temp is None)

fig = go.Figure()
blocks = (off != off.shift()).cumsum()[off]
for _, b in blocks.groupby(blocks):
    fig.add_vrect(x0=b.index[0], x1=b.index[-1] + pd.Timedelta("1h"), fillcolor=config.COLOR_OFF,
                  line_width=0, layer="below")
if events is not None:
    ev = events[(events["circuit"] == circuit) & (events["start"] < end) & (events["end"] > start)]
    for _, a in ev.iterrows():
        fig.add_vrect(x0=max(a["start"], start), x1=min(a["end"], end), fillcolor="rgba(185,28,28,0.10)",
                      line=dict(color=config.COLOR_THRESHOLD, width=1, dash="dot"),
                      annotation_text=f"{a['severity']} +{a['excess_kWh']:.0f} kWh",
                      annotation_position="top left", annotation_font_size=10)
if bands is not None:
    bb = bands[(bands["circuit"] == circuit) & bands["timestamp_local"].between(start, end)]
    if len(bb):
        g = bb.groupby("timestamp_local")
        lo, hi = g["lower_kwh"].mean().reindex(idx), g["upper_kwh"].mean().reindex(idx)
        fig.add_scatter(x=idx, y=hi, line=dict(width=0), showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=idx, y=lo, line=dict(width=0), fill="tonexty",
                        fillcolor="rgba(107,114,128,0.18)", name="90 % band")
fig.add_scatter(x=idx, y=actual, name="Actual", line=dict(color=config.COLOR_ACTUAL, width=2))
for m, ser in preds.items():
    colour, dash, _ = config.METHODS[m]
    if m.startswith("LightGBM"):
        # one segment per phase, labelled as the modelling team asks: forecast vs expected afterwards
        for ph in hour_phase.unique():
            label, ph_dash, _ = config.LGB_LABELS.get(ph, (m, dash, ""))
            seg = ser.where(hour_phase == ph)
            if seg.notna().any():
                fig.add_scatter(x=idx, y=seg, name=label, line=dict(color=colour, dash=ph_dash, width=1.8))
    else:
        fig.add_scatter(x=idx, y=ser, name=m, line=dict(color=colour, dash=dash, width=1.6))
if alarm is not None:
    fig.add_scatter(x=idx, y=alarm, name="Alarm threshold",
                    line=dict(color=config.COLOR_THRESHOLD, dash="dot", width=1))
if show_temp and temp is not None:
    fig.add_scatter(x=idx, y=temp, name="Outdoor °C", yaxis="y2", line=dict(color="#2563EB", width=1))
    fig.update_layout(yaxis2=dict(overlaying="y", side="right", title="°C", showgrid=False))
fig.update_layout(height=400, yaxis_title="kWh per hour (= kW)",
                  margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified", legend=dict(orientation="h", y=1.1))

with st.container(border=True):
    st.plotly_chart(fig)
    n_missing = int(actual.isna().sum())
    st.caption("Grey = off-hours; red = alerts (from the LightGBM model, notebook 03). "
               + (f"{n_missing} missing hours are shown as gaps, not zeros. " if n_missing else "")
               + (f"Not available this week: {', '.join(missing_methods)}." if missing_methods else ""))
    if preds:
        lgb_name = config.LGB_LABELS.get(phase, ("LightGBM (team model)",))[0]
        rows = [{"Method": lgb_name if m.startswith("LightGBM") else m,
                 "Error this week (MAE, kWh/h)": metrics.mae_kwh(actual, ser),
                 "Off-hours expected (kW)": ser[off].mean(), "Source": config.METHODS[m][2]}
                for m, ser in preds.items()]
        st.dataframe(pd.DataFrame(rows).sort_values("Error this week (MAE, kWh/h)"), hide_index=True,
                     column_config={"Error this week (MAE, kWh/h)": st.column_config.NumberColumn(format="%.3f"),
                                    "Off-hours expected (kW)": st.column_config.NumberColumn(format="%.2f")})
        st.caption(f"Actual off-hours average this week: {actual[off].mean():.2f} kW. Lower error = closer to reality.")
        if "LightGBM (team model)" in preds and phase in config.LGB_LABELS:
            st.info(f"**How to read the LightGBM line this week ({phase}):** {config.LGB_LABELS[phase][2]}"
                    + (" Its error here looks better than a real forecast would be: use the Test months "
                       "(Jan–Feb 2023) or 2025 to judge the model." if phase in ("Train", "Validation") else "")
                    + (" The alarm threshold is hidden: the alerts of these months were computed on the "
                       "cross-fitted line of notebook 03." if phase == "Test" else ""))
    if bands is None:
        st.caption("The 90 % band appears when `reports/interval_bands.parquet` (branch KAN-144) is in main.")

# --- Why did the model expect this value? (extension 7.2) ------------------------
with st.container(border=True):
    why.explain_hour(src, circuit, idx, actual, key=f"why_{circuit}_{week:%Y%m%d}")

# --- Model quality -------------------------------------------------------------
left, right = st.columns([3, 2])
with left.container(border=True):
    st.markdown("**How good is the expectation?** · MAE in kWh per hour, lower is better")
    if scores is None:
        ui.missing("This chart", "reports/model_comparison.csv")
    else:
        sc = scores[scores["circuit"] == circuit]
        periods = [p for p in config.SPLIT_LABELS if p in set(sc["period"])]
        period = st.radio("Period", periods, horizontal=True, format_func=config.SPLIT_LABELS.get,
                          index=periods.index("test") if "test" in periods else 0)
        s = sc[sc["period"] == period].sort_values("MAE_kWh")
        colors = [config.COLOR_ACTUAL if m == "LightGBM_forecast" else "#9CA3AF" for m in s["model"]]
        fig = go.Figure(go.Bar(x=s["MAE_kWh"], y=s["model"], orientation="h", marker_color=colors,
                               text=[f"{v:.3f}" for v in s["MAE_kWh"]], textposition="outside"))
        fig.update_layout(height=60 + 30 * len(s), margin=dict(l=0, r=50, t=0, b=0),
                          yaxis=dict(autorange="reversed"), xaxis=dict(visible=False))
        st.plotly_chart(fig)
        lgb = s[s["model"] == "LightGBM_forecast"]
        if len(lgb):
            cv = lgb["CV_RMSE_%"].iloc[0]
            st.caption(f"LightGBM_forecast (the model used for alerts): CV(RMSE) {cv:.0f} % — "
                       f"ASHRAE Guideline 14 asks ≤ 30 % for hourly models. Source: notebook 02.")
with right.container(border=True):
    st.markdown("**How to read this page**")
    st.markdown(
        "- **Expected** is what the model predicted a day ahead for this circuit.\n"
        "- An **alert** is raised when the actual use stays far above expected "
        "(threshold set per circuit for about one alert per week).\n"
        "- Hour-by-hour misses are large because people switch heaters and lights by hand; "
        "the model is made to catch **large** waste, not every hour.")

# --- Accuracy against the indicative targets (review slide B1) -------------------
if scores is not None:
    with st.container(border=True):
        st.markdown("**Hourly accuracy of LightGBM against the indicative targets** (all focus circuits)")
        acc = metrics.accuracy_table(scores)

        def _colour(v):
            return {"met": "color:#166534;font-weight:600", "not met": "color:#9A3412"}.get(v, "")
        styled = (acc.style.format({"CV(RMSE) Sep–Dec 22": "{:.0f} %", "CV(RMSE) Jan–Feb 23": "{:.0f} %",
                                    "NMBE Jan–Feb 23": "{:+.0f} %", "CV(RMSE) Aug–Oct 25": "{:.0f} %"}, na_rep="–")
                  .map(_colour, subset=["Val.", "Test", "2025"]))
        st.dataframe(styled, hide_index=True)
        st.caption("Targets shared by the teacher: CV(RMSE) ≤ 30 % for plugs, 30–50 % for HVAC with |NMBE| ≤ 10 %, "
                   "daily energy for lighting. Winter test months are the hardest: heaters are switched by hand. "
                   "For waste detection, large daily deviations matter more than single hours.")

ui.footnote(P)
