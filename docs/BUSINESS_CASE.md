# Business case (KAN-10, KAN-132, KAN-136 · backlog F6.1)

**Status:** measured version, 15 November 2026. It replaces the first estimate of the Sprint 2 report (25 October) with
what the detector of notebook 03 actually finds. Section 9 explains every difference.
**Numbers:** `reports/savings_summary.csv`, `reports/anomaly_events.csv`, `reports/severity_calibration.json`
(notebook 03 and `src/calibrate_severity.py`). **Assumptions:** every price, factor and rule is in the
[assumptions register](ASSUMPTIONS_REGISTER.md), with its source and status.

---

## 1. Problem

CeDInt has measured the electricity of every circuit on Storey 1 since 2020, but nobody uses these data to manage
the building. **About half of the electricity of the nine circuits people switch on and off is used while the
building is closed** (54 % in 2021, 47 % in 2022: nights 22:00–06:00, weekends, holidays and breaks).
Heaters, lights and HVAC that stay on in empty rooms cost money and emit CO₂ without serving anyone, and today nobody sees it happen.

## 2. Client question

> *Where, when and how much electricity does CeDInt waste on Storey 1, what does it cost in € and CO₂,
> and which problems should the building manager fix first?*

## 3. Definition of waste

| Kind | Definition | Counted in € savings? |
|---|---|---|
| **Chronic off-hours waste** | use above the circuit's **standby level** while the building is **closed** | **Yes**: this is the savings potential |
| **Event** | an hour far above the **expected** use for that circuit, hour, day and weather (≥ 2 h and ≥ 0.5 kWh) | Off-hours events: already inside the line above. Working-hours events: **no**, shown as "to investigate", because part of that use is legitimate |
| **Data error** | gaps, counter resets, stuck or impossible values | **Never**: reported to the maintenance technician, excluded from € and CO₂ (backlog F2.2) |

- **Closed** = nights 22:00–05:59, weekends, Madrid and national holidays, and UPM breaks (Christmas, Holy Week, August).
- **Standby level** = the 10th percentile of night-time use in the training period: the level a circuit reaches
  when almost everything is off (NW Plugs ≈ 415 W, SW and NE Plugs ≈ 185 W, SE Plugs ≈ 100 W, lighting ≈ 0).
- **Essential loads** (emergency lighting, server rack) and tiny ones (hand dryers, NE HVAC) are not counted as waste.
- The Product Backlog (F1.1) used a wider definition of closed (outside Mon–Fri 08:00–20:00). The code uses the
  narrower night window so as not to overstate waste in the evening. **The sponsor should approve one** (section 12).

## 4. Solution

A decision tool on the CeDInt sensor data: a Streamlit dashboard plus an alert list, built for three users
(stakeholders and personas, KAN-120).

| User | Needs (KAN-120) | What the product gives | Backlog |
|---|---|---|---|
| Building manager | € and base-load waste, what to fix first | out-of-hours overview, expected vs actual use, alerts ranked by severity | F1, F3, F4, F5.2 |
| Sustainability officer | auditable kg CO₂ per zone and year | € and CO₂ per alert, yearly savings per zone and circuit | F5.1, F5.3 |
| Maintenance technician | located alerts, no alert fatigue, data errors apart | alerts per zone and circuit with a plain-language reason; about one per circuit per week | F2, F4 |
| Sponsor | evidence and a basis to decide | this business case, the [deployment plan](DEPLOYMENT_PLAN.md), a documented method | F6 |

## 5. Impact: measured on 2021–2022 (9 focus circuits, Storey 1)

| | 2021 | 2022 |
|---|---|---|
| Electricity of the 9 focus circuits | 22.3 MWh | 22.6 MWh |
| Used while closed | 54 % | 47 % |
| **Chronic off-hours waste (savings potential)** | **7.2 MWh** (32 % of their use) | **6.0 MWh** (27 %) |
| **Cost**, all-in price (€ 0.142/kWh) | **€ 1,020** | **€ 850** |
| Cost, hourly wholesale price only (OMIE, lower bound) | € 740 | € 1,010 |
| **CO₂** (grid mix 259 / 273 g/kWh) | **1.9 t** | **1.6 t** |
| Working-hours events "to investigate" (not counted) | 0.7 MWh | 1.4 MWh |

In 2022 the wholesale price alone was above the all-in price: the energy crisis. So for 2022 the all-in figure understates the real cost.

**Where the waste is**

