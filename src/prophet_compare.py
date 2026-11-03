"""
Prophet compared with LightGBM on the same hours and the same split (KAN-146).

Prophet (Meta, Taylor & Letham 2018) is a classic forecasting model for business time series:
  y(t) = trend + daily / weekly / yearly seasonality + holidays + extra regressors + noise.
It does not use past values of the target (no lags), so it is the fair counterpart of the "normal" LightGBM
of notebook 02, and a strong "classic" reference for the "forecast" LightGBM.

Set-up (same protocol as src/models.evaluate_circuit):
  * same hours: those where both LightGBM feature sets and the B2 baseline exist (identical hours for every model);
  * fit on train -> score val; refit on train+val -> score test (used once); refit on train+val+test -> score 2025;
  * Prophet settings chosen on validation only (small grid on the trend flexibility);
  * regressors = the calendar and outdoor weather of notebook 02 (never the target or indoor sensors);
  * daily seasonality is learned separately for working and non-working days (offices: two different day shapes).
"""
import logging

import numpy as np
import pandas as pd

from src.features import make_features, split_of
from src.models import baseline_median_4w, make_lgb, metrics

logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
logging.getLogger("prophet").setLevel(logging.WARNING)

REGRESSORS = ["is_holiday", "is_break", "is_august_closure", "heating_deg", "cooling_deg", "wx_solar_wm2"]
# trend: stiff / flexible linear, or flat (no trend: avoids extrapolating a slope over the 2023-25 gap)
PROPHET_GRID = [{"growth": "linear", "changepoint_prior_scale": 0.01},
                {"growth": "linear", "changepoint_prior_scale": 0.1},
                {"growth": "flat", "changepoint_prior_scale": 0.05}]


def prophet_frame(df: pd.DataFrame, X: pd.DataFrame, y: pd.Series = None) -> pd.DataFrame:
    """Prophet wants columns ds (time), y (target) and one column per regressor."""
    P = pd.DataFrame({"ds": df["timestamp_local"].values}, index=X.index)
    if y is not None:
        P["y"] = y.values
    for c in REGRESSORS:
        P[c] = X[c].astype(float).values
    work = X["is_working_day"].astype(bool).values
    P["working"], P["not_working"] = work, ~work
    return P


def make_prophet(growth: str = "linear", changepoint_prior_scale: float = 0.05):
    from prophet import Prophet
    m = Prophet(growth=growth, daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=True,
                changepoint_prior_scale=changepoint_prior_scale, uncertainty_samples=0)
    m.add_seasonality("daily_working", period=1, fourier_order=8, condition_name="working")
    m.add_seasonality("daily_not_working", period=1, fourier_order=8, condition_name="not_working")
    for c in REGRESSORS:
        m.add_regressor(c)
    return m


def fit_predict_prophet(df, X, y, fit_mask, pred_mask, params) -> np.ndarray:
    m = make_prophet(**params).fit(prophet_frame(df[fit_mask], X[fit_mask], y[fit_mask]))
    return m.predict(prophet_frame(df[pred_mask], X[pred_mask]))["yhat"].clip(lower=0).values


def compare_circuit(df: pd.DataFrame, target: str, lgb_params: dict) -> dict:
    """Scores B2, LightGBM (forecast and normal, settings from reports/model_params.json) and Prophet
    on identical hours. Returns results (one row per period x model), predictions and the chosen Prophet setting."""
    y = df[target]
    s = split_of(df["timestamp_local"])
    Xf, Xn = make_features(df, target, "forecast"), make_features(df, target, "normal")
    b2 = baseline_median_4w(df, target)
    ok = y.notna() & Xf.notna().all(axis=1) & Xn.notna().all(axis=1) & b2.notna()
    m = {n: ok & (s == n) for n in ["train", "val", "test", "regime_b"]}
    fit_sets = {"val": m["train"], "test": m["train"] | m["val"], "regime_b": m["train"] | m["val"] | m["test"]}

    # Prophet setting chosen on validation only
    tune = []
    for p in PROPHET_GRID:
        pred = fit_predict_prophet(df, Xf, y, m["train"], m["val"], p)
        tune.append({**p, **metrics(y[m["val"]], pred)})
    tune = pd.DataFrame(tune).sort_values("MAE_kWh")
    best = {"growth": str(tune.iloc[0]["growth"]),
            "changepoint_prior_scale": float(tune.iloc[0]["changepoint_prior_scale"])}

    rows, preds = [], {}
    for ev, fit in fit_sets.items():
        P = pd.DataFrame({"timestamp_local": df.loc[m[ev], "timestamp_local"], "actual": y[m[ev]]})
        P["B2_median_4w"] = b2[m[ev]]
        P["LightGBM_forecast"] = make_lgb(**lgb_params["forecast"]).fit(Xf[fit], y[fit]).predict(Xf[m[ev]])
        P["LightGBM_normal"] = make_lgb(**lgb_params["normal"]).fit(Xn[fit], y[fit]).predict(Xn[m[ev]])
        P["Prophet"] = fit_predict_prophet(df, Xf, y, fit, m[ev], best)
        for col in ["B2_median_4w", "LightGBM_forecast", "LightGBM_normal", "Prophet"]:
            rows.append({"circuit": target, "period": ev, "model": col, **metrics(P["actual"], P[col])})
        preds[ev] = P
    return {"results": pd.DataFrame(rows), "predictions": preds, "prophet_params": best, "prophet_tuning": tune}
