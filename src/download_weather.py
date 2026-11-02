"""
KAN-55  Madrid hourly weather data (Open-Meteo)

Downloads hourly outdoor weather for the Montegancedo campus from the free Open-Meteo
Historical Weather API and saves it to  data/weather_hourly.parquet  (+ a .csv copy).

 * Times are requested in UTC, so they can be joined directly to 'timestamp_utc' of the building table.
 * Only the two periods that exist in our building data are downloaded (with a small margin):
       Period A  2020-04-02 .. 2023-02-28      Period B  2025-08-18 .. 2025-10-13
 * Needs only Python standard library + pandas + pyarrow (no extra install).

Usage (from the project folder, in the PyCharm Terminal):
    python src/download_weather.py
"""
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

# The URL can be overridden (only used to test the script offline).
API_URL = os.environ.get("OPEN_METEO_URL", "https://archive-api.open-meteo.com/v1/archive")

# Montegancedo campus (UPM), approximate. Open-Meteo uses a grid of ~10 km, so a few hundred metres do not matter.
LATITUDE, LONGITUDE = 40.405, -3.836

# column name in Open-Meteo  ->  our column name (prefix wx_ = weather, so it is not confused with indoor sensors)
VARIABLES = {
    "temperature_2m": "wx_temp_c",             # air temperature, deg C
    "apparent_temperature": "wx_feels_like_c", # "feels like" temperature, deg C
    "relative_humidity_2m": "wx_humidity_pct", # %
    "precipitation": "wx_precip_mm",           # mm in the previous hour
    "cloud_cover": "wx_cloud_pct",             # %
    "wind_speed_10m": "wx_wind_ms",            # m/s (we ask for m/s below)
    "shortwave_radiation": "wx_solar_wm2",     # sun power on a horizontal surface, W/m2
    "surface_pressure": "wx_pressure_hpa",     # hPa
}

# (start, end) of the chunks to download. One request per calendar year keeps every request small.
CHUNKS = [
    ("2020-04-01", "2020-12-31"),
    ("2021-01-01", "2021-12-31"),
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-03-01"),
    ("2025-08-17", "2025-10-14"),
]


def fetch_chunk(start, end, tries=4):
    params = {
        "latitude": LATITUDE, "longitude": LONGITUDE,
        "start_date": start, "end_date": end,
        "hourly": ",".join(VARIABLES),
        "timezone": "UTC",
        "wind_speed_unit": "ms",
    }
    url = API_URL + "?" + urllib.parse.urlencode(params, safe=",")
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                payload = json.load(resp)
            if "hourly" not in payload:
                raise RuntimeError(f"unexpected answer: {str(payload)[:300]}")
            return payload
        except Exception as exc:                      # network problem, rate limit, ...
            print(f"   attempt {attempt}/{tries} failed: {exc}")
            if attempt == tries:
                raise
            time.sleep(5 * attempt)                   # wait a bit and retry


def payload_to_frame(payload):
    h = payload["hourly"]
    df = pd.DataFrame({"timestamp_utc": pd.to_datetime(h["time"])})
    for api_name, our_name in VARIABLES.items():
        df[our_name] = pd.to_numeric(pd.Series(h[api_name]), errors="coerce")
    return df


def main():
    parts = []
    for start, end in CHUNKS:
        print(f"Downloading {start} .. {end} ...")
        payload = fetch_chunk(start, end)
        part = payload_to_frame(payload)
        print(f"   {len(part):,} hours  (grid point {payload.get('latitude')}, {payload.get('longitude')}, "
              f"elevation {payload.get('elevation')} m)")
        parts.append(part)
        time.sleep(1)                                 # be gentle with the free service

    w = pd.concat(parts, ignore_index=True)
    w = w.drop_duplicates("timestamp_utc").sort_values("timestamp_utc").reset_index(drop=True)

    # ---- checks ----
    assert w["timestamp_utc"].is_unique
    assert w["timestamp_utc"].dt.minute.eq(0).all(), "all times should be on the hour"
    n_nan = int(w.drop(columns="timestamp_utc").isna().sum().sum())
    print(f"\nWeather table: {len(w):,} hours x {w.shape[1]-1} variables, empty values: {n_nan}")
    print(w.describe().T[["min", "mean", "max"]].round(1))

    w.to_parquet(DATA / "weather_hourly.parquet", index=False)
    w.to_csv(DATA / "weather_hourly.csv", index=False)
    print("\nSaved data/weather_hourly.parquet and data/weather_hourly.csv")


if __name__ == "__main__":
    main()
