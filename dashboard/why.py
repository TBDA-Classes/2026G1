"""
Explanation of the expected value (customer-value document, extension 7.2).

Shows which factors raised or lowered what the model expected — outdoor temperature, type of day, recent use… —
in plain language, from dashboard/data/expected_contributions.parquet (tools/export_contributions.py).
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data_loader as dl

FACTORS = {   # column -> plain-language name
    "recent_use_W": "Recent use of this circuit (yesterday, last week)",
    "temperature_W": "Outdoor temperature",
    "hour_of_day_W": "Hour of the day",
    "day_type_W": "Type of day (weekday, weekend, holiday, break)",
    "time_of_year_W": "Time of year",
    "sun_humidity_W": "Sunlight and humidity",
    "other_W": "Other inputs",
}


def _rows(source: str, circuit: str, start, end) -> pd.DataFrame | None:
    c, _ = dl.load_contributions()
    if c is None:
        return None
    return c[(c["circuit"] == circuit) & (c["timestamp_local"] >= start) & (c["timestamp_local"] < end)]


def sentence(mean: pd.Series, temp: float | None = None, when: str = "on average") -> str:
    """'The model expected 2.1 kW: base 1.4 kW; outdoor temperature +0.6 kW (cold, 4 °C); …'"""
    parts = []
    for col in mean.drop(["base_W", "expected_W"], errors="ignore").abs().sort_values(ascending=False).index[:3]:
        v = mean[col] / 1000
        if abs(v) < 0.005:
            continue
        name = FACTORS.get(col, col).split(" (")[0].lower()
        extra = ""
        if col == "temperature_W" and temp is not None and pd.notna(temp):
            extra = f" ({'cold' if temp < 12 else 'mild' if temp < 22 else 'warm'}, {temp:.0f} °C outside)"
        parts.append(f"{name} {'raised' if v > 0 else 'lowered'} it by {abs(v):.2f} kW{extra}")
    return (f"The model expected **{mean['expected_W'] / 1000:.2f} kW** {when}: a base level of "
            f"{mean['base_W'] / 1000:.2f} kW, then " + "; ".join(parts) + ".") if parts else ""


def chart(mean: pd.Series, key: str):
    items = [(FACTORS[c], mean[c] / 1000) for c in FACTORS if c in mean and pd.notna(mean[c])]
    items.sort(key=lambda t: abs(t[1]))
    fig = go.Figure(go.Bar(
        y=[n for n, _ in items], x=[v for _, v in items], orientation="h",
        marker_color=["#C2410C" if v > 0 else "#0F766E" for _, v in items],
        text=[f"{v:+.2f} kW" for _, v in items], textposition="outside",
        hovertemplate="%{y}: %{x:+.2f} kW<extra></extra>"))
    fig.update_layout(height=60 + 30 * len(items), margin=dict(l=0, r=60, t=0, b=0),
                      xaxis=dict(title="kW added (orange) or removed (green) from the base level", zeroline=True))
    st.plotly_chart(fig, key=key, config={"displayModeBar": False})


def explain_alert(source: str, a: pd.Series):
    """In the alert detail: why the model expected what it expected during the alert."""
    rows = _rows(source, a["circuit"], a["start"], a["end"])
    with st.expander("Why did the model expect this value?", expanded=False):
        if rows is None:
            st.caption("Available once `dashboard/data/expected_contributions.parquet` exists "
                       "(run `python dashboard/tools/export_contributions.py` from the repository root).")
            return
        if rows.empty:
            st.caption("No explanation for these hours.")
            return
        hourly, _ = dl.load_hourly()
        temp = hourly.loc[hourly["timestamp_local"].between(a["start"], a["end"]), "wx_temp_c"].mean()
        mean = rows.drop(columns=["timestamp_local", "circuit"]).mean()
        st.markdown(sentence(mean, temp, "on average during the alert"))
        chart(mean, key=f"why_{a['alert_id']}")
        st.caption("The actual use was far above this expectation: that gap is the alert. Factors come from the "
                   "LightGBM model itself (TreeSHAP contributions), averaged over the hours of the alert.")


def explain_hour(source: str, circuit: str, idx: pd.DatetimeIndex, actual: pd.Series, key: str):
    """On Expected vs actual: pick one hour of the week and see why the model expected that value."""
    rows = _rows(source, circuit, idx[0], idx[-1] + pd.Timedelta("1h"))
    st.markdown("**Why did the model expect this value?**")
    if rows is None:
        st.caption("Available once `dashboard/data/expected_contributions.parquet` exists "
                   "(run `python dashboard/tools/export_contributions.py` from the repository root).")
        return
    r = rows.groupby("timestamp_local").mean(numeric_only=True).reindex(idx)
    if r["expected_W"].notna().sum() == 0:
        st.caption("No explanation for this week.")
        return
    gap = (actual - r["expected_W"] / 1000).abs()
    default = gap.idxmax() if gap.notna().any() else r["expected_W"].first_valid_index()
    hour = st.select_slider("Hour", options=list(idx), value=default, key=key,
                            format_func=lambda t: f"{t:%a %d %b %H:00}")
    mean = r.loc[hour]
    if pd.isna(mean["expected_W"]):
        st.caption("No model value for this hour.")
        return
    hourly, _ = dl.load_hourly()
    temp = hourly.loc[hourly["timestamp_local"] == hour, "wx_temp_c"].mean()
    st.markdown(sentence(mean, temp, "at that hour") + (f" Actual use: **{actual.get(hour):.2f} kW**." if pd.notna(actual.get(hour))
                                        else ""))
    chart(mean, key=f"{key}_chart")
    st.caption("Default hour = the largest gap between actual and expected this week. Contributions of the "
               "cross-fitted model (2020–23) or of the 2025 forecast model; they add up to its expected value.")
