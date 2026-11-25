# Storey 1 energy dashboard (CeDInt · UPM · TBDA Group 1)

Streamlit dashboard that shows the **results of the modelling notebooks** (`reports/`) on top of the
**cleaned zone files** (`data/zone_*_hourly.parquet`). It does not compute its own waste figures: every number
comes from the team's files, with the team's definitions (`params.yaml`).

Step-by-step guide: [INSTALL_EN.md](INSTALL_EN.md) · en français : [INSTALL_FR.md](INSTALL_FR.md)

## Run it

From the repository root:

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

The `dashboard/` folder must sit at the root of the 2026G1 repository, next to `data/`, `reports/` and `params.yaml`.

## Pages

| Section | Page | Question | For whom |
|---|---|---|---|
| Monitor | Overview | How much was wasted this month (kWh, € range, CO₂), where, what is urgent? Click a zone of the floor map to filter every page | building manager, sponsor |
| Monitor | **Live demo (2025 replay)** | Aug–Oct 2025 replayed hour by hour with the LightGBM forecast: the chart grows, alerts pop up with € and severity | presentation, jury |
| Monitor | Alerts | Which alerts first (severity, then €)? Actual vs expected ± 24 h, standby level, outdoor temperature, **why the model expected that value**; status with history; CSV export | technician |
| Analyse | Off-hours use | Use while closed per zone and circuit, weekday × hour, waste that comes back every winter | building manager |
| Analyse | Expected vs actual | Actual vs LightGBM, Ridge and baselines B1–B3 per week, labelled by evaluation phase (expected afterwards / honest test / 2025 forecast), alarm line, 90 % band, **why the model expected that hour**, accuracy against the targets | energy analyst |
| Analyse | Savings report | MWh, € range, CO₂ a year, what to fix first, **What if?** panel (definition of closed, NW night light, tariff, CO₂ method), export | sponsor, sustainability officer |
| Act | **Action planner** | Pick a circuit and a measure → yearly kWh, € range, CO₂, payback; log it; later **verify** it: waste before vs after on similar days | building manager |
| Trust | Data quality | Coverage, gaps, cleaning rules | everyone |
| Trust | Method & model card | Periods, model and alert rules, model search (EXP-13), detection test, evidence figures, model card, honest limits | jury, reviewers |
| Trust | How to use | User guide, glossary, the monthly cycle, usability-test script (Q3, Q6) | new users |

## Customer value document → where it is in the dashboard

| Requirement (Customer value and solution, Group 1) | Where |
|---|---|
| Level 1 — where each result comes from | caption with the source file under every chart; *Method → Documents & sources* lists every file read |
| Level 2 — what the terms mean | footnote of every page (closed, standby, chronic waste, € range, CO₂, severity); *How to use* glossary |
| Level 3 — why an alert was raised | Alerts detail: actual vs expected, 24 h before/after, standby level, type of day, outdoor temperature, *Why did the model expect this value?* |
| Level 4 — how good the model is | *Expected vs actual*: accuracy vs ASHRAE targets per phase, baselines, alarm line, 90 % band; *Method*: detection test |
| Incomplete months / gaps never zeros | coverage badge + warning < 95 %; gaps stay empty; *Data quality* page |
| € as a range (wholesale → all-in) | every headline € (cards, alert detail, savings, planner, demo): OMIE price hour by hour → € 0.142/kWh all-in; tables and bar charts that rank by € say "all-in" |
| "To investigate" not counted as savings | separate tab on *Alerts*; excluded from every saving |
| Monthly cycle and feedback | month navigation ◀ ▶; alert statuses incl. *This was normal* (labels for tuning) |
| Extension 7.1 — action planner with verification | *Action planner* page |
| Extension 7.2 — explanation of the expected value | *Why did the model expect this value?* panels (LightGBM TreeSHAP contributions) |

## Data sources

