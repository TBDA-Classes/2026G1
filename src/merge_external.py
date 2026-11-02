"""
KAN-58  Merge external data with building data

Joins to the cleaned hourly building table:
   * hourly weather   (data/weather_hourly.parquet,  from download_weather.py)   -> on 'timestamp_utc'
   * daily calendar   (data/calendar_daily.parquet,  from build_calendar.py)     -> on 'date_local'
   * hourly price and CO2 of the grid (data/prices_co2_hourly.parquet, from download_price_omie.py)
        -> on 'timestamp_utc'. OPTIONAL: if the file does not exist yet, this step is skipped.
and saves  data/clean_hourly_plus_external.parquet  (+ a small CSV preview).

Nothing is deleted or changed in the building columns: only new columns are added at the right.
Rows = 26,830 (same as the cleaned table).

Usage:  python src/merge_external.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

bld = pd.read_parquet(DATA / "clean_hourly_wide.parquet")
wx = pd.read_parquet(DATA / "weather_hourly.parquet")
cal = pd.read_parquet(DATA / "calendar_daily.parquet")
n_rows = len(bld)
print(f"Building table: {n_rows:,} rows x {bld.shape[1]} columns")

# ---- 1) weather: one row per UTC hour ----
merged = bld.merge(wx, on="timestamp_utc", how="left", validate="one_to_one")

# ---- 2) calendar: one row per local day (the local day of every hour is in 'date_local') ----
# columns the building table already has (weekday_local, is_weekend, date_local...) are not added twice
cal_cols = ["date_local"] + [c for c in cal.columns if c != "date_local" and c not in bld.columns and c != "weekday"]
merged["date_local"] = pd.to_datetime(merged["date_local"]).dt.normalize()
merged = merged.merge(cal[cal_cols], on="date_local", how="left", validate="many_to_one")

# ---- 3) price and CO2 of the Spanish grid (KAN-134), only if already downloaded ----
pc_path = DATA / "prices_co2_hourly.parquet"
pc_cols = []
if pc_path.exists():
    pc = pd.read_parquet(pc_path)
    pc_cols = [c for c in pc.columns if c != "timestamp_utc"]
    merged = merged.merge(pc, on="timestamp_utc", how="left", validate="one_to_one")
    print(f"Price/CO2 joined: {pc_cols}")
else:
    print("Price/CO2 file not found: skipped (run download_price_omie.py first, then this script again)")

# ---- checks (acceptance criteria of KAN-14 / KAN-125) ----
assert len(merged) == n_rows, "the merge changed the number of rows!"
assert merged["timestamp_utc"].is_unique
wx_cols = [c for c in wx.columns if c != "timestamp_utc"]
missing_wx = merged[wx_cols].isna().any(axis=1).sum()
print(f"Rows without weather:  {missing_wx}   (must be 0)")
missing_cal = merged["is_working_day"].isna().sum()
print(f"Rows without calendar: {missing_cal}   (must be 0)")
assert missing_wx == 0, "some hours have no weather: check that the download covers both periods"
assert missing_cal == 0, "some days have no calendar: check START/END in build_calendar.py"
for c in [c for c in pc_cols if not c.endswith("_is_fallback")]:
    print(f"Rows without {c}: {int(merged[c].isna().sum())}   (hours still empty after the monthly-average fallback)")

# the building columns must be exactly as before
same = merged[bld.columns].equals(bld) or merged[bld.columns].astype(str).equals(bld.astype(str))
print("Building columns unchanged:", same)
assert same

print("\nNew columns added:", len(merged.columns) - len(bld.columns))
print(merged[["timestamp_utc", "wx_temp_c", "wx_solar_wm2", "is_holiday", "is_working_day", "holiday_name"]].head(3))

merged.to_parquet(DATA / "clean_hourly_plus_external.parquet", index=False)
merged.head(500).to_csv(DATA / "clean_hourly_plus_external_preview.csv", index=False)
print("\nSaved data/clean_hourly_plus_external.parquet:", merged.shape)