"""
Dashboard settings: where the team's files are, and display choices.

Business rules (prices, CO2, off-hours, alert thresholds) are NOT here:
they are read from the team's params.yaml, so the dashboard and the
notebooks always use the same numbers.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Where things are (the dashboard/ folder sits at the root of the 2026G1 repo)
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
LOCAL_DIR = APP_DIR / "data"            # files written by / for the dashboard
REPORTS_DIR = REPO_ROOT / "reports"     # outputs of the modelling notebooks
PARAMS_FILE = REPO_ROOT / "params.yaml"
MANIFEST_FILE = REPO_ROOT / "data" / "processed" / "MANIFEST.json"
FIGURES_DIR = REPORTS_DIR / "figures"

# Hourly data. First choice: the 4 cleaned zone files of the data-cleaning group, joined exactly like
# src/zones.load_zones() (what notebooks 01–03 use since 24 Nov 2026). Fallback: the frozen dataset.
ZONE_DIR = REPO_ROOT / "data"
ZONE_FILE = "zone_{zone}_hourly"           # zone_NW_hourly.parquet (or .xlsx, sheet DATA)
ZONE_SHARED = ["timestamp_utc", "Regime", "timestamp_local", "weekday_local", "hour_local", "month",
               "wx_temp_c", "wx_feels_like_c", "wx_humidity_pct", "wx_precip_mm", "wx_cloud_pct", "wx_wind_ms",
               "wx_solar_wm2", "wx_pressure_hpa", "is_working_day", "is_weekend", "is_holiday", "holiday_name",
               "is_christmas_break", "is_holy_week", "is_august_closure", "is_covid_lockdown",
               "price_eur_mwh", "co2_intensity_g_kwh"]
ZONE_ONLY = ["low_coverage", "empty_reasons"]
HOURLY_CANDIDATES = [
    REPO_ROOT / "data" / "processed" / "cedint_hourly_v1",       # frozen dataset (reference)
    REPO_ROOT / "data" / "clean_hourly_plus_external",            # same content, before freezing
    LOCAL_DIR / "cedint_hourly_v1",
]

# Modelling outputs (searched in dashboard/data/ first, then in reports/)
EVENTS_FILE = "anomaly_events"            # signal 1: events (notebook 03)
DAILY_WASTE_FILE = "offhours_waste_daily"  # signal 2: chronic off-hours waste (notebook 03)
SAVINGS_FILE = "savings_summary"          # potential savings per year (notebook 03)
MODEL_COMPARISON_FILE = "model_comparison"  # model scores (notebook 02)
ANOMALY_K_FILE = "anomaly_k"              # alarm threshold per circuit (notebook 03)
EXPECTED_FILE = "expected_hourly"         # expected use for every hour (tools/export_expected.py)
TEST_PREDICTIONS_FILE = "test_predictions"  # LightGBM predictions on the test months (notebook 02)
BANDS_FILE = "interval_bands"             # 90 % band (notebook 04, branch KAN-144)

FINAL_SETTINGS_FILE = "final_model_settings"   # one LightGBM setting for all circuits (notebook 04_model_search)
CONTRIB_FILE = "expected_contributions"     # why the model expected a value (tools/export_contributions.py)
ACTIONS_FILE = LOCAL_DIR / "actions.csv"    # measures logged in the Action planner
CALIBRATION_FILE = "severity_calibration"  # severity thresholds and their effect (src/calibrate_severity.py, EXP-12)
MODEL_CARD_CANDIDATES = [REPO_ROOT / "docs" / n for n in ("MODEL_CARD.md", "model_card.md", "MODEL-CARD.md")]

ALERT_STATUS_FILE = LOCAL_DIR / "alert_status.csv"   # every status change, with its date (backlog F4.4)

# Team documents, linked from the dashboard (quality requirements Q2, Q6)
REPO_URL = "https://github.com/TBDA-Classes/2026G1/blob/main/"
DOC_LINKS = {
    "Business case": "docs/BUSINESS_CASE.md",
    "Assumptions register": "docs/ASSUMPTIONS_REGISTER.md",
    "Deployment plan": "docs/DEPLOYMENT_PLAN.md",
    "Methodology": "docs/METHODOLOGY.md",
    "Pipeline, cleaning and detection": "docs/PIPELINE_MODEL_DETECTION.md",
    "Experiment log": "docs/EXPERIMENT_LOG.md",
    "Customer value and solution": "dashboard/dashboard_value/group 1 customer value and solution.pdf",
}
DOC_BRANCHES = {   # documents not on main yet (25 Nov 2026): linked on their branch until they are merged
    "Business case": "amelie/business-value",
    "Assumptions register": "amelie/business-value",
    "Deployment plan": "amelie/business-value",
}

# ---------------------------------------------------------------------------
# Same definitions as src/data.py and src/features.py (modelling team)
# ---------------------------------------------------------------------------
FOCUS = ["NW|Plugs & Sockets W", "SW|Plugs & Sockets W", "SE|Plugs & Sockets W", "NE|Plugs & Sockets W",
         "NW|Lighting W", "SW|Lighting W", "SE|Lighting W", "NW|HVAC W", "SE|HVAC W"]
TRAIN_PERIOD = ("2020-06-22", "2022-08-31 23:59")   # standby level is learned on this period
SPLIT_LABELS = {"val": "Validation (Sep–Dec 2022)", "test": "Test (Jan–Feb 2023)",
                "regime_b": "2025 check (Aug–Oct 2025)"}
DROP_LOCKDOWN = True        # like src/data.load(): lockdown hours are not "normal" use

# Fallback when params.yaml is missing (copy of the team's values, 4 Nov 2026)
DEFAULT_PARAMS = {
    "price": {"all_in_eur_per_kwh": 0.142},
    "co2": {"g_per_kwh": {2020: 259, 2021: 259, 2022: 273, 2023: 260, 2025: 260}},
    "anomaly": {"min_event_hours": 2, "min_event_kwh": 0.5},
    "severity": {"eur_column": "eur_all_in", "eur": [0.25, 1.0], "long_event_hours": 24},
    "off_hours": {"night_hours": [22, 6], "standby_percentile": 10},
}

# ---------------------------------------------------------------------------
# Content from the team documents (business case §5, register A11–A15, review slides B1–B2)
# ---------------------------------------------------------------------------
PATTERNS = {   # "what it looks like", business case §5 and slide B3
    "NW Plugs & Sockets": "heaters left on at night in winter (400–900 kWh a month above standby, Nov–Mar)",
    "NW Lighting": "about 300 W every night 22:00–07:00, weekends too: security light or timer?",
    "SE Plugs & Sockets": "high in 2021, −83 % in 2022: something was switched off",
    "SW Plugs & Sockets": "base load while closed",
    "NW HVAC": "running at night and at weekends",
    "SE HVAC": "running all weekend at low power",
}
PRICE_OPTIONS = {   # € per kWh, assumptions register A11–A13 (Eurostat, Spain, non-household, 2nd half 2024)
    "Range: wholesale → € 0.142 all-in (team default)": "range",
    "OMIE wholesale price, hour by hour (lower bound)": "omie",
    "€ 0.142 — excl. VAT (all-in)": 0.142,
    "€ 0.169 — all taxes (VAT not recoverable)": 0.169,
    "€ 0.128 — without any taxes": 0.128,
}
CO2_OPTIONS = {     # params.yaml co2.method, register A14–A15
    "Hourly grid intensity, Red Eléctrica (team default)": "hourly",
    "Supplier mix CNMC, 259–273 g/kWh (yearly)": "grid",
    "Spanish generation 2024, 102 g/kWh": "low",
    "Renewable guarantees of origin: 0 (market-based)": "zero",
}
ACCURACY_TARGETS = {   # indicative targets shared by the teacher (slide B1)
    "Plugs & Sockets": ("CV(RMSE) ≤ 30 %", 30),
    "HVAC": ("CV(RMSE) 30–50 %, |NMBE| ≤ 10 %", 50),
    "Lighting": ("daily energy", None),
}
DETECTION_TEST = [  # notebook 03 section 3 (final model, 24 Nov 2026): 40 fake loads per circuit, Sep 2022 – Feb 2023
    ("NW Plugs & Sockets", "1 kW", 30, 1.86), ("SW Plugs & Sockets", "1 kW", 100, 1.08),
    ("SE Plugs & Sockets", "1 kW", 100, 1.35), ("NE Plugs & Sockets", "1 kW", 100, 0.23),
    ("NW Lighting", "300 W", 15, 0.08), ("SW Lighting", "300 W", 100, 0.97),
    ("SE Lighting", "300 W", 100, 5.26), ("NW HVAC", "300 W", 100, 0.31), ("SE HVAC", "300 W", 100, 0.39),
]
DETECTION_SIZES = [("1 kW", 30), ("2 kW", 92), ("3 kW", 98), ("5 kW", 100), ("8 kW", 100)]   # NW Plugs

# Prediction methods that can be drawn as the "expected" line (notebook 02, src/models.py)
# name: (colour, dash, where it comes from)
METHODS = {
    "LightGBM (team model)": ("#7C3AED", "dash", "expected_hourly (all hours) or test_predictions (Jan–Feb 2023)"),
    "Ridge (linear model)": ("#2563EB", "dot", "test_predictions: Jan–Feb 2023 only"),
    "B1 · same hour last week": ("#9CA3AF", "dot", "computed here, every hour"),
    "B2 · 4-week median": ("#6B7280", "dash", "computed here, every hour"),
    "B3 · day-type profile": ("#D97706", "dashdot", "computed here, every hour (learned on Jun 2020 – Aug 2022)"),
}
TEST_MODEL_COLUMNS = {"LightGBM (team model)": "LightGBM_forecast", "Ridge (linear model)": "Ridge_forecast"}

# Evaluation phases of the modelling team (notebook 02, src/features.SPLITS), local time
PHASES = [  # name, start, end, colour, what happens
    ("Lockdown (left out)", "2020-04-02", "2020-06-21 23:59", "#E5E7EB", "COVID lockdown: not normal use, not used"),
    ("Train", "2020-06-22", "2022-08-31 23:59", "#BFDBFE", "the models learn"),
    ("Validation", "2022-09-01", "2022-12-31 23:59", "#C7D2FE", "settings chosen; models trained on the train period only"),
    ("Test", "2023-01-01", "2023-02-28 23:59", "#FDE68A",
     "models retrained on train + validation, then predicted ONCE (honest score)"),
    ("No data", "2023-03-01", "2025-08-17 23:59", "#F3F4F6", "gap in the source files"),
    ("Out-of-time 2025", "2025-08-18", "2025-10-13 23:59", "#BBF7D0",
     "models trained only on 2020 – Feb 2023: a real forecast, 2.5 years later"),
]
# How the LightGBM line must be read in each phase (advice of the modelling team)
LGB_LABELS = {
    "Train": ("LightGBM · expected afterwards", "dot",
              "cross-fitted: each quarter predicted by a model trained on the other quarters, later ones included. "
              "Fine for a historical report, but not a real forecast."),
    "Validation": ("LightGBM · expected afterwards", "dot",
                   "cross-fitted: each quarter predicted by a model trained on the other quarters, later ones included. "
                   "Fine for a historical report, but not a real forecast."),
    "Test": ("LightGBM · forecast (test)", "dash",
             "honest test: trained up to 31 Dec 2022, predicted once, one day ahead (reports/test_predictions.parquet)."),
    "Out-of-time 2025": ("LightGBM · forecast (2025)", "dash",
                         "real forecast: trained only on 2020 – Feb 2023, predicted 2.5 years later, one day ahead."),
}

# Demo mode: replay of period B (2025), as if the data arrived live
DEMO_CIRCUIT = "SE Lighting"          # top 2025 event of the storyline: on all weekend 26–29 Sep
DEMO_TICK_S = 0.5                     # screen refresh: 2 small steps a second look smoother than 1 big one
DEMO_SPEEDS = {"2 hours / s": 2, "6 hours / s": 6, "12 hours / s": 12, "1 day / s": 24}

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
DEFAULT_MONTH = "2022-01"      # the sketch shows January 2022
ZONES = ["NW", "NE", "SW", "SE"]
COVERAGE_WARNING = 0.95        # months with less data are flagged on every page
OFF_HOURS_SHARE_FOR_WASTE = 0.5  # an event mostly in off-hours = waste; otherwise "to investigate"

THEMES = {   # applied with the sidebar switch (ui.theme_switch)
    "light": {"base": "light", "primaryColor": "#C2410C", "backgroundColor": "#FFFFFF",
              "secondaryBackgroundColor": "#F3F4F6", "textColor": "#111827"},
    "dark": {"base": "dark", "primaryColor": "#F97316", "backgroundColor": "#0B1220",
             "secondaryBackgroundColor": "#1F2937", "textColor": "#E5E7EB"},
}
FONT = "Inter, 'Segoe UI', system-ui, sans-serif"
COLOR_INK = "#111827"
COLOR_MUTED = "#6B7280"
COLOR_GRID = "#E5E7EB"
COLOR_WASTE = "#C2410C"
COLOR_WASTE_LIGHT = "#F2B48C"
COLOR_ACTUAL = "#0F5F5C"
COLOR_EXPECTED = "#6B7280"
COLOR_THRESHOLD = "#B91C1C"
COLOR_OFF = "rgba(148,163,184,0.18)"
COLOR_OPEN = "#94A3B8"
SEVERITY_COLORS = {"High": "#B91C1C", "Medium": "#B45309", "Low": "#1D4ED8"}
