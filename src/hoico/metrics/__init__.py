"""Operational metric definitions used by tests, forecasts, and the API."""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from hoico.config import CANCELLED_STATUS, PRESSURE_THRESHOLD


def usable_beds(staffed_beds: float, blocked_beds: float) -> float:
    return max(float(staffed_beds) - float(blocked_beds), 0.0)


def occupancy_rate(occupied_beds: float, staffed_beds: float, blocked_beds: float) -> float | None:
    """Occupied divided by usable beds. Zero usable beds is undefined, not zero."""
    usable = usable_beds(staffed_beds, blocked_beds)
    if usable <= 0:
        return None
    return float(occupied_beds) / usable


def pressure_band(rate: float | None, threshold: float = PRESSURE_THRESHOLD) -> str:
    if rate is None:
        return "undefined"
    if rate >= 1:
        return "over_capacity"
    if rate >= threshold:
        return "elevated"
    return "within_capacity"


def count_arrivals(encounters: pd.DataFrame) -> int:
    if encounters.empty:
        return 0
    status = encounters["encounter_status"].astype(str)
    return int((status != CANCELLED_STATUS).sum())


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    actual_arr = np.asarray(actual, dtype=float)
    predicted_arr = np.asarray(predicted, dtype=float)
    if actual_arr.size == 0:
        return float("nan")
    return float(np.mean(np.abs(actual_arr - predicted_arr)))


def wape(actual: np.ndarray, predicted: np.ndarray) -> float | None:
    """Weighted absolute percentage error. Null when the actual sum is zero."""
    actual_arr = np.asarray(actual, dtype=float)
    predicted_arr = np.asarray(predicted, dtype=float)
    denominator = float(np.abs(actual_arr).sum())
    if denominator == 0:
        return None
    return float(np.abs(actual_arr - predicted_arr).sum() / denominator)


def interval_coverage(
    actual: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> float | None:
    actual_arr = np.asarray(actual, dtype=float)
    if actual_arr.size == 0:
        return None
    inside = (actual_arr >= np.asarray(lower, dtype=float)) & (
        actual_arr <= np.asarray(upper, dtype=float)
    )
    return float(np.mean(inside))


def occupies(
    arrival: datetime,
    departure: datetime | None,
    status: str,
    hour_start: datetime,
) -> bool:
    """An encounter occupies a clock hour when the stay overlaps that hour."""
    if status == CANCELLED_STATUS:
        return False
    hour_end = hour_start + timedelta(hours=1)
    if arrival >= hour_end:
        return False
    if departure is None:
        return arrival < hour_end
    return departure > hour_start and arrival < hour_end


def length_of_stay_hours(arrival: datetime, departure: datetime | None, status: str) -> float | None:
    """Completed encounters only. Open stays are right-censored and return null."""
    if status != "completed" or departure is None:
        return None
    hours = (departure - arrival).total_seconds() / 3600
    if hours < 0 or math.isnan(hours):
        return None
    return float(hours)


def little_census(daily_arrivals: float, mean_los_days: float) -> float:
    """Average census approximation: L = lambda * W."""
    return float(daily_arrivals) * float(mean_los_days)
