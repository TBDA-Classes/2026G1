# Dashboard stack (KAN-118)

Went with Streamlit.

Looked at Grafana as well but it doesn't really fit what we're doing. The data lives in pandas/parquet (and DuckDB later in 7.16), and Streamlit just reads that directly. Grafana would need a running server plus a datasource in between, which is a lot of setup for a 5 sprint project.

Other reasons:
- it runs with one command from the repo, nothing else to install or host
- the pages we have in the backlog (overview with KPIs, actual vs expected chart, warnings) are easier to write as plain python than as grafana panels
- demo mode in sprint 5 (replay a period hour by hour) is basically a slider and a loop in streamlit, in grafana we'd have to fake a live datasource
- everyone in the team can write python, nobody has done grafana before

If the sponsor at some point wants a permanently hosted monitoring tool on a live sensor feed then grafana makes more sense, but that's not in scope.

## Running it

```
pip install -r requirements.txt
python -m src.data.combine
streamlit run dashboard/app.py
```

combine.py builds data/processed/combined.parquet from the four zone excel files. It's a temporary version until 3.1 (KAN-11) is done, then we should use that one instead and keep this as the refresh command.

Files:
- dashboard/app.py - the app, pages go in dashboard/pages/ later
- src/data/combine.py - builds the combined table
- data/processed/ is gitignored
