"""Small display helpers shared by the pages."""
import streamlit as st

import config


def eur(x: float) -> str:
    return f"€ {x:,.0f}" if abs(x) >= 100 else f"€ {x:,.1f}"


def eur_range(r: tuple) -> str:
    lo, hi = r
    if round(lo) == round(hi):
        return eur(hi)
    return f"€ {lo:,.0f} – {hi:,.0f}" if hi >= 100 else f"€ {lo:,.1f} – {hi:,.1f}"


def page_header(title: str, subtitle: str, coverage: float | None = None):
    left, right = st.columns([4, 1])
    left.title(title)
    left.caption(subtitle)
    if coverage is not None:
        ok = coverage >= config.COVERAGE_WARNING
        bg, fg = ("#DCFCE7", "#166534") if ok else ("#FFEDD5", "#9A3412")
        right.markdown(f"<div style='margin-top:1.6rem;padding:.4rem .7rem;border-radius:999px;"
                       f"background:{bg};color:{fg};text-align:center;font-size:.85rem'>"
                       f"Data coverage {coverage*100:.1f} %</div>", unsafe_allow_html=True)
        if not ok:
            st.warning(f"Only {coverage:.0%} of the hours have data this month: "
                       "figures on this page are incomplete.", icon="⚠️")


def severity_pill(sev: str) -> str:
    c = config.SEVERITY_COLORS.get(sev, "#6B7280")
    return (f"<span style='background:{c}1A;color:{c};padding:1px 8px;"
            f"border-radius:999px;font-size:.8rem'>{sev}</span>")


def _set_zone(zone: str):
    # Called by a button BEFORE the next run, so changing a widget's value is allowed here
    st.session_state["f_zone"] = zone


def floor_map(values: dict, unit: str = "kWh"):
    """2x2 schematic of Storey 1 coloured by waste; a click on a zone filters every page."""
    vmax = max(values.values()) or 1
    selected = st.session_state.get("f_zone", "All zones")

    def cell(z):
        v = values.get(z, 0)
        alpha = 0.12 + 0.88 * v / vmax
        dark = alpha > 0.55
        border = "3px solid #111827" if z == selected else "3px solid transparent"
        return (f"<div style='background:rgba(194,65,12,{alpha:.2f});border:{border};"
                f"color:{'white' if dark else '#7C2D12'};padding:12px;border-radius:6px;height:84px'>"
                f"<b>{z}</b><br><span style='font-family:monospace'>{v:,.0f} {unit}</span></div>")

    st.markdown("<div style='display:grid;grid-template-columns:1fr 1fr;gap:6px'>"
                + "".join(cell(z) for z in ["NW", "NE", "SW", "SE"]) + "</div>",
                unsafe_allow_html=True)
    cols = st.columns(5)
    for col, z in zip(cols, config.ZONES):
        col.button(z, key=f"map_{z}", on_click=_set_zone, args=(z,))
    cols[4].button("All", key="map_all", on_click=_set_zone, args=("All zones",))
    st.caption("Schematic floor plan, not to scale · click a zone to filter every page")


def missing(what: str, file: str, who: str = "modelling team"):
    st.info(f"{what} needs `{file}` ({who}). It is not in the repository yet.")


def footnote(P: dict):
    co2 = P["co2"]["g_per_kwh"]
    night = P["off_hours"]["night_hours"]
    st.caption(
        f"Off-hours = {night[0]}:00–{night[1]:02d}:00 plus weekends, holidays and breaks (team calendar). "
        f"Chronic waste = use above each circuit's standby level (P{P['off_hours']['standby_percentile']} "
        f"of night use, 2020–22) during off-hours. € = OMIE hourly wholesale price (lower bound) – "
        f"{P['price']['all_in_eur_per_kwh']} €/kWh all-in · CO₂ = {min(co2.values())}–{max(co2.values())} g/kWh "
        "(Spanish grid, to confirm). Source: modelling notebooks 02–03, params.yaml. "
        "9 focus circuits; emergency lighting, rack, hand dryers and NE HVAC are fixed loads.")
