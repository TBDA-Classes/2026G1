"""
TBDA Group 1 - Storey 1: cleaning, ONE DATASET PER ZONE (NE, NW, SE, SW)

Input : data/raw/Storey1_{NE,NW,SE,SW}_report_by_device.xlsx   (the 4 original files, nothing else)
Output (for every zone Z):
   data/zones/hourly_Z.parquet          cleaned hourly table of the zone (wide: one row per hour)
   data/zones/hourly_Z_reasons.parquet  same shape: WHY each empty cell is empty (a short code), empty if the cell has a value
   data/zones/raw_hourly_Z.parquet      the hourly table BEFORE cleaning (nothing removed), for traceability
   out/cleaning_log.csv                 every rule x zone x column with the number of values touched

Step 1 - from the original files to one hourly table per zone (same method as the Sprint 1 table of the group;
         checked cell by cell against it):
   * Period A (2020-23): one reading per hour -> copied as it is.
   * Period B (2025): the minute readings are averaged per hour.
   * Environment sensor (Lum, Hum, Temp, Pres): ONE per zone. The minute readings of all sheets of the zone are put
     together (one value per minute); minutes where Lum = Hum = Temp = 0 are "sensor not reporting" and are ignored;
     then hourly average. Pres = share of readings that were 1.  NE has no environment sensor (all zeros): no ENV columns.
   * Same hourly grid for all zones: 26,830 hours (period A 25,489 + period B 1,341). Missing hours stay EMPTY.

Step 2 - cleaning rules (numbers as in the group's document; the rules are listed in the log):
   R1  timezone: timestamps are UTC (to be confirmed by the professor) -> Madrid local time columns
   R3  dead circuits left out: SE Projector (always 0), SW RACK (stops in Dec 2021)
   R4  NW Emerg. Lighting: sign flipped (meter wired in reverse, 97.7% negative)    [open group decision: flip or drop]
   R5  small negatives (-10..0 W) -> 0 (meter noise)
   R6  big negatives (< -10 W) -> EMPTY
   R7  same non-zero value 6+ hours in a row -> EMPTY (period A only)
   R8  6+ hours of exact 0 where the circuit normally uses > 1 W at that weekday and hour -> EMPTY (sensor stopped)
   X1  NW Emerg. Lighting: values below 3 W after the sign flip -> EMPTY (level jumps to ~0 W, not real consumption)
   R9  environment: Lum = Hum = Temp = 0 -> EMPTY (sensor not reporting)
   R10 environment: temperature outside 0-45 C -> temperature, humidity, light and presence of that hour EMPTY
   R11 low_coverage = TRUE in period B when a circuit of the zone has fewer than 30 minute readings in that hour
   R12 ZONE TOTAL W = sum of the circuits of the zone, only if ALL of them have a value in that hour
   Not done on purpose: no interpolation, no filling of gaps, spikes kept, energy counters (Ea, Er) not used.

Every cell that becomes empty gets a reason code (see REASON_TEXT below), so no empty cell is a mystery.

Run (from the project root, the folder that contains src/ and data/):   py src/clean_zones.py
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "zones"
LOG_DIR = ROOT / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

ZONES = ["NE", "NW", "SE", "SW"]
DROP_CIRCUITS = {"SE": ["Projector"], "SW": ["RACK"]}          # R3
SPLIT = pd.Timestamp("2024-01-01")                              # any date inside the 901-day gap
LONG_RUN = 6                                                    # hours: R7 and R8
TEMP_MIN, TEMP_MAX = 0.0, 45.0                                  # R10
X1_LIMIT_W = 3.0                                                # X1
LOW_COVERAGE_READINGS = 30                                      # R11
ENV = {"Hum": "ENV Hum %RH", "Lum": "ENV Lum lux", "Pres": "ENV Pres share", "Temp": "ENV Temp °C"}

REASON_TEXT = {
    "NO_DATA": "No value for this hour in the original file (the logger sent nothing for this circuit/sensor).",
    "NO_DATA_ZONE": "No value for this hour in ANY circuit of the zone: the whole zone was not logged (acquisition outage).",
    "R6_NEG": "Value below -10 W: impossible for a consumer, not meter noise. Discarded.",
    "R7_STUCK": "Same non-zero value for 6+ hours in a row (period A): stuck sensor. Discarded.",
    "R8_ZERO_RUN": "Exact 0 for 6+ hours where the circuit normally uses more than 1 W at that weekday and hour: the sensor stopped sending, it is not real consumption. Discarded.",
    "X1_LEVEL_DROP": "NW Emerg. Lighting below 3 W after the sign flip: the level jumps to about 0 W for weeks (Dec 2021, Feb-Apr 2022), probably work on the measuring system. Discarded.",
    "R9_ENV_ZEROS": "Light, humidity and temperature all read 0 at the same time: the environment sensor was not reporting. Discarded.",
    "R10_TEMP_RANGE": "Indoor temperature outside 0-45 C (e.g. SW sensor 739-1,411 C on 1-7 Mar 2022): sensor fault, so temperature, humidity, light and presence of that hour are discarded.",
    "TOTAL_INCOMPLETE": "The zone total is only computed when ALL circuits of the zone have a value in that hour; at least one is empty.",
}

log = []


def note(rule, zone, column, n, detail=""):
    log.append({"rule": rule, "zone": zone, "column": column, "values_affected": int(n), "detail": detail})


def runs(mask: pd.Series) -> pd.Series:
    """Length of the run of True values each position belongs to (0 where False)."""
    grp = (mask != mask.shift()).cumsum()
    return mask.groupby(grp).transform("size").where(mask, 0)


def read_zone(zone):
    f = RAW_DIR / f"Storey1_{zone}_report_by_device.xlsx"
    if not f.exists():
        raise SystemExit(f"File not found: {f}")
    try:
        sheets = pd.read_excel(f, sheet_name=None, engine="calamine")
    except (ImportError, ValueError):
        print("   (calamine not installed: openpyxl is much slower, a few minutes)")
        sheets = pd.read_excel(f, sheet_name=None, engine="openpyxl")
    parts = []
    for name, df in sheets.items():
        df.insert(0, "circuit", name)
        parts.append(df)
    raw = pd.concat(parts, ignore_index=True)
    raw["Timestamp"] = pd.to_datetime(raw["Timestamp"])
    raw["h"] = raw["Timestamp"].dt.floor("h")
    return raw


def hourly_zone(raw, zone):
    """Step 1 for one zone. Returns (circuit hours W, readings per hour, environment, hours that had rows, hours with env rows)."""
    g = raw.groupby(["circuit", "h"])["W"]
    W = g.mean().unstack(0)
    N = g.size().unstack(0)
    env = None
    env_hours_with_rows = None
    if zone != "NE":                                   # NE has no sensor: Lum/Hum/Temp/Pres are 0 in every row
        env_hours_with_rows = pd.DatetimeIndex(raw["h"].unique())
        ok = raw[~((raw["Lum"] == 0) & (raw["Hum"] == 0) & (raw["Temp"] == 0))]
        minute = ok.groupby("Timestamp")[["Lum", "Hum", "Temp", "Pres"]].mean()     # one value per minute
        env = minute.groupby(minute.index.floor("h")).mean()
    return W, N, env, env_hours_with_rows


def main():
    raws, hourly = {}, {}
    for z in ZONES:
        print(f"Reading zone {z} ...")
        raws[z] = read_zone(z)
        hourly[z] = hourly_zone(raws[z], z)
        print(f"   {len(raws[z]):,} rows, circuits: {sorted(raws[z]['circuit'].unique())}")

    # ---- common hourly grid: one block per period, from the first to the last hour of the original data ----
    all_h = pd.DatetimeIndex(sorted(set().union(*[set(hourly[z][0].index) for z in ZONES])))
    A, B = all_h[all_h < SPLIT], all_h[all_h >= SPLIT]
    grid = pd.date_range(A.min(), A.max(), freq="h").union(pd.date_range(B.min(), B.max(), freq="h"))
    regime = np.where(grid < SPLIT, "A", "B")
    print(f"Hourly grid: {len(grid):,} hours  (A {len(pd.date_range(A.min(), A.max(), freq='h')):,}, B {len(pd.date_range(B.min(), B.max(), freq='h')):,})")
    for z in ZONES:
        note("R2", z, "grid", len(grid) - hourly[z][0].reindex(grid).notna().any(axis=1).sum(),
             "hours of the common grid without any reading in this zone (kept as empty rows)")

    for z in ZONES:
        print(f"\n===== zone {z} =====")
        W, N, env, env_rows = hourly[z]
        W, N = W.reindex(grid), N.reindex(grid)

        df = pd.DataFrame({"timestamp_utc": grid, "Regime": regime})
        # ---- R1 timezone
        local = df["timestamp_utc"].dt.tz_localize("UTC").dt.tz_convert("Europe/Madrid")
        df["timestamp_local"] = local.dt.tz_localize(None)
        df["date_local"] = df["timestamp_local"].dt.normalize()
        df["weekday_local"] = df["timestamp_local"].dt.dayofweek          # 0 = Monday
        df["hour_local"] = df["timestamp_local"].dt.hour
        df["month"] = df["timestamp_local"].dt.month
        note("R1", z, "timestamp", len(df), "timestamps treated as UTC, Madrid local time added (summer/winter time included)")

        # ---- circuits (before R3 the dropped ones are kept for the raw file)
        circuits = sorted(W.columns)
        pw = pd.DataFrame({f"{c} W": W[c].values for c in circuits}, index=df.index)
        env_cols = []
        envdf = pd.DataFrame(index=df.index)
        env_state = {}                                      # per ENV column: 'rows but all zeros' hours
        if env is not None:
            e = env.reindex(grid)
            for k, name in ENV.items():
                envdf[name] = e[k].values
            env_cols = list(ENV.values())
            had_rows = pd.Series(grid.isin(env_rows), index=df.index)
            env_state = had_rows & envdf["ENV Temp °C"].isna()
        raw_hourly = pd.concat([df, pw, envdf], axis=1)
        raw_hourly["raw_readings_min"] = N.min(axis=1, skipna=True).values
        raw_hourly.to_parquet(OUT_DIR / f"raw_hourly_{z}.parquet", index=False)

        # ---- R3 dead circuits
        for c in DROP_CIRCUITS.get(z, []):
            col = f"{c} W"
            note("R3", z, col, pw[col].notna().sum(), "circuit left out of the clean data (always 0 / stops in Dec 2021)")
            pw = pw.drop(columns=col)
        power_cols = list(pw.columns)
        kept = [c.replace(" W", "") for c in power_cols]
        data = pd.concat([pw, envdf], axis=1)
        data_cols = power_cols + env_cols
        why = pd.DataFrame(None, index=df.index, columns=data_cols + ["ZONE TOTAL W"], dtype=object)

        # ---- initial empties: why were they empty already in the original data?
        zone_off = pw.isna().all(axis=1)                    # no circuit of the zone logged anything
        for c in power_cols:
            m = data[c].isna()
            why.loc[m & zone_off, c] = "NO_DATA_ZONE"
            why.loc[m & ~zone_off, c] = "NO_DATA"
            note("NO_DATA", z, c, m.sum(), "empty in the original data")
        for c in env_cols:
            m = data[c].isna()
            r9 = m & env_state
            why.loc[m & ~r9 & zone_off, c] = "NO_DATA_ZONE"
            why.loc[m & ~r9 & ~zone_off, c] = "NO_DATA"
            why.loc[r9, c] = "R9_ENV_ZEROS"
            note("R9", z, c, r9.sum(), "light, humidity and temperature all 0 -> sensor not reporting (hour left empty)")

        def blank(col, mask, code, rule, detail):
            mask = mask & data[col].notna()
            data.loc[mask, col] = np.nan
            why.loc[mask, col] = code
            note(rule, z, col, mask.sum(), detail)

        # ---- R4 sign flip
        if z == "NW":
            c = "Emerg. Lighting W"
            note("R4", z, c, (data[c] < 0).sum(), "sign flipped (values x -1): meter wired in reverse")
            data[c] = -data[c]

        # ---- R5 / R6 negatives
        for c in power_cols:
            small = data[c].ge(-10) & data[c].lt(0)
            note("R5", z, c, small.sum(), "-10..0 W set to 0 (meter noise)")
            data.loc[small, c] = 0.0
            blank(c, data[c] < -10, "R6_NEG", "R6", "below -10 W -> empty")

        # ---- R7 / R8 stuck values and dropouts (per period)
        for c in power_cols:
            stuck_tot = 0
            drop_mask = pd.Series(False, index=df.index)
            for reg in ("A", "B"):
                m = df["Regime"] == reg
                s = data.loc[m, c]
                if reg == "A":                                       # period B is rounded to whole watts: repeats are normal
                    same = (s == s.shift()) | (s == s.shift(-1))
                    stuck = runs(same & s.ne(0) & s.notna()) >= LONG_RUN
                    idx = stuck[stuck].index
                    data.loc[idx, c] = np.nan
                    why.loc[idx, c] = "R7_STUCK"
                    stuck_tot += len(idx)
                s = data.loc[m, c]
                typical = pd.DataFrame({"s": s, "wd": df.loc[m, "weekday_local"], "hr": df.loc[m, "hour_local"]}) \
                    .groupby(["wd", "hr"])["s"].transform("median")
                drop = (runs(s.eq(0)) >= LONG_RUN) & (typical > 1)
                drop_mask.loc[drop[drop].index] = True
            note("R7", z, c, stuck_tot, "same non-zero value 6+ h (period A) -> empty")
            blank(c, drop_mask, "R8_ZERO_RUN", "R8", "6+ h of exact 0 where the circuit normally uses > 1 W -> empty")

        # ---- X1 NW Emerg. Lighting level drop (after the flip and after R8)
        if z == "NW":
            c = "Emerg. Lighting W"
            blank(c, data[c] < X1_LIMIT_W, "X1_LEVEL_DROP", "X1", f"below {X1_LIMIT_W:g} W after the sign flip -> empty")

        # ---- R10 environment temperature range
        if env_cols:
            t = data["ENV Temp °C"]
            bad = t.notna() & ~t.between(TEMP_MIN, TEMP_MAX)
            for c in env_cols:
                blank(c, bad, "R10_TEMP_RANGE", "R10", f"temperature outside {TEMP_MIN:g}-{TEMP_MAX:g} C -> temperature, humidity, light, presence empty")

        # ---- R11 low coverage (period B): a circuit of the zone with < 30 minute readings in that hour
        kept_counts = N[[c for c in N.columns if c in kept]].reset_index(drop=True)
        low = pd.Series(regime == "B", index=df.index) & (kept_counts.min(axis=1, skipna=True) < LOW_COVERAGE_READINGS)
        data["low_coverage"] = low
        note("R11", z, "low_coverage", low.sum(), f"period B hour with a circuit built from < {LOW_COVERAGE_READINGS} minute readings (flag only)")

        # ---- R12 zone total
        total = data[power_cols].sum(axis=1, min_count=len(power_cols))
        data["ZONE TOTAL W"] = total
        why.loc[total.isna(), "ZONE TOTAL W"] = "TOTAL_INCOMPLETE"
        note("R12", z, "ZONE TOTAL W", total.notna().sum(), " + ".join(kept) + " (only if all are present)")

        out = pd.concat([df, data[power_cols + env_cols + ["low_coverage", "ZONE TOTAL W"]]], axis=1)
        out.to_parquet(OUT_DIR / f"hourly_{z}.parquet", index=False)
        rs = why.copy()
        rs.insert(0, "timestamp_utc", grid)
        rs.to_parquet(OUT_DIR / f"hourly_{z}_reasons.parquet", index=False)
        print(f"   saved hourly_{z}.parquet {out.shape}; hours with a zone total: {total.notna().sum():,}")
        print("   empty cells by reason:")
        print(why.stack().value_counts().to_string())

    pd.DataFrame(log).to_csv(LOG_DIR / "cleaning_log.csv", index=False)
    print("\nSaved out/cleaning_log.csv")


if __name__ == "__main__":
    main()
