# CeDInt Storey 1 — Energy waste & anomaly detection (TBDA 2026, Group 1)

Predict the **expected** hourly electricity use of every zone × circuit on Storey 1 of the CeDInt building (UPM),
flag hours that use much more than expected (lights, plugs or HVAC on at night, at weekends, on holidays),
and put a € and CO₂ figure on each event. Method: CRISP-DM in Scrum sprints. Jira: see `docs/reports/Link to jira`.

Status of every workstream: [docs/STATUS_AUDIT.md](docs/STATUS_AUDIT.md).
Modelling summary: [docs/modelling.md](docs/modelling.md). 

## Documentation

| Document | Content |
|---|---|
| [Methodology](docs/METHODOLOGY.md) | CRISP-DM in Scrum sprints, and a short description of the data |
| [Data dictionary](docs/DATA_DICTIONARY.md) | every column of the modelling dataset: meaning, unit, source |
| [Pipeline, cleaning and detection](docs/PIPELINE_MODEL_DETECTION.md) | every cleaning decision, the model and the alert rules, with reasons |
| [Experiment log](docs/EXPERIMENT_LOG.md) | every modelling experiment with settings, results and decisions |
| [Presentation storyline](docs/reports/PRESENTATION_STORYLINE.md) | plan for the final presentation (draft) |

## Notebooks (read in this order)

| Notebook | Question |
|---|---|
| `notebooks/01_eda.ipynb` | What drives the electricity use of each circuit? → decisions for modelling |
| `notebooks/02_models.ipynb` | How well can we predict the expected use? Baselines vs Ridge vs LightGBM, time split, leakage checks |
| `notebooks/03_anomalies_and_savings.ipynb` | Which hours/events are waste, how sure are we (synthetic test), and what is it worth in € and CO₂? |

The notebooks only read the frozen dataset; reusable code is in `src/` (`data.py`, `features.py`, `models.py`, `anomalies.py`),
parameters for € / CO₂ / alarm thresholds in `params.yaml`. Run them in order (02 writes `reports/model_params.json`, which 03 reads).
Jupyter kernel: the project venv (`python -m ipykernel install --user --name tbda`).

## Repository layout

```
data/
  raw/                  4 original exports Storey1_{NE,NW,SE,SW}_report_by_device.xlsx
  *.parquet / *.csv     pipeline outputs (clean hourly table, calendar, prices, merged table)
  processed/            FROZEN modelling dataset cedint_hourly_v1.parquet + MANIFEST.json
  archive/              duplicate uploads, kept until the group confirms which copy is final
src/                    all pipeline code (run order below)
tests/                  pytest checks on the frozen dataset
notebooks/              01 EDA, 02 models, 03 anomalies & savings
reports/                model results, anomaly events, savings, figures (dashboard inputs)
params.yaml             prices, CO2 factors, alarm settings (with sources)
docs/                   status audit, benchmark, modelling notes; reports/ (backlog, sprint reports), building/ (floor plans)
```

## Reproduce

```bash
python -m venv .venv            # keep the venv outside OneDrive if possible
pip install -r requirements.txt

python src/save_parquet.py      # 1. raw xlsx -> data/raw_combined_long.parquet (loader.py + unify.py)
#                                 2. raw -> hourly table (00_RAW_DATA)  ** code still missing, see STATUS_AUDIT **
python src/clean.py             # 3. cleaning rules R1-R12 -> data/clean_hourly_wide/long.parquet
python src/build_calendar.py    # 4. holidays, UPM breaks, COVID lockdown -> data/calendar_daily.parquet
python src/download_weather.py  # 5. Open-Meteo hourly weather  -> data/weather_hourly.parquet
python src/download_price_omie.py  # 6. OMIE day-ahead prices    -> data/prices_co2_hourly.parquet
python src/merge_external.py    # 7. join 3-6 -> data/clean_hourly_plus_external.parquet
python src/freeze_dataset.py    # 8. -> data/processed/cedint_hourly_v1.parquet + MANIFEST.json
pytest                          # 9. data quality tests
```

Steps 1–7 are already done; their outputs are committed, so modelling can start at step 8.
`src/check_utc.py` shows that the raw timestamps are UTC (light sensors vs. sun position).

## Data in one paragraph

Hourly readings from **2020-04-02 to 2023-02-28** (Regime A) and minute readings aggregated to hourly from
**2025-08-18 to 2025-10-13** (Regime B). There is **no data between March 2023 and August 2025** in the source files.
Energy per hour = mean power `W` of that hour (checked against the `Ea` counter: median ratio 1.00), which avoids
the counter resets in `Ea`. 16 circuits are kept; see `data/processed/MANIFEST.json` for columns, units and rules.
