"""
Models for expected hourly consumption (one circuit at a time), simplest first:

  B1  same hour last week                         (seasonal naive)
  B2  median of the same hour in the last 4 weeks
  B3  profile: median per (working day?, hour) learned on the training data
  Ridge     linear regression with one-hot hour x day-type and weather, L2-regularised
  LightGBM  gradient-boosted trees, L1 loss (predicts the median -> robust to the anomalies we want to find)

Metrics in kWh per hour (W / 1000): MAE (main), RMSE, CV(RMSE) %, NMBE % (bias).
"""
import itertools

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEED = 42


# ------------------------------------------------------------------ metrics
def metrics(y, p) -> dict:
    y, p = np.asarray(y, float) / 1000, np.asarray(p, float) / 1000      # W -> kWh per hour
    e = y - p
    rmse = float(np.sqrt(np.mean(e ** 2)))
    return {"MAE_kWh": float(np.mean(np.abs(e))), "RMSE_kWh": rmse,
            "CV_RMSE_%": 100 * rmse / float(np.mean(y)), "NMBE_%": 100 * float(np.mean(e)) / float(np.mean(y)),
            "n_hours": int(len(y))}


# ------------------------------------------------------------------ baselines
def baseline_last_week(X: pd.DataFrame) -> pd.Series:
    return X["lag_168"]


def baseline_median_4w(df: pd.DataFrame, target: str) -> pd.Series:
    out = []
    for _, g in df.groupby("Regime"):
        s = g[target]
        out.append(pd.concat([s.shift(168 * k) for k in range(1, 5)], axis=1).median(axis=1))
    return pd.concat(out).reindex(df.index)


class ProfileBaseline:
    """B3: median of each (working day yes/no, hour) on the training data."""

    def fit(self, X, y):
        self.table_ = y.groupby([X["is_working_day"], X["hour"]]).median()
        return self

    def predict(self, X):
        idx = pd.MultiIndex.from_arrays([X["is_working_day"], X["hour"]])
        return pd.Series(self.table_.reindex(idx).values, index=X.index)


# ------------------------------------------------------------------ ridge
def make_ridge(numeric: list, alpha: float = 1.0) -> Pipeline:
    """Scaler / encoder are inside the pipeline, so they are fitted on training data only."""
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), ["hour_x_daytype", "weekday"]),
        ("num", StandardScaler(), numeric),
    ])
    return Pipeline([("pre", pre), ("ridge", Ridge(alpha=alpha))])


def ridge_frame(X: pd.DataFrame) -> pd.DataFrame:
    """Linear models cannot learn interactions: build 'hour x working day' and 'heating x working day' by hand."""
    R = X.copy()
    R["hour_x_daytype"] = R["hour"].astype(str) + "_" + R["is_working_day"].astype(str)
    R["heating_x_work"] = R["heating_deg"] * R["is_working_day"]
    R["heating_x_night"] = R["heating_deg"] * ((R["hour"] < 7) | (R["hour"] >= 22)).astype(int)
    return R


def ridge_numeric(R: pd.DataFrame) -> list:
    return [c for c in R.columns if c not in ("hour", "weekday", "hour_x_daytype")]


# ------------------------------------------------------------------ lightgbm
LGB_GRID = {                      # 8 combinations, chosen on the validation period
    "num_leaves": [15, 63],
    "learning_rate": [0.03, 0.1],
    "n_estimators": [600],
    "min_child_samples": [20, 80],
}


def make_lgb(**params) -> lgb.LGBMRegressor:
    base = dict(objective="regression_l1", subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                random_state=SEED, verbose=-1, n_jobs=-1)
    base.update(params)
    return lgb.LGBMRegressor(**base)


def grid(space: dict) -> list:
    keys = list(space)
    return [dict(zip(keys, v)) for v in itertools.product(*space.values())]


