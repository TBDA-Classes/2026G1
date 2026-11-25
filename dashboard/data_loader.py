"""
Reads the team's files once (Streamlit cache) and keeps track of where every
number comes from (`sources()`), so each page can say it.

Every loader returns a table, or None when the file does not exist yet:
pages then show a short explanation instead of crashing.
"""
import json
from urllib.parse import quote

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
def _find_zone(zone: str):
    """zone_NW_hourly.parquet (also zone_NW_hourly_4.parquet from a browser download), else the Excel copy."""
    for ext in (".parquet", ".csv", ".xlsx"):
        hits = sorted(config.ZONE_DIR.glob(config.ZONE_FILE.format(zone=zone) + "*" + ext))
        if hits:
            return hits[0]
    return None


def _read_zone(path) -> pd.DataFrame:
    if path.suffix == ".xlsx":
        return pd.read_excel(path, sheet_name="DATA")
    return _read(path)


@st.cache_data(show_spinner="Loading the hourly data…")
def load_hourly() -> tuple[pd.DataFrame, str]:
    P, _ = load_params()
    zone_paths = {z: _find_zone(z) for z in config.ZONES}
    if all(zone_paths.values()):                       # first choice: the data-cleaning group's zone files
        raw = metrics.join_zones({z: _read_zone(p) for z, p in zone_paths.items()})
        name = _rel(zone_paths["NW"]).replace("zone_NW", "zone_*")
        return metrics.prepare_hourly(raw, P), name
    for stem in config.HOURLY_CANDIDATES:
        path = _find(stem)
        if path is not None:
            return metrics.prepare_hourly(_read(path), P), _rel(path)
    st.error(
        "**Hourly data not found.** The dashboard looks for the zone files `data/zone_*_hourly.parquet` "
        "(or `data/processed/cedint_hourly_v1.parquet`) in the 2026G1 repository. "
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
def load_bands():
    p = _find_output(config.BANDS_FILE)
    if p is None:
        return None, None
    b = _read(p)
    b["timestamp_local"] = pd.to_datetime(b["timestamp_local"])
    b["lower_kwh"], b["upper_kwh"] = b["lower"] / 1000, b["upper"] / 1000
    return b[["timestamp_local", "circuit", "lower_kwh", "upper_kwh"]], _rel(p)


@st.cache_data
def load_calibration():
    """Severity calibration (EXP-12): share of alerts and of € per level, alerts per week."""
    p = _find_output(config.CALIBRATION_FILE, exts=(".json",))
    return (json.loads(p.read_text(encoding="utf-8")), _rel(p)) if p else (None, None)


@st.cache_data(show_spinner="Loading the model explanations…")
def load_contributions():
    """Factors behind every expected value (extension 7.2, tools/export_contributions.py)."""
    p = _find_output(config.CONTRIB_FILE)
    if p is None:
        return None, None
    c = _read(p)
    c["timestamp_local"] = pd.to_datetime(c["timestamp_local"])
    return c, _rel(p)


@st.cache_data
def load_final_settings():
    p = _find_output(config.FINAL_SETTINGS_FILE, exts=(".json",))
    return (json.loads(p.read_text(encoding="utf-8")), _rel(p)) if p else (None, None)


@st.cache_data
def load_model_card():
    for p in config.MODEL_CARD_CANDIDATES:
        if p.exists():
            return p.read_text(encoding="utf-8"), _rel(p)
    return None, None


@st.cache_data(show_spinner="Comparing definitions of 'closed'…")
def chronic_compare(source: str) -> pd.DataFrame:
    """Chronic waste per year and circuit (kWh, € wholesale, kg CO₂ hourly / yearly) for the team definition
    of 'closed' ('night') and the backlog definition ('day')."""
    df, _ = load_hourly()
    P, _ = load_params()
    sb = load_standby(source)
    return pd.concat([metrics.chronic_by_definition(df, sb, P, d).assign(definition=d) for d in ("night", "day")],
                     ignore_index=True)


@st.cache_data(show_spinner="Loading the model predictions…")
def load_test_models():
    """All model predictions of notebook 02 on the test months (Jan–Feb 2023), kWh, one row per hour and circuit."""
    p = _find_output(config.TEST_PREDICTIONS_FILE)
    if p is None:
        return None
    t = _read(p)
    if "circuit" not in t.columns:
        t = t.reset_index()
    t["timestamp_local"] = pd.to_datetime(t["timestamp_local"])
    cols = [c for c in config.TEST_MODEL_COLUMNS.values() if c in t]
    t[cols] = t[cols] / 1000
    return t[["timestamp_local", "circuit"] + cols]


@st.cache_data(show_spinner="Computing the prediction…")
def method_series(source: str, circuit: str, method: str) -> pd.Series:
    """Prediction of one method for one circuit, kWh per local hour (NaN where the method has no value)."""
    df, _ = load_hourly()
    col = next(c for c in config.FOCUS if metrics.short(c) == circuit)
    by_hour = lambda s: s.groupby(df["timestamp_local"]).mean()     # autumn DST hour appears twice
    if method.startswith("B1"):
        return by_hour(metrics.b1_expected(df, col) / 1000)
    if method.startswith("B2"):
        return by_hour(metrics.b2_expected(df, col) / 1000)
    if method.startswith("B3"):
        return by_hour(metrics.b3_expected(df, col) / 1000)
    out = pd.Series(dtype=float, index=pd.DatetimeIndex([], name="timestamp_local"))
    if method.startswith("LightGBM"):
        exp, _ = load_expected()
        if exp is not None:
            out = exp[exp["circuit"] == circuit].groupby("timestamp_local")["expected_kwh"].mean()
    # Test months: always the honest forecast of notebook 02 (trained up to 31 Dec 2022, predicted once),
    # never the cross-fitted value of notebook 03 (its model saw later quarters).
    t = load_test_models()
    name = config.TEST_MODEL_COLUMNS.get(method)
    if t is not None and name in t:
        test = t[t["circuit"] == circuit].groupby("timestamp_local")[name].mean()
        if not out.empty:                                  # drop every cross-fitted value of the test months
            _, a, b, *_ = next(ph for ph in config.PHASES if ph[0] == "Test")
            out = out[(out.index < pd.Timestamp(a)) | (out.index > pd.Timestamp(b))]
        out = test.combine_first(out) if not out.empty else test
    return out.sort_index()


def methods_covering(source: str, circuit: str, start, end, min_hours: int = 24) -> list:
    """Methods that have at least `min_hours` predictions between start and end."""
    ok = []
    for m in config.METHODS:
        s = method_series(source, circuit, m)
        if s.empty:
            continue
        if s[(s.index >= start) & (s.index < end)].notna().sum() >= min_hours:
            ok.append(m)
    return ok


@st.cache_data(show_spinner="Preparing the replay…")
def demo_frame(source: str, circuit: str, method: str):
    """Hourly series of one circuit over period B (2025) for the live demo:
    actual, expected (chosen method), 90 % band, off-hours flag, cumulative focus use. kWh per hour."""
    df, _ = load_hourly()
    B = df[df["Regime"] == "B"] if "Regime" in df else df[df["timestamp_local"].dt.year >= 2025]
    col = next(c for c in config.FOCUS if metrics.short(c) == circuit)
    g = B.groupby("timestamp_local")
    out = pd.DataFrame({"actual": g[col].mean() / 1000, "off": g["is_off_hours"].first(),
                        "focus_kwh": g[[c for c in config.FOCUS if c in B]].mean().sum(axis=1) / 1000})
    out = out.reindex(pd.date_range(out.index.min(), out.index.max(), freq="h"))
    out["off"] = out["off"].fillna(True).astype(bool)
    out["focus_cum"] = out["focus_kwh"].fillna(0).cumsum()  # precomputed: the replay only looks it up
    out["expected"] = method_series(source, circuit, method).reindex(out.index)
    bands, _ = load_bands()
    if bands is not None:
        b = bands[bands["circuit"] == circuit].groupby("timestamp_local")[["lower_kwh", "upper_kwh"]].mean()
        out = out.join(b)
    return out


def doc_link(name: str) -> str:
    """Link to a team document: on main when it is in this copy of the repository, else on the branch that has it."""
    path = config.DOC_LINKS[name]
    url = quote(path)                                   # spaces in file names
    if (config.REPO_ROOT / path).exists():
        return f"[{name}]({config.REPO_URL}{url})"
    branch = config.DOC_BRANCHES.get(name)
    if branch:
        return f"[{name}]({config.REPO_URL.replace('/blob/main/', f'/blob/{branch}/')}{url}) (branch `{branch}`, not merged yet)"
    return f"[{name}]({config.REPO_URL}{url})"


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
            ("Expected use", load_expected()[1]), ("90 % band", load_bands()[1]),
            ("Severity calibration", load_calibration()[1]), ("Model card", load_model_card()[1]),
            ("Final model settings", load_final_settings()[1]),
            ("Why the model expected a value", load_contributions()[1])]
    return pd.DataFrame([{"Used for": a, "File": b or "— not found"} for a, b in rows])


