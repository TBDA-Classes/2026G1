"""
WHY the model expected a value (customer-value document, extension 7.2).

For every hour and focus circuit, LightGBM can split its prediction into contributions of its inputs
(`pred_contrib=True`, TreeSHAP, built into LightGBM: no extra software). This script re-runs the cross-fitting of
notebook 03 exactly (same zone data, same final settings, same quarters), asks each model for these contributions,
groups them into a few plain-language factors and saves them for the dashboard.

    expected = base level + recent use + outdoor temperature + hour of the day + type of day + time of year
               + sunlight and humidity          (in W; the factors add up to the expected value)

Run from the repository root (needs the team's requirements.txt: lightgbm, scikit-learn, PyYAML, pyarrow):
    python dashboard/tools/export_contributions.py
Takes a few minutes. Writes dashboard/data/expected_contributions.parquet
(or give it to the modelling team so they add it to reports/).
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repository root
sys.path.insert(0, str(ROOT))

import numpy as np                                   # noqa: E402
import pandas as pd                                  # noqa: E402

from src.data import FOCUS, short                    # noqa: E402
from src.features import make_features              # noqa: E402
from src.models import make_lgb                      # noqa: E402

try:
    from src.zones import load_zones                 # notebooks 01–03 since 24 Nov 2026
except ImportError:
    load_zones = None
    from src.data import load

OUT = ROOT / "dashboard" / "data" / "expected_contributions.parquet"

# model inputs (src/features.make_features, "forecast" set) -> plain-language factor
GROUPS = {
    "recent_use": ["lag_24", "lag_48", "lag_168", "lag_336", "same_hour_mean_7d"],
    "temperature": ["wx_temp_c", "heating_deg", "cooling_deg"],
    "hour_of_day": ["hour"],
    "day_type": ["weekday", "is_working_day", "is_holiday", "is_break", "is_august_closure"],
    "time_of_year": ["doy_sin", "doy_cos"],
    "sun_humidity": ["wx_solar_wm2", "wx_humidity_pct"],
}


def settings_for(circuit_col: str) -> dict:
    """Final settings of notebook 04_model_search (same for all circuits), else the per-circuit ones of notebook 02."""
    final = ROOT / "reports" / "final_model_settings.json"
    if final.exists():
        return json.load(open(final))
    per = json.load(open(ROOT / "reports" / "model_params.json"))
    return per[short(circuit_col)]["forecast"]


def contributions(df: pd.DataFrame, target: str) -> pd.DataFrame:
    """Same folds as src/anomalies.crossfit_expected: each quarter of period A predicted by a model trained on the
    other quarters; period B (2025) by a model trained on all of period A."""
    X = make_features(df, target, "forecast")
    y = df[target]
    ok = y.notna()
    params = settings_for(target)
    out = np.full((len(df), X.shape[1] + 1), np.nan)
    a = df["Regime"] == "A"
    q = df["timestamp_local"].dt.to_period("Q")
    for period in q[a].unique():
        test = a & (q == period)
        model = make_lgb(**params).fit(X[a & ~test & ok], y[a & ~test & ok])
        out[test.values] = model.predict(X[test], pred_contrib=True)
    b = df["Regime"] == "B"
    if b.any():
        model = make_lgb(**params).fit(X[a & ok], y[a & ok])
        out[b.values] = model.predict(X[b], pred_contrib=True)
    C = pd.DataFrame(out[:, :-1], columns=X.columns, index=df.index)
    res = pd.DataFrame({"timestamp_local": df["timestamp_local"], "circuit": short(target),
                        "base_W": out[:, -1]})
    for g, cols in GROUPS.items():
        res[f"{g}_W"] = C[[c for c in cols if c in C]].sum(axis=1, min_count=1)
    other = [c for c in C if not any(c in cols for cols in GROUPS.values())]
    if other:                                          # an input added to src/features.py later
        print(f"   inputs not in GROUPS, shown as 'other inputs': {other}")
        res["other_W"] = C[other].sum(axis=1, min_count=1)
    res["expected_W"] = out.sum(axis=1)                # = the model's prediction (all contributions + base)
    return res


def compare_with_team(out: pd.DataFrame) -> None:
    """The expected values must be those of notebook 03 (reports/expected_hourly.parquet), else warn."""
    p = ROOT / "reports" / "expected_hourly.parquet"
    if not p.exists():
        return
    team = pd.read_parquet(p)
    m = out.merge(team[["timestamp_local", "circuit", "expected_W"]], on=["timestamp_local", "circuit"],
                  suffixes=("", "_team"))
    diff = (m["expected_W"] - m["expected_W_team"]).abs()
    print(f"check against notebook 03: median difference {diff.median():.2f} W, largest {diff.max():.1f} W "
          f"({len(m):,} hours compared)")
    if diff.median() > 1:
        print("WARNING: not the same expected values as notebook 03 (other settings or data?). "
              "The factors still explain this model, but tell the modelling team.")


def main():
    df = load_zones() if load_zones else load()
    df = df.sort_values("timestamp_utc").reset_index(drop=True)
    parts = []
    for c in FOCUS:
        t0 = time.time()
        parts.append(contributions(df, c))
        print(f"{short(c):<22} done in {time.time() - t0:5.1f} s")
    out = pd.concat(parts, ignore_index=True)
    compare_with_team(out)
    OUT.parent.mkdir(exist_ok=True)
    out.to_parquet(OUT, index=False)
    print(f"\n{len(out):,} rows written to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
