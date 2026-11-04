# Running the Storey 1 dashboard on your computer

Step-by-step guide for Windows (Mac differences are noted).
Time: 15 minutes the first time, 30 seconds afterwards.

---

## 0. What you need

| Need | How to check | If missing |
|---|---|---|
| **Anaconda** (Python 3.10 or newer) | Start menu → type "Anaconda Prompt" | Download from https://www.anaconda.com/download, install with default options |
| **The 2026G1 repository** on your computer | A folder with `data`, `reports`, `src` and `params.yaml` | Step 1 |
| A web browser (Chrome, Firefox, Edge) | — | — |

Everything runs on your computer: no Streamlit account, no internet needed once installed.

---

## 1. Get the repository

**Option A — ZIP (simplest)**
1. Open https://github.com/TBDA-Classes/2026G1 → green **Code** button → **Download ZIP**.
2. Right-click the ZIP → **Extract All…** into a simple folder, e.g. `Documents\TBDA`.

**Option B — GitHub Desktop (easy updates)**
1. Install https://desktop.github.com
2. **File → Clone repository → URL**: `https://github.com/TBDA-Classes/2026G1`
3. Later, to get updates: **Fetch origin**, then **Pull origin**.

**Check the layout.** The `dashboard` folder must be **at the root of the repository**, next to `data` and `reports`:

```
2026G1\                         (or 2026G1-main\)
├── data\
│   └── processed\cedint_hourly_v1.parquet   ← frozen data
├── reports\                                  ← modelling results
├── src\
├── params.yaml
└── dashboard\
    ├── app.py                                ← the file to run
    ├── requirements.txt
    └── views\ ...
```

If the `dashboard` folder is not in the repository yet, copy it there.
Some ZIP tools create a double folder (`2026G1-main\2026G1-main\`): use the one that contains `data`.

---

## 2. Open the Anaconda Prompt

1. **Start menu** (⊞ key) → type **Anaconda Prompt** → open it.
2. A black window shows `(base) C:\Users\Name>`. `(base)` = Anaconda's Python is active.

**Mac:** the **Terminal** app (Spotlight → "Terminal").

---

## 3. Go to the repository root

1. In Windows Explorer, open the repository folder (the one containing `data`, `reports`, `dashboard`).
2. Click in the **address bar**: the path appears as text. Copy it (Ctrl+C).
3. In the Anaconda Prompt type `cd /d "`, paste, close the quotes, press Enter:
   ```
   cd /d "C:\Users\Name\Documents\TBDA\2026G1-main"
   ```
   The **quotes** are required if the path contains spaces or accents.
4. Check with `dir`: you should see `data`, `reports`, `dashboard`, `params.yaml`.

**Mac:** `cd "/Users/name/Documents/TBDA/2026G1-main"`, then `ls`.

---

## 4. Install the libraries (once)

```
pip install -r dashboard\requirements.txt
```

Installs Streamlit (the web app), Plotly (charts), pandas, pyarrow (.parquet files) and PyYAML
(reads `params.yaml`). 1–3 minutes; the last line says `Successfully installed …`
or `Requirement already satisfied`. (Mac: `dashboard/requirements.txt`.)

**Optional, cleaner: a dedicated environment**
```
conda create -n tbda python=3.12 -y
conda activate tbda
pip install -r dashboard\requirements.txt
```
Then type `conda activate tbda` every time before starting the dashboard.

---

## 5. Start the dashboard

```
streamlit run dashboard\app.py
```

- The first time, Streamlit may ask for an e-mail: **just press Enter**.
- Your browser opens on **http://localhost:8501** (otherwise paste that address).
- **Keep the black window open**: it is what runs the dashboard.

### Check that everything is connected

- At the bottom of the sidebar: `Data: data/processed/cedint_hourly_v1.parquet`.
- **Method** page, "Data sources" table: every file found is listed; missing ones say "not found".
- Quick check: **Overview**, month **January 2022**, all zones → **3,001 kWh**, **52.1 %** in off-hours, **44** alerts.

---

## 6. Stop it

Click in the black window and press **Ctrl+C**. To start again later: steps 2, 3 and 5.

---

## 7. Edit the code and see the result

1. Start the dashboard (step 5).
2. Open a file in Spyder, e.g. `dashboard\views\overview.py`, edit it, **save** (Ctrl+S).
3. In the browser, banner at the top right → **Always rerun**: the page refreshes on every save.

Do not use Spyder's ▶ (F5) button. Business rules (prices, CO₂, off-hours, thresholds) live in
**`params.yaml`** at the repository root, shared with the modelling team: changing them also changes the notebooks.

---

## 8. Alternative: everything from Spyder

In Spyder's IPython console (bottom right):
```
cd "C:\Users\Name\Documents\TBDA\2026G1-main"
%pip install -r dashboard\requirements.txt
!streamlit run dashboard\app.py
```
To stop: the console's red square, or **Consoles → Restart kernel**.

---

## 9. "Expected" line for every hour (once, optional)

Without this step, the **Expected vs actual** page shows the real model only for January–February 2023
(and the team's B2 baseline for other weeks). To get the model everywhere:

```
pip install -r requirements.txt
python dashboard\tools\export_expected.py
```

The first line installs the modelling libraries (LightGBM, scikit-learn). The script re-uses the team's
code (`src/`) and writes `dashboard\data\expected_hourly.parquet` in a few minutes.
Then in the dashboard: ⋮ menu at the top right → **Clear cache** → **Rerun**.

---

## 10. Updating when the modelling team publishes new results

1. Get the latest repository (GitHub Desktop: **Pull origin**; or a new ZIP).
2. In the dashboard: ⋮ menu → **Clear cache** → **Rerun** (or Ctrl+C and start again).
3. If the models changed, also re-run step 9.

---

## 11. Common problems

| Message or symptom | Cause | Fix |
|---|---|---|
| `'streamlit' is not recognized…` | Streamlit installed in another Python | `python -m streamlit run dashboard\app.py` |
| `Could not open requirements file` | Not at the repository root | Redo step 3, check with `dir` |
| `ModuleNotFoundError: plotly` / `pyarrow` / `yaml` | Step 4 not done in this environment | `pip install -r dashboard\requirements.txt` |
| Red "Hourly data not found" message | `dashboard` is not at the repository root | Move it next to `data` and `reports` (step 1) |
| A page says "needs reports/…" | That modelling file is not in your copy | Update the repository (step 10) |
| `ModuleNotFoundError: lightgbm` (step 9) | Modelling libraries missing | `pip install -r requirements.txt` at the root |
| `Port 8501 is already in use` | A dashboard is already running | Close the other window, or add `--server.port 8502` |
| Red error inside the page | Bug | Copy the full message and send it to the dashboard team |
| Slow first load (≈ 10 s) | Initial computation | Normal: instant afterwards (cache) |

---

## 12. Online version (if the team sets it up)

On Streamlit Community Cloud: repository `TBDA-Classes/2026G1`, branch `main`, file `dashboard/app.py`.
Then just open the `https://….streamlit.app` link.
