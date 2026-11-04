"""
All calculations of the dashboard, in plain pandas (no Streamlit here),
so every function can be tested in Spyder.

Definitions are the modelling team's (src/data.py, src/anomalies.py):
  * off-hours  = night (22:00-05:59 by default, params.yaml) OR not a working day
  * standby    = 10th percentile of night use of the circuit in the training period
  * waste      = signal 1 (events, reports/anomaly_events.csv)
               + signal 2 (chronic off-hours waste, reports/offhours_waste_daily.csv)
"""
import numpy as np
import pandas as pd

import config

FLAG_COLUMNS = ["is_weekend", "is_holiday", "is_break", "is_working_day", "is_covid_lockdown",
                "is_august_closure", "low_coverage", "price_eur_mwh_is_fallback"]


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------
def short(col: str) -> str:
    """'NW|Plugs & Sockets W' -> 'NW Plugs & Sockets' (the name used in reports/)."""
    return col.replace("|", " ", 1).removesuffix(" W")


def split_name(name: str) -> tuple[str, str]:
    """'NW Plugs & Sockets' -> ('NW', 'Plugs & Sockets')."""
    zone, load = name.split(" ", 1)
    return zone, load


def circuit_columns(df: pd.DataFrame) -> list:
    """The 16 circuit power columns (no zone/storey totals, no indoor sensors)."""
    return [c for c in df.columns
            if "|" in c and c.endswith(" W") and "TOTAL" not in c and "|ENV " not in c]


def to_bool(s: pd.Series) -> pd.Series:
    """True/False whether the file stored booleans, 'TRUE'/'False' strings or 0/1."""
    if s.dtype == bool:
        return s
    return s.astype(str).str.strip().str.upper().isin(["TRUE", "1", "1.0"])


# ---------------------------------------------------------------------------
# Hourly table (same helper columns as src/data.load)
# ---------------------------------------------------------------------------
def prepare_hourly(raw: pd.DataFrame, P: dict) -> pd.DataFrame:
    df = raw.copy()
    df["timestamp_local"] = pd.to_datetime(df["timestamp_local"])
    for c in FLAG_COLUMNS:
        if c in df:
            df[c] = to_bool(df[c])
    df = df.sort_values("timestamp_local").reset_index(drop=True)
    if config.DROP_LOCKDOWN and "is_covid_lockdown" in df:
        df = df[~df["is_covid_lockdown"]].reset_index(drop=True)
    if "hour_local" not in df:
        df["hour_local"] = df["timestamp_local"].dt.hour
    start, end = P["off_hours"]["night_hours"]                 # e.g. [22, 6]
    df["is_night"] = (df["hour_local"] >= start) | (df["hour_local"] < end)
    df["is_off_hours"] = ~df["is_working_day"] | df["is_night"]
    df["day_type"] = "working day"
    df.loc[df["is_weekend"], "day_type"] = "weekend"
    df.loc[df["is_holiday"] & ~df["is_weekend"], "day_type"] = "holiday"
    df.loc[df["is_break"] & ~df["is_weekend"] & ~df["is_holiday"], "day_type"] = "break"
    df["month"] = df["timestamp_local"].dt.to_period("M")
    return df


def to_long(df: pd.DataFrame) -> pd.DataFrame:
    """One row per hour and circuit, in kWh (average W over 1 h / 1000)."""
    cols = circuit_columns(df)
    keep = ["timestamp_local", "month", "is_off_hours", "is_night", "day_type"]
    long = df[keep + cols].melt(id_vars=keep, var_name="column", value_name="watts")
    long["circuit"] = long["column"].map(short)
    long[["zone", "load_type"]] = long["circuit"].str.split(" ", n=1, expand=True)
    long["focus"] = long["column"].isin(config.FOCUS)
    long["kwh"] = long["watts"] / 1000
    return long.dropna(subset=["kwh"]).drop(columns=["column", "watts"])


