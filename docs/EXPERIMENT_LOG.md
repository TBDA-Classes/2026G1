# Experiment log (KAN-143)

Every modelling experiment of Group 1, in the order it was done: what we tried, on which data, with which settings,
what came out, and what we decided. New experiments are added at the bottom with the next number.

**How to add an entry:** copy the template at the end of this page, fill in every field, and link the code or notebook.
If the code is not in the repo, say so.

## Common set-up (unless an entry says otherwise)

| | |
|---|---|
| Data | frozen dataset `data/processed/cedint_hourly_v1.parquet` (see [MANIFEST](https://github.com/TBDA-Classes/2026G1/blob/main/data/processed/MANIFEST.json) and the data dictionary) |
| Data (from EXP-13) | the cleaned zone files of the data-cleaning group, `data/zone_NE/NW/SE/SW_hourly.parquet`, joined into one table by `src/zones.py` (same 26,830 hours) |
| Target | energy used per hour per circuit, in Wh (= mean W of that hour), predicted **one day ahead** |
| Circuits | 9 "focus" circuits: Plugs & Sockets (NW, SW, SE, NE), Lighting (NW, SW, SE), HVAC (NW, SE) |
| Split (by time, never random) | train Jun 2020 – Aug 2022 · validation Sep – Dec 2022 · test Jan – Feb 2023 (used once) · Regime B Aug – Oct 2025 (out-of-time check). COVID lockdown (until 21 Jun 2020) left out. |
| Main metric | **MAE in kWh per hour** (average miss, in the unit the client uses) |
| Other metrics | RMSE (punishes big misses), CV(RMSE) = RMSE ÷ mean (ASHRAE Guideline 14 target: ≤ 30 % for hourly models), NMBE = bias |
| Random seed | fixed in `src/models.py` |

---

## EXP-01 · First test model on zone totals

| | |
|---|---|
| Date / sprint | Sprint 2 (October 2026) |
| Who | Simone Massucco |
| Code | [`src/model_test.py`](https://github.com/TBDA-Classes/2026G1/blob/main/src/model_test.py) (a "spike": a quick test, not the final model) |
| Question | Can we predict tomorrow's hourly use of each zone? |
| Data | `clean_hourly_wide.parquet`, Regime A only; targets = the 4 zone totals and the storey total |
| Models | B1 same hour last week · B2 median of same weekday and hour over the last 4 weeks · LightGBM with calendar and lag features (all lags ≥ 24 h) · LightGBM quantile 5 % / 95 % as a "normal band" |
| Split | same dates as the common set-up |
| Results | Written to `out/model_results.csv`, but the `out/` folder is not in the repo, so the numbers cannot be checked here |
| Decision | Showed the approach works. Next step: model each **circuit** instead of zone totals, because waste is circuit-specific (heaters on plugs, lights at night). |

## EXP-02 · Linear regression for NW Plugs & Sockets

| | |
|---|---|
| Date / sprint | Sprint 2, reported in the Sprint 2 progress report (KAN-20) |
| Who | Owner of KAN-20 (Raffaele Simo) |
| Code | **Not in the repo** (requested in `docs/STATUS_AUDIT.md`) |
| Question | Does a simple linear model with weather and calendar beat the naive baselines? |
| Features | outdoor temperature, calendar, past use |
| Split | validation May – Oct 2022 (different from the common set-up) |
| Results | MAE 202 W on validation; error ≈ 51 % of average use vs 67–81 % for two simple baselines; R² 0.58 on training data |
| Decision | Use beats the baselines, and use rises as it gets colder, supporting the heater finding. Still far from the 30 % ASHRAE target, so a stronger model is needed (EXP-03). |
| Note | Not directly comparable with EXP-03: different validation months and no code to re-run it. |

## EXP-03 · Model ladder per circuit: baselines → Ridge → LightGBM

| | |
|---|---|
| Date | 2 November 2026 |
| Who | Emma Hendriks |
| Code | [`notebooks/02_models.ipynb`](https://github.com/TBDA-Classes/2026G1/blob/main/notebooks/02_models.ipynb), `src/features.py`, `src/models.py` |
| Results file | [`reports/model_comparison.csv`](https://github.com/TBDA-Classes/2026G1/blob/main/reports/model_comparison.csv) |
| Question | How well can we predict the expected use of each circuit, and is a complex model worth it? |

**Models tried** ("start simple, then earn complexity"):

| Model | Idea |
|---|---|
| B1 last week | same hour, 7 days earlier |
| B2 4-week median | median of the same hour in the last 4 weeks |
| B3 profile | typical value per hour and day type (working day or not), from training data; no memory, no weather |
| Ridge | linear regression with a penalty against overfitting; penalty strength α chosen on validation from 0.1, 1, 10, 100, 1000 |
| LightGBM | gradient-boosted decision trees, L1 loss (less sensitive to extreme values) |

Ridge and LightGBM were each trained with **two feature sets**:

- **forecast**: calendar + weather + recent use (yesterday same hour, 2 days ago, 1 and 2 weeks ago, mean of the last 7 days at that hour)
- **normal**: calendar + weather + a slow "level" (median working-hours use of the last 28 days), with no recent use, so that long-lasting waste is not learned as normal

**Leakage checks:** every value based on the target is at least 24 h old, lags never cross the 2023–2025 gap, no same-hour
measurements or indoor sensors, pre-processing fitted on training rows only, test used once. Checked automatically in `tests/test_features.py`.

**Results — validation (Sep – Dec 2022), MAE in kWh per hour**

| Circuit | Best model | Best baseline | LightGBM_forecast | vs best baseline | CV(RMSE) LGB |
|---|---|---|---|---|---|
| NW Plugs & Sockets | LightGBM_forecast (0.694) | B2 (0.847) | 0.694 | 18 % better | 57 % |
| SW Plugs & Sockets | Ridge_forecast (0.057) | B1 (0.074) | 0.058 | 22 % better | 25 % |
| SE Plugs & Sockets | B2 (0.054) | B2 (0.054) | 0.078 | 46 % worse | 197 % |
| NE Plugs & Sockets | LightGBM_forecast (0.028) | B1 (0.052) | 0.028 | 46 % better | 40 % |
| NW Lighting | LightGBM_forecast (0.065) | B3 (0.094) | 0.065 | 31 % better | 95 % |
| SW Lighting | LightGBM_normal (0.170) | B3 (0.206) | 0.172 | 17 % better | 157 % |
| SE Lighting | LightGBM_forecast (0.106) | B3 (0.108) | 0.106 | 2 % better | 279 % |
| NW HVAC | B2 (0.002) | B2 (0.002) | 0.004 | worse (almost no use in these months) | 30 % |
| SE HVAC | LightGBM_forecast (0.013) | B2 (0.014) | 0.013 | 9 % better | 41 % |

**Results — test (Jan – Feb 2023, used once), MAE in kWh per hour**

| Circuit | Best model | Best baseline | LightGBM_forecast | vs best baseline | CV(RMSE) LGB |
|---|---|---|---|---|---|
| NW Plugs & Sockets | LightGBM_forecast (0.974) | B2 (1.051) | 0.974 | 7 % better | 53 % |
| SW Plugs & Sockets | LightGBM_forecast (0.088) | B1 (0.125) | 0.088 | 30 % better | 47 % |
| SE Plugs & Sockets | B2 (0.059) | B2 (0.059) | 0.062 | 5 % worse | 155 % |
| NE Plugs & Sockets | Ridge_forecast (0.019) | B3 (0.040) | 0.037 | 8 % better | 46 % |
| NW Lighting | LightGBM_forecast (0.080) | B3 (0.092) | 0.080 | 14 % better | 99 % |
| SW Lighting | B2 (0.206) | B2 (0.206) | 0.209 | 1 % worse | 97 % |
| SE Lighting | B2 (0.084) | B2 (0.084) | 0.092 | 9 % worse | 221 % |
| NW HVAC | LightGBM_forecast (0.060) | B3 (0.095) | 0.060 | 37 % better | 61 % |
| SE HVAC | Ridge_forecast (0.035) | B2 (0.035) | 0.036 | 3 % worse | 52 % |

**What we learned**

- On validation, LightGBM_forecast is best on 5 circuits and within 0.002 kWh of the best on 2 more.
- On the test months it is best on 4 circuits and within about 0.01 kWh of the best on the others, **except NE Plugs**, where Ridge is clearly better (0.019 vs 0.037).
- **Ridge is close behind everywhere**, so most of the signal is simple: yesterday's use, season and temperature.
- The "normal" feature set (no recent use) is weaker almost everywhere.
- **CV(RMSE) is above the ASHRAE 30 % target for nearly all circuits.** People switching heaters and lights on and off is hard to predict hour by hour. For circuits that are almost always close to 0 (SE Lighting, NW HVAC in autumn), a percentage error is not meaningful, which is why MAE in kWh is the main metric.
- Test errors are higher than validation because January – February is the coldest and most variable period.
- The Christmas-break calendar looks wrong: 2 January 2023 was a working day in the data, but the calendar marks it as closed.

**Decision:** LightGBM_forecast is the "expected consumption" model for anomaly detection (EXP-06 onwards).
Ridge and B2 are kept as a sanity check. Deep learning is not used: the data are tabular (about 20,000 hours per circuit)
and boosted trees already beat the baselines.

## EXP-04 · LightGBM settings search

| | |
|---|---|
| Date / who | 2 November 2026 · Emma Hendriks (part of EXP-03) |
| Code | `tune_lgb()` in `src/models.py`; chosen settings in [`reports/model_params.json`](https://github.com/TBDA-Classes/2026G1/blob/main/reports/model_params.json) |
| Search space | 8 combinations: `num_leaves` 15 or 63 · `learning_rate` 0.03 or 0.1 · `min_child_samples` 20 or 80 · `n_estimators` 600 (fixed). Fixed: L1 loss, 80 % row and column sampling. |
| Chosen on | validation period only |

**Chosen settings (forecast feature set)**

| Circuit | num_leaves | learning_rate | min_child_samples |
|---|---|---|---|
| NW Plugs & Sockets | 15 | 0.03 | 20 |
| SW Plugs & Sockets | 15 | 0.03 | 80 |
| SE Plugs & Sockets | 63 | 0.03 | 80 |
| NE Plugs & Sockets | 15 | 0.03 | 20 |
| NW Lighting | 15 | 0.1 | 80 |
| SW Lighting | 15 | 0.03 | 80 |
| SE Lighting | 63 | 0.03 | 80 |
| NW HVAC | 15 | 0.03 | 80 |
| SE HVAC | 15 | 0.03 | 80 |

**Result:** small trees (15 leaves) with a slow learning rate win on most circuits. For NW Plugs, all 8 settings score between
0.694 and 0.714 kWh MAE on validation, so the result is **not sensitive to tuning**.

## EXP-05 · Out-of-time check on 2025 data

| | |
|---|---|
| Date / who | 2 November 2026 · Emma Hendriks (part of EXP-03) |
| Question | Does a model trained on 2020 – 2023 still work on the building 2.5 years later? |
| Set-up | models refitted on all 2020 – 2023 data, scored on Regime B (Aug – Oct 2025) |
| Result | LightGBM_forecast beats the 4-week median (B2) on 6 of 9 circuits and ties on NW Lighting; worse on SW Plugs and SE HVAC. NW Plugs: MAE 0.177 vs 0.197 kWh. The "normal" models do worse in 2025: without recent use they cannot adapt to changes in the building. |
| Decision | The forecast model is usable on new data, but should be **retrained on recent data before going live** (see EXP-09). |

## EXP-06 · Choosing the alarm threshold (alarm budget)

| | |
|---|---|
| Date / who | 2 November 2026 · Emma Hendriks |
| Code | [`notebooks/03_anomalies_and_savings.ipynb`](https://github.com/TBDA-Classes/2026G1/blob/main/notebooks/03_anomalies_and_savings.ipynb), `src/anomalies.py`, `params.yaml` |
| Results file | [`reports/anomaly_k.json`](https://github.com/TBDA-Classes/2026G1/blob/main/reports/anomaly_k.json) |
| Expected values | for every hour since 2020 by **cross-fitting**: each calendar quarter is predicted by a model trained on all other quarters, so no hour is predicted by a model that saw it |
| Rule | an hour is flagged when *actual − expected* > median + k × MAD (a robust measure of normal spread), computed **per circuit and per hour type** (working hours / off-hours). Flagged hours ≤ 1 h apart are merged into one event; events must last ≥ 2 h and be ≥ 0.5 kWh above expected. |
| How k was chosen | business rule: per circuit, the **smallest k that gives at most about 1 event per week** over the whole history, so the building manager is not flooded with alarms |

**Chosen k per circuit**

| Circuit | k | Circuit | k |
|---|---|---|---|
| NW Plugs & Sockets | 10 | SW Lighting | 12 |
| SW Plugs & Sockets | 2.5 | SE Lighting | 15 |
| SE Plugs & Sockets | 3.5 | NW HVAC | 8 |
| NE Plugs & Sockets | 2 | SE HVAC | 2 |
| NW Lighting | 8 | | |

**Result:** every circuit stays at about 1 event per week or less, except **SE Lighting** (1.6 per week even at k = 15).
It was almost always off in 2020 – 2023, so any use looks unusual. Its alerts mean "this light is on, which is rare", not automatically "waste".
Normal misses are about twice as large during working hours as off-hours, which is why the threshold depends on the hour type.

## EXP-07 · Does the detector find forgotten loads? (synthetic test)

| | |
|---|---|
| Date / who | 2 November 2026 · Emma Hendriks |
| Code | notebook 03, section 3; settings in `params.yaml` (`synthetic_test`, seed 7) |
| Why | no labelled waste exists (nobody recorded when something was left on), so we create our own test cases |
| Set-up | Sep 2022 – Feb 2023, model trained on Jun 2020 – Aug 2022 only. 40 fake loads of 3–12 hours added in off-hours: 1,000 W on plug circuits (one heater), 300 W on lighting and HVAC. The fake load also enters the lag features, as it would in reality. |
| Metrics | **recall** = share of fake loads found; **other events per week** = events not touching a fake load (real waste or false alarm, we cannot tell which) |

| Circuit | Fake load | k | Recall | Other events / week |
|---|---|---|---|---|
| NW Plugs & Sockets | 1,000 W | 10 | **32 %** | 1.93 |
| SW Plugs & Sockets | 1,000 W | 2.5 | 100 % | 0.97 |
| SE Plugs & Sockets | 1,000 W | 3.5 | 100 % | 1.28 |
| NE Plugs & Sockets | 1,000 W | 2 | 98 % | 0.27 |
| NW Lighting | 300 W | 8 | **10 %** | 0.23 |
| SW Lighting | 300 W | 12 | 100 % | 0.77 |
| SE Lighting | 300 W | 15 | 98 % | 5.07 |
| NW HVAC | 300 W | 8 | 100 % | 0.35 |
| SE HVAC | 300 W | 2 | 100 % | 0.35 |

**Result:** 98–100 % of fake loads found on 7 of 9 circuits. The two misses are the noisiest circuits: their normal
hour-to-hour swings are bigger than one forgotten device.

## EXP-08 · How big must a forgotten load be on NW Plugs?

| | |
|---|---|
| Date / who | 2 November 2026 · Emma Hendriks (follow-up to EXP-07) |
| Set-up | same as EXP-07, NW Plugs & Sockets only, k = 10, fake load size varied |

| Fake load | 1 kW | 2 kW | 3 kW | 5 kW | 8 kW |
|---|---|---|---|---|---|
| Recall | 32 % | 85 % | 92 % | 98 % | 98 % |

**Also tried:** judging whole nights or weekend days instead of single hours (sum of the misses per off-hours block).
This did **not** help (9–17 % recall for 1 kW), because the misses of neighbouring hours are strongly linked, so the noise does not cancel out.

**Decision:** the event alert catches several heaters or a large device left on. Smaller loads that repeat every week
are caught by a second, rule-based signal: off-hours use above the standby level (notebook 03, section 5).

## EXP-09 · Manual review of detected events

| | |
|---|---|
| Date / who | 2 November 2026 · Emma Hendriks |
| Set-up | the top 10 events over the whole history, and all events in Aug – Oct 2025, looked at one by one |
| Result | The largest NW Plugs events look like real waste: use stays flat and high through the night (e.g. 18–19 Nov 2021, +60 kWh; 25–26 Feb 2022, +96 kWh; 4–6 Jan 2023, +163 kWh). In 2025 the top event is SE Lighting on all weekend (26–29 Sep, 65 h, +21 kWh). But most other 2025 SE Lighting events are normal weekday use in August, which the 2020–23 model has never seen and the calendar marks as closed. |
| Decision | Retrain on recent data before going live; check the calendar; add a "this was normal" button in the dashboard so the manager's feedback becomes labels for future tuning. |

---

## EXP-10 · Prediction interval: a 90 % "normal band" per circuit

| | |
|---|---|
| Date / sprint | 3 November 2026 · Sprint 3 |
| Who | Marius Calves |
| Code | [`notebooks/04_prediction_interval.ipynb`](https://github.com/TBDA-Classes/2026G1/blob/main/notebooks/04_prediction_interval.ipynb), [`src/intervals.py`](https://github.com/TBDA-Classes/2026G1/blob/main/src/intervals.py), `tests/test_intervals.py` |
| Question | Can the model give a band that contains the real hourly use 90 % of the time, instead of one number? |
| Data | frozen dataset v1, 9 focus circuits, common split |
| Set-up | "forecast" features and LightGBM settings of EXP-03/04 (`reports/model_params.json`). Three versions: (1) quantile LightGBM 5 % / 95 % fitted on train; (2) + fixed conformal widening (CQR) calibrated on validation; (3) + rolling conformal widening from the misses of the last 14 / 28 / 56 days (hours ≥ 24 h old only). Window chosen on validation: **28 days**. All versions scored on the same hours. |
| Results | Average over the 9 circuits, **test** (Jan – Feb 2023): coverage 66 % (quantile) → 83 % (fixed) → **89 %** (rolling); width 0.62 → 0.67 → 0.75 kWh; Winkler score 1.19 → 1.12 → 1.12 kWh. **2025**: 73 % → 87 % → **89 %**. Raw quantile bands are far too narrow (SE Plugs only 9 % inside: its use dropped in 2022). Rolling coverage on test per circuit: 83.5–92.4 %, lowest on NW HVAC (83.5 %) and SE Plugs (84.8 %). |
| Decision | Keep quantile LightGBM + rolling 28-day conformal widening. Band saved for the dashboard in `reports/interval_bands.parquet` (test and 2025); all scores in `reports/interval_results.csv`. Next: add to the model card (KAN-162) and the "actual vs expected" chart (KAN-26). |

---

## EXP-11 · Prophet compared with LightGBM

| | |
|---|---|
| Date / sprint | 3 November 2026 · Sprint 3 |
| Who | Marius Calves |
| Code | [`notebooks/05_prophet_comparison.ipynb`](https://github.com/TBDA-Classes/2026G1/blob/main/notebooks/05_prophet_comparison.ipynb), [`src/prophet_compare.py`](https://github.com/TBDA-Classes/2026G1/blob/main/src/prophet_compare.py) |
| Question | Is LightGBM better than a well-known classic forecasting tool? |
| Data | frozen dataset v1, 9 focus circuits, common split; every model scored on identical hours |
| Set-up | Prophet (trend + daily shape for working and non-working days + weekly + yearly + regressors: holiday, break, August, heating / cooling degrees, sun). Trend chosen on validation from: stiff linear, flexible linear, flat. Compared with B2 and LightGBM forecast / normal (settings of EXP-04). Same refit scheme as EXP-03. |
| Results | Average MAE (kWh per hour) — validation: LightGBM_forecast 0.135 · B2 0.167 · LightGBM_normal 0.175 · Prophet 0.183. **Test:** 0.182 · 0.208 · 0.220 · **0.259**. **2025:** 0.051 · 0.061 · 0.075 · **0.354**. Prophet is best on no circuit in any period; LightGBM_forecast is best on 6 / 5 / 5 circuits. On 2025 Prophet's linear trend is extended over the 2.5-year gap (bias up to −7,700 % on SW Lighting). Sanity check: LightGBM test MAE identical to EXP-03 on all 9 circuits. |
| Decision | Keep LightGBM_forecast. Prophet cannot follow the recent level (no memory of recent use), and its trend is a risk after a data gap. SARIMA not tried. Results to be added to the model card (KAN-162). |

---

## EXP-13 · Model search: seven model types, four input sets, month-by-month check

| | |
|---|---|
| Date / sprint | 20 November 2026 · Sprint 4 |
| Who | Linnéa Alindell |
| Code | [`notebooks/04_model_search.ipynb`](https://github.com/TBDA-Classes/2026G1/blob/main/notebooks/04_model_search.ipynb), [`src/zones.py`](https://github.com/TBDA-Classes/2026G1/blob/main/src/zones.py) |
| Results file | [`reports/final_model_settings.json`](https://github.com/TBDA-Classes/2026G1/blob/main/reports/final_model_settings.json) |
| Question | Can other model types, other inputs or better settings predict normal use more accurately than the LightGBM of EXP-03? |
| Data | the new cleaned zone files (see common set-up); COVID lockdown removed; same split as EXP-03. Sections 2–6 on NW Plugs & Sockets only (the largest circuit, 43 % of all electricity on Storey 1), section 7 on all 9 circuits. |
| Score to beat | LightGBM with forecast inputs (EXP-03 settings): 0.698 kWh per hour on validation, NW Plugs |

**1. Seven model types × four input sets** (NW Plugs, validation, MAE in kWh per hour; 15 random settings per model, 6 for the neural network)

| Model | Calendar | + weather | + 28-day level ("normal") | + past use ("forecast") |
|---|---|---|---|---|
| Random forest | 0.826 | 0.916 | 0.822 | **0.650** |
| Decision tree | 0.801 | 0.892 | 0.858 | **0.650** |
| Neural network (MLP) | 0.811 | 0.935 | 0.786 | 0.681 |
| LightGBM | 0.906 | 1.050 | 0.834 | 0.698 |
| Linear / Ridge / Lasso | 0.949 | 0.955 | 0.913 | 0.738 |

- Past use is by far the most useful input: every model is best with it.
- Weather on its own makes every model worse. Use grows from year to year, so the models link older, lower-use years to their weather. Once past use is added, this effect disappears.
- Ridge and Lasso equal plain linear regression: with 18,000 training hours the penalty changes almost nothing.
- Random forest and a single decision tree look best here. But one four-month validation period can be lucky, so the best models were checked month by month.

**2. Month-by-month check** (walk-forward: for each month from Sep 2021 to Dec 2022, train on everything before it and predict that month; Sep 2022 skipped, only 105 usable hours)

| Model | Average MAE | Months won (of 15) |
|---|---|---|
| **LightGBM** | **0.570** | **9** |
| Neural network | 0.572 | 0 |
| Random forest | 0.579 | 4 |
| Linear regression | 0.595 | 2 |
| Decision tree | 0.601 | 0 |
| Baseline: 4-week median | 0.725 | 0 |

The decision tree drops from shared first place to last: its good score in step 1 was luck. All models beat the baseline by about 20 %.
Winter is much harder than summer (about 0.8–1.3 kWh per hour from November to March, below 0.2 in summer).

**3. How far ahead** (month-by-month, average MAE)

| Model | 1 hour ahead | 1 day ahead | 1 week ahead |
|---|---|---|---|
| LightGBM | 0.303 | **0.569** | 0.707 |
| Neural network | 0.288 | 0.576 | 0.667 |
| Random forest | 0.306 | 0.576 | 0.686 |

1 hour ahead is about twice as accurate, but it is **not used for the alerts**: a model that sees the last hour quickly
"gets used to" a heater left on and stops warning while it is still on. A model that only knows yesterday keeps warning.

**4. Training window** (LightGBM, month-by-month): all history 0.570 · last 12 months 0.571 · last 6 months 0.678.
Six months is clearly worse because the model never sees a full year of seasons. Keep all history; retrain with at least one full year.

**5. Bigger settings search** (50 random settings each for LightGBM and the neural network, LightGBM with early stopping)

| Model | Validation | Month-by-month |
|---|---|---|
| LightGBM, settings of step 1 | 0.698 | **0.570** (best in 10 of 15 months) |
| LightGBM, bigger search | 0.684 | 0.582 |
| Neural network, settings of step 1 | 0.681 | 0.572 |
| Neural network, bigger search | 0.678 | 0.627 |

Better on validation but worse month by month: the bigger search overfits the four validation months. Keep the settings of step 1.

**6. All 9 circuits** (month-by-month, average MAE over 9 circuits): LightGBM with **one shared set of settings** 0.117 ·
LightGBM with settings chosen per circuit 0.120 · baseline 0.157. LightGBM beats the baseline on all 9 circuits (by 12 % on SE Lighting
to 49 % on NW Lighting). The shared settings win on 7 of 9 circuits; where they lose, the difference is at most 0.001 kWh per hour.

**7. Final test** (used once; average MAE over 9 circuits)

| Model | Test Jan – Feb 2023 | 2025 (Aug – Oct) |
|---|---|---|
| **Final model** (shared settings) | **0.181** | **0.049** |
| Notebook 02 model (settings per circuit, EXP-04) | 0.182 | 0.050 |
| Baseline: 4-week median | 0.208 | 0.061 |

13 % better than the baseline on the test months and 21 % in 2025. On a few small, regular circuits the baseline is as good or
better (the three SE circuits in Jan – Feb 2023, by at most 0.007 kWh; SE HVAC and SW Plugs in 2025). The model predicts 12–18 % below
actual use on average. This is on purpose: it predicts the median, so rare peaks (the waste we look for) do not pull the expected value up.
The alarm thresholds of EXP-06 are measured from each circuit's own typical miss, so this bias does not cause extra alerts.

| Decision | |
|---|---|
| Final model | **One LightGBM model per circuit, all with the same settings** (`reports/final_model_settings.json`: 37 leaves, learning rate 0.0118, 691 trees, min_child_samples 97, subsample 0.68, colsample_bytree 0.83), forecast inputs, 1 day ahead, trained on all history. Simpler than nine sets of settings and just as accurate. |
| Not yet applied | Notebook 03 and the dashboard export (`dashboard/tools/export_expected.py`) still use the per-circuit settings of EXP-04 (`reports/model_params.json`). Switching changes the test MAE by only 0.001 kWh per hour, but the code and the notebooks should say the same thing. See open experiments. |

---

## Open experiments (not done yet)

| Planned | Jira | Note |
|---|---|---|
| Retrain after the calendar fix (Christmas break, August) | KAN-56 | results of EXP-03 to EXP-09 may change slightly |
| Re-run EXP-02 on the common split | KAN-20 | only if the code is pushed |
| Use the final settings of EXP-13 in notebook 03 and the dashboard export | KAN-162 | now `reports/model_params.json` (EXP-04); results change very little |
| Re-run notebooks 02 and 03 on the new zone files | – | notebooks 02–03 use the frozen dataset v1, notebook 04 the zone files; same hours, but both should use one source |
| Retrain once more 2025 data exists | – | SE HVAC and SE Lighting behave differently in 2025 (EXP-05, EXP-09, EXP-13) |
| Settings search per horizon (1 hour, 1 week) | – | all settings were chosen for 1 day ahead (EXP-13, step 3) |

---

## Template for a new entry

```
## EXP-NN · Short title

| | |
|---|---|
| Date / sprint | |
| Who | |
| Code | link to script or notebook (or "not in repo") |
| Question | what do we want to know? |
| Data | dataset version, circuits, period |
| Set-up | models, features, settings, split |
| Results | numbers, with the metric and the period they are measured on |
| Decision | what we do next because of this |
```
