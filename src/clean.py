"""
TBDA Group 1 - Storey 1 data cleaning (story 3.3 + 3.4)

Input : the consolidated hourly table (tab 00_RAW_DATA of Storey1_Anomaly_Analysis.xlsx,
        or data/raw_hourly.parquet made from it)
Output: data/clean_hourly_wide.parquet   one row per hour, one column per circuit
        data/clean_hourly_long.parquet   one row per hour x circuit (easiest for modelling)
        data/clean_hourly_wide.csv       same as wide, for Excel users
        out/cleaning_log.csv             every rule, which column, how many values it touched

Rules (each one is numbered in the log):
  R1  Timezone: timestamps treated as UTC, local Madrid time added (DST handled)
  R2  Full hourly grid per regime: missing hours become empty rows (not imputed)
  R3  Dead / incomplete circuits dropped from modelling: SE|Projector, SW|RACK
  R4  NW|Emerg. Lighting sign flipped (meter wired in reverse, 99% negative)
  R5  Small negatives (-10..0 W) on consumption circuits -> 0 (meter noise)
  R6  Big negatives (< -10 W) -> missing
  R7  Stuck sensor: same non-zero value 6+ hours in a row -> missing
  R8  Dropout: 6+ hours of exact 0 where that circuit is normally > 1 W -> missing
  R9  Environment: Lum=Hum=Temp=0 at the same time -> missing (safeguard; already empty in 00_RAW_DATA)
  R10 Environment: temperature outside 5-45 C -> missing (SW 1-7 Mar 2022), same hour Hum/Lum too
  R11 Regime B hours built from < 30 one-minute readings -> flagged low_coverage
  R12 Zone totals and storey total recomputed from clean circuits (only if all circuits present)

Nothing in the raw file is changed. Every removed value is still in raw_hourly.parquet.
Run:  python src/clean.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_PARQUET = ROOT / "data" / "raw_hourly.parquet"
RAW_XLSX = ROOT / "data" / "Storey1_Anomaly_Analysis.xlsx"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

log = []


def note(rule, column, n, detail=""):
    log.append({"rule": rule, "column": column, "values_affected": int(n), "detail": detail})


def runs(mask: pd.Series) -> pd.Series:
    """Length of the run of True values each position belongs to."""
    grp = (mask != mask.shift()).cumsum()
    return mask.groupby(grp).transform("size").where(mask, 0)


# ---------------------------------------------------------------- load
if RAW_PARQUET.exists():
    raw = pd.read_parquet(RAW_PARQUET)
else:
    raw = pd.read_excel(RAW_XLSX, sheet_name="00_RAW_DATA", header=3)
    raw.to_parquet(RAW_PARQUET)

raw["Timestamp"] = pd.to_datetime(raw["Timestamp"])
power_cols = [c for c in raw.columns if c.endswith(" W") and not c.startswith("STOREY1")]
env_cols = [c for c in raw.columns if "|ENV " in c]
keep = ["Timestamp", "Regime", "Min raw readings in hour (all circuits)"] + power_cols + env_cols
df = raw[keep].rename(columns={"Min raw readings in hour (all circuits)": "raw_readings"})

# ---------------------------------------------------------------- R2 full hourly grid
parts = []
for reg, g in df.groupby("Regime"):
    grid = pd.date_range(g.Timestamp.min(), g.Timestamp.max(), freq="h")
    added = len(grid) - len(g)
    g = g.set_index("Timestamp").reindex(grid)
    g["Regime"] = reg
    g.index.name = "timestamp_utc"
    parts.append(g)
    note("R2", f"regime {reg}", added, "hours missing in source, added as empty rows")
df = pd.concat(parts).reset_index()

# ---------------------------------------------------------------- R1 timezone
local = df["timestamp_utc"].dt.tz_localize("UTC").dt.tz_convert("Europe/Madrid")
df["timestamp_local"] = local.dt.tz_localize(None)
df["date_local"] = df["timestamp_local"].dt.normalize()
df["hour_local"] = df["timestamp_local"].dt.hour
df["weekday_local"] = df["timestamp_local"].dt.dayofweek  # 0 = Monday
df["is_weekend"] = df["weekday_local"] >= 5
df["month"] = df["timestamp_local"].dt.month
note("R1", "timestamp", len(df), "assumed UTC (summer/winter ramp-up shift of 1 h supports this) -> Europe/Madrid")

# ---------------------------------------------------------------- R3 drop dead circuits
for c in ["SE|Projector W", "SW|RACK W"]:
    why = "always reads 0" if "Projector" in c else "stops in Dec 2021, absent in 2025"
    note("R3", c, df[c].notna().sum(), "dropped from modelling set: " + why)
    df = df.drop(columns=c)
power_cols = [c for c in power_cols if c not in ("SE|Projector W", "SW|RACK W")]

# ---------------------------------------------------------------- R4 sign flip
c = "NW|Emerg. Lighting W"
note("R4", c, (df[c] < 0).sum(), "sign flipped (values * -1)")
df[c] = -df[c]

# ---------------------------------------------------------------- R5/R6 negatives
for c in power_cols:
    small = df[c].between(-10, 0, inclusive="left")
    big = df[c] < -10
    note("R5", c, small.sum(), "-10..0 W set to 0")
    note("R6", c, big.sum(), "< -10 W set to missing")
    df.loc[small, c] = 0.0
    df.loc[big, c] = np.nan

# ---------------------------------------------------------------- R7/R8 stuck & dropouts (per regime)
for c in power_cols:
    stuck_tot = drop_tot = 0
    for reg in ["A", "B"]:
        m = df["Regime"] == reg
        s = df.loc[m, c]
        # R7 stuck: identical non-zero value repeated 6+ h (Regime B is integer-rounded,
        # so only check Regime A where values have 3 decimals)
        if reg == "A":
            same = (s == s.shift()) | (s == s.shift(-1))
            stuck = (runs(same & s.ne(0) & s.notna()) >= 6)
            df.loc[stuck[stuck].index, c] = np.nan
            stuck_tot += stuck.sum()
        # R8 dropout: 6+ h of zeros where normal level for that weekday-hour > 5 W
        s = df.loc[m, c]
        typical = df.loc[m].groupby(["weekday_local", "hour_local"])[c].transform("median")
        zero_run = runs(s.eq(0)) >= 6
        dropout = zero_run & (typical > 1)
        df.loc[dropout[dropout].index, c] = np.nan
        drop_tot += dropout.sum()
    note("R7", c, stuck_tot, "same non-zero value 6+ h -> missing")
    note("R8", c, drop_tot, "6+ h of 0 where circuit is normally > 1 W -> missing")

# ---------------------------------------------------------------- R9/R10 environment
for z in ["NW", "SE", "SW"]:
    cols = [f"{z}|ENV Lum lux", f"{z}|ENV Hum %RH", f"{z}|ENV Temp °C"]
    allzero = (df[cols] == 0).all(axis=1)
    bad_t = ~df[f"{z}|ENV Temp °C"].between(5, 45) & df[f"{z}|ENV Temp °C"].notna()
    note("R9", f"{z} ENV", allzero.sum(), "Lum=Hum=Temp=0 -> missing")
    note("R10", f"{z} ENV", (bad_t & ~allzero).sum(), "temperature outside 5-45 C -> missing")
    df.loc[allzero | bad_t, cols + [f"{z}|ENV Pres share"]] = np.nan

# ---------------------------------------------------------------- R11 low coverage
df["low_coverage"] = (df["Regime"] == "B") & (df["raw_readings"] < 30)
note("R11", "regime B", df["low_coverage"].sum(), "hour built from < 30 minute readings (flag only)")

# ---------------------------------------------------------------- R12 totals
zones = {}
for z in ["NE", "NW", "SE", "SW"]:
    cols = [c for c in power_cols if c.startswith(z + "|")]
    zones[z] = cols
    df[f"{z}|ZONE TOTAL W"] = df[cols].sum(axis=1, min_count=len(cols))
    note("R12", f"{z} total", df[f"{z}|ZONE TOTAL W"].notna().sum(), " + ".join(cols))
df["STOREY1|TOTAL W"] = df[[f"{z}|ZONE TOTAL W" for z in zones]].sum(axis=1, min_count=4)
note("R12", "STOREY1 total", df["STOREY1|TOTAL W"].notna().sum(), "sum of 4 zone totals")

# ---------------------------------------------------------------- save
df.to_parquet(ROOT / "data" / "clean_hourly_wide.parquet", index=False)
df.to_csv(ROOT / "data" / "clean_hourly_wide.csv", index=False)

id_cols = ["timestamp_utc", "timestamp_local", "date_local", "hour_local", "weekday_local",
           "is_weekend", "month", "Regime", "low_coverage"]
value_cols = power_cols + [c for c in df.columns if "TOTAL" in c]
long = df.melt(id_vars=id_cols, value_vars=value_cols, var_name="series", value_name="W")
long["zone"] = long["series"].str.split("|").str[0]
long["circuit"] = long["series"].str.split("|").str[1].str.replace(" W", "", regex=False)
long.to_parquet(ROOT / "data" / "clean_hourly_long.parquet", index=False)

pd.DataFrame(log).to_csv(OUT / "cleaning_log.csv", index=False)
print(f"clean wide: {df.shape}, long: {long.shape}")
print(pd.DataFrame(log).groupby("rule")["values_affected"].sum().to_string())
