"""
TBDA Group 1 - first test model (stories 5.1, 5.2, 5.3, 5.5, 5.6 as a spike)

Question : how much should each zone use in each hour of tomorrow?  (day-ahead forecast)
Target   : hourly mean power W of each zone total (= Wh used in that hour)
Data     : clean_hourly_wide.parquet, Regime A only (Apr 2020 - Feb 2023)
Split    : by time, never random
           train      2020-04-03 .. 2022-08-31
           validation 2022-09-01 .. 2022-12-31   (choose settings here)
           test       2023-01-01 .. 2023-02-28   (used once, at the end)
Models   : B1  same hour last week
           B2  median of same weekday+hour over the last 4 weeks
           LGB LightGBM with calendar + lag features (all lags >= 24 h, so no leakage)
           Q   LightGBM quantile 5% / 95% -> normal band; above the band = possible waste
Metrics  : MAE, RMSE, CV(RMSE) = RMSE / mean (ASHRAE Guideline 14 target: < 30 % hourly)

Run:  python src/model_test.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
import holidays
import lightgbm as lgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

TRAIN_END, VAL_END, TEST_END = "2022-08-31", "2022-12-31", "2023-02-28"
TARGETS = ["NE|ZONE TOTAL W", "NW|ZONE TOTAL W", "SE|ZONE TOTAL W", "SW|ZONE TOTAL W", "STOREY1|TOTAL W"]

df = pd.read_parquet(ROOT / "data" / "clean_hourly_wide.parquet")
df = df[df["Regime"] == "A"].sort_values("timestamp_utc").reset_index(drop=True)

# calendar features (local time)
es = holidays.Spain(subdiv="MD", years=range(2020, 2024))
d = df["timestamp_local"].dt.date
df["holiday"] = d.map(lambda x: x in es).astype(int)
md = df["timestamp_local"].dt.strftime("%m-%d")
df["xmas_break"] = ((md >= "12-23") | (md <= "01-07")).astype(int)   # UPM closure (approx.)
df["august"] = (df["month"] == 8).astype(int)
df["dayofyear"] = df["timestamp_local"].dt.dayofyear
df["off_day"] = ((df["is_weekend"]) | (df["holiday"] == 1) | (df["xmas_break"] == 1)).astype(int)

date = df["timestamp_local"]
split = np.where(date <= TRAIN_END, "train", np.where(date <= VAL_END, "val",
                 np.where(date <= TEST_END + " 23:59", "test", "none")))
df["split"] = split


def make_features(y: pd.Series) -> pd.DataFrame:
    """Only information available 24 h before the hour we predict."""
    f = pd.DataFrame(index=y.index)
    for lag in [24, 48, 168, 336]:
        f[f"lag_{lag}"] = y.shift(lag)
    f["same_hour_mean_7d"] = pd.concat([y.shift(24 * k) for k in range(1, 8)], axis=1).mean(axis=1)
    f["mean_24h_before"] = y.shift(24).rolling(24, min_periods=12).mean()
    f["max_24h_before"] = y.shift(24).rolling(24, min_periods=12).max()
    for col in ["hour_local", "weekday_local", "month", "dayofyear", "holiday", "xmas_break", "august", "off_day"]:
        f[col] = df[col].astype(int)
    return f


def baselines(y: pd.Series) -> pd.DataFrame:
    b = pd.DataFrame(index=y.index)
    b["B1_last_week"] = y.shift(168)
    b["B2_median_4w"] = pd.concat([y.shift(168 * k) for k in range(1, 5)], axis=1).median(axis=1)
    return b


def metrics(y, p):
    e = y - p
    rmse = float(np.sqrt(np.mean(e ** 2)))
    return {"MAE": float(np.mean(np.abs(e))), "RMSE": rmse, "CV(RMSE) %": 100 * rmse / float(np.mean(y))}


PARAMS = dict(n_estimators=600, learning_rate=0.03, num_leaves=31, min_child_samples=40,
              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1)

rows, preds_all = [], {}
for t in TARGETS:
    y = df[t]
    X = make_features(y)
    B = baselines(y)
    ok = y.notna() & X[["lag_168", "lag_336"]].notna().all(axis=1) & B.notna().all(axis=1)
    tr, va, te = ok & (df.split == "train"), ok & (df.split == "val"), ok & (df.split == "test")

    # 1) fit on train, check on validation
    m = lgb.LGBMRegressor(objective="regression_l1", **PARAMS).fit(X[tr], y[tr])
    for name, mask in [("val", va)]:
        for b in B.columns:
            rows.append({"target": t, "set": name, "model": b, **metrics(y[mask], B.loc[mask, b])})
        rows.append({"target": t, "set": name, "model": "LightGBM", **metrics(y[mask], m.predict(X[mask]))})

    # 2) final: refit on train + validation, evaluate test ONCE
    trva = tr | va
    m = lgb.LGBMRegressor(objective="regression_l1", **PARAMS).fit(X[trva], y[trva])
    p_te = m.predict(X[te])
    for b in B.columns:
        rows.append({"target": t, "set": "test", "model": b, **metrics(y[te], B.loc[te, b])})
    rows.append({"target": t, "set": "test", "model": "LightGBM", **metrics(y[te], p_te)})

    # 3) normal band with quantile models -> coverage + share of hours above band
    lo = lgb.LGBMRegressor(objective="quantile", alpha=0.05, **PARAMS).fit(X[trva], y[trva]).predict(X[te])
    hi = lgb.LGBMRegressor(objective="quantile", alpha=0.95, **PARAMS).fit(X[trva], y[trva]).predict(X[te])
    yt = y[te].values
    rows.append({"target": t, "set": "test", "model": "Band 5-95%",
                 "coverage %": 100 * np.mean((yt >= lo) & (yt <= hi)),
                 "hours above band %": 100 * np.mean(yt > hi)})
    preds_all[t] = pd.DataFrame({"time": df.loc[te, "timestamp_local"].values, "actual": yt,
                                 "LightGBM": p_te, "B2": B.loc[te, "B2_median_4w"].values,
                                 "lo": lo, "hi": hi})
    if t == TARGETS[0]:
        imp = pd.Series(m.feature_importances_, index=X.columns).sort_values(ascending=False)
        imp.to_csv(OUT / "feature_importance_NE.csv")

res = pd.DataFrame(rows)
res.to_csv(OUT / "model_results.csv", index=False)
pd.concat(preds_all, names=["target"]).to_csv(OUT / "test_predictions.csv")

table = (res[res.model != "Band 5-95%"]
         .pivot_table(index=["target", "model"], columns="set", values="CV(RMSE) %")
         [["val", "test"]].round(1))
print("CV(RMSE) %  (lower is better, ASHRAE target < 30)\n", table.to_string())
print("\nNormal band on test:\n",
      res[res.model == "Band 5-95%"][["target", "coverage %", "hours above band %"]].round(1).to_string(index=False))

# chart: two test weeks for the storey total
p = preds_all["STOREY1|TOTAL W"]
p = p[(p.time >= "2023-02-06") & (p.time < "2023-02-20")].reset_index(drop=True)
p["time"] = pd.to_datetime(p["time"])
p = p.set_index("time").asfreq("h").reset_index()  # show missing hours as gaps
fig, ax = plt.subplots(figsize=(12, 4.5))
ax.fill_between(p.time, p.lo / 1000, p.hi / 1000, color="#9ec5e8", alpha=0.5, label="Normal band (5–95 %)")
ax.plot(p.time, p.actual / 1000, color="#1b1b1b", lw=1.2, label="Actual")
ax.plot(p.time, p.LightGBM / 1000, color="#1f6fb2", lw=1.2, label="LightGBM forecast")
ax.plot(p.time, p.B2 / 1000, color="#d98c1f", lw=1, ls="--", label="Baseline: 4-week median")
above = p.actual > p.hi
ax.scatter(p.time[above], p.actual[above] / 1000, color="#c0392b", s=14, zorder=5, label="Above band (possible waste)")
ax.set_xlim(p.time.min(), p.time.max())
ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%a %d %b"))
ax.set_title("Storey 1 total — test period, 6–19 Feb 2023 (day-ahead forecast)")
ax.set_ylabel("Power (kW) = kWh per hour")
ax.legend(loc="upper left", fontsize=8, ncol=3, frameon=False)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "test_forecast_storey1.png", dpi=150)
print("\nsaved out/model_results.csv, out/test_predictions.csv, out/test_forecast_storey1.png")
