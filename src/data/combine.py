"""Build the combined table from the four CeDint zone files (KAN-11 / KAN-44).

Temporary builder so the dashboard skeleton (KAN-118) has something to read.
Squad A owns the final version in KAN-11; when that lands, this script should
either be replaced by it or kept as the one-command refresh (KAN-230).

Usage:
    python -m src.data.combine
Output:
    data/processed/combined.parquet
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "CeDint DataSet"
OUT = ROOT / "data" / "processed" / "combined.parquet"

ZONES = ["NE", "NW", "SE", "SW"]


def load_zone(zone: str) -> pd.DataFrame:
    path = RAW_DIR / f"Storey1_{zone}_report_by_device.xlsx"
    frames = []
    for sheet, df in pd.read_excel(path, sheet_name=None).items():
        df = df.copy()
        df["zone"] = zone
        df["circuit"] = sheet  # one sheet per circuit / load type
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def build() -> pd.DataFrame:
    df = pd.concat([load_zone(z) for z in ZONES], ignore_index=True)
    df = df.rename(columns={"Timestamp": "timestamp", "E Device type": "device_type",
                            "Number of Edevices": "n_devices"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    cols = ["timestamp", "zone", "circuit", "device_type", "n_devices",
            "W", "I", "Ea", "Er", "Pa", "Lum", "Hum", "Temp", "Pres"]
    return df[cols].sort_values(["zone", "circuit", "timestamp"]).reset_index(drop=True)


def main() -> None:
    df = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"wrote {len(df):,} rows to {OUT.relative_to(ROOT)}")
    print(df.groupby(["zone", "circuit"]).size().to_string())


if __name__ == "__main__":
    main()
