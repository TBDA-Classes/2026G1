"""
Anomaly and waste detection on top of the expected-consumption model (notebook 03).

Two signals:
  1. EVENT (model-based): actual use is far above what LightGBM_forecast expected for that hour
     -> "something unusual happened today" (heater left on, lights not switched off, ...)
  2. CHRONIC off-hours waste (rule-based): use above the standby level during nights, weekends, holidays, breaks
     -> catches waste that repeats every week and that a lag-based model would learn as normal

Both are valued in EUR (OMIE hourly = lower bound, all-in price) and kg CO2 with params.yaml.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.data import ROOT, short
from src.features import make_features
from src.models import make_lgb

MAD_SCALE = 1.4826          # MAD * 1.4826 = standard deviation for normal data


def load_params(path: Path = ROOT / "params.yaml") -> dict:
    return yaml.safe_load(open(path, encoding="utf-8"))


# ------------------------------------------------------------------ expected values for the whole history
def crossfit_expected(df: pd.DataFrame, target: str, lgb_params: dict, fold: str = "QS") -> pd.Series:
    """
    Out-of-fold expected values for every hour (retrospective audit).
    Regime A is cut into calendar quarters; each quarter is predicted by a model trained on all OTHER quarters,
    so no hour is predicted by a model that has seen it. Regime B is predicted by a model trained on all of Regime A.
    (For the honest forecast score see notebook 02, which uses a strict past -> future split.)
    """
    X = make_features(df, target, "forecast")
    y = df[target]
    ok = y.notna()
    out = pd.Series(np.nan, index=df.index)
    a = (df["Regime"] == "A")
    q = df["timestamp_local"].dt.to_period(fold[0])
    for period in q[a].unique():
        test = a & (q == period)
        train = a & ~test & ok
        m = make_lgb(**lgb_params).fit(X[train], y[train])
        out[test] = m.predict(X[test])
    b = df["Regime"] == "B"
    m = make_lgb(**lgb_params).fit(X[a & ok], y[a & ok])
    out[b] = m.predict(X[b])
    return out


# ------------------------------------------------------------------ thresholds and flags
def hour_type(df: pd.DataFrame) -> pd.Series:
    return pd.Series(np.where(df["is_off_hours"], "off-hours", "working hours"), index=df.index)


def threshold_stats(resid: pd.Series, htype: pd.Series) -> pd.DataFrame:
    """Robust centre and spread of the residuals per hour type (working hours / off-hours)."""
    r = resid.dropna()
    return r.groupby(htype.loc[r.index]).agg(med="median", mad=lambda x: MAD_SCALE * (x - x.median()).abs().median())


def robust_thresholds(htype: pd.Series, stats: pd.DataFrame, k: float) -> pd.Series:
    """Threshold for every hour: median + k * scaled MAD of its hour type."""
    thr = stats["med"] + k * stats["mad"].clip(lower=1.0)     # at least 1 W, for circuits that are almost always 0
    return htype.map(thr)


def to_events(flag: pd.Series, ts: pd.Series, merge_gap: int = 1, min_hours: int = 2) -> pd.DataFrame:
    """Group flagged hours into events (consecutive hours, small gaps merged). Index of `flag` = row ids."""
    idx = flag.index[flag.fillna(False)]
    if len(idx) == 0:
        return pd.DataFrame(columns=["event_id", "row"])
    t = ts.loc[idx]
    new = t.diff() > pd.Timedelta(hours=merge_gap + 1)
    ev = new.cumsum()
    out = pd.DataFrame({"event_id": ev.values, "row": idx})
    size = out.groupby("event_id")["row"].transform("size")
    return out[size >= min_hours]


def events_fast(H: pd.DataFrame, ts: pd.Series, P: dict) -> pd.DataFrame:
    """Flagged hours -> events, keeping only events with at least `min_event_kwh` above expected."""
    A = P["anomaly"]
    ev = to_events(H["flag_model"].fillna(False), ts, A["merge_gap_hours"], A["min_event_hours"])
    if ev.empty:
        return ev
    ev = ev.assign(excess_kWh=(H.loc[ev["row"].values, "resid"].clip(lower=0) / 1000).values)
    return ev[ev.groupby("event_id")["excess_kWh"].transform("sum") >= A["min_event_kwh"]]


def severity(kwh: float, cuts) -> str:
    return "low" if kwh < cuts[0] else ("medium" if kwh <= cuts[1] else "high")


# ------------------------------------------------------------------ valuation
def co2_factor(df: pd.DataFrame, P: dict) -> pd.Series:
    """g CO2 per kWh for every hour, from params.yaml (by year)."""
    table = P["co2"]["g_per_kwh"]
    return df["timestamp_local"].dt.year.map(lambda y: table.get(int(y), table[max(table)]))


def value(kwh: pd.Series, df: pd.DataFrame, P: dict) -> pd.DataFrame:
    """EUR (OMIE lower bound, all-in) and kg CO2 for an energy series in kWh."""
    return pd.DataFrame({
        "eur_omie": kwh * df.loc[kwh.index, "price_eur_mwh"] / 1000,
        "eur_all_in": kwh * P["price"]["all_in_eur_per_kwh"],
        "kg_co2": kwh * co2_factor(df.loc[kwh.index], P) / 1000,
    })


# ------------------------------------------------------------------ explanation text for the client / dashboard
ZONE_ENV = {"NW": "NW|ENV Temp °C", "SE": "SE|ENV Temp °C", "SW": "SW|ENV Temp °C"}


def hint(circuit: str, rows: pd.DataFrame, df: pd.DataFrame) -> str:
    zone, kind = circuit.split("|")[0], circuit.split("|")[1]
    cold = rows["wx_temp_c"].mean() < 12
    off = rows["is_off_hours"].mean() > 0.5
    when = "while the building is closed" if off else "during working hours"
    if "Plugs" in kind:
        txt = f"Plug load higher than expected {when}" + (" on a cold day: possibly electric heaters left on." if cold else ": devices left on?")
    elif "Lighting" in kind:
        txt = f"Lights on more than expected {when}: lights not switched off or a timer setting?"
    else:
        txt = f"HVAC running more than expected {when}: schedule / setpoint?"
    env = ZONE_ENV.get(zone)
    if env and ("Plugs" in kind or "HVAC" in kind) and cold:
        # indoor temperature compared with the usual value for that month and hour
        typical = df.groupby([df["timestamp_local"].dt.month, "hour_local"])[env].median()
        exp_t = typical.reindex(pd.MultiIndex.from_arrays([rows["timestamp_local"].dt.month, rows["hour_local"]])).values
        diff = exp_t - rows[env].values
        drop = np.nanmean(diff) if np.isfinite(diff).any() else np.nan
        if np.isfinite(drop) and drop > 1.5:
            txt += f" Indoor temperature was {drop:.1f} °C below normal at the same time: heat may be escaping (window or door open?)."
    return txt


# ------------------------------------------------------------------ main entry points
def detect(df: pd.DataFrame, target: str, expected: pd.Series, P: dict, k: float = None, describe: bool = True,
           stats: pd.DataFrame = None) -> tuple:
    """
    Hour table with residual, threshold and flags + event table for one circuit.
    stats: residual median / MAD per hour type; if None they are computed from these residuals.
    describe=False: flags only (fast).
    """
    k = P["anomaly"]["k_mad"] if k is None else k
    H = pd.DataFrame({"actual": df[target], "expected": expected})
    H["resid"] = H["actual"] - H["expected"]
    H["hour_type"] = hour_type(df)
    stats = threshold_stats(H["resid"], H["hour_type"]) if stats is None else stats
    H["threshold"] = robust_thresholds(H["hour_type"], stats, k)
    H["flag_model"] = H["resid"] > H["threshold"]
    if not describe:
        return H, None

    ev = events_fast(H, df["timestamp_local"], P)
    rows = []
    for eid, g in ev.groupby("event_id"):
        r = df.loc[g["row"]]
        excess = (H.loc[g["row"], "resid"].clip(lower=0) / 1000)                    # kWh above expected
        v = value(excess, df, P).sum()
        rows.append({
            "circuit": short(target), "zone": target.split("|")[0], "device": target.split("|")[1].removesuffix(" W"),
            "start": r["timestamp_local"].min(), "end": r["timestamp_local"].max() + pd.Timedelta(hours=1),
            "hours": len(g), "share_off_hours": r["is_off_hours"].mean(), "day_type": r["day_type"].mode().iat[0],
            "actual_kWh": H.loc[g["row"], "actual"].sum() / 1000, "expected_kWh": H.loc[g["row"], "expected"].sum() / 1000,
            "excess_kWh": excess.sum(), "eur_omie": v["eur_omie"], "eur_all_in": v["eur_all_in"], "kg_co2": v["kg_co2"],
            "severity": severity(excess.sum(), P["anomaly"]["severity_kwh"]),
            "message": hint(target, r, df),
        })
    return H, pd.DataFrame(rows)


def offhours_waste(df: pd.DataFrame, target: str, P: dict, train_mask: pd.Series) -> pd.DataFrame:
    """Chronic signal: kWh above the standby level during off-hours, per hour."""
    pct = P["off_hours"]["standby_percentile"] / 100
    standby = df.loc[train_mask & df["is_night"], target].quantile(pct)
    excess = ((df[target] - standby).clip(lower=0) / 1000).where(df["is_off_hours"], 0.0)
    out = value(excess.fillna(0), df, P)
    out.insert(0, "excess_kWh", excess.fillna(0))
    out["standby_W"] = standby
    return out


def inject(df: pd.DataFrame, target: str, mask: pd.Series, P: dict) -> tuple:
    """Add synthetic 'forgotten load' blocks during off-hours inside `mask`. Returns (new df, injected-hours flag)."""
    S = P["synthetic_test"]
    rng = np.random.default_rng(S["seed"])
    extra = next(v for k, v in S["extra_w"].items() if k in target)
    cand = df.index[mask & df["is_off_hours"] & df[target].notna()]
    d2, inj = df.copy(), pd.Series(False, index=df.index)
    blocks = 0
    for _ in range(5000):
        if blocks == S["n_blocks"]:
            break
        start = int(rng.choice(cand))
        length = int(rng.integers(S["block_hours"][0], S["block_hours"][1] + 1))
        block = pd.RangeIndex(start, min(start + length, df.index[-1] + 1))
        if inj.loc[max(block[0] - 24, 0): block[-1] + 24].any() or not df.loc[block, "is_off_hours"].all():
            continue                                         # keep blocks separate and fully off-hours
        d2.loc[block, target] = d2.loc[block, target] + extra
        inj.loc[block] = True
        blocks += 1
    return d2, inj
