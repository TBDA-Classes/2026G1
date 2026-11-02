"""
KAN-134 / KAN-57  Hourly electricity price of the Spanish market (OMIE day-ahead), no token needed

What it does
  1. For every day of our two periods it downloads the small public text file that OMIE publishes
     (the same files the Python package "OMIEData" uses) and keeps the SPANISH hourly price in EUR/MWh.
  2. Converts every OMIE hour (Madrid local time, 23/24/25 hours on the daylight-saving days) to UTC.
  3. Saves  data/prices_co2_hourly.parquet  (+ csv)  with the columns
        timestamp_utc, price_eur_mwh, price_eur_mwh_is_fallback
     The CO2 columns will be added to the same file later.

Fallback (ticket KAN-134): if an hour has no price, we use the AVERAGE of that month and mark it with
price_eur_mwh_is_fallback = True. If a month has less than 7 days of real prices (or none), the cells stay empty (nothing is invented).

The raw OMIE files are kept in data/omie_raw/ : the second time you run the script nothing is downloaded again.
About 1,100 small files are needed, so the first run takes some minutes.

Needs only pandas + pyarrow (already installed). Usage:   py src/download_price_omie.py
"""
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "omie_raw"
RAW.mkdir(parents=True, exist_ok=True)

# can be overridden only to test the script offline
BASE = os.environ.get("OMIE_URL", "https://www.omie.es/sites/default/files/dados/")
URL = BASE + "AGNO_{Y}/MES_{M}/TXT/INT_PBC_EV_H_1_{D}_{M}_{Y}_{D}_{M}_{Y}.TXT"

# the days we need (local dates): period A and period B, with one day of margin
PERIODS = [("2020-04-01", "2023-03-01"), ("2025-08-17", "2025-10-14")]
MIN_HOURS_FOR_MONTHLY_AVERAGE = 168      # a monthly average is used only if the month has at least 7 days of real prices


def download_day(day):
    """Download one day (or reuse the file already on disk). Returns the path, or None if OMIE has no file."""
    f = RAW / f"PMD_{day:%Y%m%d}.txt"
    if f.exists() and f.stat().st_size > 200:
        return f
    url = URL.format(Y=f"{day:%Y}", M=f"{day:%m}", D=f"{day:%d}")
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                content = r.read()
            if len(content) > 200:
                f.write_bytes(content)
                return f
            return None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * attempt)
        except Exception:
            time.sleep(2 * attempt)
    return None


def to_float(text):
    text = text.strip()
    if text == "":
        return None
    return float(text.replace(".", "").replace(",", "."))      # OMIE writes 1.234,56


def parse_day(path):
    """Returns a Series indexed by UTC hour (naive), or None if the file has no Spanish price."""
    lines = path.read_bytes().decode("latin-1").splitlines()
    dates = re.findall(r"\d\d/\d\d/\d{4}", lines[0])
    if not dates:
        return None
    day = pd.to_datetime(dates[-1], format="%d/%m/%Y")
    for line in lines[1:]:
        low = line.lower()
        if low.startswith("precio marginal") and "portugu" not in low:
            parts = line.split(";")
            mult = 10.0 if "cent/kwh" in parts[0].lower() else 1.0       # Cent/kWh -> EUR/MWh
            vals = [to_float(p) for p in parts[1:]]
            vals = [v * mult for v in vals if v is not None]
            n = len(vals)
            start = day.tz_localize("Europe/Madrid")                        # local midnight
            if n in (23, 24, 25):                                           # normal / short / long day, hourly
                idx = [start + pd.Timedelta(hours=k) for k in range(n)]
                s = pd.Series(vals, index=pd.DatetimeIndex(idx))
            elif n in (92, 96, 100):                                        # 15-minute market (since Oct 2025)
                idx = [start + pd.Timedelta(minutes=15 * k) for k in range(n)]
                s = pd.Series(vals, index=pd.DatetimeIndex(idx))
                s = s.groupby(s.index.floor("h")).mean()
            else:
                return None
            s.index = s.index.tz_convert("UTC").tz_localize(None)
            return s
    return None


def main():
    days = []
    for a, b in PERIODS:
        days += list(pd.date_range(a, b, freq="D"))
    print(f"{len(days):,} days to read (files already on disk are not downloaded again)")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        paths = []
        for i, p in enumerate(ex.map(download_day, days), 1):
            paths.append(p)
            if i % 100 == 0:
                print(f"   {i:,}/{len(days):,} days done  ({time.time() - t0:.0f} s)")

    parts, bad_days = [], []
    for d, p in zip(days, paths):
        s = parse_day(p) if p else None
        if s is None:
            bad_days.append(d)
        else:
            parts.append(s)
    print(f"Days read correctly: {len(parts):,} | days without a usable file: {len(bad_days)}")
    if bad_days:
        print("   first problem days:", [f"{d:%Y-%m-%d}" for d in bad_days[:10]])
    if not parts:
        raise SystemExit("No price could be read: send me the first lines of one file in data/omie_raw/")

    price = pd.concat(parts)
    price = price[~price.index.duplicated()].sort_index()

    grid = pd.DatetimeIndex([])
    for a, b in PERIODS:
        grid = grid.union(pd.date_range(f"{a} 00:00", f"{b} 23:00", freq="h"))
    raw = price.reindex(grid)
    month = raw.index.to_period("M")
    monthly = raw.groupby(month).transform("mean")
    monthly[raw.groupby(month).transform("count") < MIN_HOURS_FOR_MONTHLY_AVERAGE] = float("nan")   # too little data: no average
    filled = raw.fillna(monthly)

    out = pd.DataFrame({"timestamp_utc": grid,
                        "price_eur_mwh": filled.values,
                        "price_eur_mwh_is_fallback": (raw.isna() & filled.notna()).values})
    n_missing, n_fb, n_left = int(raw.isna().sum()), int(out["price_eur_mwh_is_fallback"].sum()), int(filled.isna().sum())
    print(f"\nHours: {len(grid):,} | without OMIE price: {n_missing:,} | filled with monthly average: {n_fb:,} | still empty: {n_left:,}")
    print(out["price_eur_mwh"].describe().round(1).to_string())

    out.to_parquet(DATA / "prices_co2_hourly.parquet", index=False)
    out.to_csv(DATA / "prices_co2_hourly.csv", index=False)
    print("\nSUMMARY (to copy in Jira):")
    print(f"  price_eur_mwh: {len(grid):,} hours, {n_missing:,} missing at source, {n_fb:,} filled with monthly average, {n_left:,} left empty")
    print("Saved data/prices_co2_hourly.parquet and data/prices_co2_hourly.csv")


if __name__ == "__main__":
    main()
