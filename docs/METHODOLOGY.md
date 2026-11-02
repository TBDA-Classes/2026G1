# Methodology: CRISP-DM in Scrum sprints (KAN-102)

## Two methods, two jobs

We combine two well-known methods, because they answer different questions:

| Method | Answers | In our project |
|---|---|---|
| **CRISP-DM** (Cross-Industry Standard Process for Data Mining) | *What* steps does a data project go through? | the six phases below, from understanding the business problem to deploying the result |
| **Scrum** | *How* does the team organise the work? | 2-week sprints, a Product Backlog of user features ordered by value, tasks in Jira, a sprint review with the sponsor at the end of every sprint |

CRISP-DM is not a straight line: findings in a later phase often send you back to an earlier one.
Scrum suits this well, because every sprint can revisit a phase when new information appears.

## The six CRISP-DM phases in this project

### 1. Business understanding

**Question from the client (CeDInt, UPM):** where and when is electricity wasted on Storey 1, what does it cost
in € and CO₂, and what should be fixed first?

- **Stakeholders:** building manager, sustainability officer, maintenance technician, and the UPM / CeDInt sponsor (Product Owner).
- **Definition of waste:** electricity used above the standby level while the building is closed.
- **Success criteria:** a credible € and CO₂ figure per zone and year, alerts a manager can act on, and a forecast model that beats simple baselines.
- **Links:** SDG 7, 11, 12 and 13, and the EELISA alliance.

*Where:* Product Backlog report, business case (Jira epic 2).

### 2. Data understanding

- **The data:** four Excel exports, one per zone (NE, NW, SE, SW), with the electricity use of each circuit and indoor sensors.
- **Two periods:** hourly 2020–2023 and minute data in 2025, with a 2.5-year gap in between.
- **What we checked:** completeness per column and month, gaps, duplicates, counter resets, impossible values and stuck sensors.
- **Result:** 18 of 30 columns are fully reliable. Some meters are faulty, such as reversed emergency lighting, a dead projector circuit and stuck presence sensors.
- **First exploration:**
  - NW plug sockets use 45 % of the floor's electricity and rise sharply in cold weather, which points to electric heaters.
  - NW lights are on every night.
  - Use grows from year to year.

*Where:* data quality report and `Storey1_cleaned_data.xlsx` (KAN-12), `notebooks/01_eda.ipynb`.

### 3. Data preparation

- **Cleaning:** 12 numbered rules; wrong values become empty, never invented.
- **Time and grid:** times converted from UTC to Madrid time, and one complete hourly grid.
- **Added data:** outdoor weather, the Madrid and UPM holiday calendar, and hourly electricity prices.
- **Frozen version:** one dataset (`cedint_hourly_v1`) with a fingerprint of every file, so every result can be reproduced.

*Where:* `src/`, `data/processed/`, [data dictionary](DATA_DICTIONARY.md), [pipeline and cleaning decisions](PIPELINE_MODEL_DETECTION.md).

### 4. Modelling

- **Expected use:** for each of 9 circuits, a model predicts the use for every hour, from simple baselines up to Ridge and LightGBM.
- **Two alert signals:**
  - **Events:** use far above the expected value.
  - **Chronic waste:** off-hours use above standby.
- **Value:** each alert gets a value in € and CO₂.

*Where:* `notebooks/02_models.ipynb`, `notebooks/03_anomalies_and_savings.ipynb`, [experiment log](EXPERIMENT_LOG.md).

### 5. Evaluation

**Technical evaluation**

- Time-ordered train / validation / test split, with the test period used once.
- An extra check on 2025 data.
- MAE in kWh as the main metric, with the ASHRAE Guideline 14 target as a reference.

**Detector evaluation**

- Fake "forgotten devices" added to the data to measure how many are found.
- A manual review of the largest events.

**Business evaluation**

- Potential savings of 6–7 MWh, about €740–1,020 and 1.6–1.9 t CO₂ per year on the focus circuits.
- About one alert per circuit per week, so the manager is not flooded.

*Where:* [experiment log](EXPERIMENT_LOG.md), [modelling summary](modelling.md).

### 6. Deployment

- **Streamlit dashboard:** an overview, alerts, a floor map and a savings report.
- **Deployment plan:** how the product would run on CeDInt's live data (data connection, hosting, retraining, monitoring).
- **Demo mode:** replays historical data as if it were live.
- **Delivery:** documentation, the final presentation (30 Nov 2026) and the upload to Moodle (14 Dec 2026).

*Where:* Jira epics 7 and 8, deployment plan (KAN-159).

## How the phases map onto the sprints

| Sprint | Dates | Main CRISP-DM phases |
|---|---|---|
| 1 | 28 Sep – 11 Oct | Business understanding, data understanding |
| 2 | 12 – 25 Oct | Data preparation, first models, business case |
| 3 | 26 Oct – 8 Nov | Modelling and evaluation, dashboard skeleton |
| 4 | 9 – 22 Nov | Evaluation, dashboard, documentation |
| 5 | 30 Nov – 14 Dec | Deployment: final presentation, demo, delivery |

## Examples of going back a phase

- **Modelling → data preparation:** the models showed that 2 January 2023 was a normal working day, while the calendar marked it as closed. The calendar dates need checking.
- **Evaluation → modelling:** the event detector misses small repeated waste, such as one heater left on every weekend. So a second, rule-based signal (chronic waste) was added.
- **Evaluation → business understanding:** in 2025, one lighting circuit is used in a new way. The model must be retrained on recent data before going live, and the dashboard needs a "this was normal" button so the manager's feedback can improve the alerts.

## Data description

| | |
|---|---|
| Building | CeDInt, Universidad Politécnica de Madrid, Montegancedo campus — Storey 1, four zones (NE, NW, SE, SW) |
| Source | four Excel exports from the building's metering system, one per zone |
| Measurements | average power per circuit (plugs and sockets, lighting, HVAC, emergency lighting, hand dryers, server rack), plus indoor temperature, humidity, light and presence in three zones |
| Periods | 2 Apr 2020 – 28 Feb 2023 (hourly) and 18 Aug – 13 Oct 2025 (per minute, averaged to hourly) |
| Size | 26,830 hours; 16 usable circuits after cleaning |
| Added data | Open-Meteo hourly weather, Madrid and UPM holiday calendar, OMIE hourly electricity prices |
| Privacy | no personal data; presence only as a zone-level share of the hour |

Every column is described in the [data dictionary](DATA_DICTIONARY.md).
