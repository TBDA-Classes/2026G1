"""Quality checks on the frozen modelling dataset. Run:  pytest"""
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "data" / "processed" / "cedint_hourly_v1.parquet"
MANIFEST = ROOT / "data" / "processed" / "MANIFEST.json"


@pytest.fixture(scope="module")
def df():
    return pd.read_parquet(FROZEN)


def test_no_duplicate_hours(df):
    assert df["timestamp_utc"].is_unique


def test_regular_hourly_grid_per_regime(df):
    for _, g in df.groupby("Regime"):
        steps = g["timestamp_utc"].sort_values().diff().dropna()
        assert (steps == pd.Timedelta(hours=1)).all()


def test_no_negative_energy(df):
    power = [c for c in df.columns if c.endswith(" W")]
    assert (df[power].fillna(0) >= 0).all().all()


def test_required_columns(df):
    needed = {"timestamp_utc", "timestamp_local", "Regime", "hour_local", "weekday_local",
              "is_working_day", "is_covid_lockdown", "wx_temp_c", "price_eur_mwh"}
    assert needed <= set(df.columns)


def test_calendar_and_weather_complete(df):
    assert df["is_working_day"].notna().all()
    assert df["wx_temp_c"].notna().all()


def test_matches_manifest(df):
    from src.freeze_dataset import data_hash
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert len(df) == m["rows"]
    assert data_hash(df) == m["content_sha256"]
