# Final presentation — storyline (KAN-107, draft)

**Date:** 30 November 2026 · **Audience:** the CeDInt / UPM sponsor (our "client") and the course teachers
**Message the client should leave with:** *"Our organisation has the right tools to do the best with your asset."*

The presentation is a **Sprint Review with the sponsor**: we show a working product, the evidence behind it,
and ask for a decision. It is not a tour of everything we did.

## The story in one sentence

> Storey 1 uses more than half of its non-essential electricity when nobody is there; we built a tool that finds
> that waste every week, puts a price on it, and tells the building manager what to fix first.

## Storyline (about 15 minutes; adjust to the time slot)

| # | Part | Key message | Content / evidence | Time |
|---|---|---|---|---|
| 1 | **Hook** | The building works hardest when it is empty | One chart: a normal week of NW plug use, high at night and at weekends. "This is a Saturday at 3 a.m." | 1 min |
| 2 | **The client's problem** | CeDInt has the data but no answers | Building manager: where and when? Sustainability officer: how much in € and CO₂? Technician: real problem or broken meter? | 1 min |
| 3 | **What we found** | Most waste has two simple causes | More than half of non-essential use happens while closed. Electric heaters on NW sockets (3–4 MWh/year) and NW lights on every night (about 1 MWh/year). Proof: use rises sharply below about 15 °C, and on some weekends the heaters *are* switched off, so it is avoidable. | 2 min |
| 4 | **Live demo** | The manager sees what to fix in one minute | See the demo script below | 4 min |
| 5 | **Why you can trust the numbers** | Careful data, honest testing | Cleaning: 12 documented rules, nothing invented. Model: beats simple methods, tested on months it never saw. Detector: finds 98–100 % of fake "forgotten devices" on 7 of 9 circuits. About 1 alert per circuit per week, so no flood of alarms. | 2 min |
| 6 | **What it is worth** | A small cost, a clear return | 6–7 MWh, €740–1,020 and 1.6–1.9 t CO₂ per year on one floor. Most of it is fixed by behaviour or timers, at almost no cost. Scaled to the whole building, and linked to SDG 7, 11, 12 and 13 and EELISA. | 2 min |
| 7 | **Honest limits** | We know where the tool is weak | No confirmed waste labels yet. Hour-by-hour accuracy is below the industry target (people are hard to predict). Calendar and CO₂ factor still to confirm. Retrain on recent data before going live. | 1 min |
| 8 | **Next step: the decision** | Ready to run on live data | Deployment plan: data connection, hosting, retraining, monitoring, cost. The ask: approve a pilot on the live IoT platform, and start with the two quick wins (NW heaters, NW night light). | 2 min |

## Demo script (part 4)

Use **demo mode** (historical data replayed as if live), so the demo does not depend on a network connection.

1. **Overview page:** this month's kWh, € and CO₂ wasted, plus open alerts. "In one glance, the manager knows the size of the problem."
2. **Floor map:** NW is red. Click NW.
3. **Alert list,** sorted by severity. Open the top alert, e.g. *SE Lighting on all weekend, Fri 26 Sep 16:00 to Mon 09:00, 65 hours, +21 kWh, about €3 and 5.5 kg CO₂*. Or one of the large NW heater events (25–26 Feb 2022, +96 kWh).
4. **Alert detail:** actual versus expected use, outdoor temperature, and the plain-language reason ("Lighting on Sunday 02:00, far above standby").
5. **Mark the alert as handled.** "Feedback makes the tool better over time."
6. **Savings report:** export to PDF for the sustainability officer.

Backup: if the dashboard fails, have screenshots of every step on hidden slides.

## Likely questions, and who answers

| Question | Short answer | Who |
|---|---|---|
| What exactly do you predict? | Energy used per hour per circuit, one day ahead; the gap between actual and expected is possible waste | modelling team |
| How did you prevent leakage? | Only information at least 24 h old, time-ordered split, test used once, automatic tests | modelling team |
| Why MAE and not accuracy? | The client thinks in kWh and €; percentages are meaningless for circuits close to 0 | modelling team |
| Why LightGBM and not deep learning? | Tabular data, about 20,000 hours per circuit; trees already beat the baselines; a linear model comes close, so the complexity is justified but not excessive | modelling team |
| How do you know an alert is real waste? | Fake-load test, plus a manual check of the largest events (flat high use all night) | modelling team |
| Why are your numbers different from the Sprint 2 report? | Now calculated hour by hour in code, with a real grid CO₂ factor instead of a temporary one | business team |
| What would deployment cost? | See the deployment plan (KAN-159) | business team |

## Still to decide in the group

- Time slot and number of speakers (who presents which part).
- Whether the dashboard runs live on a laptop or in demo mode only (KAN-101).
- Final numbers after the calendar fix and the CO₂ confirmation. **Update parts 3 and 6 then.**
- Which real alert to use in the demo.
