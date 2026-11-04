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

exp_label, alarm = None, None
if expected is not None:
    e = expected[(expected["circuit"] == circuit) & expected["timestamp_local"].between(start, end)]
    if e["expected_kwh"].notna().sum() > 24:
        g = e.groupby("timestamp_local")
        exp_series = g["expected_kwh"].mean().reindex(idx)
        alarm = g["alarm_kwh"].mean().reindex(idx) if "alarm_kwh" in e else None
        exp_label = exp_src
if exp_label is None:
    b2 = metrics.b2_expected(hourly, col) / 1000
    exp_series = b2.groupby(hourly["timestamp_local"]).mean().reindex(idx)
    exp_label = "team baseline B2 (median of the same hour, last 4 weeks)"
    if expected is not None:
        exp_label += " — the model's values do not cover this week"

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
fig.add_scatter(x=idx, y=exp_series, name="Expected", line=dict(color=config.COLOR_EXPECTED, dash="dash"))
if alarm is not None:
    fig.add_scatter(x=idx, y=alarm, name="Alarm threshold",
                    line=dict(color=config.COLOR_THRESHOLD, dash="dot", width=1))
if show_temp and temp is not None:
    fig.add_scatter(x=idx, y=temp, name="Outdoor °C", yaxis="y2", line=dict(color="#2563EB", width=1))
    fig.update_layout(yaxis2=dict(overlaying="y", side="right", title="°C", showgrid=False))
fig.update_layout(height=400, plot_bgcolor="white", yaxis_title="kWh per hour (= kW)",
                  margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified", legend=dict(orientation="h", y=1.1))

with st.container(border=True):
    st.plotly_chart(fig)
    n_missing = int(actual.isna().sum())
    st.caption(
        f"Expected = {exp_label}. Grey = off-hours; red = alerts. "
        f"Off-hours average {actual[off].mean():.2f} kW vs {exp_series[off].mean():.2f} kW expected. "
        + (f"{n_missing} missing hours are shown as gaps, not zeros." if n_missing else ""))
    if bands is None:
        st.caption("The 90 % band appears when `reports/interval_bands.parquet` (branch KAN-144) is in main.")

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
        fig.update_layout(height=60 + 30 * len(s), margin=dict(l=0, r=50, t=0, b=0), plot_bgcolor="white",
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

ui.footnote(P)
