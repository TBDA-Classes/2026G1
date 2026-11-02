"""
Features and time split for the expected-consumption models.

Two feature sets (see notebook 01, section 8):
  * "forecast" : calendar + weather + lags of the target (>= 24 h old). Best accuracy for a day-ahead forecast.
  * "normal"   : calendar + weather + a slow 'level' (typical working-day use of the last 28 days, >= 24 h old).
                 No recent lags, so a heater left on for weeks is NOT learned as normal. Used for anomaly detection.

No leakage rules:
  * every lag / rolling value of the target is shifted by >= 24 h;
  * lags are computed inside each Regime (the 2.5-year gap is never bridged);
  * only outdoor weather and the calendar are used, never W/I/Pa/Ea or indoor sensors of the same hour.
"""
import numpy as np
import pandas as pd

# Time split (local time). Test is used ONCE, at the end (notebook 02).
SPLITS = {
    "train": ("2020-06-22", "2022-08-31 23:59"),
    "val": ("2022-09-01", "2022-12-31 23:59"),
    "test": ("2023-01-01", "2023-02-28 23:59"),
    "regime_b": ("2025-08-18", "2025-10-13 23:59"),   # out-of-time check, never used for fitting
}

CALENDAR = ["hour", "weekday", "is_working_day", "is_holiday", "is_break", "is_august_closure",
            "doy_sin", "doy_cos"]
WEATHER = ["wx_temp_c", "heating_deg", "cooling_deg", "wx_solar_wm2", "wx_humidity_pct"]
LAGS = [24, 48, 168, 336]
MIN_LAG = 24


def split_of(ts_local: pd.Series) -> pd.Series:
    out = pd.Series("none", index=ts_local.index)
    for name, (a, b) in SPLITS.items():
        out[(ts_local >= a) & (ts_local <= b)] = name
    return out


def _per_regime(df: pd.DataFrame, y: pd.Series, fn) -> pd.Series:
    """Apply a lag/rolling function separately inside each regime (regimes are full hourly grids)."""
    return pd.concat([fn(y[g.index]) for _, g in df.groupby("Regime")]).reindex(y.index)


def make_features(df: pd.DataFrame, target: str, kind: str = "normal") -> pd.DataFrame:
    """Feature table for one circuit. `df` must be sorted by time and contain whole regimes."""
    y = df[target]
    X = pd.DataFrame(index=df.index)
    X["hour"] = df["hour_local"]
    X["weekday"] = df["weekday_local"]
    for c in ["is_working_day", "is_holiday", "is_break", "is_august_closure"]:
        X[c] = df[c].astype(int)
    doy = df["timestamp_local"].dt.day_of_year
    X["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    X["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    X["wx_temp_c"] = df["wx_temp_c"]
    X["heating_deg"] = (15 - df["wx_temp_c"]).clip(lower=0)      # EDA: heaters switch on below ~15 C
    X["cooling_deg"] = (df["wx_temp_c"] - 24).clip(lower=0)
    X["wx_solar_wm2"] = df["wx_solar_wm2"]
    X["wx_humidity_pct"] = df["wx_humidity_pct"]

    if kind == "forecast":
        for lag in LAGS:
            X[f"lag_{lag}"] = _per_regime(df, y, lambda s, l=lag: s.shift(l))
        X["same_hour_mean_7d"] = _per_regime(
            df, y, lambda s: pd.concat([s.shift(24 * k) for k in range(1, 8)], axis=1).mean(axis=1))
    elif kind == "normal":
        # typical use during working hours of working days, last 28 days, at least 24 h old
        work = df["is_working_day"] & df["hour_local"].between(9, 17)
        y_work = y.where(work)
        X["level_work_28d"] = _per_regime(
            df, y_work, lambda s: s.shift(MIN_LAG).rolling(24 * 28, min_periods=24).median())
    else:
        raise ValueError(kind)
    return X


def feature_lags(X: pd.DataFrame) -> list:
    """Names of features that use past target values (for the leakage test)."""
    return [c for c in X.columns if c.startswith("lag_") or c in ("same_hour_mean_7d", "level_work_28d")]
