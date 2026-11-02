# Data dictionary — `cedint_hourly_v1` (KAN-129)

This page describes every column of the frozen modelling dataset
`data/processed/cedint_hourly_v1.parquet`: what it means, its unit, and where it comes from.
Technical details (checksums, build steps, missing shares) are in `data/processed/MANIFEST.json`.

## The dataset in short

| | |
|---|---|
| One row = | one hour on Storey 1 of the CeDInt building (UPM, Montegancedo campus) |
| Rows / columns | 26,830 rows · 64 columns |
| Period A (Regime A) | 2 Apr 2020 – 28 Feb 2023, hourly readings (25,489 rows) |
| Period B (Regime B) | 18 Aug 2025 – 13 Oct 2025, minute readings combined into hours (1,341 rows) |
| Gap | No data between March 2023 and August 2025. This gap is in the original files, not caused by cleaning. |
| Missing hours | Kept as empty rows, never filled in (cleaning rule R2) |

## How to read the electricity columns

Electricity columns are named `ZONE|Circuit W`, for example `NW|Plugs & Sockets W`.

- **Zone**: one of the four parts of Storey 1: NE, NW, SE, SW.
- **Circuit**: the type of equipment on that electrical circuit (see below).
- **Value**: the average power used during that hour, in watts (W). Because it is an average over one hour,
  the same number is also the energy used in that hour in watt-hours (Wh). Divide by 1,000 to get kWh.

We use this average power instead of the meters' own energy counters (`Ea`), because those counters
sometimes reset or jump. Both give the same result where the counters work correctly.

## 1. Time columns

| Column | Meaning | Unit / values |
|---|---|---|
| `timestamp_utc` | Start of the hour in UTC (the time zone of the raw files, checked against sunrise and sunset in `src/check_utc.py`) | date and time |
| `timestamp_local` | Same hour in Madrid local time, including summer time | date and time |
| `date_local` | Local date | date |
| `weekday_local` | Day of the week, local time | 0 = Monday … 6 = Sunday |
| `hour_local` | Hour of the day, local time | 0–23 |
| `month` | Month | 1–12 |
| `Regime` | Which data period the row belongs to | `A` (2020–23, hourly) or `B` (2025, minute data) |
| `low_coverage` | Period B only: the hour was built from fewer than 30 one-minute readings, so treat it with care (rule R11) | True / False |

## 2. Electricity per circuit (16 circuits)

All values: average power in the hour [W] = energy in that hour [Wh].
"Missing" is the share of hours without a usable value.

| Column | What it is | Missing | Notes |
|---|---|---|---|
| `NE\|HVAC W` | Heating, ventilation and air conditioning, zone NE | 2.0 % | |
| `NE\|Plugs & Sockets W` | Wall sockets (computers, screens, portable heaters…), zone NE | 2.0 % | |
| `NW\|Emerg. Lighting W` | Emergency and exit lighting, zone NW | 13.0 % | Must run 24/7, not counted as waste. Meter was wired in reverse; sign corrected (R4) |
| `NW\|HVAC W` | Heating, ventilation and air conditioning, zone NW | 7.6 % | |
| `NW\|Hand Dryer W` | Hand dryers, zone NW | 2.0 % | Small, short bursts of use |
| `NW\|Lighting W` | Ceiling lighting, zone NW | 2.0 % | On every night 22:00–07:00 (see EDA) |
| `NW\|Plugs & Sockets W` | Wall sockets, zone NW | 2.0 % | Largest consumer of the floor (about 45 %); rises sharply in cold weather |
| `NW\|RACK W` | Server / network rack, zone NW | 2.0 % | Must run 24/7, not counted as waste |
| `SE\|Emerg. Lighting W` | Emergency and exit lighting, zone SE | 7.7 % | Must run 24/7, not counted as waste |
| `SE\|HVAC W` | Heating, ventilation and air conditioning, zone SE | 7.6 % | |
| `SE\|Lighting W` | Ceiling lighting, zone SE | 4.1 % | |
| `SE\|Plugs & Sockets W` | Wall sockets, zone SE | 8.3 % | |
| `SW\|Emerg. Lighting W` | Emergency and exit lighting, zone SW | 4.9 % | Must run 24/7, not counted as waste |
| `SW\|Hand Dryer W` | Hand dryers, zone SW | 4.9 % | |
| `SW\|Lighting W` | Ceiling lighting, zone SW | 5.2 % | |
| `SW\|Plugs & Sockets W` | Wall sockets, zone SW | 4.7 % | |

Two circuits from the raw files were removed (rule R3): `SE|Projector` (always 0) and `SW|RACK`
(stops sending data in December 2021).

## 3. Totals

Totals are recalculated from the cleaned circuits, and only for hours where every circuit of that zone
has a value (rule R12). That is why they have more missing hours than the single circuits.

