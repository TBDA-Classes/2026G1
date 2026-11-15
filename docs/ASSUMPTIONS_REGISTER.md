# Assumptions and decisions register (KAN-91 · quality requirements Q2, Q5)

Every assumption behind the € and CO₂ figures, the waste definition and the alerts, in one place:
the value, where it is set, its source, its status, and what happens to the result if it changes.
The values themselves live in `params.yaml` or in the code named below, so changing them updates every figure (Q5).

**Status:** ✅ checked in data or code · 📄 published source · ⚠️ assumption, to confirm · ❓ decision needed from the sponsor

## Data and time

| ID | Assumption | Value | Where set | Source / evidence | Status | If it changes |
|---|---|---|---|---|---|---|
| A1 | Period for yearly figures | 2021 and 2022: the only complete calendar years without lockdown | notebook 03, section 6 | data coverage 96–100 % of hours | ✅ | 2020 and 2023 are incomplete years |
| A2 | Timestamps | raw data are UTC, shown in Europe/Madrid | `src/clean.py` R1–R2 | `src/check_utc.py`: light sensors follow the sun in UTC | ✅ | a 1–2 h shift moves use between "open" and "closed" |
| A3 | Energy per hour | mean power `W` of the hour = Wh | `src/clean.py` | median ΔEa / W = 1.00 in 2020–23; avoids the `Ea` counter resets | ✅ | – |
| A4 | Circuits counted | 9 focus circuits (Plugs NW, SW, SE, NE; Lighting NW, SW, SE; HVAC NW, SE) | `src/data.py` (`FOCUS`) | emergency lighting and server rack must run 24/7; hand dryers and NE HVAC are tiny; SE projector has no data | ✅ | – |
| A5 | Lockdown | hours until 21 Jun 2020 left out | `src/build_calendar.py` | not normal use of the building | ✅ | – |

## Waste definition

| ID | Assumption | Value | Where set | Source / evidence | Status | If it changes |
|---|---|---|---|---|---|---|
| A6 | Which hours are "closed" | nights 22:00–05:59, weekends, holidays, UPM breaks | `src/data.py` (`NIGHT_HOURS`). `params.yaml` → `off_hours.night_hours` repeats it, but the code does not read it yet (Q5 gap) | chosen narrow so as not to count evening work as waste | ❓ | the backlog (F1.1) used outside Mon–Fri 08:00–20:00 (Sprint 2 estimate: 59 % of use while closed, now 47–54 %) |
| A7 | Holidays and breaks | Madrid and national holidays, UPM non-teaching days, Christmas until 6 Jan, Holy Week, all of August | `src/build_calendar.py` | UPM academic calendar | ⚠️ KAN-56 | 2 Jan 2023 and August 2025 look like normal working days: fewer closed days → slightly less waste |
| A8 | Standby level | 10th percentile of night use in the training period, per circuit (NW Plugs ≈ 415 W, SE Plugs ≈ 100 W, lighting ≈ 0) | `params.yaml` → `off_hours.standby_percentile` | "the level a circuit reaches when almost everything is off" | ⚠️ | 5th pct: 7.0–8.3 MWh · 20th: 5.5–6.4 · 30th: 5.1–5.9 MWh a year (now 6.0–7.2) |
| A9 | Working-hours events | shown as "to investigate", **not** counted as savings | notebook 03, section 6 | part of daytime use is legitimate | ✅ decision | counting them would add 0.7–1.4 MWh a year |
| A10 | Savings are a potential | all off-hours use above standby | notebook 03 | upper estimate of what is avoidable | ✅ stated | the business case shows 25 / 50 / 75 % scenarios |

## Money and CO₂