# ---------------------------------------------------------------------------
# Alert status, saved in dashboard/data/alert_status.csv
# ---------------------------------------------------------------------------
STATUSES = ["Open", "Handled", "Under investigation", "This was normal", "Data error"]


def load_actions() -> pd.DataFrame:
    """Measures logged in the Action planner (dashboard/data/actions.csv)."""
    if config.ACTIONS_FILE.exists():
        return pd.read_csv(config.ACTIONS_FILE)
    return pd.DataFrame(columns=["date", "circuit", "measure", "share", "cost_eur", "expected_kWh_per_year"])


def save_action(row: dict) -> None:
    config.LOCAL_DIR.mkdir(exist_ok=True)
    pd.concat([load_actions(), pd.DataFrame([row])], ignore_index=True).to_csv(config.ACTIONS_FILE, index=False)


def _status_log() -> pd.DataFrame:
    if config.ALERT_STATUS_FILE.exists():
        s = pd.read_csv(config.ALERT_STATUS_FILE)
        if "changed_at" not in s:            # file written by an older version: no dates
            s["changed_at"] = ""
        return s
    return pd.DataFrame(columns=["alert_id", "status", "changed_at"])


def load_status() -> dict:
    """Latest status of every alert that was changed at least once."""
    s = _status_log()
    return dict(zip(s["alert_id"], s["status"]))   # later rows overwrite earlier ones


