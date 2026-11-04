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

# Hourly data, first file found wins (Parquet, CSV or Excel)
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

ALERT_STATUS_FILE = LOCAL_DIR / "alert_status.csv"   # "Handled", "This was normal"... (written here)

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
    "anomaly": {"severity_kwh": [2, 10], "min_event_hours": 2, "min_event_kwh": 0.5},
    "off_hours": {"night_hours": [22, 6], "standby_percentile": 10},
}

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
DEFAULT_MONTH = "2022-01"      # the sketch shows January 2022
ZONES = ["NW", "NE", "SW", "SE"]
COVERAGE_WARNING = 0.95        # months with less data are flagged on every page
OFF_HOURS_SHARE_FOR_WASTE = 0.5  # an event mostly in off-hours = waste; otherwise "to investigate"

COLOR_WASTE = "#C2410C"
COLOR_WASTE_LIGHT = "#F2B48C"
COLOR_ACTUAL = "#0F5F5C"
COLOR_EXPECTED = "#6B7280"
COLOR_THRESHOLD = "#B91C1C"
COLOR_OFF = "rgba(148,163,184,0.18)"
COLOR_OPEN = "#94A3B8"
SEVERITY_COLORS = {"High": "#B91C1C", "Medium": "#B45309", "Low": "#1D4ED8"}