| ID | Assumption | Value | Where set | Source / evidence | Status | If it changes |
|---|---|---|---|---|---|---|
| A11 | All-in electricity price | **€ 0.142 / kWh**, flat | `params.yaml` → `price.all_in_eur_per_kwh` | Eurostat, non-household consumers, Spain, 2nd half 2024, excluding VAT (includes network charges and electricity tax). Same source: € 0.128 without any taxes, € 0.169 with all taxes | 📄 average, not CeDInt's contract | every € scales with the price: CeDInt's contract may be higher or lower |
| A12 | VAT | excluded, as for a business that recovers it | – | Eurostat definition | ❓ | if UPM cannot recover VAT, use the price with all taxes (€ 0.169): every € figure rises by about 19 % |
| A13 | Hourly wholesale price | OMIE day-ahead price for Spain, per hour (mean € 112/MWh in 2021, € 168/MWh in 2022) | `src/download_price_omie.py` | OMIE | 📄 | energy only, no network charges or taxes: a **lower bound** for the cost of that hour |
| A14 | CO₂ factor | **259 / 273 / 260 g CO₂-eq per kWh** (2021 / 2022 / 2023); 2020 uses 2021, 2025 uses 2023 | `params.yaml` → `co2.g_per_kwh` | mix of Spanish suppliers without guarantees of origin, published yearly by the CNMC and used in the MITECO carbon-footprint register (the MITECO guide uses 0.273 for 2022) | 📄 2022 checked; 2021 and 2023 to check against the CNMC labelling (KAN-134) | ± 5 % between years |
| A15 | CO₂ method | grid average without guarantees of origin (location-like) | – | – | ❓ | if UPM buys renewable electricity with guarantees of origin, the **market-based** CO₂ of the savings is 0. Lower reference: 102 g/kWh, average of Spanish generation 2024 (REE/CNMC), in `params.yaml` |

## Alerts

| ID | Assumption | Value | Where set | Source / evidence | Status | If it changes |
|---|---|---|---|---|---|---|
| A16 | Event threshold | per circuit k (2–15) so that each circuit raises about one event a week | `reports/anomaly_k.json`, `params.yaml` → `anomaly` | EXP-06: alarm budget a manager can follow | ✅ | lower k finds more, but floods the manager |
| A17 | Smallest event | ≥ 2 hours and ≥ 0.5 kWh above expected | `params.yaml` → `anomaly` | smaller events are worth less than € 0.07 | ✅ | – |
| A18 | Severity | € < 0.25 Low, € 0.25–1.00 Medium, ≥ € 1.00 High; +1 level for events ≥ 24 h | `params.yaml` → `severity` | EXP-12: High ≈ top 20 % of alerts, ≈ 1.5 a week, 62 % of the € | ✅ calibrated · ❓ sponsor to approve | re-calibrate after retraining, the calendar fix, or a tariff change |
| A19 | Severity price | ranked on the flat all-in € | `params.yaml` → `severity.eur_column` | the same waste gets the same level in every year | ✅ decision | ranking on OMIE would move 2022 events up a level (energy crisis) |
| A20 | Model is valid for new data | trained on 2020–23 | notebooks 02–03 | 2025: SE Lighting is used in a new way (EXP-05, EXP-09) | ⚠️ | retrain on recent data before going live (deployment plan) |

## Deployment

| ID | Assumption | Value | Source / evidence | Status |
|---|---|---|---|---|
| A21 | Hosting | € 0 on an existing UPM server, or € 120–240 a year for a small cloud VM (2 vCPU, 4 GB) | typical price range of small cloud VMs; the full history is about 27,000 hourly rows | ⚠️ estimate |
| A22 | Set-up effort | pilot 5–8 developer days; live service 15–20 days in total | team estimate, see the deployment plan | ⚠️ estimate (± 50 %) |
| A23 | Operation | about 2 hours a month (High alerts, monthly report, configuration) | ≈ 1.5 High alerts a week (EXP-12) | ⚠️ estimate |
| A24 | Data access | read-only access to the CeDInt IoT platform, or a scheduled export in the current format | same device and zone IDs across plans, platform and database | ❓ |

## Open decisions (summary)

| ID | Question | Who decides | Effect |
|---|---|---|---|
| A6 | Which hours count as closed? | sponsor | off-hours share and waste |
| A7 | Real UPM closure dates (Christmas, August) | KAN-56 owner + facility team | holiday alerts, small change in waste |
| A12 | Can UPM recover VAT? | sponsor | all € about +19 % if not |
| A11 | CeDInt's contract price | sponsor | all € figures |
| A15 | Guarantees of origin? | sponsor / sustainability officer | CO₂ of the savings |
| A18 | Approve the severity levels | sponsor | which alerts are High |
| — | Is the NW night lighting needed (security lighting)? | facility team | about 1 MWh a year in or out of the waste |

### Sources

- Eurostat, electricity prices for non-household consumers (nrg_pc_205): <https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_205/default/table>
- CNMC, electricity labelling (etiquetado de la electricidad), yearly: <https://gdo.cnmc.es>
- MITECO, carbon-footprint register and guide (Registro de huella de carbono): <https://www.miteco.gob.es/es/cambio-climatico/temas/mitigacion-politicas-y-medidas/calculadoras.html>
- OMIE, day-ahead market prices: <https://www.omie.es>
