"""Leakage and shape tests for features and baselines. Run:  pytest"""
import numpy as np
import pandas as pd
import pytest

from src.data import load
from src.features import make_features, feature_lags, split_of
from src.models import ProfileBaseline, baseline_median_4w

T = "NW|Plugs & Sockets W"


@pytest.fixture(scope="module")
def df():
    return load()


@pytest.mark.parametrize("kind", ["forecast", "normal"])
def test_no_look_ahead(df, kind):
    """Changing the target from hour k onwards must not change any feature before hour k + 24."""
    X1 = make_features(df, T, kind)
    k = 10_000
    df2 = df.copy()
    df2.loc[k:, T] = df2.loc[k:, T] * 10 + 999
    X2 = make_features(df2, T, kind)
    cols = feature_lags(X1)
    assert cols, "no lag features found"
    pd.testing.assert_frame_equal(X1.loc[: k + 23, cols], X2.loc[: k + 23, cols])


@pytest.mark.parametrize("kind", ["forecast", "normal"])
def test_no_same_hour_measurements(df, kind):
    X = make_features(df, T, kind)
    forbidden = [c for c in X.columns if c.endswith(" W") or "|ENV" in c or c in ("I", "Pa", "Ea")]
    assert not forbidden


def test_lags_do_not_cross_the_gap(df):
    X = make_features(df, T, "forecast")
    first_b = df.index[df["Regime"] == "B"][0]
    assert X.loc[first_b: first_b + 23, "lag_24"].isna().all()


def test_baselines_shape(df):
    X = make_features(df, T, "forecast")
    tr = split_of(df["timestamp_local"]) == "train"
    p3 = ProfileBaseline().fit(X[tr], df.loc[tr, T]).predict(X)
    p2 = baseline_median_4w(df, T)
    assert len(p3) == len(df) == len(p2)
    assert p3.notna().all()


def test_splits_are_in_time_order(df):
    s = split_of(df["timestamp_local"])
    last = {n: df.loc[s == n, "timestamp_local"].max() for n in ["train", "val"]}
    first = {n: df.loc[s == n, "timestamp_local"].min() for n in ["val", "test"]}
    assert last["train"] < first["val"] and last["val"] < first["test"]
