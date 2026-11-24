"""Checks on the cleaned zone files and on load_zones(). Run:  pytest"""
import pandas as pd
import pytest

from src.data import FOCUS, circuits
from src.zones import ZONES, load_zones


@pytest.fixture(scope="module")
def df():
    return load_zones(drop_lockdown=False)


def test_all_zones_and_focus_circuits_present(df):
    assert len(circuits(df)) == 16
    assert all(c in df for c in FOCUS)
    assert all(f"{z}|ZONE TOTAL W" in df for z in ZONES)


def test_no_duplicate_hours_and_regular_grid(df):
    assert df["timestamp_utc"].is_unique
    for _, g in df.groupby("Regime"):
        assert (g["timestamp_utc"].diff().dropna() == pd.Timedelta(hours=1)).all()


def test_no_negative_power(df):
    assert (df[circuits(df)].fillna(0) >= 0).all().all()


def test_storey_total_is_sum_of_zone_totals(df):
    zones = df[[f"{z}|ZONE TOTAL W" for z in ZONES]]
    full = zones.notna().all(axis=1)
    assert ((df.loc[full, "STOREY1|TOTAL W"] - zones[full].sum(axis=1)).abs() < 1e-6).all()
    assert df.loc[~full, "STOREY1|TOTAL W"].isna().all()


def test_hourly_co2_and_price_complete(df):
    assert df["co2_intensity_g_kwh"].notna().all()
    assert df["price_eur_mwh"].notna().all()
