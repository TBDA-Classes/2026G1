# Storey 1 energy dashboard (CeDInt · UPM · TBDA Group 1)

Streamlit dashboard that shows the **results of the modelling notebooks** (`reports/`) on top of the
**frozen hourly dataset** (`data/processed/cedint_hourly_v1.parquet`). It does not compute its own waste
figures: every number comes from the team's files, with the team's definitions (`params.yaml`).

Step-by-step guide: [INSTALL_EN.md](INSTALL_EN.md) · en français : [INSTALL_FR.md](INSTALL_FR.md)

## Run it

From the repository root:

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

The `dashboard/` folder must sit at the root of the 2026G1 repository, next to `data/`, `reports/` and `params.yaml`.

## Pages

| Page | Question | For whom | Main source |
|---|---|---|---|
| Overview | How much was wasted this month, where, what is urgent? | building manager, sponsor | `offhours_waste_daily.csv`, `anomaly_events.csv` |
| Off-hours use | How much energy is used when the building is empty? Which waste comes back every winter? | building manager | frozen dataset, `offhours_waste_daily.csv` |
| Expected vs actual | Does this circuit use more than the model expects? How good is the model? | energy analyst | `expected_hourly` (or `test_predictions`), `interval_bands`, `model_comparison.csv` |
| Alerts | Which events to check first? Mark them handled / "this was normal" | technician | `anomaly_events.csv` |
| Savings report | What is the waste worth per year, what to fix first? Export | sustainability officer, sponsor | `savings_summary.csv` |
| Data quality | Can I trust these numbers? | everyone | frozen dataset, `MANIFEST.json` |
| Method | How does it work, how was it tested, what are the limits? | jury, reviewers | `anomaly_k.json`, `reports/figures/` |

Sidebar filters (month, zone, load type) apply to every page. Clicking a zone on the Overview floor map sets the zone filter.

## Data sources

| File | Made by | Used for | If missing |
|---|---|---|---|
| `data/processed/cedint_hourly_v1.parquet` | data team (`src/freeze_dataset.py`) | use per hour and circuit, off-hours, coverage | falls back to `data/clean_hourly_plus_external.parquet`, else error |
| `params.yaml` | modelling team | prices, CO₂, off-hours, severity | built-in copy in `config.py` |
| `reports/anomaly_events.csv` | notebook 03 | alerts (signal 1) | pages show a note |
| `reports/offhours_waste_daily.csv` | notebook 03 | chronic waste (signal 2), € and CO₂ | pages show a note |
| `reports/savings_summary.csv` | notebook 03 | Savings report | page shows a note |
| `reports/model_comparison.csv` | notebook 02 | model scores | chart hidden |
| `dashboard/data/expected_hourly.parquet` | `python dashboard/tools/export_expected.py` | expected line + alarm threshold for every hour | `reports/test_predictions.parquet` (Jan–Feb 2023 only), else team baseline B2 |
| `reports/interval_bands.parquet` | notebook 04 (branch KAN-144) | 90 % band | no band |

Every output is searched first in `dashboard/data/`, then in `reports/`.

### Definitions (same as `src/data.py`, `src/anomalies.py`)

- **Off-hours** = nights 22:00–05:59 (`params.yaml`) + weekends, holidays, breaks (team calendar).
- **Standby level** = 10th percentile of the circuit's night use, Jun 2020 – Aug 2022.
- **Chronic waste** = use above standby during off-hours. **Alert** = hours far above the model's expectation
  (≥ 2 h, ≥ 0.5 kWh, k per circuit for ≈ 1 alert/week). Alerts mostly in off-hours are listed as waste,
  the others as "to investigate".
- **9 focus circuits**: plugs (4 zones), lighting NW/SW/SE, HVAC NW/SE. Emergency lighting, rack, hand dryers
  and NE HVAC are fixed loads (shown in totals and data quality only).
- COVID lockdown hours are left out, as in the models.

## Folder

```
dashboard/
├── app.py              entry point: menu + sidebar filters
├── config.py           paths, file names, display settings (business rules are in params.yaml)
├── data_loader.py      reads every file once (cache), alert status, filters
├── metrics.py          all calculations, plain pandas (testable in Spyder)
├── ui.py               header, floor map, pills, footnote
├── views/              one file per page
├── tools/
│   └── export_expected.py   expected use for every hour, re-using src/ (run once)
└── data/               expected_hourly.parquet, alert_status.csv (written locally)
```

## Check

January 2022, all zones: 3,001 kWh used (all circuits), 52.1 % in off-hours, chronic waste 974 kWh
(€138–189), 44 alerts (8 high). Standby NW Plugs 415 W, SE Plugs 97 W (team docs: ≈ 415 W and ≈ 100 W).