def standby_levels(df: pd.DataFrame, P: dict) -> pd.Series:
    """Standby level (W) per focus circuit, exactly as src/anomalies.offhours_waste."""
    a, b = config.TRAIN_PERIOD
    train = df["timestamp_local"].between(a, b)
    pct = P["off_hours"]["standby_percentile"] / 100
    return pd.Series({short(c): df.loc[train & df["is_night"], c].quantile(pct)
                      for c in config.FOCUS if c in df}, name="standby_W")


def b2_expected(df: pd.DataFrame, col: str) -> pd.Series:
    """Team baseline B2 (src/models.baseline_median_4w): median of the same hour
    in the last 4 weeks, computed inside each regime. Watts."""
    out = []
    for _, g in df.groupby("Regime"):
        s = g[col]
        out.append(pd.concat([s.shift(168 * k) for k in range(1, 5)], axis=1).median(axis=1))
    return pd.concat(out).reindex(df.index)


# ---------------------------------------------------------------------------
# Modelling outputs
# ---------------------------------------------------------------------------
def prepare_events(ev: pd.DataFrame) -> pd.DataFrame:
    ev = ev.copy()
    ev["start"] = pd.to_datetime(ev["start"])
    ev["end"] = pd.to_datetime(ev["end"])
    if "zone" not in ev or "device" not in ev:
        ev[["zone", "device"]] = ev["circuit"].str.split(" ", n=1, expand=True)
    ev = ev.rename(columns={"device": "load_type"})
    ev["severity"] = ev["severity"].astype(str).str.capitalize()
    share = ev["share_off_hours"] if "share_off_hours" in ev else 1.0
    ev["category"] = np.where(share >= config.OFF_HOURS_SHARE_FOR_WASTE,
                              "Off-hours waste", "To investigate")
    # stable id, so a status saved today still matches after the notebook is re-run
    ev["alert_id"] = ev["circuit"] + " " + ev["start"].dt.strftime("%Y-%m-%d %H:%M")
    ev["month"] = ev["start"].dt.to_period("M")
    for c in ["eur_omie", "eur_all_in", "kg_co2", "actual_kWh", "expected_kWh"]:
        if c not in ev:
            ev[c] = np.nan
    if "message" not in ev:
        ev["message"] = ""
    return ev


