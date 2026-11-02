# Modelling — energy waste & anomaly detection (G1)

Short summary of notebooks `01_eda`, `02_models` and `03_anomalies_and_savings`. Details, plots and code are in the notebooks;
every number below comes from them.

## Approach in one picture

```
frozen dataset v1 ──► 01 EDA: what drives use? ──► 02 expected use per circuit ──► 03 residual = actual − expected
(hourly, 2020-23 + 2025)   (calendar, temperature,    (baselines → Ridge →          ├─ signal 1: events (model)
                            memory, trend)             LightGBM, time split)         ├─ signal 2: chronic off-hours waste (rule)
                                                                                     └─ € (OMIE / all-in) and CO₂ → dashboard CSVs
```

## Key findings from the EDA (notebook 01)
* NW Plugs & Sockets = **45 %** of Storey 1 electricity; it rises steeply below ~15 °C → **electric heaters on sockets**.
* NW Plugs stays high at night and steps up at 07:00 on weekends too (timer). NW Lighting is on **every night 22:00–07:00**.
* Use grows from year to year (NW Plugs winter level 1.6 → 2.4 → 2.8 kW); strong memory at 24 h and 1 week.
* Indoor presence sensor is not usable (does not follow working hours); indoor lux/temperature are effects of the target.

## Target, split, features, models (notebook 02)
| | |
|---|---|
| Target | energy per hour (Wh = mean W) per circuit, one day ahead; 9 "focus" circuits (plugs, lighting, NW/SE HVAC) |
| Split | train Jun 2020–Aug 2022 · validation Sep–Dec 2022 · test Jan–Feb 2023 (once) · 2025 = out-of-time check · lockdown removed |
| Features | hour, weekday, working day / holiday / break / August, season (sin/cos), outdoor temperature + heating/cooling degrees, sun, humidity; *forecast set*: lags 24 h/48 h/1 w/2 w + 7-day mean; *normal set*: 28-day working-hours level |
| Models | B1 last week, B2 4-week median, B3 day-type profile, Ridge (Pipeline), LightGBM (L1 loss, 8-setting search on validation) |
| Metric | **MAE in kWh** (main), RMSE, CV(RMSE) (ASHRAE 14), NMBE |

**Result:** LightGBM_forecast is best or within 0.002 kWh of the best on 7 of 9 circuits. NW Plugs: MAE 0.69 (val) / 0.97 (test)
vs 0.85 / 1.05 for the best baseline. Ridge is close. The "normal" set without recent lags is only baseline-level.
Full table: `reports/model_comparison.csv`.

## Anomalies and value (notebook 03)
* Expected values for all hours via quarterly **cross-fitting** (no hour predicted by a model that saw it).
* **Events:** residual > median + k·MAD per circuit and hour type; ≥ 2 h and ≥ 0.5 kWh; **k per circuit = smallest k with ≤ ~1 event/week** (alarm budget).
* **Synthetic test:** 98–100 % of injected loads found on 7 of 9 circuits; NW Plugs from ~2 kW (85 %), 1 kW only 32 %.
* **Chronic waste:** off-hours use above standby (10th percentile of night use).
* **Value (9 focus circuits):** 2021 — 7.2 MWh, €740–1,020, 1.9 t CO₂; 2022 — 6.0 MWh, €850–1,010, 1.6 t CO₂.
  Biggest lever: heaters on NW plugs (3–4 MWh/year), then the NW night light (~1 MWh/year).
* Outputs: `reports/anomaly_events.csv`, `reports/offhours_waste_daily.csv`, `reports/savings_summary.csv`; parameters in `params.yaml`.

## Defending the model (lecture "final challenge")
| Question | Answer |
|---|---|
| A. What exactly is the target? | Wh used in each hour per circuit, predicted a day ahead; residual vs this expectation = possible waste. |
| B. How was leakage prevented? | Target information ≥ 24 h old only; lags never cross the 2023-25 gap; no same-hour W/I/Pa/Ea or indoor sensors; scaler/encoder inside a Pipeline fitted on train; time-ordered split, test used once; `tests/test_features.py`. |
| C. Which metric matches the decision? | MAE in kWh (client thinks in kWh/€). For alarms: an alarm budget of ~1/week per circuit (alarm fatigue), with recall measured on synthetic loads. |
| D. Why is this complexity justified? | LightGBM beats all naive baselines on validation and test for the main circuits, Ridge shows most signal is simple, tuning is not fragile. No deep learning: tabular data, ~20k hours per circuit. |

## Limitations
No labelled waste (synthetic validation only) · hourly CV(RMSE) above the ASHRAE 30 % target for most circuits (occupant behaviour) ·
calendar assumptions (Christmas break, whole of August) look wrong in places · CO₂ factor and all-in price to be confirmed ·
use in 2025 differs from 2020-23 (retrain before going live) · "potential" savings may include some legitimate off-hours use.
