# combines the four zone files (NE, NW, SE, SW) into one parquet
# each sheet in the excel files is one circuit, so we add zone + circuit columns
#
# temporary until KAN-11 is done, after that this should just be the refresh step
#
# run: python -m src.data.combine
# output: data/processed/combined.parquet

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "CeDint DataSet"
OUT = ROOT / "data" / "processed" / "combined.parquet"

ZONES = ["NE", "NW", "SE", "SW"]


def load_zone(zone):
    sheets = pd.read_excel(RAW / f"Storey1_{zone}_report_by_device.xlsx", sheet_name=None)
    frames = []
    for circuit, df in sheets.items():
        df = df.copy()
        df["zone"] = zone
        df["circuit"] = circuit
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def build():
    df = pd.concat([load_zone(z) for z in ZONES], ignore_index=True)
    df = df.rename(columns={
        "Timestamp": "timestamp",
        "E Device type": "device_type",
        "Number of Edevices": "n_devices",
    })
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    cols = ["timestamp", "zone", "circuit", "device_type", "n_devices",
            "W", "I", "Ea", "Er", "Pa", "Lum", "Hum", "Temp", "Pres"]
    return df[cols].sort_values(["zone", "circuit", "timestamp"]).reset_index(drop=True)


if __name__ == "__main__":
    df = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"{len(df)} rows -> {OUT.relative_to(ROOT)}")
    print(df.groupby(["zone", "circuit"]).size())
