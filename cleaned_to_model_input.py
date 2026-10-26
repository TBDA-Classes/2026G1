"""
Converts the cleaned Excel file (sheet CLEAN, or PULITO in the Italian version, made in Excel with the guide) into the file
the modeling code expects: data/clean_hourly_wide.parquet (same column names as clean.py output).

Usage:  python src/pulito_to_model_input.py <path to Storey1_cleaned_data.xlsx>
"""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
xlsx = Path(sys.argv[1])
sheets = pd.ExcelFile(xlsx, engine="calamine").sheet_names
sheet = "CLEAN" if "CLEAN" in sheets else "PULITO"      # English or Italian version of the file
df = pd.read_excel(xlsx, sheet_name=sheet, engine="calamine")

df = df.rename(columns={"Timestamp UTC": "timestamp_utc",
                        "ora_locale": "timestamp_local", "local_time": "timestamp_local",
                        "weekday_loc": "weekday_local", "local_weekday": "weekday_local",
                        "hour_loc": "hour_local", "local_hour": "hour_local"})
df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"])
df["timestamp_local"] = pd.to_datetime(df["timestamp_local"])
df["date_local"] = df["timestamp_local"].dt.normalize()
df["month"] = df["timestamp_local"].dt.month
df["is_weekend"] = df["weekday_local"] >= 5
df["low_coverage"] = df["low_coverage"].astype(str).str.upper().eq("TRUE")
for c in df.columns:                                   # empty Excel cells -> NaN numbers
    if c not in ("Regime", "timestamp_utc", "timestamp_local", "date_local", "is_weekend", "low_coverage"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

out = ROOT / "data" / "clean_hourly_wide.parquet"
out.parent.mkdir(exist_ok=True)
df.to_parquet(out, index=False)
print(f"saved {out}: {df.shape[0]:,} rows x {df.shape[1]} columns")

# ---- long format (one row per hour x series), same layout as clean.py -> clean_hourly_long.parquet
id_cols = ["timestamp_utc", "timestamp_local", "date_local", "hour_local", "weekday_local",
           "is_weekend", "month", "Regime", "low_coverage"]
power_cols = [c for c in df.columns if c.endswith(" W") and "TOTAL" not in c]
value_cols = power_cols + [c for c in df.columns if "TOTAL" in c]
long = df.melt(id_vars=id_cols, value_vars=value_cols, var_name="series", value_name="W")
long["zone"] = long["series"].str.split("|").str[0]
long["circuit"] = long["series"].str.split("|").str[1].str.replace(" W", "", regex=False)
out_long = ROOT / "data" / "clean_hourly_long.parquet"
long.to_parquet(out_long, index=False)
print(f"saved {out_long}: {long.shape[0]:,} rows x {long.shape[1]} columns")
