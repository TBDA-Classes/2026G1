"""Checks for the prediction interval (KAN-144). Run:  pytest"""
import numpy as np
import pandas as pd

from src.intervals import conformal_margin, interval_metrics, rolling_margin, scores


def test_conformal_margin_reaches_target_coverage():
    """After widening by the CQR margin, at least 90 % of the calibration points are inside."""
    rng = np.random.default_rng(0)
    y = rng.normal(100, 20, 2000)
    lo, hi = np.full_like(y, 90.0), np.full_like(y, 110.0)          # far too narrow on purpose
    m = conformal_margin(y, lo, hi, alpha=0.10)
    inside = (y >= lo - m) & (y <= hi + m)
    assert m > 0 and inside.mean() >= 0.90


def test_rolling_margin_uses_only_old_hours():
    """Changing the score from hour k onwards must not change the margin before hour k + 24."""
    s = pd.Series(np.random.default_rng(1).normal(size=24 * 60))
    k = 24 * 30
    s2 = s.copy()
    s2[k:] = s2[k:] * 100 + 999
    pd.testing.assert_series_equal(rolling_margin(s)[: k + 24], rolling_margin(s2)[: k + 24])


def test_scores_sign_and_metrics():
    y, lo, hi = np.array([5.0, 15.0, 25.0]), np.full(3, 10.0), np.full(3, 20.0)
    assert list(scores(y, lo, hi)) == [5.0, -5.0, 5.0]               # outside -> positive, inside -> negative
    r = interval_metrics(y * 1000, lo * 1000, hi * 1000, alpha=0.10)
    assert round(r["coverage_%"], 6) == round(100 / 3, 6) and r["width_kWh"] == 10
    assert r["winkler_kWh"] > r["width_kWh"]                        # misses are penalised
