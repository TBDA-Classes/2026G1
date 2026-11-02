"""
Shared helpers to load the frozen dataset and describe its series.
Every notebook and model script starts with `load()`.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "data" / "processed" / "cedint_hourly_v1.parquet"
FIG = ROOT / "reports" / "figures"

# The circuits where waste can happen (people switch them on/off).
FOCUS = ["NW|Plugs & Sockets W", "SW|Plugs & Sockets W", "SE|Plugs & Sockets W", "NE|Plugs & Sockets W",
         "NW|Lighting W", "SW|Lighting W", "SE|Lighting W", "NW|HVAC W", "SE|HVAC W"]

# Fixed loads: always on by design (emergency lights, server rack) or tiny (hand dryers, NE HVAC).
FIXED = ["NW|RACK W", "NW|Emerg. Lighting W", "SW|Emerg. Lighting W", "SE|Emerg. Lighting W",
         "NW|Hand Dryer W", "SW|Hand Dryer W", "NE|HVAC W"]

NIGHT_HOURS = list(range(22, 24)) + list(range(0, 6))   # 22:00-05:59 local time


def circuits(df: pd.DataFrame) -> list:
    """All 16 circuit columns (no zone / storey totals)."""
    return [c for c in df.columns if c.endswith(" W") and "TOTAL" not in c]


def load(drop_lockdown: bool = True) -> pd.DataFrame:
    """Frozen dataset with a few helper columns. Lockdown hours dropped by default (not 'normal' use)."""
    df = pd.read_parquet(FROZEN).sort_values("timestamp_utc").reset_index(drop=True)
    if drop_lockdown:
        df = df[~df["is_covid_lockdown"]].reset_index(drop=True)
    df["is_night"] = df["hour_local"].isin(NIGHT_HOURS)
    df["is_off_hours"] = (~df["is_working_day"]) | df["is_night"]          # building (mostly) empty
    df["day_type"] = pd.Series("working day", index=df.index)
    df.loc[df["is_weekend"], "day_type"] = "weekend"
    df.loc[df["is_holiday"] & ~df["is_weekend"], "day_type"] = "holiday"
    df.loc[df["is_break"] & ~df["is_weekend"] & ~df["is_holiday"], "day_type"] = "break (Xmas/Easter/Aug)"
    return df


def short(col: str) -> str:
    """'NW|Plugs & Sockets W' -> 'NW Plugs & Sockets'."""
    return col.replace("|", " ").removesuffix(" W")
