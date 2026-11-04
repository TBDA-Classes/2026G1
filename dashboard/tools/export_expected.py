"""
Export the model's EXPECTED use for every hour since 2020, for the "Expected vs actual" page.

Notebook 03 computes these values (cross-fitting: each quarter predicted by a LightGBM trained on the
other quarters) but does not save them. This script re-runs exactly the team's code from src/
(same data, same settings from reports/model_params.json, same alarm k from reports/anomaly_k.json),
so the values are identical to the notebook's.

Run from the repository root (needs the team's requirements.txt: lightgbm, scikit-learn, PyYAML):
    python dashboard/tools/export_expected.py
Takes a few minutes. Writes dashboard/data/expected_hourly.parquet:
    timestamp_local | circuit | actual_W | expected_W | threshold_W | flag
(alarm line on the chart = expected_W + threshold_W)
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repository root
sys.path.insert(0, str(ROOT))

import pandas as pd                                  # noqa: E402

from src.anomalies import crossfit_expected, detect, hour_type, load_params, threshold_stats  # noqa: E402
from src.data import FOCUS, load, short             # noqa: E402

OUT = ROOT / "dashboard" / "data" / "expected_hourly.parquet"


def main():
    P = load_params()
    df = load()                                      # frozen dataset, lockdown removed (as notebook 03)
    params = json.load(open(ROOT / "reports" / "model_params.json"))
    lgb = {k.replace(" ", "|", 1) + " W": v["forecast"] for k, v in params.items()}
    kmap = json.load(open(ROOT / "reports" / "anomaly_k.json"))
    htype = hour_type(df)

    parts = []
    for c in FOCUS:
        t0 = time.time()
        expected = crossfit_expected(df, c, lgb[c])
        stats = threshold_stats(df[c] - expected, htype)
        H, _ = detect(df, c, expected, P, k=kmap[short(c)], describe=False, stats=stats)
        parts.append(pd.DataFrame({
            "timestamp_local": df["timestamp_local"], "circuit": short(c),
            "actual_W": H["actual"], "expected_W": H["expected"],
            "threshold_W": H["threshold"], "flag": H["flag_model"].fillna(False)}))
        print(f"{short(c):<22} done in {time.time() - t0:5.1f} s")

    out = pd.concat(parts, ignore_index=True)
    OUT.parent.mkdir(exist_ok=True)
    out.to_parquet(OUT, index=False)
    print(f"\n{len(out):,} rows written to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
