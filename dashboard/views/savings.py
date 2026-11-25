import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import data_loader as dl
import metrics
import ui

hourly, src = dl.load_hourly()
P, _ = dl.load_params()
f = dl.get_filters()
sav, sav_src = dl.load_savings()

st.title("Savings report")
st.caption("What the off-hours waste is worth per year, and what to fix first · for the sponsor and the "
           "sustainability officer · " + dl.doc_link("Business case"))
if sav is None:
    ui.missing("The savings report", "reports/savings_summary.csv")
    st.stop()

sav = sav.rename(columns={"device": "load_type"})
sav["circuit"] = sav["zone"] + " " + sav["load_type"]
years = sorted(sav["year"].unique())
choices = ["Average " + "–".join(str(y)[-2:] if i else str(y) for i, y in enumerate(years))] + years
choice = st.radio("Period", choices, horizontal=True, index=0,
                  format_func=lambda c: c if isinstance(c, str) else str(c))
cols = ["potential_kWh", "eur_omie", "eur_all_in", "kg_co2", "to_investigate_workhours_kWh", "total_use_kWh"]
sel = dl.apply_filters(sav, f)
if isinstance(choice, str):
    y = sel.groupby(["circuit", "zone", "load_type"], as_index=False)[cols].mean()
    period = f"average of {', '.join(map(str, years))}, per year"
else:
    y = sel[sel["year"] == choice].copy()
    period = str(choice)
scope = " · ".join(x for x in [f["zone"], f["load"]] if not x.startswith("All")) or "9 focus circuits"

kwh, use = y["potential_kWh"].sum(), y["total_use_kWh"].sum()
nw = y.loc[y["zone"] == "NW", "potential_kWh"].sum()
c1, c2, c3, c4 = st.columns(4)
with c1.container(border=True):
    st.metric("Wasted after hours", f"{kwh / 1000:,.1f} MWh")
    st.caption(f"{kwh / use * 100:.0f} % of the use of the {scope} · {period}" if use else period)
with c2.container(border=True):
    st.metric("Cost", ui.eur_range(metrics.eur_range(y["eur_omie"].sum(), y["eur_all_in"].sum())))
    st.caption(f"wholesale price (lower bound) → € {P['price']['all_in_eur_per_kwh']}/kWh all-in: "
               "the exact tariff of CeDInt is not known")
with c3.container(border=True):
    st.metric("CO₂", f"{y['kg_co2'].sum() / 1000:,.2f} t")
    st.caption(ui.co2_label(P))
with c4.container(border=True):
    st.metric("Share in zone NW", f"{nw / kwh:.0%}" if kwh else "–")
    st.caption("heaters on the NW sockets, NW night light")

# --- Per circuit ------------------------------------------------------------------
left, right = st.columns([3, 2])
with left.container(border=True):
    st.markdown(f"**Waste per circuit, MWh a year** ({period}; orange = zone NW)")
    t = y.sort_values("potential_kWh", ascending=True)
    fig = go.Figure(go.Bar(
        y=t["circuit"], x=t["potential_kWh"] / 1000, orientation="h",
        marker_color=[config.COLOR_WASTE if z == "NW" else config.COLOR_WASTE_LIGHT for z in t["zone"]],
        text=[f"{k / 1000:.1f} MWh · {ui.eur_range(metrics.eur_range(o, e))}"
              for k, o, e in zip(t["potential_kWh"], t["eur_omie"], t["eur_all_in"])],
        textposition="outside", hovertemplate="%{y}: %{x:.2f} MWh<extra></extra>"))
    fig.update_layout(height=60 + 36 * len(t), margin=dict(l=0, r=110, t=0, b=0), xaxis=dict(visible=False))
    st.plotly_chart(fig)
    st.caption("Use above standby while the building is closed. Working-hours events are listed in Alerts "
               f"as \"to investigate\" ({y['to_investigate_workhours_kWh'].sum() / 1000:.1f} MWh, not counted).")

with right.container(border=True):
    st.markdown("**What to fix first**")
    top = y.sort_values("potential_kWh", ascending=False).head(3)
    for i, (_, r) in enumerate(top.iterrows(), 1):
        st.markdown(f"{i}. **{r['circuit']}** — {r['potential_kWh'] / 1000:.1f} MWh, "
                    f"{ui.eur_range(metrics.eur_range(r['eur_omie'], r['eur_all_in']))} a year  \n"
                    f"<span style='color:{config.COLOR_MUTED}'>{config.PATTERNS.get(r['circuit'], '')}</span>",
                    unsafe_allow_html=True)
    st.markdown("Mostly behaviour and timers: a rule for heaters at the end of the day, a timer or presence "
                "sensor on the NW lights, HVAC off at weekends.")
    st.markdown("**If CeDInt removes part of it**")
    base_eur = y["eur_all_in"].sum()
    base_omie = y["eur_omie"].sum()
    st.dataframe(pd.DataFrame({"Share removed": ["25 %", "50 %", "75 %"],
                               "MWh / yr": [kwh / 1000 * s for s in (0.25, 0.5, 0.75)],
                               "€ / yr": [ui.eur_range(metrics.eur_range(base_omie * s, base_eur * s))
                                          for s in (0.25, 0.5, 0.75)],
                               "t CO₂ / yr": [y["kg_co2"].sum() / 1000 * s for s in (0.25, 0.5, 0.75)]}).round(2),
                 hide_index=True)

