"""Tests for the event grouping, thresholds and valuation. Run:  pytest"""
import numpy as np
import pandas as pd

from src.anomalies import to_events, threshold_stats, robust_thresholds, load_params, value, events_fast


def _ts(n):
    return pd.Series(pd.date_range("2022-01-01", periods=n, freq="h"))


def test_events_group_consecutive_hours_and_merge_small_gaps():
    flag = pd.Series([0, 1, 1, 0, 1, 0, 0, 0, 1, 0], dtype=bool)
    ev = to_events(flag, _ts(10), merge_gap=1, min_hours=2)
    # hours 1,2,4 form one event (gap of 1 h merged); hour 8 alone is too short
    assert ev["row"].tolist() == [1, 2, 4]
    assert ev["event_id"].nunique() == 1


def test_threshold_is_per_hour_type():
    resid = pd.Series([0, 10, -10, 0, 100, -100] * 50, dtype=float)
    htype = pd.Series(["off", "off", "off", "work", "work", "work"] * 50)
    stats = threshold_stats(resid, htype)
    thr = robust_thresholds(htype, stats, k=3)
    assert thr[htype == "work"].iloc[0] > thr[htype == "off"].iloc[0]


def test_small_events_are_dropped():
    P = load_params()
    n = 6
    H = pd.DataFrame({"flag_model": [True] * n, "resid": [50.0] * n})      # 6 h x 50 W = 0.3 kWh < 0.5 kWh
    assert events_fast(H, _ts(n), P).empty
    H["resid"] = 500.0                                                     # 3 kWh -> kept
    assert not events_fast(H, _ts(n), P).empty


def test_value_uses_price_and_co2_factor():
    P = load_params()
    df = pd.DataFrame({"price_eur_mwh": [100.0], "timestamp_local": [pd.Timestamp("2022-06-01 12:00")]})
    v = value(pd.Series([10.0]), df, P)                                    # 10 kWh
    assert np.isclose(v["eur_omie"].iat[0], 1.0)                           # 10 kWh * 0.1 EUR/kWh
    assert np.isclose(v["eur_all_in"].iat[0], 10 * P["price"]["all_in_eur_per_kwh"])
    assert np.isclose(v["kg_co2"].iat[0], 10 * P["co2"]["g_per_kwh"][2022] / 1000)
