# Pipeline, cleaning decisions, model and detection rules (KAN-142, KAN-103)

This page explains, in plain terms, how we go from the four raw Excel files to alerts with a € and CO₂ value,
and **why** we made each choice. The experiments behind the choices are in the [experiment log](EXPERIMENT_LOG.md);
every column is described in the [data dictionary](DATA_DICTIONARY.md).

## 1. The pipeline at a glance

```
4 raw Excel files (one per zone)
   │  1. combine and unify           src/save_parquet.py (loader.py, unify.py)
   │  2. build one hourly table      ** script missing in the repo **
   │  3. clean (rules R1–R12)        src/clean.py
   │  4. add calendar                src/build_calendar.py
   │  5. add outdoor weather         src/download_weather.py
   │  6. add electricity prices      src/download_price_omie.py
   │  7. merge everything            src/merge_external.py
   │  8. freeze dataset v1           src/freeze_dataset.py  → data/processed/cedint_hourly_v1.parquet
   ▼
Notebook 01  Exploration: what drives electricity use?
Notebook 02  Expected use per circuit (baselines → Ridge → LightGBM)
Notebook 03  Alerts, chronic waste, € and CO₂   → reports/*.csv (input for the dashboard)
```

Each step writes a file that the next step reads, so any step can be re-run on its own.
The frozen dataset comes with a `MANIFEST.json` that stores a fingerprint (SHA-256) of every input and output file,
so anyone can check that they are using exactly the same data. `pytest` runs automatic checks on it
(no duplicate hours, correct grid, no leakage in the features).

**Known gap:** step 2 (turning the 2025 minute readings into hours and building the hourly table) was done,
but its script is not in the repo yet. Until it is pushed, the pipeline cannot be rebuilt from the raw files.

## 2. Cleaning decisions (KAN-103)

### Principles

- **Never invent data.** A wrong or missing value becomes an empty cell, not a guess. An empty cell means "unknown", not zero.
- **Never change the raw files.** Every removed value can still be found in the raw data.
- **Every rule has a number and a count**, so the effect of each decision is visible.

### The two data periods

| | Period A | Period B |
|---|---|---|
| Dates | 2 Apr 2020 – 28 Feb 2023 | 18 Aug – 13 Oct 2025 |
| Readings | one reading per hour | up to one per minute, averaged to one value per hour |
| Hours | 25,489 | 1,341 |

There is **no data at all between March 2023 and August 2025** (901 days). This gap is in the source files.
Because of it, the two periods are never joined: features that look back in time (e.g. "last week") stop at the gap.
Period A is used to build the models, period B to check them on recent data.

### Rules applied

| Rule | Problem found | Decision | Why | Values touched |
|---|---|---|---|---|
| R1 | Timestamps have no time zone | Treated as UTC; Madrid local time added | No jumps at the daylight-saving changes, and light sensors match sunrise and sunset in UTC (`src/check_utc.py`) | all rows |
| R2 | Some hours are missing | Complete hourly grid; missing hours left empty | So every analysis sees the gaps instead of skipping them | 524 empty hours |
| R3 | Two circuits measure nothing useful | SE Projector (always 0) and SW RACK (stops 3 Dec 2021) removed | No information | 2 circuits |
| R4 | NW Emergency Lighting is negative 97.7 % of the time | Sign flipped | The meter is wired in reverse; a lamp cannot produce energy | 24,230 |
| R5 | Small negative values (−10 to 0 W) | Set to 0 | Meter noise around zero | 31,870 |
| R6 | Larger negative values (below −10 W) | Set to empty | Not noise; a real error | 4 |
| R7 | Same non-zero value for 6+ hours | Set to empty (period A) | A stuck sensor | 0 found |
| R8 | 6+ hours of exact 0 on a circuit that normally uses power | Set to empty | Sensor off, not real zero use | 3,694 |
| R9 | Temperature, humidity and light all 0 together | Set to empty | Sensor failure | safeguard |
| R10 | Indoor temperature of 739–1,411 °C (SW, 1–7 Mar 2022) | Values outside the allowed range set to empty | Impossible values | see note below |
| R11 | 2025 hours built from few minute readings | Flagged `low_coverage` (kept) | The hourly average is less reliable | 611 |
| R12 | Totals in the raw file include bad values | Zone and storey totals recalculated from clean circuits, only when all circuits are present | A total with a missing part would look like a drop in use | all totals |

