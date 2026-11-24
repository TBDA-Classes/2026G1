"""
Load the cleaned data from the data-cleaning group (one file per zone) as ONE table.

The data-cleaning group delivers four files, one per zone of Storey 1:
    zone_NE_hourly.parquet, zone_NW_hourly.parquet, zone_SE_hourly.parquet, zone_SW_hourly.parquet
Every file has one row per hour (the same 26,830 hours in all four files).

The model code (src/features.py, src/models.py, src/anomalies.py) expects one table with
  * circuit columns named "<zone>|<circuit>", e.g. "NW|Plugs & Sockets W"
  * the column is_break (Christmas break, Holy Week or August closure)
so this file joins the four zone files and adds those columns.
"""
from pathlib import Path

import pandas as pd

from src.data import NIGHT_HOURS, ROOT

ZONES = ["NE", "NW", "SE", "SW"]
ZONE_DIR = ROOT / "data"                       # folder with the four zone files

# Columns that are the same in all four zone files (time, weather, calendar, price, CO2)
SHARED = ["timestamp_utc", "Regime", "timestamp_local", "weekday_local", "hour_local", "month",
          "wx_temp_c", "wx_feels_like_c", "wx_humidity_pct", "wx_precip_mm", "wx_cloud_pct", "wx_wind_ms",
          "wx_solar_wm2", "wx_pressure_hpa",
          "is_working_day", "is_weekend", "is_holiday", "holiday_name",
          "is_christmas_break", "is_holy_week", "is_august_closure", "is_covid_lockdown",
          "price_eur_mwh", "co2_intensity_g_kwh"]

# Columns that belong to one zone only: they get the zone name in front ("NW|...")
ZONE_ONLY = ["low_coverage", "empty_reasons"]


def find_zone_file(zone: str, folder: Path) -> Path:
    """zone_NW_hourly.parquet (also accepts names like zone_NW_hourly_4.parquet from a download)."""
    matches = sorted(folder.rglob(f"zone_{zone}_hourly*.parquet"))
    if not matches:
        raise FileNotFoundError(f"No file zone_{zone}_hourly.parquet found in {folder}")
    return matches[0]


def load_zones(folder: Path = ZONE_DIR, drop_lockdown: bool = True) -> pd.DataFrame:
    """The four zone files joined into one hourly table, ready for the model code."""
    tables = {zone: pd.read_parquet(find_zone_file(zone, folder)).sort_values("timestamp_utc").reset_index(drop=True)
              for zone in ZONES}

    # 1. time, weather and calendar: taken once (identical in every zone file)
    df = tables["NW"][SHARED].copy()

    # 2. electricity and indoor-sensor columns of each zone, with the zone name in front
    for zone, t in tables.items():
        assert t["timestamp_utc"].equals(df["timestamp_utc"]), f"zone {zone} has different hours"
        own = [c for c in t.columns if c not in SHARED and c not in ZONE_ONLY]
        df = pd.concat([df, t[own].add_prefix(f"{zone}|")], axis=1)
        df[f"{zone}|low_coverage"] = t["low_coverage"]

    # 3. columns the model code needs that are not in the zone files
    df["is_break"] = df["is_christmas_break"] | df["is_holy_week"] | df["is_august_closure"]   # long closure
    df["low_coverage"] = df[[f"{z}|low_coverage" for z in ZONES]].any(axis=1)               # any zone
    df["date_local"] = df["timestamp_local"].dt.normalize()
    # storey total = sum of the 4 zone totals, only when all 4 exist (same rule as R12 in src/clean.py)
    df["STOREY1|TOTAL W"] = df[[f"{z}|ZONE TOTAL W" for z in ZONES]].sum(axis=1, min_count=len(ZONES))

    # 4. the same steps as src.data.load(): remove the COVID lockdown, add helper columns
    if drop_lockdown:
        df = df[~df["is_covid_lockdown"]].reset_index(drop=True)
    df["is_night"] = df["hour_local"].isin(NIGHT_HOURS)
    df["is_off_hours"] = (~df["is_working_day"]) | df["is_night"]          # building (mostly) empty
    df["day_type"] = "working day"
    df.loc[df["is_weekend"], "day_type"] = "weekend"
    df.loc[df["is_holiday"] & ~df["is_weekend"], "day_type"] = "holiday"
    df.loc[df["is_break"] & ~df["is_weekend"] & ~df["is_holiday"], "day_type"] = "break (Xmas/Easter/Aug)"
    return df
