# Backlog coverage: every backlog item, its evidence and what is left (KAN-8)

**Status on 15 November 2026**, Sprint 4 (9 – 22 Nov). Final presentation 30 Nov, Moodle release 14 Dec.
Checks every item of the Product Backlog (`docs/reports/TBDA1_Product_Backlog_Updated (1).docx`, 23 stories and
8 quality requirements) against what is really in the repository: on `main`, or on an open branch or pull request.
Use it to plan the last sprint, and as the traceability table for the final report.

**Legend:** ✅ done on `main` · 🔀 done on an open branch / pull request, not merged yet · 🟡 partly done · ⬜ not started · ⏸ on hold
Open branches: `dashboard` (PR #8, Hector), `KAN-118-dashboard-skeleton` (PR #5, Viktor), `KAN-144-prediction-interval` (PR #6, Marius),
`KAN-146-prophet-comparison` (PR #7, Marius), `linnea/model-search` (Linnea), `amelie/business-value` (Amélie: severity, business case, register, deployment plan, this page).

## Summary

| Theme | ✅ | 🔀 | 🟡 | ⬜ | ⏸ |
|---|---|---|---|---|---|
| F1 See where and when energy is used (4) | – | 3 | 1 | – | – |
| F2 Trust the data (2) | – | – | 2 | – | – |
| F3 Know what consumption is normal (3) | 2 | – | 1 | – | – |
| F4 Detect waste and anomalies (5) | – | 1 | 3 | 1 | – |
| F5 Value and prioritise (3) | 1 | 2 | – | – | – |
| F6 Decide, deploy and share (6) | – | 2 | – | 2 | 2 |
| Quality requirements Q1–Q8 (8) | 2 | – | 4 | 2 | – |

**Reading:** the analysis is done (data, models, detection, € and CO₂). Most product features exist, but in branches
that are not merged. Merging them is the step with the most value left; the gaps after that are small and listed at the end.

## F1. See where and when energy is used

| ID | Story | Status | Evidence | Gap | Jira |
|---|---|---|---|---|---|
| F1.1 | Out-of-hours overview per zone × load type | 🔀 | `reports/offhours_waste_daily.csv`, `savings_summary.csv` (notebook 03); figure `eda_09_night_load.png` (notebook 01); dashboard page "Off-hours use" (PR #8) | acceptance asks for editable opening hours (Mon–Fri 08–20); the code uses nights 22–06, hard-coded in `src/data.py` (register A6) | KAN-15, 122, 125, 127, 128 |
| F1.2 | Consumption explorer with shared filters | 🔀 | dashboard sidebar filters (month, zone, load type) apply to every page (PR #8); data 2020–23 and 2025 | "runs from the raw files with one command" needs the raw → hourly script (see Q1) | KAN-11, 123, 118, 119, 140, 25 |
| F1.3 | Floor map coloured by waste | 🔀 | `ui.floor_map` on the Overview page; clicking a zone filters every page (PR #8) | schematic plan; the real plan is in `docs/building/proyectoedificio-planta-1.svg` | KAN-157 |
| F1.4 | Day × hour heatmap | 🟡 | hour profile heatmap and chronic-waste heatmap on "Off-hours use" (PR #8); `anom_03_chronic_heatmap.png` | check that nights, weekends and holidays are visibly marked | KAN-139 |

## F2. Trust the data

| ID | Story | Status | Evidence | Gap | Jira |
|---|---|---|---|---|---|
| F2.1 | Data reliability per zone, load and month | 🟡 | cleaning rules R1–R12 (`src/clean.py`); frozen dataset + `MANIFEST.json`; `tests/test_dataset.py`; data reliability report (KAN-12, Sprint 2); "Data quality" page with monthly coverage (PR #8) | gaps and resets marked on every chart; cleaning log not committed | KAN-12, 13, 154 |
| F2.2 | Data errors as a separate alert type | 🟡 | bad hours are empty, so they never get € or CO₂; dashboard status "Data error" (PR #8) | no data-error detector or list yet (dead meter, flat line, reset) | KAN-148 |

## F3. Know what consumption is normal

| ID | Story | Status | Evidence | Gap | Jira |
|---|---|---|---|---|---|
| F3.1 | Expected vs actual consumption | ✅ | baselines B1–B3 and models in `src/models.py`, `notebooks/02_models.ipynb`, `reports/model_comparison.csv` (EXP-03); chart on "Expected vs actual" (PR #8) | – | KAN-18, 126, 26 |
| F3.2 | Weather- and calendar-aware expectation | ✅ | LightGBM with Open-Meteo weather and UPM calendar; time-based split; beats the best baseline on test (NW Plugs CV(RMSE) 52.5 % vs 56.0 %) | calendar dates to fix (KAN-56), then re-run | KAN-14, 124, 133, 17, 19, 20 |
| F3.3 | Model compared with alternatives, model card | 🟡 | Prophet vs LightGBM (EXP-11, PR #7); 7 models on 4 input sets (`linnea/model-search`); prediction band (EXP-10, PR #6) | **model card not written** (branch KAN-162 has no commits); two different "notebook 04" files on two branches: renumber before merging | KAN-146, 162 |

## F4. Detect waste and anomalies

| ID | Story | Status | Evidence | Gap | Jira |
|---|---|---|---|---|---|
| F4.1 | Out-of-hours waste alerts | 🟡 | events (signal 1) and chronic off-hours waste (signal 2) in `src/anomalies.py`, notebook 03; each event has zone, load, start, end, excess kWh; top events checked by hand (EXP-09); no alert on bad-data hours | **waste definition not yet approved by the sponsor** (business case §12); no catalogue of known events | KAN-10, 16, 22, 137, 24 |
| F4.2 | Alert list and detail | 🔀 | one table `reports/anomaly_events.csv`; "Alerts" page with filters by zone, load, severity, status, and a detail view (PR #8) | chronic waste is shown per day, not as alerts; presence not in the detail view | KAN-135, 149, 141, 166 |
| F4.3 | Abnormal-use alerts from a prediction interval | 🟡 | 90 % band with rolling conformal widening, 89 % coverage on test (EXP-10, PR #6); events today use a robust residual threshold (EXP-06) | decide whether alerts switch to the band; final review of all alerts | KAN-144, 145, 163 |
| F4.4 | Mark an alert handled / false alarm / data error | 🟡 | status saved in `dashboard/data/alert_status.csv` (PR #8) | date and history of each change; thresholds not yet tuned with the feedback | KAN-161, 150 |
| F4.5 | Weekly e-mail with the most severe alerts | ⬜ | – | planned in the deployment plan, option B | – |

## F5. Value and prioritise

| ID | Story | Status | Evidence | Gap | Jira |
|---|---|---|---|---|---|
| F5.1 | € and kg CO₂ per alert, totals per day, month, zone | ✅ | `value()` in `src/anomalies.py`: hourly OMIE price and all-in price, CO₂ factor per year; totals in `offhours_waste_daily.csv` and `savings_summary.csv`; sources in `params.yaml` and the [assumptions register](ASSUMPTIONS_REGISTER.md) | CO₂ factor for 2021 and 2023 to check against the CNMC labelling (KAN-134) | KAN-134, 23 |
| F5.2 | Severity levels | 🔀 | € + duration rule, calibrated on the 1,128 real events: ≈ 1.5 High a week cover 62 % of the € (EXP-12); `params.yaml` → `severity`; `rank_alerts()`; `tests/test_severity.py` (`amelie/business-value`) | dashboard caption still reads the old `severity_kwh` (one line in PR #8); sponsor to approve | KAN-152 |
| F5.3 | Monthly and yearly savings report with export | 🔀 | `reports/savings_summary.csv`; "Savings report" page with Markdown and CSV download, PDF via the browser (PR #8) | – | KAN-155, 156, 168 |

## F6. Decide, deploy and share

| ID | Story | Status | Evidence | Gap | Jira |
|---|---|---|---|---|---|
| F6.1 | Business case | 🔀 | [`BUSINESS_CASE.md`](BUSINESS_CASE.md): measured potential 6.0–7.2 MWh, € 850–1,020, 1.6–1.9 t CO₂ a year; SDGs and EELISA; success KPIs; reconciliation with Sprint 2 (`amelie/business-value`) | KPIs to agree with the sponsor | KAN-131, 132, 136, 153 |
| F6.2 | Deployment plan | 🔀 | [`DEPLOYMENT_PLAN.md`](DEPLOYMENT_PLAN.md): options A/B/C, data connection, hosting, retraining, monitoring, costs, roles (`amelie/business-value`) | – | KAN-159 |
| F6.3 | Demo mode (replay as if live) | ⬜ | – | needed for the live demo on 30 Nov (storyline part 4) | KAN-167 |
| F6.4 | Demo video | ⬜ | – | after the demo mode | KAN-165 |
| F6.5 | Floors 2 and 3 | ⏸ | – | waiting for data exports | – |
| F6.6 | Alerts from the live IoT platform | ⏸ | deployment plan, option C | depends on the sponsor's decision | – |

## Quality requirements

| ID | Requirement | Status | Evidence | Gap |
|---|---|---|---|---|
| Q1 | Reproducible and auditable | 🟡 | frozen dataset with SHA-256 manifest; 27 `pytest` checks; experiment log (EXP-01 to EXP-12); MkDocs site; notebook 03 re-run on 15 Nov reproduced every output exactly | **raw → hourly script missing**, so the pipeline cannot run from the raw Excel files with one command |
| Q2 | Transparent numbers | ✅ | every parameter in `params.yaml` with its source; [assumptions register](ASSUMPTIONS_REGISTER.md) with status and effect of each assumption | dashboard should link to the register |
| Q3 | Usable without data-science knowledge | ⬜ | wireframe and dashboard sketch (KAN-121, `docs/reports/`) | **test with 3 people outside the team** not done |
| Q4 | Pages load in under 3 s | ⬜ | – | not measured |
| Q5 | Configurable in one file | 🟡 | price, CO₂ factor, alert and severity thresholds in `params.yaml` | opening hours are hard-coded in `src/data.py`; `params.yaml` → `off_hours.night_hours` is not read |
| Q6 | User documentation | 🟡 | `dashboard/INSTALL_EN.md`, `INSTALL_FR.md` and a "Method" page (PR #8) | a user guide on the waste definition and alert types, reachable from the dashboard |
| Q7 | Privacy and safe access | ✅ | no personal data; presence only as a zone share; read-only design (deployment plan §7) | – |
| Q8 | Forecast accuracy | 🟡 | MAE, CV(RMSE), NMBE on unseen test months and on 2025 (EXP-03, EXP-05); ASHRAE gap stated | hourly CV(RMSE) above the ASHRAE 30 % target on most circuits (people switch loads by hand); stated in the docs |

## What is left, in order (proposal for the rest of Sprint 4)

| # | Action | Unlocks | Suggested owner |
|---|---|---|---|
| 1 | **Review and merge** PR #6, #7, #8, `linnea/model-search` and `amelie/business-value`; close PR #5 if PR #8 replaces it; renumber the two notebook 04s | F1, F3.3, F4.2–F4.4, F5, F6.1–F6.2 move to ✅ | each author + one reviewer |
| 2 | Push the raw → hourly script | Q1, F1.2 | Massucco (data team) |
| 3 | Fix the UPM calendar, re-run notebooks 02–03, re-run `src/calibrate_severity.py` | F3.2, F4.1, correct numbers in the presentation | KAN-56 owner |
| 4 | Demo mode in the dashboard | F6.3, the live demo on 30 Nov | dashboard team |
| 5 | Model card (data, features, accuracy, band, limits) | F3.3 | modelling team |
| 6 | Usability test with 3 people outside the team | Q3 | dashboard team + scrum masters |
| 7 | Data-error list (dead meter, flat line, reset) | F2.2 | data team |
| 8 | Read opening hours from `params.yaml`; link the register from the dashboard | Q5, Q2 | modelling + dashboard |
| 9 | Ask the sponsor the open decisions (business case §12) | F4.1, F5.2, F6.1 | product owner contact |
