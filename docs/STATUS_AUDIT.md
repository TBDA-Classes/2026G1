# Status audit — Group 1 (2 Nov 2026)

Audit of what is really in the repo, compared with the professor's review slide (early November).
Scale: 🟢 code/data in the repo · 🟡 partial · 🔴 only described in a report · ⚪ not started.

## Who did what

| Who | What (in repo) |
|---|---|
| Roberto Moran | raw data `data/raw/*.xlsx` |
| Massucco | all pipeline code in `src/`: loader, unify, save_parquet, clean (rules R1–R12), check_utc, build_calendar, download_weather, download_price_omie, merge_external, model_test |
| raffaelesimo | cleaned data files (`data/Storey1_cleaned_data.xlsx`, parquets) |
| AmelieBuysse1 | backlog, Sprint 2 report, dashboard sketch, Jira link (`docs/reports/`) |
| Hector D | backlog report (`docs/reports/`) |
| Viktor Kalinowski | Streamlit skeleton — branch `KAN-118-dashboard-skeleton`, PR #5, **not merged** |
| Emma Hendriks | repo structure, frozen dataset + manifest, tests, README, this audit; modelling (Phase 3) |

## Workstreams

| Workstream | Slide said | Now | Evidence | Missing vs G2/G3 |
|---|---|---|---|---|
| Planning & backlog | Done | 🟢 | `docs/reports/*.docx`, Sprint 2 report, Jira link | experiment logbook (G3 has one) |
| Data cleaning | Claimed | 🟡 | `src/clean.py` (12 numbered rules), `data/clean_hourly_*.parquet` | cannot run from raw (input `Storey1_Anomaly_Analysis.xlsx` not in repo); cleaning log / QA report not committed |
| Timestamps & resampling | Claimed | 🟡 | `src/clean.py` R1/R2, `src/check_utc.py` | minute→hour aggregation code (Regime B) missing |
| External data | Claimed | 🟢 (CO₂ 🔴) | `src/build_calendar.py`, `src/download_weather.py`, `src/download_price_omie.py`, `src/merge_external.py` + data | CO₂ emission factor; `weather_hourly.parquet` itself not committed (merged copy is) |
| EDA & profiles | No evidence | 🔴 | text in Sprint 2 report only | EDA script + figures (G2 `eda_analysis.py`, G3 zone comparison) |
| Baselines | Claimed | 🟡 | `src/model_test.py` B1 last week, B2 4-week median | tests; committed results |
| ML forecasting | In progress | 🟡 | `src/model_test.py` LightGBM + quantile band, time split | per-circuit models, linear model (claimed in report, no code), committed results |
| Frozen dataset | No evidence | 🟢 | `data/processed/cedint_hourly_v1.parquet` + `MANIFEST.json` (SHA-256), `tests/test_dataset.py` | — |
| Dashboard | Partial | 🟡 | PR #5, unmerged | — |

## Cleaning traps — checked

| Trap | Status | Evidence |
|---|---|---|
| `Ea`/`Er` cumulative counters with resets | Handled by using `W` instead: in Regime A, median(ΔEa / W) = 1.00, so W = Wh per hour; `Ea` on NE Plugs has 20 negative and 14 huge jumps that are avoided | `src/clean.py` |
| Sampling frequency change | Partial: Regime B was aggregated to hourly (`raw_readings`, `low_coverage` R11) but the code is not in the repo | `src/clean.py:33-56` |
| Lum/Hum/Temp/Pres = 0 means missing | Partial: only when all three are 0 together (R9) + temp outside 5–45 °C (R10) | `src/clean.py:130-137` |
| Duplicates, gaps, DST | Handled: full hourly grid, UTC → Madrid, 0 duplicates (tested) | R1/R2, `tests/test_dataset.py` |
| COVID lockdown 2020 | Flag exists (`is_covid_lockdown` ≤ 2020-06-21); first model trains on it — fixed in Phase 3 | `src/build_calendar.py:39` |
| Number of devices changes | Not checked | — |
| 2.5-year gap (Mar 2023 – Aug 2025) | In the raw files themselves, not a cleaning error | checked on NE xlsx |

## Blocking issues for modelling
None: the frozen dataset is enough to start. Open points for reproducibility are in the list below.

## Ask the group
- **Massucco** — please push the script that builds the hourly table `00_RAW_DATA` / `data/raw_hourly.parquet` from the raw xlsx (minute→hour for 2025, `Regime`, `raw_readings`), plus `out/cleaning_log.csv` and `data/weather_hourly.parquet`. Without it the pipeline can't be rebuilt from raw.
- **raffaelesimo** — which of `Storey1_cleaned_data.xlsx`, `data/archive/Storey1_cleaned data (1)` and `KAN-49_attachments.zip` is final? OK to delete the duplicates in `data/archive/`?
- **Owner of KAN-20** — push the linear regression for NW plugs mentioned in the Sprint 2 report.
- **Owner of KAN-134** — status of the CO₂ factor (REE).
- **Viktor** — PR #5: please rebase on `emma/structure-and-modelling` once merged (files now live in `src/` and `data/`).
- **Everyone** — upload with `git` (branch + PR), not "Add files via upload": the web upload flattens folders.

## Ideas taken from other groups (public repos, ideas only, no code copied)
- Dataset manifest with SHA-256 and versioned file name — G2 (`Storey1_hourly_v1.2_META.json`).
- pytest checks on the data and models — G2 (`tests/`).
- CV(RMSE) / ASHRAE Guideline 14 as an extra metric — G3 (`team_b_eval.py`); our `model_test.py` already used it.
- Experiment logbook — G3 (`EXPERIMENT_LOGBOOK.md`).
