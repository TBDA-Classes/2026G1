"""
Freeze the modelling dataset (v1) and write its manifest.

Input : data/clean_hourly_plus_external.parquet   (output of clean.py + merge_external.py)
Output: data/processed/cedint_hourly_v1.parquet    the ONLY file the models read
        data/processed/MANIFEST.json               sources, rows, ranges, columns, rules, SHA-256

All modelling code reads the frozen file, so results can always be traced to one exact dataset.
Re-running this script on the same input gives the same data hash.

Run:  python src/freeze_dataset.py
"""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SRC = DATA / "clean_hourly_plus_external.parquet"
OUT_DIR = DATA / "processed"
VERSION = "v1"
OUT = OUT_DIR / f"cedint_hourly_{VERSION}.parquet"

CLEANING_RULES = {
    "R1": "Timestamps treated as UTC (checked against sun position, src/check_utc.py), Europe/Madrid local time added",
    "R2": "Full hourly grid per regime; missing hours are empty rows (not imputed)",
    "R3": "Dead circuits dropped: SE|Projector (always 0), SW|RACK (stops Dec 2021)",
    "R4": "NW|Emerg. Lighting sign flipped (meter wired in reverse)",
    "R5": "Small negatives (-10..0 W) -> 0",
    "R6": "Big negatives (< -10 W) -> missing",
    "R7": "Stuck sensor: same non-zero value 6+ h -> missing (Regime A)",
    "R8": "Dropout: 6+ h of 0 where the circuit is normally > 1 W -> missing",
    "R9": "Environment: Lum=Hum=Temp=0 together -> missing",
    "R10": "Environment: temperature outside 5-45 C -> missing",
    "R11": "Regime B hours built from < 30 one-minute readings -> low_coverage flag",
    "R12": "Zone and storey totals recomputed from clean circuits (only if all circuits present)",
}

UNITS = {
    " W": "mean active power in the hour [W] = energy in that hour [Wh]",
    "ENV Temp": "indoor temperature [C]", "ENV Hum": "indoor relative humidity [%]",
    "ENV Lum": "indoor illuminance [lux]", "ENV Pres": "share of the hour with presence detected [0-1]",
    "wx_": "outdoor weather, Open-Meteo archive, Montegancedo campus (see src/download_weather.py)",
    "price_eur_mwh": "OMIE Spanish day-ahead price [EUR/MWh], wholesale only",
    "is_": "calendar flag (see src/build_calendar.py)",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def data_hash(df: pd.DataFrame) -> str:
    """Hash of the table content (independent of parquet writer version)."""
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def unit_of(col: str) -> str:
    for key, unit in UNITS.items():
        if key in col:
            return unit
    return ""


def main():
    df = pd.read_parquet(SRC).sort_values("timestamp_utc").reset_index(drop=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)

    regimes = {
        r: {"start_utc": str(g.timestamp_utc.min()), "end_utc": str(g.timestamp_utc.max()), "rows": int(len(g))}
        for r, g in df.groupby("Regime")
    }
    power = [c for c in df.columns if c.endswith(" W")]
    manifest = {
        "dataset": f"cedint_hourly_{VERSION}",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "code_commit": git_commit(),
        "built_by": ["src/save_parquet.py (raw -> long)", "[missing in repo] raw -> hourly table '00_RAW_DATA'",
                     "src/clean.py", "src/build_calendar.py", "src/download_weather.py",
                     "src/download_price_omie.py", "src/merge_external.py", "src/freeze_dataset.py"],
        "raw_sources": {p.name: sha256(p) for p in sorted((DATA / "raw").glob("*.xlsx"))},
        "input_file": {"path": str(SRC.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(SRC)},
        "output_file": {"path": str(OUT.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(OUT)},
        "content_sha256": data_hash(df),
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "regimes": regimes,
        "note_gap": "No data between 2023-03-01 and 2025-08-18 in the raw files (source gap, not cleaning).",
        "missing_share_power": {c: round(float(df[c].isna().mean()), 4) for c in power},
        "cleaning_rules": CLEANING_RULES,
        "column_units": {c: unit_of(c) for c in df.columns},
    }
    (OUT_DIR / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {OUT.relative_to(ROOT)}: {df.shape}")
    print(f"content_sha256 = {manifest['content_sha256']}")


if __name__ == "__main__":
    main()
