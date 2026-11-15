# Deployment plan: from the course version to CeDInt's live data (KAN-159 · backlog F6.2)

**Status:** 15 November 2026. Covers what the backlog asks for F6.2: data connection, hosting, retraining,
monitoring, costs and responsibilities. Cost and effort figures are team estimates (assumptions A21–A24 in the
[register](ASSUMPTIONS_REGISTER.md)); the expected savings are in the [business case](BUSINESS_CASE.md).

---

## 1. Goal

Move from the course version (Excel exports up to October 2025, run on a laptop) to a service that reads new
CeDInt data on a schedule, raises waste alerts within a day, and sends a monthly savings report.
It should need about 2 hours of attention a month and never control the building: it only advises (read-only).

## 2. Three options, in steps

| Option | What it is | Data freshness | Infrastructure | Effort | When |
|---|---|---|---|---|---|
| **A. Hand-over** (delivered with the course) | the repository, the frozen dataset and the dashboard on a laptop, with a demo mode that replays 2025 as if it were live (F6.3) | frozen (Oct 2025) | none | done | final presentation (30 Nov), Moodle release (14 Dec), training of users |
| **B. Pilot with scheduled refresh** (recommended next step) | every night a job takes a new export, runs the pipeline, updates the alerts and the dashboard on a UPM server, and e-mails the High alerts once a week (F4.5) | daily | one small server or VM | about 5–8 developer days | one heating season on Storey 1, to measure the KPIs of the business case |
| **C. Live service** | hourly reading from the IoT platform API, a small database with alert status history, single sign-on, all floors | hourly | server, database, monitoring, backups | about 10–12 more days (15–20 in total) | only if the pilot meets its KPIs (backlog F6.5, F6.6) |

Starting with B keeps the first decision small: no API access, no database and no new software are needed,
and the sponsor sees real results on new data before committing to C.

## 3. Pipeline: what exists and what is missing

The course pipeline is reused step by step. Only the first step changes between options.

