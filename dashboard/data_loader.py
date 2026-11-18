"""
Reads the team's files once (Streamlit cache) and keeps track of where every
number comes from (`sources()`), so each page can say it.

Every loader returns a table, or None when the file does not exist yet:
pages then show a short explanation instead of crashing.
"""
import json

import pandas as pd
import streamlit as st

import config
import metrics

try:
    import yaml
except ImportError:          # PyYAML missing -> built-in copy of the parameters
    yaml = None


# ---------------------------------------------------------------------------
# Finding and reading files
# ---------------------------------------------------------------------------
def _find(stem, exts=(".parquet", ".csv", ".xlsx")):
    """Path of `stem` with the first extension that exists, or None."""
    for ext in exts:
        p = stem.parent / f"{stem.name}{ext}"
        if p.exists():
            return p
    return None


def _find_output(name, exts=(".parquet", ".csv")):
    """A modelling output: dashboard/data/ first (local copy), then reports/."""
    for folder in (config.LOCAL_DIR, config.REPORTS_DIR):
        p = _find(folder / name, exts)
        if p is not None:
            return p
    return None


def _read(path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".xlsx":
        return pd.read_excel(path, sheet_name=0)
    return pd.read_csv(path)


def _rel(path) -> str:
    try:
        return str(path.relative_to(config.REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return path.name


# ---------------------------------------------------------------------------
# Parameters and manifest
# ---------------------------------------------------------------------------
@st.cache_data
def load_params() -> tuple[dict, str]:
    if yaml is not None and config.PARAMS_FILE.exists():
        with open(config.PARAMS_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f), "params.yaml"
    return config.DEFAULT_PARAMS, "built-in copy (params.yaml not found)"


@st.cache_data
def load_manifest() -> dict | None:
    if config.MANIFEST_FILE.exists():
        return json.loads(config.MANIFEST_FILE.read_text(encoding="utf-8"))
    return None


# ---------------------------------------------------------------------------
# Hourly data
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading the hourly data…")
def load_hourly() -> tuple[pd.DataFrame, str]:
    for stem in config.HOURLY_CANDIDATES:
        path = _find(stem)
        if path is not None:
            P, _ = load_params()
            return metrics.prepare_hourly(_read(path), P), _rel(path)
    st.error(
        "**Hourly data not found.** The dashboard looks for "
        "`data/processed/cedint_hourly_v1.parquet` in the 2026G1 repository. "
        "Put the `dashboard/` folder at the root of the repository (next to `data/`, `src/`, `reports/`).")
    st.stop()


@st.cache_data(show_spinner="Preparing circuits…")
def load_long(source: str) -> pd.DataFrame:
    df, _ = load_hourly()
    return metrics.to_long(df)


@st.cache_data
def load_standby(source: str) -> pd.Series:
    df, _ = load_hourly()
    P, _ = load_params()
    return metrics.standby_levels(df, P)


# ---------------------------------------------------------------------------
# Modelling outputs
# ---------------------------------------------------------------------------
@st.cache_data
def load_events():
    p = _find_output(config.EVENTS_FILE)
    return (metrics.prepare_events(_read(p)), _rel(p)) if p else (None, None)


@st.cache_data
def load_daily_waste():
    p = _find_output(config.DAILY_WASTE_FILE)
    return (metrics.prepare_daily(_read(p)), _rel(p)) if p else (None, None)


@st.cache_data
def load_savings():
    p = _find_output(config.SAVINGS_FILE)
    return (_read(p), _rel(p)) if p else (None, None)


@st.cache_data
def load_model_comparison():
    p = _find_output(config.MODEL_COMPARISON_FILE)
    if p is None:
        return None, None
    m = _read(p)
    m["circuit"] = m["circuit"].map(lambda c: metrics.short(c) if "|" in c else c)
    return m, _rel(p)


@st.cache_data
def load_anomaly_k():
    p = _find_output(config.ANOMALY_K_FILE, exts=(".json",))
    return (json.loads(p.read_text(encoding="utf-8")), _rel(p)) if p else (None, None)


@st.cache_data(show_spinner="Loading expected values…")
def load_expected():
    """Expected use (kWh) per circuit and hour, best source first:
       1. expected_hourly  — every hour since 2020 (tools/export_expected.py)
       2. test_predictions — LightGBM, test months only (notebook 02)
    Returns (table with timestamp_local, circuit, expected_kwh[, alarm_kwh], label) or (None, None)."""
    p = _find_output(config.EXPECTED_FILE)
    if p is not None:
        e = _read(p)
        e["timestamp_local"] = pd.to_datetime(e["timestamp_local"])
        e["expected_kwh"] = e["expected_W"] / 1000
        if "threshold_W" in e:
            e["alarm_kwh"] = (e["expected_W"] + e["threshold_W"]) / 1000
        keep = [c for c in ["timestamp_local", "circuit", "expected_kwh", "alarm_kwh"] if c in e]
        return e[keep], f"LightGBM, cross-fitted ({_rel(p)})"
    p = _find_output(config.TEST_PREDICTIONS_FILE)
    if p is not None:
        t = _read(p)
        if "circuit" not in t.columns:
            t = t.reset_index()
        t["timestamp_local"] = pd.to_datetime(t["timestamp_local"])
        t["expected_kwh"] = t["LightGBM_forecast"] / 1000
        return t[["timestamp_local", "circuit", "expected_kwh"]], f"LightGBM, test months only ({_rel(p)})"
    return None, None


@st.cache_data
def load_model_predictions():
    """Hourly predictions of every model on the test months (notebook 02).
    Returns (table with timestamp_local, circuit and one column per model, in W) or (None, None)."""
    p = _find_output(config.TEST_PREDICTIONS_FILE)
    if p is None:
        return None, None
    t = _read(p)
    if "circuit" not in t.columns:
        t = t.reset_index()
    t["timestamp_local"] = pd.to_datetime(t["timestamp_local"])
    return t, _rel(p)


@st.cache_data
def load_bands():
    p = _find_output(config.BANDS_FILE)
    if p is None:
        return None, None
    b = _read(p)
    b["timestamp_local"] = pd.to_datetime(b["timestamp_local"])
    b["lower_kwh"], b["upper_kwh"] = b["lower"] / 1000, b["upper"] / 1000
    return b[["timestamp_local", "circuit", "lower_kwh", "upper_kwh"]], _rel(p)


@st.cache_data(show_spinner="Checking data coverage…")
def coverage_tables(source: str):
    """(monthly coverage, coverage per circuit, largest gaps) on all 16 circuits."""
    df, _ = load_hourly()
    return metrics.monthly_coverage(df), metrics.circuit_coverage(df), metrics.largest_gaps(df)


def month_coverage(source: str, month) -> float | None:
    monthly, _, _ = coverage_tables(source)
    v = monthly.loc[monthly["month"] == month, "coverage"]
    return float(v.iloc[0]) if len(v) else None


def sources() -> pd.DataFrame:
    """Which file feeds what — shown on the Method page."""
    _, hourly = load_hourly()
    _, params = load_params()
    rows = [("Hourly data", hourly), ("Parameters (€, CO₂, off-hours)", params),
            ("Alerts (signal 1)", load_events()[1]), ("Chronic waste (signal 2)", load_daily_waste()[1]),
            ("Savings per year", load_savings()[1]), ("Model scores", load_model_comparison()[1]),
            ("Expected use", load_expected()[1]), ("90 % band", load_bands()[1])]
    return pd.DataFrame([{"Used for": a, "File": b or "— not found"} for a, b in rows])


# ---------------------------------------------------------------------------
# Alert status, saved in dashboard/data/alert_status.csv
# ---------------------------------------------------------------------------
STATUSES = ["Open", "Handled", "Under investigation", "This was normal", "Data error"]


def load_status() -> dict:
    if config.ALERT_STATUS_FILE.exists():
        s = pd.read_csv(config.ALERT_STATUS_FILE)
        return dict(zip(s["alert_id"], s["status"]))
    return {}


def save_status(alert_id: str, status: str) -> None:
    current = load_status()
    current[alert_id] = status
    config.LOCAL_DIR.mkdir(exist_ok=True)
    pd.DataFrame({"alert_id": list(current), "status": list(current.values())}) \
      .to_csv(config.ALERT_STATUS_FILE, index=False)


# ---------------------------------------------------------------------------
# Filters shared by every page (sidebar)
# ---------------------------------------------------------------------------
LOADS = ["Plugs & Sockets", "Lighting", "HVAC"]


def sidebar_filters(df: pd.DataFrame) -> None:
    n = df.groupby("month").size()
    months = sorted(n[n >= 168].index)          # at least a week of data (drops the single hour of Mar 2023)
    default = pd.Period(config.DEFAULT_MONTH, "M")
    with st.sidebar:
        st.divider()
        st.caption("FILTERS")
        st.selectbox("Month", months, index=months.index(default) if default in months else len(months) - 1,
                     format_func=lambda p: p.strftime("%B %Y"), key="f_month")
        st.selectbox("Zone", ["All zones"] + config.ZONES, key="f_zone")
        st.selectbox("Load type", ["All loads"] + LOADS, key="f_load")


def get_filters() -> dict:
    return {"month": st.session_state["f_month"], "zone": st.session_state["f_zone"],
            "load": st.session_state["f_load"]}


def apply_filters(df: pd.DataFrame, f: dict, month: bool = False) -> pd.DataFrame:
    """Works on any table with `zone` and `load_type` columns (long data, events, daily waste)."""
    if df is None:
        return None
    if f["zone"] != "All zones":
        df = df[df["zone"] == f["zone"]]
    if f["load"] != "All loads":
        df = df[df["load_type"] == f["load"]]
    if month:
        df = df[df["month"] == f["month"]]
    return df