| Column | What it is | Missing |
|---|---|---|
| `NE\|ZONE TOTAL W` | Sum of all circuits in zone NE | 2.0 % |
| `NW\|ZONE TOTAL W` | Sum of all circuits in zone NW | 13.0 % |
| `SE\|ZONE TOTAL W` | Sum of all circuits in zone SE | 11.4 % |
| `SW\|ZONE TOTAL W` | Sum of all circuits in zone SW | 6.4 % |
| `STOREY1\|TOTAL W` | Sum of the four zones | 21.4 % |

Unit: average power in the hour [W] = energy in that hour [Wh].

## 4. Indoor environment sensors (zones NW, SE, SW)

| Column pattern | Meaning | Unit | Notes |
|---|---|---|---|
| `ZONE\|ENV Temp °C` | Indoor temperature | °C | Values outside 5–45 °C removed (R10) |
| `ZONE\|ENV Hum %RH` | Indoor relative humidity | % | |
| `ZONE\|ENV Lum lux` | Indoor light level | lux | |
| `ZONE\|ENV Pres share` | Share of the hour in which presence was detected | 0–1 | **Not reliable**: sensors get stuck for weeks and do not follow working hours. Not used in the models. |

If temperature, humidity and light are all exactly 0 at the same time, the reading is treated as missing (R9).
Indoor temperature and light are partly *caused by* the electricity use (heaters, lamps), so they are not
used to predict it.

## 5. Outdoor weather

Source: Open-Meteo historical archive for the Montegancedo campus (`src/download_weather.py`).

| Column | Meaning | Unit |
|---|---|---|
| `wx_temp_c` | Outdoor temperature | °C |
| `wx_feels_like_c` | Felt temperature | °C |
| `wx_humidity_pct` | Outdoor relative humidity | % |
| `wx_precip_mm` | Rain / precipitation in the hour | mm |
| `wx_cloud_pct` | Cloud cover | % |
| `wx_wind_ms` | Wind speed | m/s |
| `wx_solar_wm2` | Sunlight reaching the ground | W/m² |
| `wx_pressure_hpa` | Air pressure | hPa |

## 6. Calendar

Source: `src/build_calendar.py`. All flags are True / False for the local date.

| Column | Meaning |
|---|---|
| `is_weekend` | Saturday or Sunday |
| `is_holiday_national_madrid` | National or Community of Madrid public holiday |
| `is_holiday_madrid_city` | Madrid city holiday |
| `is_upm_nonteaching_day` | UPM-specific day without teaching (e.g. Santo Tomás) |
| `is_holiday` | Any of the three holiday flags above |
| `is_christmas_break` | UPM Christmas break |
| `is_holy_week` | Holy Week (Semana Santa) |
| `is_august_closure` | August closure |
| `is_break` | Any of the three break flags above |
| `is_working_day` | Not a weekend, holiday or break |
| `is_covid_lockdown` | COVID-19 lockdown (until 21 June 2020). Separate flag, not included in `is_working_day`; these weeks are left out of model training |
| `holiday_name` | Name of the holiday, if any | 
| `academic_year` | UPM academic year, starting in September (e.g. `2021-22`) |

⚠️ **To check:** the Christmas break and August closure dates look too wide in places
(normal working days appear on 2 Jan 2023, and lighting is used on weekdays in August 2025).
See `docs/STATUS_AUDIT.md`.

## 7. Electricity price

Source: OMIE, the Spanish day-ahead electricity market (`src/download_price_omie.py`).

| Column | Meaning | Unit |
|---|---|---|
| `price_eur_mwh` | Wholesale electricity price for that hour. Energy only: no network costs or taxes, so the real cost is higher. | € per MWh |
| `price_eur_mwh_is_fallback` | True when OMIE had no price for that hour and the monthly average was used instead. If a month has fewer than 7 days of real prices, the hours stay empty. | True / False |

The CO₂ factor and the all-in price used for the € and CO₂ figures are not in this dataset;
they are set in `params.yaml`.

## Cleaning rules referred to above

| Rule | What it does |
|---|---|
| R1 | Raw timestamps treated as UTC; Madrid local time added |
| R2 | Complete hourly grid; missing hours left empty, not filled in |
| R3 | Dead circuits removed (SE Projector, SW RACK) |
| R4 | NW emergency lighting sign flipped (meter wired in reverse) |
| R5 | Small negative values (−10 to 0 W) set to 0 |
| R6 | Large negative values (below −10 W) set to missing |
| R7 | Same non-zero value for 6 hours or more (stuck sensor) set to missing (period A) |
| R8 | 6 hours or more of 0 on a circuit that normally uses power set to missing |
| R9 | Temperature, humidity and light all 0 together set to missing |
| R10 | Indoor temperature outside 5–45 °C set to missing |
| R11 | Period B hours built from fewer than 30 minute readings flagged `low_coverage` |
| R12 | Zone and floor totals recalculated from clean circuits |