### What we checked and did *not* change

| Finding | Decision | Reason |
|---|---|---|
| Energy counters (`Ea`, `Er`) reset and jump | Not used at all; energy per hour is taken from the average power `W` | Where the counters work, both give the same result (ratio 1.00), and `W` has no resets |
| Presence sensors stuck at 1.0 for weeks (NW, SE, SW) | Kept, but **not used** in models or conclusions | Presence cannot be 100 % for 83 days; this is a sensor fault |
| SW humidity identical for up to 71 days | Kept, not used | Stuck or insensitive sensor |
| NE Plugs drops from about 190 W to 25 W for whole days (10 periods) | Kept | Plausible (load switched off) but cannot be confirmed |
| NW Plugs peaks up to 8.25 kW in January 2023 | Kept | Neighbouring hours are consistent, so they look real (heaters) |
| COVID lockdown (spring 2020) | Kept in the data, flagged, left out of model training | The building was not used normally |

### Open points (to settle in the group)

1. **R10 threshold differs between two versions.** `src/clean.py` removes indoor temperatures outside 5–45 °C.
   The cleaned Excel file uses 0–45 °C and keeps 70 hours of 3.8–5 °C in January 2021 (a real cold wave).
   We should agree on one value.
2. **Extra rule in the Excel file only:** it also blanks 934 hours where NW Emergency Lighting reads about 0 W
   (Dec 2021, Feb–Apr 2022). This rule is not in `src/clean.py`. Agree whether to add it.
3. **Calendar dates:** the Christmas break (until 6 January) and the whole-August closure look wrong in places.
4. **Missing script** for step 2 (see above).

## 3. The model: what is "normal" use?

To say that something is wasted, we first need to know how much each circuit *normally* uses at a given hour.
The model predicts this **expected** use; the gap between actual and expected is what we look at.

| | |
|---|---|
| What we predict | energy used per hour per circuit (Wh), one day ahead |
| Circuits | 9 "focus" circuits: Plugs & Sockets (all 4 zones), Lighting (NW, SW, SE), HVAC (NW, SE) |
| Information the model uses | hour, day of the week, working day / holiday / break, season, outdoor temperature (and how far it is below or above a comfortable level), sunlight, humidity, and the circuit's own use 1 day, 2 days, 1 week and 2 weeks earlier |
| Information it may **not** use | anything from the same hour (that would be cheating), indoor sensors (they are effects of the use, not causes), anything across the 2023–2025 gap |
| Final model | **LightGBM** (gradient-boosted decision trees), one model per circuit |
| Why this model | beats the simple "same as last week" methods on most circuits; Ridge (linear regression) comes close, which shows the model is not over-complicated; results barely change with different settings |
| How we tested | trained on Jun 2020 – Aug 2022, settings chosen on Sep – Dec 2022, tested once on Jan – Feb 2023, then checked on Aug – Oct 2025 |
| Main metric | MAE in kWh: the average miss, in the unit the client thinks in |

**Honest limitation:** hour by hour, the model is still off by more than the 30 % that the industry guideline ASHRAE 14
asks for, on most circuits. The main reason is people: heaters and lights are switched on and off by hand.
For finding *large* waste this is good enough (see the synthetic test below), but it should be said in the presentation.

## 4. Detection rules: from "unusual" to "alert"

We use **two signals**, because one model cannot see everything.

### Signal 1 — Events (something unusual today)

