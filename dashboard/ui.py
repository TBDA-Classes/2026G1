"""Display helpers shared by the pages: style, header, floor map, pills, footnote."""
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import config
import metrics

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stMetric {{font-family: {config.FONT};}}
.block-container {{padding-top: 1.6rem; max-width: 1400px;}}
h1 {{font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0;}}
/* sidebar: dark, like the sketch */
[data-testid="stSidebar"] {{background-color: {config.COLOR_INK};}}
[data-testid="stSidebar"] * {{color: #E5E7EB;}}
[data-testid="stSidebar"] [data-baseweb="select"] > div {{background-color: #1F2937 !important;
                                                           border-color: #374151 !important;}}
[data-testid="stSidebar"] [data-baseweb="select"] * {{color: #F9FAFB !important; opacity: 1 !important;}}
[data-testid="stSidebar"] [data-baseweb="select"] svg {{fill: #F9FAFB !important;}}
[data-testid="stSidebar"] button {{background-color: #1F2937; border-color: #374151;}}
/* KPI cards */
[data-testid="stMetric"] {{padding: 2px 4px;}}
[data-testid="stMetricLabel"] p {{font-size: .85rem; color: {config.COLOR_MUTED}; text-transform: uppercase;
                                   letter-spacing: .04em;}}
[data-testid="stMetricValue"] {{font-family: ui-monospace, 'SF Mono', monospace; font-weight: 600;}}
/* bordered containers = cards */
[data-testid="stVerticalBlockBorderWrapper"] {{border-radius: 10px;}}
.pill {{display:inline-block; padding:1px 9px; border-radius:999px; font-size:.8rem; font-weight:600;}}
.big-number {{font-family: ui-monospace, monospace; font-size: 2.1rem; font-weight: 700; color: {config.COLOR_WASTE};}}
.big-number.clock {{color: inherit;}}
</style>
"""

# Extra CSS only used when Streamlit cannot switch its own theme (very old versions): approximate dark mode
CSS_DARK_FALLBACK = """
<style>
.stApp, [data-testid="stHeader"] {background-color: #0B1220 !important;}
.stApp p, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp label, .stApp span {color: #E5E7EB;}
[data-testid="stVerticalBlockBorderWrapper"] {background-color: #111827;}
</style>
"""


def theme_switch() -> bool:
    """Light / dark switch at the top of the sidebar. Returns True when dark mode is on.

    Streamlit sends its theme to the browser at the start of every run, so the switch changes the
    theme options and re-runs the page once. This uses Streamlit's own config module (not a public
    API): if a future version refuses it, the CSS fallback below still darkens the page."""
    ss = st.session_state
    dark = st.sidebar.toggle("🌙 Dark mode", key="dark_mode")
    wanted = "dark" if dark else "light"
    if ss.get("_theme_applied") != wanted:
        try:
            from streamlit import config as st_config
            for key, value in config.THEMES[wanted].items():
                st_config.set_option(f"theme.{key}", value)
            ss["_theme_native"] = True
        except Exception:                      # option refused: use the CSS fallback
            ss["_theme_native"] = False
        first_run = "_theme_applied" not in ss
        ss["_theme_applied"] = wanted
        if ss["_theme_native"] and not first_run:
            st.rerun()                         # the next run carries the new theme to the browser
    if dark and not ss.get("_theme_native", False):
        st.markdown(CSS_DARK_FALLBACK, unsafe_allow_html=True)
    return dark


def apply_style(dark: bool = False):
    """Call once per run (app.py): CSS + one Plotly theme for every chart, light or dark."""
    st.markdown(CSS, unsafe_allow_html=True)
    t = config.THEMES["dark" if dark else "light"]
    grid = "#374151" if dark else config.COLOR_GRID
    pio.templates["storey"] = go.layout.Template(layout=dict(
        font=dict(family=config.FONT, size=13, color=t["textColor"]),
        colorway=["#14B8A6" if dark else config.COLOR_ACTUAL, config.COLOR_WASTE, "#3B82F6", "#8B5CF6",
                  config.COLOR_EXPECTED],
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor=grid, zeroline=False, linecolor=grid),
        yaxis=dict(gridcolor=grid, zeroline=False),
        hoverlabel=dict(font_family=config.FONT, bgcolor=t["secondaryBackgroundColor"]),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=10, b=0)))
    pio.templates.default = ("plotly_dark" if dark else "plotly_white") + "+storey"


def eur(x: float) -> str:
    if x != x:                                   # NaN: no price for these hours
        return "—"
    return f"€ {x:,.0f}" if abs(x) >= 100 else f"€ {x:,.1f}" if abs(x) >= 10 else f"€ {x:,.2f}"


def eur_range(r: tuple) -> str:
    lo, hi = r
    if lo != lo or hi != hi:                     # one bound missing: show the other one
        return eur(hi if lo != lo else lo)
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
        right.markdown(f"<div style='margin-top:1.4rem;text-align:center'><span class='pill' "
                       f"style='background:{bg};color:{fg}'>Data coverage {coverage*100:.1f} %</span></div>",
                       unsafe_allow_html=True)
        if not ok:
            st.warning(f"Only {coverage:.0%} of the hours have data this month: "
                       "figures on this page are incomplete.", icon="⚠️")


def severity_pill(sev: str) -> str:
    c = config.SEVERITY_COLORS.get(sev, "#6B7280")
    return f"<span class='pill' style='background:{c}1A;color:{c}'>{sev}</span>"


def _set_zone(zone: str):
    # Called by a button BEFORE the next run, so changing a widget's value is allowed here
    st.session_state["f_zone"] = zone


def floor_map(values: dict, unit: str = "kWh"):
    """2x2 schematic of Storey 1 coloured by waste; a click on a zone filters every page."""
    vmax = max(values.values()) or 1
    total = sum(values.values()) or 1
    selected = st.session_state.get("f_zone", "All zones")

    def cell(z):
        v = values.get(z, 0)
        alpha = 0.10 + 0.90 * v / vmax
        dark = alpha > 0.55
        border = "3px solid #2563EB" if z == selected else "3px solid transparent"   # visible in both themes
        return (f"<div style='background:rgba(194,65,12,{alpha:.2f});border:{border};"
                f"color:{'white' if dark else '#7C2D12'};padding:12px 14px;border-radius:8px;height:88px'>"
                f"<div style='font-weight:700'>{z}</div>"
                f"<div style='font-family:monospace;font-size:1.05rem'>{v:,.0f} {unit}</div>"
                f"<div style='font-size:.8rem;opacity:.85'>{v / total:.0%} of the floor</div></div>")

    st.markdown("<div style='display:grid;grid-template-columns:1fr 1fr;gap:6px'>"
                + "".join(cell(z) for z in ["NW", "NE", "SW", "SE"]) + "</div>",
                unsafe_allow_html=True)
    cols = st.columns(5)
    for col, z in zip(cols, config.ZONES):
        col.button(z, key=f"map_{z}", on_click=_set_zone, args=(z,))
    cols[4].button("All", key="map_all", on_click=_set_zone, args=("All zones",))
    st.caption("Schematic floor plan, not to scale · click a zone to filter every page")


def missing(what: str, file: str, who: str = "modelling team"):
    st.info(f"{what} needs `{file}` ({who}). It is not in this copy of the repository yet.")


def co2_label(P: dict) -> str:
    """How CO₂ is computed, whichever version of params.yaml is in the repo."""
    if P.get("co2", {}).get("method") == "hourly":
        return "hourly CO₂ intensity of the Spanish grid (Red Eléctrica, ESIOS 10355)"
    g = P["co2"]["g_per_kwh"]
    return f"Spanish supplier mix, {min(g.values())}–{max(g.values())} g/kWh (CNMC, yearly)"


def footnote(P: dict):
    """Definitions under the main pages (customer document, explainability level 'meaning of a term')."""
    night = P["off_hours"]["night_hours"]
    st.caption(
        f"**Closed / off-hours** = {night[0]}:00–{night[1]:02d}:00 plus weekends, holidays and UPM breaks (team "
        f"calendar). **Standby level** = what a circuit uses when almost everything is off (P"
        f"{P['off_hours']['standby_percentile']} of its night use, 2020–22). **Chronic waste** = use above standby "
        f"while closed. **€** = range from the wholesale price (OMIE, lower bound) to "
        f"{P['price']['all_in_eur_per_kwh']} €/kWh all-in (Eurostat, excl. VAT): CeDInt's exact tariff is not known. "
        f"**CO₂** = {co2_label(P)}. {metrics.severity_rule_text(P)} 9 focus circuits; emergency lighting, rack, hand "
        f"dryers and NE HVAC are fixed loads. Every assumption: {config.REPO_URL}{config.DOC_LINKS['Assumptions register']}")