| Circuit | 2021 MWh | 2022 MWh | € / yr (all-in) | What it looks like |
|---|---|---|---|---|
| **NW Plugs & Sockets** | 3.1 | 3.9 | € 440 – 560 | 400–900 kWh a month above standby from November to March, flat and high through the night: **electric heaters left on** in empty rooms |
| **NW Lighting** | 1.4 | 0.8 | € 110 – 200 | on every night 22:00–07:00; 66–72 % of its use is above standby while closed. **Security lighting or a timer setting?** (to confirm) |
| SE Plugs & Sockets | 1.7 | 0.3 | € 40 – 240 | high in 2021, **down 83 % in 2022**: something was switched off, which shows the savings are achievable |
| NW HVAC | 0.2 | 0.4 | € 25 – 55 | running at night and at weekends |
| Other 5 circuits | 0.8 | 0.6 | € 90 – 120 | SW Plugs, SE HVAC, NE Plugs, SW and SE Lighting |

**Zone NW is 65–85 % of all waste.** By load type: plugs 4.7–5.4 MWh, lighting 0.8–1.5 MWh, HVAC 0.3–0.5 MWh a year.

**How solid is the number?** The standby level is the main judgement call. With a much more generous standby
(30th instead of 10th percentile of night use) the potential is still **5.1–5.9 MWh a year**.

## 6. What to fix first

1. **NW heaters (≈ 3–4 MWh, € 440–560 a year).** Check what is plugged into the NW sockets; agree a rule or a timer
   that switches heaters off at the end of the day and over weekends and breaks. Mostly behaviour, almost no cost.
2. **NW night lighting (≈ 1 MWh, € 110–200 a year).** Confirm with the facility team whether it is needed. If not,
   a timer or presence sensor.
3. **HVAC running all weekend** (NW and SE). These alerts are raised to a higher severity by the duration rule (EXP-12).

**Prioritisation:** alerts are ranked by € and duration ([EXP-12](EXPERIMENT_LOG.md)). The building manager gets
**about 1.5 High alerts a week for the whole floor, and handling those covers 62 % of the € at stake** in all alerts.
Every circuit raises about one alert a week, so there is no flood of alarms.

## 7. Costs and benefits

**Costs** (details in the [deployment plan](DEPLOYMENT_PLAN.md))

| Item | Estimate |
|---|---|
| Development | done within the TBDA course; no cost to CeDInt |
| Pilot set-up (scheduled refresh on a UPM server) | about 5–8 developer days, once |
| Hosting | € 0 on an existing UPM server, or about € 120–240 a year for a small cloud VM |
| Operation | about 2 hours a month: review the High alerts and the monthly report |
| Software | open source only (Python, pandas, LightGBM, Streamlit): no licences |

**Benefit scenarios** (average of 2021–2022: 6.6 MWh, € 940 all-in, 1.75 t CO₂ of potential a year)

| Share of the potential removed | kWh / yr | € / yr (all-in) | t CO₂ / yr |
|---|---|---|---|
| 25 % (only the quick wins, partly) | 1.6 MWh | € 230 | 0.4 |
| 50 % (heaters and night light handled) | 3.3 MWh | € 470 | 0.9 |
| 75 % (all High alerts acted on) | 4.9 MWh | € 700 | 1.3 |

- A cloud VM is paid back once **13–26 % of the potential** is removed; on an existing UPM server there is no hosting cost.
- The main cost is people's time (about 24 hours a year). On one floor, the money saved is in the same range as that time,
  so the case gets stronger with scale: **the same pipeline runs on every floor and zone** of the CeDInt IoT platform,
  because devices keep the same IDs across the plans, the platform and the database. Floors 2–3 (backlog F6.5) add
  savings at almost no development cost.
- **Non-financial value:** credible CO₂ figures for the university's sustainability reporting, and a working demonstrator
  of the DataPack message: *"our organisation has the right tools and capabilities to do the best with your asset."*

## 8. Success KPIs for a pilot (KAN-131)

Linked to the focus metrics of the personas (KAN-120). Baseline = 2021–2022.

| KPI | Persona | Baseline | Target after one heating season |
|---|---|---|---|
| Off-hours share of focus-circuit use | Building manager | 47–54 % | below 40 % |
| NW Plugs off-hours use above standby, Nov–Mar | Building manager | 400–900 kWh a month | –30 % |
| Avoided cost and CO₂, reported monthly | Sustainability officer | € 940 / 1.75 t potential a year | report produced every month; ≥ 25 % of the potential removed |
| High alerts reviewed within one week | Maintenance technician | – | ≥ 80 % |
| Alerts marked "false alarm" (backlog F4.4) | Maintenance technician | – | below 30 %, else re-tune (KAN-150) |
| Model accuracy on new data (CV(RMSE), NMBE) | Sponsor | notebook 02 | no worse than at hand-over; retrain if worse for 2 weeks |