def prepare_daily(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["month"] = d["date"].dt.to_period("M")
    d[["zone", "load_type"]] = d["circuit"].str.split(" ", n=1, expand=True)
    return d


def sort_alerts(ev: pd.DataFrame) -> pd.DataFrame:
    order = {"High": 0, "Medium": 1, "Low": 2}
    return (ev.assign(_s=ev["severity"].map(order).fillna(3))
              .sort_values(["_s", "excess_kWh"], ascending=[True, False])
              .drop(columns="_s"))


def eur_range(lo: float, hi: float) -> tuple[float, float]:
    """OMIE and all-in can be in either order (2022: wholesale above all-in)."""
    return (min(lo, hi), max(lo, hi))


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
def month_kpis(long_sel, daily_sel, events_sel, month) -> dict:
    cur, prev = long_sel[long_sel["month"] == month], long_sel[long_sel["month"] == month - 1]
    used, used_prev = cur["kwh"].sum(), prev["kwh"].sum()
    w, wp = daily_sel[daily_sel["month"] == month], daily_sel[daily_sel["month"] == month - 1]
    ev = events_sel[events_sel["month"] == month]
    return {
        "used_kwh": used,
        "used_delta_pct": (used / used_prev - 1) * 100 if used_prev else None,
        "off_share_pct": cur.loc[cur["is_off_hours"], "kwh"].sum() / used * 100 if used else 0.0,
        "waste_kwh": w["excess_kWh"].sum(),
        "waste_eur": eur_range(w["eur_omie"].sum(), w["eur_all_in"].sum()),
        "waste_co2": w["kg_co2"].sum(),
        "waste_eur_prev": wp["eur_all_in"].sum() if len(wp) else None,
        "events": len(ev),
        "events_by_sev": ev["severity"].value_counts().to_dict(),
        "events_kwh": ev["excess_kWh"].sum(),
    }


def monthly_waste(daily_sel: pd.DataFrame) -> pd.DataFrame:
    m = daily_sel.groupby("month", as_index=False)[["excess_kWh", "eur_all_in", "eur_omie", "kg_co2"]].sum()
    m["label"] = m["month"].dt.strftime("%b %Y")
    return m


def waste_by(daily_sel: pd.DataFrame, col: str) -> pd.DataFrame:
    return (daily_sel.groupby(col, as_index=False)[["excess_kWh", "eur_all_in", "eur_omie", "kg_co2"]]
                     .sum().sort_values("excess_kWh", ascending=False))


def chronic_heatmap(daily_sel: pd.DataFrame) -> pd.DataFrame:
    """kWh above standby in off-hours, circuit x month."""
    return daily_sel.pivot_table(index="circuit", columns="month", values="excess_kWh",
                                 aggfunc="sum").sort_index()


# ---------------------------------------------------------------------------
# Off-hours page
# ---------------------------------------------------------------------------
def open_off_split(long_sel: pd.DataFrame, col: str) -> pd.DataFrame:
    t = (long_sel.assign(state=np.where(long_sel["is_off_hours"], "Off-hours", "Working hours"))
                 .pivot_table(index=col, columns="state", values="kwh", aggfunc="sum", fill_value=0)
                 .reindex(columns=["Working hours", "Off-hours"], fill_value=0))
    t["off_pct"] = t["Off-hours"] / (t["Working hours"] + t["Off-hours"]).replace(0, np.nan) * 100
    return t.sort_values("Off-hours", ascending=False).reset_index()


def weekday_hour_profile(long_sel: pd.DataFrame) -> pd.DataFrame:
    """Average power (kW) by weekday x hour; 1 kWh in an hour = 1 kW average."""
    total = long_sel.groupby("timestamp_local")["kwh"].sum()
    prof = total.groupby([total.index.dayofweek, total.index.hour]).mean().unstack()
    prof.index = [["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i] for i in prof.index]
    return prof


# ---------------------------------------------------------------------------
# Data quality (on all 16 circuits)
# ---------------------------------------------------------------------------
def monthly_coverage(df: pd.DataFrame) -> pd.DataFrame:
    cols = circuit_columns(df)
    present = df[cols].notna().mean(axis=1)
    cov = present.groupby(df["timestamp_local"].dt.to_period("M")).mean()
    return cov.rename("coverage").rename_axis("month").reset_index()


def circuit_coverage(df: pd.DataFrame) -> pd.DataFrame:
    cols = circuit_columns(df)
    out = pd.DataFrame({"circuit": [short(c) for c in cols],
                        "coverage": [df[c].notna().mean() for c in cols],
                        "focus": [c in config.FOCUS for c in cols]})
    out["status"] = np.select([out["coverage"] >= 0.99, out["coverage"] >= 0.90],
                              ["Reliable", "Use with caution"], "Unreliable")
    return out.sort_values("coverage")


def largest_gaps(df: pd.DataFrame, top: int = 8, min_hours: int = 6) -> pd.DataFrame:
    """Runs of empty hours per circuit (inside the hourly grid of each regime)."""
    rows = []
    ts = df["timestamp_local"]
    for c in circuit_columns(df):
        miss = df[c].isna()
        run = (miss != miss.shift()).cumsum()
        for _, g in ts[miss].groupby(run[miss]):
            if len(g) >= min_hours:
                rows.append({"start": g.iloc[0], "end": g.iloc[-1], "hours": len(g), "circuit": short(c)})
    if not rows:
        return pd.DataFrame(columns=["When", "What is missing", "Hours"])
    r = pd.DataFrame(rows)
    n = len(circuit_columns(df))
    out = (r.groupby(["start", "end", "hours"])["circuit"]
             .agg(lambda s: "All circuits" if len(s) == n else ", ".join(sorted(s)))
             .reset_index().sort_values("hours", ascending=False).head(top))
    out["When"] = out["start"].dt.strftime("%d %b %Y %H:%M") + " → " + out["end"].dt.strftime("%d %b %Y %H:%M")
    return out.rename(columns={"circuit": "What is missing", "hours": "Hours"})[["When", "What is missing", "Hours"]]
