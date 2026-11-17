"""
Prediction interval for the expected hourly use (KAN-144).

Instead of one number ("2.5 kWh expected") the model gives a band ("between 1.9 and 3.2 kWh"),
which should contain the real value about 90 % of the time. Hours above the band are possible waste.

Three versions are compared (notebook 04), all on the "forecast" feature set and settings of notebook 02:

  1. quantile            LightGBM for the 5 % quantile (lower edge) and the 95 % quantile (upper edge),
                         fitted on the training period only.
  2. conformal (fixed)   CQR (Romano et al. 2019): quantile models are often too confident, so the band is
                         widened by ONE number per circuit, chosen on the validation period so that 90 % of the
                         validation hours are inside.
  3. conformal (rolling) same idea, but the widening is recomputed every hour from the last ROLLING_DAYS days
                         of misses that are at least 24 h old. It follows changes in use (season, new devices),
                         and it is what a live system can do: every day it knows yesterday's real values.
                         ROLLING_DAYS was chosen on the validation period (notebook 04), not on test.

Protocol (dates in src/features.SPLITS): fit on train -> choose / calibrate on val -> measure once on test
(Jan-Feb 2023) -> out-of-time check on Regime B (2025) with the same models.
No leakage: features are those of notebook 02 (>= 24 h old); the rolling widening only uses hours >= 24 h old;
train hours are never used for calibration (the model has seen them, so its misses there are too small).

Metrics (kWh per hour):
  coverage_%        share of hours inside the band (target 90 %)
  above_% / below_% share of hours above / below the band (above = possible waste)
  width_kWh         mean band width (narrower = more useful, at the same coverage)
  winkler_kWh       interval score = width + penalty for every miss (lower is better; Gneiting & Raftery 2007)
"""
import numpy as np
import pandas as pd

from src.features import make_features, split_of
from src.models import make_lgb

ALPHA = 0.10                 # 1 - target coverage -> a 90 % band
ROLLING_DAYS = 28            # window of the rolling calibration (chosen on validation, notebook 04)
MIN_DAYS = 7                 # the rolling band starts after 7 days of known misses (warm-up)
METHODS = ["quantile", "conformal (fixed)", "conformal (rolling)"]


def make_quantile_lgb(q: float, params: dict):
    """Same trees as the point model of notebook 02, trained for quantile q instead of the median."""
    return make_lgb(**params, objective="quantile", alpha=q)


def scores(y, lo, hi):
    """How far the real value is outside the band (negative when inside). Works on arrays or Series."""
    return np.maximum(lo - y, y - hi)


def conformal_margin(y_cal, lo_cal, hi_cal, alpha: float = ALPHA) -> float:
    """Fixed CQR margin: the (1 - alpha) quantile of the calibration scores, with the finite-sample correction."""
    s = np.asarray(scores(np.asarray(y_cal, float), np.asarray(lo_cal, float), np.asarray(hi_cal, float)))
    n = len(s)
    level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(s, level, method="higher"))


def rolling_margin(score: pd.Series, days: int = ROLLING_DAYS, alpha: float = ALPHA,
                   min_days: int = MIN_DAYS) -> pd.Series:
    """Margin for every hour from the scores of the previous `days` days, at least 24 h old.
    `score` must be on a full hourly grid of ONE regime (NaN where there is no prediction or no actual)."""
    return score.shift(24).rolling(24 * days, min_periods=24 * min_days).quantile(1 - alpha)


def interval_metrics(y, lo, hi, alpha: float = ALPHA) -> dict:
    y, lo, hi = (np.asarray(a, float) / 1000 for a in (y, lo, hi))      # W -> kWh per hour
    above, below = y > hi, y < lo
    width = hi - lo
    winkler = width + (2 / alpha) * ((lo - y) * below + (y - hi) * above)
    return {"coverage_%": 100 * float(np.mean(~above & ~below)),
            "above_%": 100 * float(np.mean(above)), "below_%": 100 * float(np.mean(below)),
            "width_kWh": float(np.mean(width)), "winkler_kWh": float(np.mean(winkler)),
            "n_hours": int(len(y))}


def interval_for_circuit(df: pd.DataFrame, target: str, params: dict, alpha: float = ALPHA,
                         windows=(ROLLING_DAYS,)) -> dict:
    """Fit, calibrate and evaluate the band for one circuit.

    `params` = forecast LightGBM settings from reports/model_params.json (chosen on validation in notebook 02).
    `windows` = rolling windows (days) to evaluate; the first one is used for the saved bands.
    Returns results (one row per period x method x window), bands (DataFrames per period) and the fixed margin.
    All methods are scored on the same hours (those where the rolling margin exists), so the comparison is fair.
    """
    y = df[target]
    X = make_features(df, target, "forecast")
    s = split_of(df["timestamp_local"])
    ok = y.notna() & X.notna().all(axis=1)
    m = {n: ok & (s == n) for n in ["train", "val", "test", "regime_b"]}

    lo_model = make_quantile_lgb(alpha / 2, params).fit(X[m["train"]], y[m["train"]])
    hi_model = make_quantile_lgb(1 - alpha / 2, params).fit(X[m["train"]], y[m["train"]])

    # raw band on every hour that can be predicted after training (val, test, regime B)
    pred = m["val"] | m["test"] | m["regime_b"]
    lo = pd.Series(np.nan, index=df.index)
    hi = lo.copy()
    a, b = lo_model.predict(X[pred]), hi_model.predict(X[pred])
    lo[pred], hi[pred] = np.minimum(a, b), np.maximum(a, b)        # quantile models can cross: keep lo <= hi
    sc = scores(y, lo, hi)                                          # NaN outside `pred`

    fixed = conformal_margin(y[m["val"]], lo[m["val"]], hi[m["val"]], alpha)

    # rolling margins, computed inside each regime (the 2.5-year gap is never bridged)
    roll = {}
    for w in windows:
        roll[w] = pd.concat([rolling_margin(sc[g.index], w, alpha) for _, g in df.groupby("Regime")]).reindex(df.index)

    rows, bands = [], {}
    for period in ["val", "test", "regime_b"]:
        for w in windows:
            mm = m[period] & roll[w].notna()
            versions = {
                "quantile": (lo[mm], hi[mm]),
                "conformal (fixed)": ((lo[mm] - fixed).clip(lower=0), hi[mm] + fixed),
                "conformal (rolling)": ((lo[mm] - roll[w][mm]).clip(lower=0), hi[mm] + roll[w][mm]),
            }
            for method, (l, u) in versions.items():
                rows.append({"circuit": target, "period": period, "method": method, "window_days": w,
                             **interval_metrics(y[mm], l, u, alpha)})
        w0 = windows[0]
        mm = m[period] & roll[w0].notna()
        bands[period] = pd.DataFrame({
            "timestamp_local": df.loc[mm, "timestamp_local"], "actual": y[mm],
            "lower": (lo[mm] - roll[w0][mm]).clip(lower=0), "upper": hi[mm] + roll[w0][mm]})
    return {"results": pd.DataFrame(rows), "bands": bands, "fixed_margin_W": fixed}
