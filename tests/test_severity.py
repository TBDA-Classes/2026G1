"""Tests for the EUR + duration severity rule (backlog F5.2, KAN-152) and its calibration (EXP-12). Run:  pytest"""
import pandas as pd
import pytest

from src.anomalies import LEVELS, load_params, rank_alerts, severity
from src.calibrate_severity import apply_rule, choose, grid_table
from src.data import ROOT

S = {"eur": [0.25, 1.0], "long_event_hours": 24}


@pytest.mark.parametrize("eur, hours, expected", [
    (0.10, 3, "low"),
    (0.25, 3, "medium"),       # lower bound belongs to medium
    (0.99, 3, "medium"),
    (1.00, 3, "high"),         # lower bound belongs to high
    (23.0, 44, "high"),
])
def test_level_from_eur(eur, hours, expected):
    assert severity(eur, hours, S) == expected


def test_long_event_goes_up_one_level_and_high_stays_high():
    assert severity(0.10, 24, S) == "medium"    # a cheap event that lasted a whole day
    assert severity(0.50, 30, S) == "high"
    assert severity(5.00, 200, S) == "high"     # never above high
    assert severity(0.10, 23, S) == "low"       # 23 h is not long yet


def test_params_yaml_is_valid():
    P = load_params()
    s = P["severity"]
    assert s["eur"][0] < s["eur"][1]
    assert s["long_event_hours"] > 0
    assert s["eur_column"] in {"eur_all_in", "eur_omie"}
    assert "severity_kwh" not in P["anomaly"]   # the old kWh rule is gone, so nobody reads stale thresholds


def test_rank_alerts_orders_by_severity_then_eur():
    ev = pd.DataFrame({"severity": ["low", "high", "medium", "high"], "eur_all_in": [5.0, 1.0, 2.0, 3.0]})
    out = rank_alerts(ev)
    assert out["severity"].tolist() == ["high", "high", "medium", "low"]
    assert out["eur_all_in"].tolist() == [3.0, 1.0, 2.0, 5.0]


def test_calibration_picks_the_workload_targets():
    # 100 alerts with EUR 0.01 .. 1.00: the cheapest half is below ~0.5, the top 20 % above ~0.8
    ev = pd.DataFrame({"eur_all_in": [i / 100 for i in range(1, 101)], "hours": 3})
    lo, hi = choose(grid_table(ev, long_hours=24, weeks=10))
    assert lo == 0.50
    assert hi == 0.75 or hi == 1.00                 # grid values around the 80th percentile
    sev = apply_rule(ev, (lo, hi), 24)
    assert set(sev) <= set(LEVELS)


def test_published_events_use_the_current_rule():
    """reports/anomaly_events.csv must be regenerated whenever params.yaml -> severity changes."""
    P = load_params()
    ev = pd.read_csv(ROOT / "reports" / "anomaly_events.csv")
    col = P["severity"]["eur_column"]
    expected = [severity(e, h, P["severity"]) for e, h in zip(ev[col], ev["hours"])]
    assert (ev["severity"] == pd.Series(expected)).all()
