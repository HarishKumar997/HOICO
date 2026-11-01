"""Contracts that do not need Spark or Postgres."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from hoico.config import HISTORY_END, HISTORY_START, HORIZON_DAYS, TRAIN_DAYS, VAL_DAYS
from hoico.forecasting.engine import build_feature_frame, chronological_windows, seasonal_naive
from hoico.generate.synthetic import generate, history_dates
from hoico.ingest.mock_api import fetch_operational_events
from hoico.metrics import mae, occupancy_rate, occupies, wape
from hoico.optimization.engine import ScenarioParams, WardDay, solve_scenario
from hoico.quality.prepare import occupied_bounds, prepare_encounters
from hoico.quality.rules import (
    REASON_ARRIVAL_AFTER_DEPARTURE,
    REASON_INVALID_TIMESTAMP,
    REASON_MISSING_DEPARTURE,
    REASON_UNKNOWN_SERVICE_LINE,
)


def test_history_length_matches_split():
    days = history_dates()
    assert days[0] == HISTORY_START
    assert days[-1] == HISTORY_END
    assert len(days) == TRAIN_DAYS + VAL_DAYS + HORIZON_DAYS


def test_generator_is_deterministic(tmp_path):
    from hoico.generate.synthetic import write_bundle

    end = HISTORY_START + timedelta(days=6)
    first = generate(start=HISTORY_START, end=end, seed=42)
    second = generate(start=HISTORY_START, end=end, seed=42)
    assert first.encounters.equals(second.encounters)
    assert write_bundle(first, tmp_path / "a") == write_bundle(second, tmp_path / "b")


def test_identifiers_are_synthetic_keys():
    bundle = generate(start=HISTORY_START, end=HISTORY_START + timedelta(days=2), seed=42)
    columns = " ".join(bundle.encounters.columns).lower()
    for banned in ("ssn", "email", "phone", "address", "mrn", "patient_name"):
        assert banned not in columns
    assert bundle.encounters["synthetic_patient_key"].str.startswith("SP-").all()


def test_quarantine_reasons_and_dedup():
    bundle = generate(start=HISTORY_START, end=HISTORY_START + timedelta(days=3), seed=7)
    as_of = int(datetime(2026, 7, 1, tzinfo=ZoneInfo("America/Chicago")).timestamp())
    prepared = prepare_encounters(bundle.encounters, as_of)
    reasons = set(prepared.quarantined["reject_reason"])
    assert REASON_INVALID_TIMESTAMP in reasons
    assert REASON_UNKNOWN_SERVICE_LINE in reasons
    assert REASON_ARRIVAL_AFTER_DEPARTURE in reasons
    assert REASON_MISSING_DEPARTURE in reasons
    kept = prepared.accepted[prepared.accepted["encounter_id"] == "ENC-DUP"]
    assert len(kept) == 1
    assert kept.iloc[0]["arrival_mode"] == "scheduled"
    again = prepare_encounters(bundle.encounters, as_of)
    assert len(again.accepted) == len(prepared.accepted)
    assert again.duplicates_removed == prepared.duplicates_removed


def test_occupancy_zero_denominator_is_null():
    assert occupancy_rate(3, 0, 0) is None
    assert occupancy_rate(3, 4, 4) is None
    assert occupancy_rate(3, 10, 2) == pytest.approx(3 / 8)


def test_wape_zero_denominator_is_null():
    assert wape(np.array([0.0, 0.0]), np.array([1.0, 1.0])) is None
    assert mae(np.array([1.0, 3.0]), np.array([2.0, 1.0])) == pytest.approx(1.5)
    assert wape(np.array([10.0, 10.0]), np.array([12.0, 8.0])) == pytest.approx(0.2)


def test_dst_gap_skips_the_missing_hour():
    zone = ZoneInfo("America/Chicago")
    arrival = datetime(2026, 3, 8, 1, 30, tzinfo=zone)
    departure = datetime(2026, 3, 8, 4, 30, tzinfo=zone)
    assert occupies(arrival, departure, "completed", datetime(2026, 3, 8, 1, 0, tzinfo=zone))
    assert occupies(arrival, departure, "completed", datetime(2026, 3, 8, 3, 0, tzinfo=zone))
    assert not occupies(arrival, departure, "cancelled", datetime(2026, 3, 8, 1, 0, tzinfo=zone))
    bounds = occupied_bounds(int(arrival.timestamp()), int(departure.timestamp()), "completed", 0)
    assert bounds is not None
    # 02:00 does not exist, so 01:00 to 04:00 is two hours of UTC.
    assert bounds[1] - bounds[0] == 2 * 3600


def test_chronological_windows_do_not_overlap():
    days = history_dates()
    windows = chronological_windows(days)
    assert windows["train"][-1] < windows["validation"][0]
    assert windows["validation"][-1] < windows["test"][0]
    assert len(windows["test"]) == HORIZON_DAYS


def test_features_ignore_a_future_spike():
    dates = history_dates()
    rows = []
    for current in dates:
        rows.append({"service_line": "ED", "date": current, "arrivals": 10.0})
        rows.append({"service_line": "MED", "date": current, "arrivals": 8.0})
    daily = pd.DataFrame(rows)
    train_end = dates[TRAIN_DAYS - 1]
    original = build_feature_frame(daily, train_end)
    spiked = daily.copy()
    spiked.loc[spiked["date"] > train_end, "arrivals"] = 9999
    mutated = build_feature_frame(spiked, train_end)
    pd.testing.assert_frame_equal(
        original.reset_index(drop=True),
        mutated.reset_index(drop=True),
        check_dtype=False,
    )
    assert original["target_date"].max() <= train_end


def test_seasonal_naive_uses_only_history():
    history = pd.Series([float(index) for index in range(21)])
    forecast = seasonal_naive(history, horizon=14, season=7)
    assert forecast[0] == 14
    assert forecast[7] == 14
    assert min(forecast) >= 0


def test_scenario_constraints_and_determinism():
    days = [
        WardDay("ED-A", 0, "2026-07-01", 12, 10, 20, 6, 4, 2),
        WardDay("MED-1", 0, "2026-07-01", 8, 10, 16, 4, 5, 2),
    ]
    params = ScenarioParams(name="open_beds", demand_uplift=0.0)
    first = solve_scenario(days, params)
    second = solve_scenario(days, params)
    assert first["status"] == "feasible"
    assert first["objective"] == second["objective"]
    assert first["decisions"] == second["decisions"]
    assert all(row["staffed_beds"] + row["extra_beds"] <= row["max_usable_beds"] + 1e-6 for row in first["decisions"])
    blocked = solve_scenario(
        [WardDay("ED-A", 0, "2026-07-01", 40, 10, 10, 2, 4, 0)],
        ScenarioParams(name="too_much", demand_uplift=0.5),
    )
    assert blocked["status"] == "infeasible"
    with pytest.raises(ValueError):
        solve_scenario(days, ScenarioParams(name="bad", demand_uplift=-0.95))


def test_mock_event_feed_round_trip(tmp_path):
    path = tmp_path / "operational_events.json"
    path.write_text('[{"event_id": "EVT-0001", "event_type": "surge"}]', encoding="utf-8")
    payload = fetch_operational_events(path)
    assert payload[0]["event_id"] == "EVT-0001"
