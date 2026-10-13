# Dashboard stack decision (KAN-118)

**Decision: Streamlit.**

## Why Streamlit over Grafana

1. Same stack as the rest of the project. The data layer is pandas, DuckDB and Parquet (KAN-25, KAN-44). Streamlit reads those directly; Grafana needs a database or plugin in between.
2. One command, no server setup. `streamlit run dashboard/app.py` from the repo. Grafana needs a running service, provisioning files and a data source, which is more to maintain for a five-sprint project.
3. Custom pages are code. The overview with KPIs (KAN-128), the actual vs expected chart with highlighted waste (KAN-26) and the warnings page (KAN-154) are plain Python and plotting code. Grafana panels are limited to what its panel types allow.
4. Demo mode (KAN-167). Replaying a past period hour by hour with alerts appearing in real time is a loop and a slider in Streamlit. In Grafana it would need a fake live data source.
5. Everyone in the team can contribute. Only Python is required; no Grafana-specific knowledge.

Grafana would be the better choice if the sponsor needed a permanently hosted monitoring tool fed by a live sensor stream. That is out of scope.

## How to run

```bash
pip install -r requirements.txt
python -m src.data.combine        # builds data/processed/combined.parquet from the four zone files
streamlit run dashboard/app.py
```

## Layout

- `dashboard/app.py`: the app. Later sprints add pages under `dashboard/pages/`.
- `src/data/combine.py`: builds the combined table. Temporary until KAN-11 (squad A) lands; then that script becomes the one-command refresh (KAN-230).
- `data/processed/`: generated files, not committed.
