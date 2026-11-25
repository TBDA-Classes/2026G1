"""User guide (quality requirement Q6) and the usability-test script (Q3)."""
import streamlit as st

import config
import data_loader as dl

P, _ = dl.load_params()
night = P["off_hours"]["night_hours"]

st.title("How to use this dashboard")
st.caption("For the building manager, the technician and the sponsor — no data-science knowledge needed · "
           "what the dashboard must give its users: " + dl.doc_link("Customer value and solution"))

st.markdown(f"""
### In one minute

1. **Overview** — pick a month in the sidebar. You see how much electricity Storey 1 used, how much of it was
   wasted while the building was empty, what that cost, and which alerts to look at. Click a zone of the floor map
   to focus on it: every page follows.
2. **Alerts** — the list of unusual events, the most expensive first. Click a line to see why it was raised, then
   mark it *Handled*, *Under investigation*, *This was normal* or *Data error*.
3. **Savings report** — what the waste is worth per year and what to fix first. Download it for a meeting.
4. **Action planner** — choose a measure (switch off heaters, timer on the lights…), see what it saves in kWh,
   € and CO₂ and how fast it pays back; later, check that the waste really went down after the date it was taken.
5. **Live demo** — replays autumn 2025 as if the data arrived now: alerts pop up when they happen.

**The monthly cycle:** see the month (Overview) → locate it (floor map, Off-hours use) → understand it (Alerts,
*Why did the model expect this value?*) → act (Action planner) → verify the next month (Action planner, tab 2).
""")

left, right = st.columns(2)
with left.container(border=True):
    st.markdown(f"""
**Words used in the dashboard**

| Word | Meaning |
|---|---|
| Closed / off-hours | nights {night[0]}:00–{night[1]:02d}:00, weekends, holidays, UPM breaks |
| Standby level | what a circuit uses when almost everything is off (e.g. NW plugs ≈ 415 W) |
| Waste | electricity above the standby level while the building is closed |
| Expected | what the model predicts for that hour, day and weather; *Why did the model expect this value?* shows which factors (temperature, type of day, recent use…) pushed it up or down |
| Alert | several hours well above the expected use |
| High / Medium / Low | money at stake and duration of the alert |
| To investigate | an alert mostly during working hours: maybe legitimate, not counted as savings |
| Data error | missing or wrong readings: never counted as waste |
""")
with right.container(border=True):
    st.markdown("**Good to know**")
    st.markdown(
        "- All numbers are **historical** (2020–23 and 2025): the dashboard does not switch anything.\n"
        "- € are given as a **range**: from the wholesale market price (OMIE, lower bound) to an all-in tariff of "
        "€ 0.142/kWh excl. VAT (upper bound). CeDInt's real tariff is not known (try yours in "
        "*Savings report → What if?*).\n"
        "- CO₂ uses the hourly carbon intensity of the Spanish grid (Red Eléctrica).\n"
        "- Missing hours are left empty, never counted as zero or as waste.\n"
        "- An orange *Data coverage* badge means many hours are missing that month: read the figures with care.\n"
        "- Every assumption is listed in the " + dl.doc_link("Assumptions register") + ".")

with st.expander("Usability test script (for 3 people outside the team, quality requirement Q3)"):
    st.markdown("""
Give the person the laptop on the Overview page, say nothing else, and time each task. Note where they hesitate.

| # | Task | Success if they… |
|---|---|---|
| 1 | "How much did the waste cost in January 2022?" | find the € figure on the Overview in under 1 min |
| 2 | "Which zone wastes the most?" | name NW, using the floor map |
| 3 | "Find the most expensive alert of February 2022 and say why it was raised" | open Alerts, click the first line, read the reason |
| 4 | "Mark that alert as handled" | change the status |
| 5 | "How much could CeDInt save per year, and on what first?" | open the Savings report, read the total and the top item |
| 6 | "If the NW heaters were switched off at night, how much would CeDInt save, and did a past change work?" | use both tabs of the Action planner |

After the tasks: *What was hard to understand? What would you remove? Would you use it every week?*
Write the answers in the backlog (KAN item for Q3) and fix the two most frequent problems.
""")