# --- What if? (the questions for CeDInt, review slide B4) --------------------------
with st.container(border=True):
    st.markdown("### What if CeDInt answers differently?")
    st.caption("The final figure depends on four answers from CeDInt (business case §12). Change them here; "
               "the team figures above stay as they are.")
    a, b, c, d = st.columns(4)
    closed_def = a.radio("Which hours count as closed?", ["Nights 22:00–06:00 (team)", "Outside 08:00–20:00 (backlog)"])
    night_light = b.toggle("NW night light is needed (security)", value=False)
    price_label = c.selectbox("Tariff", list(config.PRICE_OPTIONS) + ["Other price…"])
    price = (c.number_input("€ per kWh", 0.05, 0.50, 0.142, 0.001, format="%.3f") if price_label == "Other price…"
             else config.PRICE_OPTIONS[price_label])
    co2_mode = config.CO2_OPTIONS[d.selectbox("CO₂ method", list(config.CO2_OPTIONS))]

    comp = dl.apply_filters(dl.chronic_compare(src), f)
    comp = comp[comp["year"].isin(years) & (comp["definition"] == ("night" if closed_def.startswith("Nights") else "day"))]
    team = dl.apply_filters(dl.chronic_compare(src), f)
    team = team[team["year"].isin(years) & (team["definition"] == "night")]
    if night_light:
        comp = comp[comp["circuit"] != "NW Lighting"]

    def per_year(t: pd.DataFrame, col: str) -> float:
        v = t.groupby("year")[col].sum()
        if v.empty:                               # no focus circuit in this selection (e.g. NE HVAC)
            return 0.0
        return float(v.mean() if isinstance(choice, str) else v.get(choice, 0.0))

    w_kwh = per_year(comp, "kWh")
    if price == "range":
        cost = (per_year(comp, "eur_omie"), w_kwh * P["price"]["all_in_eur_per_kwh"])
    elif price == "omie":
        cost = (per_year(comp, "eur_omie"),) * 2
    else:
        cost = (w_kwh * price,) * 2
    co2_kg = {"hourly": per_year(comp, "kg_hourly"), "grid": per_year(comp, "kg_yearly"),
              "low": w_kwh * P["co2"].get("low_reference_g_per_kwh", 102) / 1000, "zero": 0.0}[co2_mode]
    team_kwh = per_year(team, "kWh")
    r1, r2, r3 = st.columns(3)
    r1.metric("Waste", f"{w_kwh / 1000:,.1f} MWh / yr", f"{(w_kwh - team_kwh) / 1000:+.1f} MWh vs team settings",
              delta_color="off")
    r2.metric("Cost", ui.eur_range(metrics.eur_range(*cost)))
    r3.metric("CO₂", f"{co2_kg / 1000:,.2f} t / yr")
    st.caption("Same formula as notebook 03 (use above the standby level while closed), recomputed here hour by hour "
               "from the zone files for the chosen answers. Prices and CO₂ factors: "
               + dl.doc_link("Assumptions register") + " (A6, A11–A15).")

# --- Export ---------------------------------------------------------------------
lines = [f"# Storey 1 — potential savings ({period}, {scope})", "",
         f"- Wasted after hours: {kwh / 1000:,.1f} MWh ({kwh / use * 100:.0f} % of their use)" if use else "",
         f"- Cost: {ui.eur_range(metrics.eur_range(y['eur_omie'].sum(), base_eur))} a year "
         f"(wholesale price → {P['price']['all_in_eur_per_kwh']} €/kWh all-in)",
         f"- CO₂: {y['kg_co2'].sum() / 1000:,.2f} t · zone NW: {nw / kwh:.0%} of the waste" if kwh else "", "",
         "| Circuit | MWh / yr | € / yr (all-in) | kg CO₂ / yr | What it looks like |", "|---|---|---|---|---|"]
lines += [f"| {r['circuit']} | {r['potential_kWh'] / 1000:.2f} | {r['eur_all_in']:,.0f} | {r['kg_co2']:,.0f} | "
          f"{config.PATTERNS.get(r['circuit'], '')} |" for _, r in y.sort_values("potential_kWh", ascending=False).iterrows()]
lines += ["", "Source: TBDA Group 1, notebook 03 (reports/savings_summary.csv), params.yaml, business case."]
e1, e2 = st.columns(2)
e1.download_button("Download the report (Markdown)", "\n".join(lines).encode("utf-8"),
                   file_name="storey1_savings.md", mime="text/markdown")
e2.download_button("Download the data (CSV)", y.to_csv(index=False).encode("utf-8"),
                   file_name="storey1_savings.csv", mime="text/csv")
st.caption("For a PDF: print this page from the browser (Ctrl+P → Save as PDF). The savings are a potential, "
           f"not a guarantee: part of the off-hours use may be legitimate. Source: {sav_src}.")