| Step | What happens | Existing code | Gap for the pilot (B) | Extra for live (C) |
|---|---|---|---|---|
| 1 Ingest | read new meter data | `src/loader.py`, `unify.py`, `save_parquet.py` (Excel exports) | **push the raw → hourly script** (minute data to hours; missing in the repo, see STATUS_AUDIT); accept a new export file | REST reader for the ThingsBoard / Graphite API, last 3 h every hour (overlap fills late readings) |
| 2 Clean | rules R1–R12 | `src/clean.py` | run on a date window, append to the history | – |
| 3 Context | calendar, weather, price | `src/build_calendar.py`, `download_weather.py` (Open-Meteo archive), `download_price_omie.py` | **fix the UPM closure dates** (KAN-56); add the next academic year | Open-Meteo forecast endpoint for "today" |
| 4 Expect | expected use per circuit and hour | `src/features.py`, `src/models.py`, `reports/model_params.json` | a script that trains and saves one model per circuit (today this happens inside notebooks 02–03) | prediction band (branch KAN-144, `src/intervals.py`) |
| 5 Detect | events and chronic off-hours waste | `src/anomalies.py` (`detect`, `offhours_waste`), `reports/anomaly_k.json` | a script version of notebook 03 sections 4–5 for a date window | – |
| 6 Value | €, CO₂, severity, ranking | `src/anomalies.py` (`value`, `severity`, `rank_alerts`), `params.yaml` | tariff and CO₂ method confirmed by the sponsor (register A11–A15) | hourly CO₂ factor if REE data are used |
| 7 Store | readings, forecasts, alerts | Parquet / CSV files in `data/` and `reports/` | keep the alert status (handled, false alarm, data error: F4.4) in a small file | DuckDB or PostgreSQL, nightly backup |
| 8 Serve | dashboard and reports | Streamlit dashboard (branch `dashboard`, PR #8; skeleton PR #5) | **merge the dashboard**; read the store; weekly e-mail with the High alerts | single sign-on, all floors |

## 4. Data needed for live operation

| Requirement | Detail | Why |
|---|---|---|
| Source | Storey 1 meters and indoor sensors, same structure as the current exports (power `W` per circuit, counters, environment, presence) | the cleaning rules and the model depend on these columns |
| Access | read-only service account on ThingsBoard / Graphite, or a nightly export to a shared folder | the tool must never write to building systems |
| Resolution | minute or hourly; hours are built from minutes as in 2025 | the model works on hours |
| Latency | the full previous day available by 06:00 | alerts must be ready when the building manager starts |
| Completeness | missing readings stay missing, never 0 | a 0 would look like savings, a gap must look like a data error |
| Time | timestamps in UTC, shown in Madrid time | daylight-saving days (A2) |
| Calendar | UPM holidays, breaks and opening hours for each academic year | "closed" decides what counts as waste (A6, A7) |
| Tariff and CO₂ | CeDInt's contract price, VAT status, guarantees of origin | € and CO₂ figures (A11–A15) |
| Device list | which circuit feeds what (sockets, lighting, HVAC) and changes to it | new equipment changes "normal" use |

## 5. Retraining

The model learned 2020–2023. In 2025 one lighting circuit is already used differently (EXP-05, EXP-09), so
**retraining on recent data is the first task of the pilot**, before any alert goes to the building manager.

| When | What | Check before using the new model |
|---|---|---|
| Before the pilot starts | retrain on all data up to the newest export | CV(RMSE) and NMBE on the last 2 months no worse than at hand-over (notebook 02) |
| Every month | retrain on a rolling 24-month window | same check; keep the old model if the new one is worse |
| After a change in the building (new equipment, refurbishment, new opening hours) | retrain, and mark the change date in the calendar | – |
| After every retraining | re-choose k per circuit (EXP-06 rule: about 1 event per circuit per week) and re-run `src/calibrate_severity.py` (EXP-12) | `pytest` passes; log the run in the experiment log |

## 6. Monitoring

Thresholds are starting values, to be tuned during the pilot.

| What | Indicator | Starting threshold | Action |
|---|---|---|---|
| Data | a meter sends nothing | 3 hours (live) or a missing day (pilot) | data-error alert to the maintenance technician |
| Data | share of flagged (bad) hours | above 10 % in a day | check the meters before trusting the alerts |
| Model | weekly CV(RMSE) and NMBE per circuit, against the hand-over values | worse for 2 weeks in a row | retrain (section 5). ASHRAE Guideline 14 (30 % / ±10 %) is the reference; the hand-over model does not meet it hour by hour on most circuits, so it is monitored relative to its own starting level |
| Alerts | events per circuit per week | above 3 for 2 weeks, or 0 for 4 weeks | review k for that circuit |
| Usefulness | share of alerts marked "false alarm" (F4.4) | above 30 % | re-tune thresholds (KAN-150) |
| Usefulness | High alerts reviewed within a week | below 80 % | review the alert load with the building manager |
| Service | job failures, dashboard up | any failure | e-mail to the product maintainer |

## 7. Security and privacy (quality requirement Q7)

- Read-only access to the building data; the tool never switches anything.
- Dashboard behind UPM single sign-on or the VPN.
- Presence data only as zone totals; no personal data stored.
- All code open source in the course repository; secrets (API account) outside the repository.

## 8. Costs

| Item | One-off | Per year |
|---|---|---|
| Pilot set-up (option B): raw → hourly script, training and detection scripts, scheduler, e-mail, server set-up | about 5–8 developer days | – |
| Live service (option C), on top of B: API reader, database, alert history, single sign-on | about 10–12 developer days | – |
| Hosting on an existing UPM / CeDInt server | – | € 0 |
| Hosting on a small cloud VM (2 vCPU, 4 GB RAM; the whole history is about 27,000 hourly rows) | – | about € 120–240 |
| Operation: High alerts, monthly report, configuration (about 2 h a month) | – | about 24 hours |
| Software licences (Python, pandas, LightGBM, Streamlit) | – | € 0 |

Against this, the potential on Storey 1 alone is about **€ 850–1,020 and 1.6–1.9 t CO₂ a year** (business case).
A cloud VM is paid back once 13–26 % of that potential is removed.

## 9. Responsibilities after hand-over

These are roles in CeDInt's organisation, not tasks for team members.

| Role | Responsible for |
|---|---|
| CeDInt IT / platform administrator | server or VM, read-only API account or export, backups, single sign-on |
| Product maintainer (a CeDInt developer or a follow-up student project) | pipeline jobs, monthly retraining, monitoring, configuration updates |
| Building manager | acting on High alerts, marking alerts handled or false alarm, keeping opening hours and holidays current |
| Sustainability officer | monthly savings report and its use in sustainability reporting |
| Maintenance technician | fixing meters reported as data errors |
| Product owner at CeDInt (sponsor) | approving the waste definition and thresholds, deciding on option C and on floors 2–3 |

## 10. Rollout

| Month | Step | Who sees alerts | Decision at the end |
|---|---|---|---|
| 0 | set up option B; retrain on recent data; **shadow mode**: alerts produced, only the team reviews them | team | are the alerts sensible? |
| 1 | building manager receives the weekly High alerts; quick wins started (NW heaters, NW night light) | building manager | is the alert load manageable? |
| 2–5 | heating season: all alerts and the monthly report; feedback buttons collect labels | building manager, sustainability officer, technician | – |
| 6 | compare with the KPIs of the business case (section 8) | sponsor | go to option C and floors 2–3, adjust, or stop |

## 11. Risks

| Risk | Mitigation |
|---|---|
| API access to the platform is not granted | option B works with a nightly export in the current format |
| Meters drop out or reset (seen in 2020–2025) | data-error alerts, a separate category with no € counted |
| The building is used differently (as in 2025) | retrain before the pilot and every month; feedback "this was normal" |
| Too many alerts, users stop looking | severity levels, start with High only, tune with false-alarm feedback |
| Nobody owns the tool after the course | named product maintainer and product owner before the pilot starts (section 9) |
| Wrong closure dates create false alerts | fix the calendar first (KAN-56); building manager keeps it current |

## 12. Hand-over checklist (option A, for the Moodle release)

- [ ] All branches merged; `pytest` passes on `main`.
- [ ] Raw → hourly script in the repository, so the pipeline runs from the raw files (quality requirement Q1).
- [ ] Calendar fixed (KAN-56); notebook 03 re-run; severity re-calibrated.
- [ ] Dashboard runs with one command, including demo mode (F6.3).
- [ ] Business case, this plan and the assumptions register approved by the sponsor or their open points listed.
- [ ] User guide reachable from the dashboard (quality requirement Q6).
