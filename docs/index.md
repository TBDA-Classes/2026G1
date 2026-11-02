# CeDInt Storey 1 — Energy waste finder

**TBDA 2026 · Group 1 · Universidad Politécnica de Madrid**

This site documents a decision tool for CeDInt. It turns the building's electricity data into clear answers to three questions:

1. **Where and when** is electricity used while Storey 1 is empty?
2. **What does it cost** in euros and CO₂?
3. **What should be fixed first?**

## The main finding

More than half of the floor's non-essential electricity is used while the building is closed:
at night, at weekends and during holidays. The biggest single cause is **electric heaters on the plug
sockets of zone NW**, left on in empty rooms. The second is the **NW lighting**, which is on every night.

| Year | Potential savings | € per year | CO₂ per year |
|---|---|---|---|
| 2021 | 7.2 MWh | €740 – 1,020 | 1.9 t |
| 2022 | 6.0 MWh | €850 – 1,010 | 1.6 t |

*Nine focus circuits; CO₂ factor still to be confirmed.*

## How it works, in one paragraph

We cleaned four years of hourly meter data and added weather, holidays and electricity prices. For each circuit, a
model (LightGBM) learns how much electricity is *normally* used at each hour. When the real use is far above that, or
when the building is closed and use stays above the standby level, the tool raises an alert. Each alert gets a value
in € and CO₂ and a severity, so the building manager sees the most important problems first. The alerts are tuned so
that each circuit raises about one alert per week.

## Where to find what

| Page | For whom | Content |
|---|---|---|
| [Methodology](METHODOLOGY.md) | everyone | how the project is organised (CRISP-DM in Scrum sprints) and the data in short |
| [Data dictionary](DATA_DICTIONARY.md) | anyone using the data | every column: meaning, unit, source |
| [Pipeline, cleaning and detection](PIPELINE_MODEL_DETECTION.md) | technical readers, maintenance | every cleaning decision, the model and the alert rules |
| [Experiment log](EXPERIMENT_LOG.md) | technical readers, reviewers | every experiment with settings and results |
| [Modelling summary](modelling.md) | technical readers | short summary of the three notebooks |
| [Project status](STATUS_AUDIT.md) | the team | what is done and what is open |

The code is on [GitHub](https://github.com/TBDA-Classes/2026G1). The project is planned in Jira (project KAN).