def status_history(alert_id: str) -> pd.DataFrame:
    s = _status_log()
    return s[s["alert_id"] == alert_id][["changed_at", "status"]].iloc[::-1]


def save_status(alert_id: str, status: str) -> None:
    """Append one line per change, with its date (backlog F4.4: date and history of each change)."""
    config.LOCAL_DIR.mkdir(exist_ok=True)
    row = pd.DataFrame([{"alert_id": alert_id, "status": status,
                         "changed_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}])
    pd.concat([_status_log(), row], ignore_index=True).to_csv(config.ALERT_STATUS_FILE, index=False)


# ---------------------------------------------------------------------------
# Filters shared by every page (sidebar)
# ---------------------------------------------------------------------------
LOADS = ["Plugs & Sockets", "Lighting", "HVAC"]


def _shift_month(months: list, step: int) -> None:
    """Previous / next month buttons (a callback may change a widget's value before the next run)."""
    i = months.index(st.session_state["f_month"]) + step
    st.session_state["f_month"] = months[max(0, min(i, len(months) - 1))]


def sidebar_filters(df: pd.DataFrame) -> None:
    n = df.groupby("month").size()
    months = sorted(n[n >= 168].index)          # at least a week of data (drops the single hour of Mar 2023)
    default = pd.Period(config.DEFAULT_MONTH, "M")
    with st.sidebar:
        st.divider()
        st.caption("FILTERS")
        if "f_month" not in st.session_state or st.session_state["f_month"] not in months:
            st.session_state["f_month"] = default if default in months else months[-1]
        st.selectbox("Month", months, format_func=lambda p: p.strftime("%B %Y"), key="f_month")
        prev_col, next_col = st.columns(2)
        prev_col.button("◀ Previous", key="m_prev", on_click=_shift_month, args=(months, -1),
                        disabled=st.session_state["f_month"] == months[0])
        next_col.button("Next ▶", key="m_next", on_click=_shift_month, args=(months, 1),
                        disabled=st.session_state["f_month"] == months[-1])
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
