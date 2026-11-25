# Expected vs actual: comparing prediction methods

The **Expected vs actual** page of the dashboard compares what a model expected for one circuit with what was actually
measured, one week at a time. It builds on the model selector of PR #9 (Edin): you still choose several models and see
them in the same chart, but the page now covers **every week** (2020–2023 and 2025), not only the test months, and it
says in which **evaluation phase** the week is, so nobody reads a fitted value as a forecast.

## What you can do on the page

- **Circuit and week** selectors (the week follows the month chosen in the sidebar).
- **Phase strip**: Train · Validation · Test · Out-of-time 2025. A red line shows where the week is.
- **"Prediction methods to compare"**: any of the methods that have values for that week.

| Method | Where the values come from | Weeks |
|---|---|---|
| LightGBM (team model) | `reports/expected_hourly.parquet` (notebook 03), except Jan–Feb 2023 → `reports/test_predictions.parquet` (notebook 02) | all |
| Ridge (linear model) | `reports/test_predictions.parquet` | Jan–Feb 2023 |
| B1 · same hour last week | computed in the dashboard (`metrics.b1_expected`) | all |
| B2 · 4-week median | computed in the dashboard (`metrics.b2_expected`) | all |
| B3 · day-type profile | computed in the dashboard, learned on Jun 2020 – Aug 2022 | all |

- **The LightGBM line is labelled by phase**:
  - Jun 2020 – Dec 2022: *expected afterwards* (cross-fitted: each quarter predicted by a model trained on the other
    quarters, later ones included). Good for finding past waste, not a forecast.
  - Jan – Feb 2023: *honest test* (trained up to 31 Dec 2022, predicted once). The cross-fitted values of these months
    are dropped on purpose.
  - Aug – Oct 2025: *real forecast* (trained only on 2020 – Feb 2023).
- **Alarm line and 90 % band** are drawn with LightGBM (not in the test months, where the alarm line belongs to the
  cross-fitted model).
- **MAE this week** for each method drawn, and the **accuracy table** (CV(RMSE), NMBE against the ASHRAE targets) for
  validation, test and 2025.
- **Why did the model expect this value?** Pick an hour (by default the largest gap of the week) and see which factors
  raised or lowered the LightGBM expectation: recent use, outdoor temperature, hour of the day, type of day, time of
  year, sunlight and humidity. Values from `dashboard/data/expected_contributions.parquet` (or `reports/`), made by
  `python dashboard/tools/export_contributions.py` (LightGBM `pred_contrib`, i.e. TreeSHAP; same data, settings and
  folds as notebook 03; the script checks that its expected values equal those of `expected_hourly.parquet`).

## Where the code is

| File | What it does |
|---|---|
| `dashboard/views/expected_vs_actual.py` | the page: selectors, phase strip, chart, MAE table, accuracy table, explanation panel |
| `dashboard/data_loader.py` | `method_series()` one method for one circuit (LightGBM test months from `test_predictions`), `methods_covering()` methods with values in a week, `load_expected()`, `load_bands()`, `load_test_models()`, `load_contributions()` |
| `dashboard/metrics.py` | baselines B1–B3, `phase_of()`, `accuracy_table()` |
| `dashboard/config.py` | `METHODS` (colour, line style, source), `PHASES`, `LGB_LABELS` |
| `dashboard/why.py` | the *Why did the model expect this value?* panels (also used on the Alerts page) |
| `dashboard/tools/export_contributions.py` | computes the factors once |

## How to run it

From the repository root:

```
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

Then open **Expected vs actual** and try the week of 9 Jan 2023 (honest test: LightGBM vs Ridge vs B1–B3), then a week of
September 2025 (real forecast).

## Source

Model selector: PR #9 (commit `456b955`), by Edinav03. Phases, methods for every week and explanations: dashboard v4,
by Hector D.