def tune_lgb(X_tr, y_tr, X_va, y_va, space=LGB_GRID) -> tuple:
    """Pick hyper-parameters on the validation period (lecture: train -> validate -> test)."""
    log = []
    for params in grid(space):
        m = make_lgb(**params).fit(X_tr, y_tr)
        log.append({**params, **metrics(y_va, m.predict(X_va))})
    log = pd.DataFrame(log).sort_values("MAE_kWh")
    best = {k: log.iloc[0][k] for k in space}
    best = {k: (int(v) if float(v).is_integer() else float(v)) for k, v in best.items()}
    return best, log


def tune_ridge(R_tr, y_tr, R_va, y_va, alphas=(0.1, 1, 10, 100, 1000)) -> tuple:
    num = ridge_numeric(R_tr)
    log = []
    for a in alphas:
        m = make_ridge(num, a).fit(R_tr, y_tr)
        log.append({"alpha": a, **metrics(y_va, m.predict(R_va))})
    log = pd.DataFrame(log).sort_values("MAE_kWh")
    return float(log.iloc[0]["alpha"]), log


# ------------------------------------------------------------------ full evaluation of one circuit
def evaluate_circuit(df: pd.DataFrame, target: str, kinds=("forecast", "normal"), space=LGB_GRID) -> dict:
    """
    1. choose settings on validation (models fitted on train)
    2. refit on train + validation, evaluate the test period ONCE
    3. refit on all of Regime A, evaluate Regime B (2025) as an out-of-time check
    All models are scored on the same hours (where every feature exists), so the comparison is fair.
    """
    from src.features import make_features, split_of

    y = df[target]
    s = split_of(df["timestamp_local"])
    feats = {k: make_features(df, target, k) for k in kinds}
    Xf = feats.get("forecast", make_features(df, target, "forecast"))
    ok = y.notna() & Xf.notna().all(axis=1)
    for X in feats.values():
        ok &= X.notna().all(axis=1)
    m = {n: ok & (s == n) for n in ["train", "val", "test", "regime_b"]}
    fit_sets = {"val": m["train"], "test": m["train"] | m["val"],
                "regime_b": m["train"] | m["val"] | m["test"]}

    rows, preds, info = [], {}, {"target": target}
    b2 = baseline_median_4w(df, target)
    for ev, fit in fit_sets.items():
        P = pd.DataFrame({"actual": y[m[ev]]})
        P["B1_last_week"] = Xf.loc[m[ev], "lag_168"]
        P["B2_median_4w"] = b2[m[ev]]
        P["B3_profile"] = ProfileBaseline().fit(Xf[fit], y[fit]).predict(Xf[m[ev]])
        for k, X in feats.items():
            R = ridge_frame(X)
            if ev == "val":
                info[f"ridge_alpha_{k}"], _ = tune_ridge(R[m["train"]], y[m["train"]], R[m["val"]], y[m["val"]])
                info[f"lgb_params_{k}"], info[f"lgb_log_{k}"] = tune_lgb(
                    X[m["train"]], y[m["train"]], X[m["val"]], y[m["val"]], space)
            ridge = make_ridge(ridge_numeric(R), info[f"ridge_alpha_{k}"]).fit(R[fit], y[fit])
            P[f"Ridge_{k}"] = ridge.predict(R[m[ev]])
            gbm = make_lgb(**info[f"lgb_params_{k}"]).fit(X[fit], y[fit])
            P[f"LightGBM_{k}"] = gbm.predict(X[m[ev]])
            if ev == "test":
                info[f"importance_{k}"] = pd.Series(gbm.booster_.feature_importance("gain"), index=X.columns)
                info[f"model_{k}"] = gbm
        for col in P.columns.drop("actual"):
            rows.append({"circuit": target, "period": ev, "model": col, **metrics(P["actual"], P[col])})
        P.insert(0, "timestamp_local", df.loc[P.index, "timestamp_local"])
        preds[ev] = P
    info["results"] = pd.DataFrame(rows)
    info["predictions"] = preds
    return info
