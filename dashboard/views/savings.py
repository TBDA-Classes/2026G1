import plotly.graph_objects as go
import streamlit as st

import config
import data_loader as dl
import metrics
import ui

P, _ = dl.load_params()
f = dl.get_filters()
sav, sav_src = dl.load_savings()

st.title("Savings report")
st.caption("What the off-hours waste is worth per year · for the sustainability officer and the sponsor")
if sav is None:
    ui.missing("The savings report", "reports/savings_summary.csv")
    st.stop()

sav = sav.rename(columns={"device": "load_type"})
sav["circuit"] = sav["zone"] + " " + sav["load_type"]
years = sorted(sav["year"].unique())
year = st.radio("Year", years, horizontal=True, index=len(years) - 1)
y = dl.apply_filters(sav[sav["year"] == year], f)
scope = " · ".join(x for x in [f["zone"], f["load"]] if not x.startswith("All")) or "9 focus circuits"

kwh, use = y["potential_kWh"].sum(), y["total_use_kWh"].sum()
eur = metrics.eur_range(y["eur_omie"].sum(), y["eur_all_in"].sum())
c1, c2, c3, c4 = st.columns(4)
with c1.container(border=True):
    st.metric("Potential savings", f"{kwh / 1000:,.1f} MWh")
    st.caption(scope)
with c2.container(border=True):
    st.metric("Share of their use", f"{kwh / use * 100:.0f} %" if use else "–")
    st.caption(f"of {use / 1000:,.1f} MWh used in {year}")
with c3.container(border=True):
    st.metric("Value", ui.eur_range(eur))
    st.caption("OMIE wholesale (lower bound) – all-in price")
with c4.container(border=True):
    st.metric("CO₂ avoided", f"{y['kg_co2'].sum() / 1000:,.2f} t")
    st.caption("Spanish grid factor, to confirm")

left, right = st.columns([3, 2])
with left.container(border=True):
    st.markdown(f"**Potential savings per circuit, {year} (kWh)**")
    t = y.sort_values("potential_kWh", ascending=True)
    fig = go.Figure()
    fig.add_bar(y=t["circuit"], x=t["potential_kWh"], orientation="h", name="Off-hours above standby",
                marker_color=config.COLOR_WASTE,
                text=[f"{k:,.0f} kWh · {ui.eur(e)}" for k, e in zip(t["potential_kWh"], t["eur_all_in"])],
                textposition="outside")
    fig.add_bar(y=t["circuit"], x=t["to_investigate_workhours_kWh"], orientation="h",
                name="To investigate (working hours, not counted)", marker_color=config.COLOR_OPEN)
    fig.update_layout(barmode="group", height=80 + 46 * len(t), margin=dict(l=0, r=120, t=10, b=0),
                      plot_bgcolor="white", legend=dict(orientation="h", y=-0.12), xaxis=dict(visible=False))
    st.plotly_chart(fig)

with right.container(border=True):
    st.markdown("**What to fix first**")
    top = y.sort_values("potential_kWh", ascending=False).head(3)
    for i, (_, r) in enumerate(top.iterrows(), 1):
        st.markdown(f"{i}. **{r['circuit']}** — {r['potential_kWh']:,.0f} kWh, "
                    f"{ui.eur_range(metrics.eur_range(r['eur_omie'], r['eur_all_in']))}, "
                    f"{r['share_of_use_%']:.0f} % of its use")
    st.markdown("Team findings (notebook 01, 03): electric heaters on the NW sockets left on at night, at "
                "weekends and in breaks; NW lights on every night 22:00–07:00. Most of it is fixed by "
                "behaviour or timers, at almost no cost.")
    st.markdown("**Compared over the years**")
    comp = dl.apply_filters(sav, f).groupby("year")[["potential_kWh", "eur_omie", "eur_all_in", "kg_co2"]].sum()
    comp = comp.assign(MWh=comp["potential_kWh"] / 1000, t_CO2=comp["kg_co2"] / 1000)
    st.dataframe(comp[["MWh", "eur_omie", "eur_all_in", "t_CO2"]].round(2)
                 .rename(columns={"eur_omie": "€ OMIE", "eur_all_in": "€ all-in", "t_CO2": "t CO₂"}))

# --- Export ---------------------------------------------------------------------
lines = [f"# Storey 1 — potential savings {year} ({scope})", "",
         f"- Potential savings: {kwh / 1000:,.1f} MWh ({kwh / use * 100:.0f} % of their use)" if use else "",
         f"- Value: {ui.eur_range(eur)} (OMIE wholesale – all-in {P['price']['all_in_eur_per_kwh']} €/kWh)",
         f"- CO₂: {y['kg_co2'].sum() / 1000:,.2f} t", "", "## Per circuit", "",
         "| Circuit | kWh | € all-in | kg CO₂ | share of use |", "|---|---|---|---|---|"]
lines += [f"| {r['circuit']} | {r['potential_kWh']:,.0f} | {r['eur_all_in']:,.0f} | {r['kg_co2']:,.0f} | "
          f"{r['share_of_use_%']:.0f} % |" for _, r in y.sort_values("potential_kWh", ascending=False).iterrows()]
lines += ["", "Source: TBDA Group 1, notebook 03 (reports/savings_summary.csv), params.yaml."]
c1, c2 = st.columns(2)
c1.download_button("Download the report (Markdown)", "\n".join(lines).encode("utf-8"),
                   file_name=f"storey1_savings_{year}.md", mime="text/markdown")
c2.download_button("Download the data (CSV)", y.to_csv(index=False).encode("utf-8"),
                   file_name=f"storey1_savings_{year}.csv", mime="text/csv")
st.caption("For a PDF: print this page from the browser (Ctrl+P → Save as PDF). "
           f"Potential savings are an upper estimate: some off-hours use may be legitimate. Source: {sav_src}.")