| File | Made by | Used for | If missing |
|---|---|---|---|
| `data/zone_{NE,NW,SE,SW}_hourly.parquet` (or `.xlsx`) | data-cleaning group (`data/build_zone_files.py`) | use per hour and circuit, weather, calendar, hourly price and CO₂ intensity, coverage | `data/processed/cedint_hourly_v1.parquet`, else error |
| `params.yaml` | modelling team | prices, CO₂ method, off-hours, severity | built-in copy in `config.py` |
| `reports/anomaly_events.csv` | notebook 03 | alerts (signal 1) | pages show a note |
| `reports/offhours_waste_daily.csv` | notebook 03 | chronic waste (signal 2), € and CO₂, verification of measures | pages show a note |
| `reports/savings_summary.csv` | notebook 03 | Savings report, Action planner | page shows a note |
| `reports/expected_hourly.parquet` | notebook 03 | LightGBM expected line + alarm line, 2020–23 (cross-fitted) and 2025 (forecast) | Jan–Feb 2023 only, else baselines |
| `reports/test_predictions.parquet` | notebook 02 | honest test, Jan–Feb 2023 (LightGBM, Ridge) | test months from expected_hourly |
| `reports/model_comparison.csv` | notebook 02 | accuracy tables, model scores | tables hidden |
| `reports/final_model_settings.json` | notebook 04 (model search, EXP-13) | Method page | not shown |
| `reports/interval_bands.parquet` | notebook 04 intervals | 90 % band | no band |
| `dashboard/data/expected_contributions.parquet` (or `reports/`) | `python dashboard/tools/export_contributions.py` | *Why did the model expect this value?* | panel explains how to create it |
| `dashboard/data/alert_status.csv`, `actions.csv` | the dashboard itself | alert statuses, measures logged | created on first use |

Every output is searched first in `dashboard/data/`, then in `reports/`.

### Definitions (same as `src/data.py`, `src/anomalies.py`)

- **Off-hours / closed** = nights 22:00–05:59 (`params.yaml`) + weekends, holidays, breaks (team calendar).
- **Standby level** = 10th percentile of the circuit's night use, Jun 2020 – Aug 2022.
- **Chronic waste** = use above standby during off-hours. **Alert** = hours far above the model's expectation
  (≥ 2 h, ≥ 0.5 kWh, k per circuit for ≈ 1 alert/week). Alerts mostly in off-hours are listed as waste,
  the others as "to investigate".
- **€** = a range: OMIE wholesale price of each hour (lower bound) → € 0.142/kWh all-in excl. VAT (upper bound).
- **CO₂** = hourly carbon intensity of the Spanish grid (Red Eléctrica, `co2.method: hourly`); the What-if panel
  also offers the supplier mix (CNMC), the 2024 generation mix and 0 (guarantees of origin).
- **Severity**: read from `params.yaml` (kWh rule `anomaly.severity_kwh`, or € + duration rule `severity:`, EXP-12).
- **9 focus circuits**: plugs (4 zones), lighting NW/SW/SE, HVAC NW/SE. Emergency lighting, rack, hand dryers
  and NE HVAC are fixed loads (shown in totals and data quality only).
- COVID lockdown hours are left out, as in the models.

## Folder

```
dashboard/
├── app.py              entry point: menu + sidebar filters
├── config.py           paths, file names, display settings (business rules are in params.yaml)
├── data_loader.py      reads every file once (cache), alert status, measures, filters
├── metrics.py          all calculations, plain pandas (testable in Spyder)
├── ui.py               header, floor map, pills, footnote, theme
├── why.py              "Why did the model expect this value?" panels (extension 7.2)
├── views/              one file per page (10 pages)
├── tools/
│   ├── export_contributions.py   factors behind every expected value (LightGBM pred_contrib), run once
│   └── export_expected.py        fallback: rebuilds expected_hourly if reports/ does not have it
└── data/               files written locally (statuses, measures, contributions)
```

## Check (main, 25 Nov 2026, zone files)

- January 2022, all zones: 3,001 kWh used, 52.1 % in off-hours, off-hours waste 974 kWh = € 138 – 189, 136 kg CO₂,
  43 alerts (8 High, 20 Medium, 15 Low).
- Savings report, average 2021–22: 6.64 MWh, € 883 – 943, 0.80 t CO₂ (hourly intensity).
- "What if?" with the team settings reproduces `savings_summary.csv` exactly (7,205 / 6,075 kWh for 2021 / 2022).
- Standby NW Plugs 415 W, SE Plugs 97 W (team docs: ≈ 415 W and ≈ 100 W).
- Action planner, tab 2, default example: SE Plugs & Sockets on 2 Dec 2021 → waste −92 % on similar days.
