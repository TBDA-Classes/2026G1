# Expected vs actual: model selector

The **Expected vs actual** page of the dashboard compares what a model expected for the building's electricity use with what was actually measured. Since PR #9, you can choose which model to look at and compare it with others in the same chart.

## What you can do on the page

- **Model dropdown:** choose one of the models from `reports/test_predictions.parquet`: B1, B2, B3, Ridge and LightGBM.
- **"Compare with" box:** add up to two more models to draw them in the same chart.
- **Quality chart:** highlights the selected model and shows its CV(RMSE).

## Things to know

- The alarm threshold and the 90 % band are only shown for the default alert model (`Alert model (LightGBM, all months)`).
- The other models only have predictions for the test months (Jan-Feb 2023). For other weeks the page shows a warning and falls back to the default model.
- If `reports/test_predictions.parquet` doesn't exist, the page shows an explanation instead of the models. The file is created by `notebooks/02_models.ipynb`.

## Where the code is

| File | What it does |
|------|--------------|
| `dashboard/views/expected_vs_actual.py` | The page: model dropdown, "Compare with" box, fallback warning, highlighted quality chart |
| `dashboard/data_loader.py` | `load_model_predictions()` reads the hourly predictions of every model on the test months (cached with `@st.cache_data`) |

## How to run it

```
cd dashboard
streamlit run app.py
```

Then open the **Expected vs actual** page and try the week of 02 Jan 2023: change the model and compare two more in the same chart.

## Source

Added in pull request #9 (commit `456b955`), by Edinav03.