1. For every hour: **miss = actual − expected**.
2. An hour is flagged when its miss is far above the normal spread of misses **for that circuit and that type of hour**
   (working hours or off-hours). Normal misses are about twice as big during working hours, so one threshold for
   all hours would either miss night waste or flood the manager with daytime alarms.
3. Flagged hours close together (gap ≤ 1 h) become one **event**. An event must last at least 2 hours and be at
   least 0.5 kWh above expected (smaller events are worth less than €0.07).
4. **How strict?** For each circuit we chose the threshold that gives **about one event per week** at most.
   A building manager stops reading alarms if there are too many.

**Tested with fake loads:** we added 40 fake "forgotten devices" at night (1 kW on plug circuits, 300 W on lights and HVAC)
and checked whether the detector found them. It found 98–100 % on 7 of the 9 circuits. On NW Plugs, the noisiest circuit,
one heater is found only 32 % of the time, but 2 kW is found 85 % of the time.

### Signal 2 — Chronic off-hours waste (the same thing every week)

A model that looks at last week's use slowly learns repeated waste (heaters on a timer every weekend) as "normal".
So we add a simple, transparent rule:

- **Standby level** = the lowest level the circuit reaches at night when nobody is there
  (10th percentile of night-time use in the training period). Examples: NW Plugs ≈ 415 W, SE Plugs ≈ 100 W, lighting ≈ 0.
- **Off-hours** = nights 22:00–06:00, weekends, holidays and breaks.
- **Chronic waste** = everything above the standby level during off-hours.

### Severity

| Severity | Excess energy per event |
|---|---|
| Low | under 2 kWh |
| Medium | 2 – 10 kWh |
| High | over 10 kWh |

Thresholds are in `params.yaml` and can be changed without touching the code.

### Value in € and CO₂

| | How | Source |
|---|---|---|
| € (lower bound) | excess kWh × hourly wholesale price | OMIE (energy only, no network costs or taxes) |
| € (all-in) | excess kWh × €0.142/kWh | Eurostat non-household price |
| CO₂ | excess kWh × Spanish grid emission factor (259–273 g/kWh by year) | CNMC grid mix, **placeholder to confirm** (KAN-134) |

Events during working hours are shown as "to investigate" but **not** counted as savings, because part of that use is legitimate.

### Outputs (input for the dashboard)

| File | Content |
|---|---|
| `reports/anomaly_events.csv` | one row per event: circuit, start, end, excess kWh, €, kg CO₂, severity, message |
| `reports/offhours_waste_daily.csv` | chronic waste per circuit per day |
| `reports/savings_summary.csv` | potential savings per zone, circuit and year |

## 5. Main results

| Year | Potential savings (9 focus circuits) | € | CO₂ |
|---|---|---|---|
| 2021 | 7.2 MWh (32 % of their use) | €740 – 1,020 | 1.9 t |
| 2022 | 6.0 MWh (27 % of their use) | €850 – 1,010 | 1.6 t |

Biggest lever: **electric heaters on the NW plug circuits** at night, at weekends and in breaks (3–4 MWh per year),
then the **NW lights that are on every night** 22:00–07:00 (about 1 MWh per year).

## 6. Limitations

- There is no list of confirmed waste, so the detector is validated with fake loads and a manual check of the largest events.
- "Potential" savings are an upper estimate: part of the off-hours use above standby may be legitimate (late work, equipment that must stay on).
- The calendar assumptions look wrong in places; alerts on holidays must be read with care.
- The CO₂ factor and the all-in price are placeholders to confirm.
- The building is used differently in 2025 than in 2020–2023; the model must be retrained on recent data before going live.
- **Two definitions of "closed" exist in the project:** the Product Backlog (F1.1) uses opening hours Mon–Fri 08:00–20:00,
  while the detection code uses nights 22:00–06:00. The group should agree on one, because it changes the waste figures.
