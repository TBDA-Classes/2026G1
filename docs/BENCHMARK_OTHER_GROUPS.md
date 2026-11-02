# Benchmark: what G2 and G3 have that we don't (2 Nov 2026)

Read-only look at the public repos `TBDA-Classes/2026G2` and `TBDA-Classes/2026G3`. Ideas only; no code or text copied.

| Workstream | G2 | G3 | G1 now | What we do |
|---|---|---|---|---|
| Reproducibility | frozen v1.0 CSV → derived v1.2 parquet with META.json (SHA-256, parameters, splits); `DECISIONS` file | raw → clean in one script `clean_cedint.py` (v0.4); data kept on Drive | frozen v1 + MANIFEST.json, but raw → hourly step missing | ask Massucco for the missing step; keep one MANIFEST per dataset version |
| Cleaning | per-zone rules, notebook v4, data dictionary of anomalies | "nothing deleted": raw columns kept + 0/1 flag columns; anomaly log | 12 numbered rules R1–R12 in `clean.py` | add a short cleaning QA summary (counts per rule) to reports/ |
| Calendar / weather | calendar script, weather 2019–26 | holiday / August flags | calendar with UPM breaks + COVID, Open-Meteo weather, OMIE prices | already at their level; prices are an extra |
| EDA | `eda_analysis.py` + EDA report | profiles, zone comparison notebooks | nothing in repo | EDA script with daily/weekly profiles per circuit and off-hours share |
| Baselines | B1 last week, B2 weekday×hour, B3 persistence, with tests | seasonal-naive, linear | B1, B2 in `model_test.py` | B1, B2, hour-of-week profile, tested |
| ML | GBM + linear + Chronos (pretrained, = transfer learning), ≥100 configs per model, val/test **on 35 days of 2025 data only** | not started | LightGBM on zone totals | per-circuit Ridge + LightGBM trained on **~2.5 years** of Regime A — our main advantage; Regime B as an out-of-time check |
| Metrics | scaled MAE (÷ train mean), RMSE | MAE, RMSE, CV(RMSE), NMBE, ASHRAE pass/fail | MAE, RMSE, CV(RMSE) | MAE (kWh) main, RMSE, CV(RMSE) |
| Anomalies / waste | not yet | anomaly candidates in eval toolkit | € estimate in report only | residual + off-hours rules → events with € and CO₂ (our topic) |
| Dashboard | Streamlit mockup | — | Streamlit skeleton (PR #5) | feed it `reports/anomaly_events.csv` |
