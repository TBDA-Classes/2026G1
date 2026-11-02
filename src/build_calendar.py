"""
KAN-56  Spanish/Madrid holidays and UPM academic calendar (incl. closures, COVID)

Builds one row per DAY (2020-04-01 .. 2025-10-31) with holiday / closure flags and saves
data/calendar_daily.parquet (+ .csv, easy to open in Excel).

Needs:  pip install holidays        (library with the official Spanish public holidays)

Usage:  python src/build_calendar.py

WHAT IS CHECKED AND WHAT IS AN ASSUMPTION  (also written in the 'note' printed at the end)
  verified in official sources
    * national + Madrid-region holidays  -> from the 'holidays' library, cross-checked with the
      official lists of UPM (2021-22, 2022-23, 2025-26) and the BOCM (Madrid official bulletin 2022, 2023)
    * Madrid-city local holidays: 15 May (San Isidro) and 9 Nov (Almudena); UPM lists both as non-teaching days
      (in 2025 the Almudena was moved from Sunday 9 Nov to Monday 10 Nov, as in the UPM calendar)
    * 28 Jan Santo Tomas de Aquino (UPM non-teaching day every year)
    * state of alarm / COVID lockdown ended on 21 June 2020 (UPM rector's letter of 20 June 2020)
  ASSUMPTIONS (edit the block below if the group knows the real dates)
    * Christmas closure 24 Dec - 6 Jan, Holy Week closure Monday-Sunday of Holy Week, August closure 1-31 Aug.
      The UPM calendars show these breaks only as a drawing, without written dates.
"""
from datetime import date, timedelta
from pathlib import Path

import holidays
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

START, END = "2020-04-01", "2025-10-31"

# ------------------------- ASSUMPTIONS (edit here) -------------------------
CHRISTMAS_BREAK = ((12, 24), (1, 6))        # from 24 Dec to 6 Jan (inclusive)
AUGUST_CLOSURE = ((8, 1), (8, 31))          # whole of August
HOLY_WEEK_FROM_MONDAY = True                # Holy Week = Monday before Easter Sunday .. Easter Sunday
COVID_LOCKDOWN_END = date(2020, 6, 21)      # last day of the state of alarm (verified)
# ---------------------------------------------------------------------------

days = pd.date_range(START, END, freq="D")
years = sorted(set(days.year))

# ---- national + Madrid-region public holidays (official, includes moves from Sunday to Monday) ----
public = holidays.Spain(subdiv="MD", years=years, language="en_US")

# ---- Madrid-city local holidays and UPM non-teaching days ----
local = {}
for y in years:
    local[date(y, 5, 15)] = "San Isidro (Madrid city)"
    nov9 = date(y, 11, 9)
    local[nov9 + timedelta(days=1) if nov9.weekday() == 6 else nov9] = "La Almudena (Madrid city)"
upm_extra = {date(y, 1, 28): "Santo Tomas de Aquino (UPM)" for y in years}


def _easter(y):                                    # standard Gauss/Meeus algorithm (Western Easter)
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(y, month, day)


holy_week = set()
for y in years:
    easter = _easter(y)
    for k in range(7):                              # Monday .. Sunday of Holy Week
        holy_week.add(easter - timedelta(days=6 - k))


def in_range(d, rng):
    (m1, d1), (m2, d2) = rng
    md = (d.month, d.day)
    return (md >= (m1, d1) or md <= (m2, d2)) if (m1, d1) > (m2, d2) else ((m1, d1) <= md <= (m2, d2))


rows = []
for ts in days:
    d = ts.date()
    names = []
    if d in public: names.append(public[d])
    if d in local: names.append(local[d])
    if d in upm_extra: names.append(upm_extra[d])
    rows.append({
        "date_local": ts,
        "weekday": ts.weekday(),                                   # 0 = Monday ... 6 = Sunday
        "is_weekend": ts.weekday() >= 5,
        "is_holiday_national_madrid": d in public,                 # national + Madrid region
        "is_holiday_madrid_city": d in local,                      # San Isidro, Almudena
        "is_upm_nonteaching_day": d in upm_extra,                  # Santo Tomas
        "is_christmas_break": in_range(d, CHRISTMAS_BREAK),
        "is_holy_week": d in holy_week,
        "is_august_closure": in_range(d, AUGUST_CLOSURE),
        "is_covid_lockdown": d <= COVID_LOCKDOWN_END,
        "holiday_name": "; ".join(names),
    })

cal = pd.DataFrame(rows)

# one summary flag: is it a normal working day for the building?
cal["is_holiday"] = cal[["is_holiday_national_madrid", "is_holiday_madrid_city", "is_upm_nonteaching_day"]].any(axis=1)
cal["is_break"] = cal[["is_christmas_break", "is_holy_week", "is_august_closure"]].any(axis=1)
cal["is_working_day"] = ~(cal["is_weekend"] | cal["is_holiday"] | cal["is_break"])

# academic year label (course starts in September)
cal["academic_year"] = [f"{d.year}-{str(d.year + 1)[2:]}" if d.month >= 9 else f"{d.year - 1}-{str(d.year)[2:]}"
                        for d in cal["date_local"]]

# ---- checks ----
assert cal["date_local"].is_unique
assert len(cal) == (pd.Timestamp(END) - pd.Timestamp(START)).days + 1
print(f"Calendar: {len(cal):,} days, {START} .. {END}")
for c in ["is_weekend", "is_holiday", "is_holiday_national_madrid", "is_holiday_madrid_city", "is_upm_nonteaching_day",
          "is_christmas_break", "is_holy_week", "is_august_closure", "is_covid_lockdown", "is_working_day"]:
    print(f"  {c:30s} {int(cal[c].sum()):5d} days")

cal.to_parquet(DATA / "calendar_daily.parquet", index=False)
cal.assign(date_local=cal["date_local"].dt.strftime("%Y-%m-%d")).to_csv(DATA / "calendar_daily.csv", index=False)
print("Saved data/calendar_daily.parquet and data/calendar_daily.csv")
