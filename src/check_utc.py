"""
Is 'timestamp_utc' really UTC?   (open question for the professor, KAN-122)

Idea: the light sensors measure daylight. Daylight follows the sun, and the sun's position at a given
UTC time is known exactly (astronomy). If the building timestamps are UTC, the sensor curve and the sun curve
line up with NO shift. If the timestamps were local Madrid time, the curve would be shifted by 1 h in winter
and 2 h in summer.

No internet and no weather file needed: the sun height is computed with a standard formula.

Usage:  python src/check_utc.py            (needs data/clean_hourly_wide.parquet)
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LAT, LON = 40.405, -3.836                      # Montegancedo campus


def sun_height_factor(ts_utc):
    """sin(sun elevation), 0 when the sun is below the horizon.  (NOAA simplified formula)"""
    t = pd.DatetimeIndex(ts_utc)
    doy = t.dayofyear.values
    hour = t.hour.values + t.minute.values / 60
    g = 2 * math.pi / 365 * (doy - 1 + (hour - 12) / 24)
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    eqtime = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                       - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))       # minutes
    solar_minutes = hour * 60 + eqtime + 4 * LON                                    # true solar time
    hour_angle = np.radians(solar_minutes / 4 - 180)
    lat = math.radians(LAT)
    sin_elev = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(hour_angle)
    return np.clip(sin_elev, 0, None)


df = pd.read_parquet(ROOT / "data" / "clean_hourly_wide.parquet")
a = df[df["Regime"] == "A"].set_index("timestamp_utc")          # period A: 1 sample per hour, 2020-2023

print("Correlation between the light sensor and the sun, when the sensor time is moved by N hours")
print("(the highest value tells which time the sensor clock really uses; 0 = UTC)\n")
for col in ["NW|ENV Lum lux", "SW|ENV Lum lux", "SE|ENV Lum lux"]:
    best = None
    out = []
    for shift in range(-3, 4):
        # building row at time t compared with the sun at time t+shift
        sun = pd.Series(sun_height_factor(a.index + pd.Timedelta(hours=shift)), index=a.index)
        c = a[col].corr(sun)
        out.append((shift, c))
        if best is None or c > best[1]:
            best = (shift, c)
    print(col, " ".join(f"{s:+d}h:{c:.3f}" for s, c in out), f"  -> best shift {best[0]:+d} h")

print("\nSame test split by season (all three sensors together):")
print("  if the clock were Madrid local time we would expect about -2 h in summer and -1 h in winter; UTC gives 0 in both")
for months, label in [((6, 7, 8), "summer"), ((12, 1, 2), "winter")]:
    sub = a[a.index.month.isin(months)]
    res = []
    for shift in range(-3, 4):
        sun = pd.Series(sun_height_factor(sub.index + pd.Timedelta(hours=shift)), index=sub.index)
        cs = [sub[c].corr(sun) for c in ["NW|ENV Lum lux", "SW|ENV Lum lux", "SE|ENV Lum lux"]]
        res.append((shift, float(np.nanmean(cs))))
    best = max(res, key=lambda r: r[1])
    print(f"  {label}: best shift {best[0]:+d} h   " + " ".join(f"{sh:+d}h:{c:.3f}" for sh, c in res))