## 9. From the first estimate to the measured numbers

The Sprint 2 report gave a first estimate. The numbers changed because they are now computed hour by hour in code,
with documented parameters. The sponsor may ask why, so here is every difference.

| | Sprint 2 (25 Oct) | Now (notebook 03) | Why it changed |
|---|---|---|---|
| Share used while closed | 59 % | 47–54 % | closed now means nights 22:00–06:00 instead of outside 08:00–20:00 |
| Waste per year | 5.5–7.9 MWh | **6.0–7.2 MWh** | standby per circuit from the training period; 9 focus circuits |
| Cost per year | € 790–1,130 | **€ 850–1,020** all-in (€ 740–1,010 OMIE) | follows the kWh; hourly wholesale price added as a second view |
| CO₂ per year | 0.55–0.79 t | **1.6–1.9 t** | 0.10 kg/kWh was a temporary factor; now the Spanish grid mix of 259–273 g/kWh (CNMC, via MITECO) |
| Alerts to handle | ≈ 4 High a week cover 73 % of € | **≈ 1.5 High a week cover 62 % of €** | real detector (≈ 7.6 alerts a week) instead of a prototype (≈ 19 a week); new € + duration rule |

The headline did not change: **zone NW, heaters and the night light, about € 1,000 and 2 t CO₂ a year on one floor.**

## 10. Risks and limitations

- **No confirmed waste labels.** The detector is validated with fake loads (98–100 % found on 7 of 9 circuits) and a
  manual check of the largest events. Feedback buttons in the dashboard (F4.4) will create labels.
- **Potential, not guaranteed savings.** Part of the off-hours use above standby may be legitimate (late work, equipment that must stay on).
- **Calendar and prices to confirm**: the Christmas break and August closure look wrong in places (KAN-56); the price is an
  average, not CeDInt's contract (see the register).
- **The building changes.** In 2025 one lighting circuit is used in a new way. Retrain on recent data before going live.

## 11. SDGs and EELISA

| SDG | Target | Contribution |
|---|---|---|
| 7 Affordable and clean energy | 7.3 energy efficiency | finds electricity that can be saved without reducing comfort |
| 11 Sustainable cities and communities | 11.6 environmental impact of cities | turns an existing IoT network into lower building emissions |
| 12 Responsible consumption and production | 12.2 efficient use of natural resources | makes waste visible per zone and circuit, so it can be managed |
| 13 Climate action | 13.3 institutional capacity on mitigation | credible CO₂ figures and a repeatable method |

UPM is a founding partner of the **EELISA** alliance. Its SUSBCC community (Sustainable Buildings, Cities and
Communities) works on exactly this subject, and EELISA visited CeDInt-UPM in June 2025 in the ESA-ESAC think tank on
sustainable buildings. This open-source, student-built tool could be shared with that community and reused on partner campuses.

## 12. Decisions requested from the sponsor

1. **Approve the definition of waste** (section 3), including which hours count as closed.
2. **NW lighting:** is it security lighting on a timer? This decides whether about 1 MWh a year counts as waste.
3. **Tariff and VAT:** CeDInt's contract price, and whether UPM can recover VAT (if not, the price with all taxes applies and every € figure rises by about 19 %).
4. **CO₂:** does UPM buy electricity with renewable guarantees of origin? If so, the market-based CO₂ of the savings is 0, and we report the grid-average figure separately.
5. **Pilot:** approve a pilot on live data (deployment plan, option B) and start with the two quick wins.

### Sources

- Eurostat, electricity prices for non-household consumers, Spain (dataset nrg_pc_205): <https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_205/default/table>
- MITECO, *Guía para el cálculo de la huella de carbono*: uses 0.273 kg CO₂-eq/kWh for a supplier without guarantees of origin in its 2022 example; yearly factors from the CNMC electricity labelling: <https://gdo.cnmc.es>
- CeDInt-UPM, *EELISA visits CeDInt-UPM as part of the ESA-ESAC think tank* (10 July 2025): <https://www.cedint.upm.es/en/node/1701>
- UN SDG targets 7.3, 11.6, 12.2, 13.3: <https://sdgs.un.org/goals>
