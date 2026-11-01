"""Stable product constants. Analytical timestamps use America/Chicago wall time."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date


def seed() -> int:
    return int(os.environ.get("HOICO_SEED", "42"))


TIMEZONE = os.environ.get("HOICO_TIMEZONE", "America/Chicago")
FACILITY_ID = "F001"
FACILITY_NAME = "Cedarline General"
FACILITY_KIND = "synthetic community hospital"

# 118 days so the chronological split is 90 train + 14 validation + 14 test.
HISTORY_START = date(2026, 3, 5)
HISTORY_END = date(2026, 6, 30)
TRAIN_DAYS = 90
VAL_DAYS = 14
HORIZON_DAYS = 14
SCENARIO_DAYS = 7
PRESSURE_THRESHOLD = 0.85
OVER_CAPACITY_THRESHOLD = 1.0

ARRIVAL_MODES = ("walk_in", "ambulance", "transfer", "scheduled")
ACUITY_CATEGORIES = ("low", "moderate", "high", "critical")
ENCOUNTER_STATUSES = ("completed", "in_progress", "cancelled")
ROLE_GROUPS = ("rn", "aide")
DISCHARGE_STATUSES = ("home", "transfer_unit", "left_before_placement")
DELAY_CATEGORIES = ("none", "placement", "transport", "paperwork")
EVENT_TYPES = ("staff_shortage", "bed_block", "equipment_down", "surge")

# Eligible arrivals exclude cancelled registrations.
CANCELLED_STATUS = "cancelled"
COMPLETED_STATUS = "completed"


@dataclass(frozen=True)
class ServiceLine:
    service_line_id: str
    name: str
    base_daily: float
    weekend_factor: float
    holiday_factor: float
    los_mean_hours: float
    los_sigma: float
    los_min_hours: float
    los_max_hours: float
    target_los_hours: float
    patients_per_rn: float
    hour_weights: tuple[float, ...]


@dataclass(frozen=True)
class Ward:
    ward_id: str
    service_line_id: str
    name: str
    staffed_beds: int
    physical_beds: int
    patients_per_rn: float
    arrival_share: float


def _norm(weights: list[float]) -> tuple[float, ...]:
    total = sum(weights)
    return tuple(weight / total for weight in weights)


def _day_profile(day_peak: float, night_peak: float) -> tuple[float, ...]:
    raw = []
    for hour in range(24):
        if 7 <= hour <= 15:
            raw.append(day_peak)
        elif 16 <= hour <= 21:
            raw.append((day_peak + night_peak) / 2)
        else:
            raw.append(night_peak)
    return _norm(raw)


SERVICE_LINES: tuple[ServiceLine, ...] = (
    ServiceLine(
        "ED",
        "Emergency",
        base_daily=72,
        weekend_factor=1.14,
        holiday_factor=1.08,
        los_mean_hours=8,
        los_sigma=0.35,
        los_min_hours=1,
        los_max_hours=36,
        target_los_hours=8,
        patients_per_rn=4,
        hour_weights=_day_profile(1.1, 1.35),
    ),
    ServiceLine(
        "MED",
        "General Medicine",
        base_daily=14,
        weekend_factor=0.92,
        holiday_factor=0.84,
        los_mean_hours=76,
        los_sigma=0.28,
        los_min_hours=12,
        los_max_hours=240,
        target_los_hours=72,
        patients_per_rn=5,
        hour_weights=_day_profile(1.4, 0.45),
    ),
    ServiceLine(
        "SURG",
        "General Surgery",
        base_daily=12,
        weekend_factor=0.42,
        holiday_factor=0.38,
        los_mean_hours=58,
        los_sigma=0.30,
        los_min_hours=8,
        los_max_hours=200,
        target_los_hours=48,
        patients_per_rn=4,
        hour_weights=_day_profile(1.8, 0.25),
    ),
    ServiceLine(
        "CARD",
        "Cardiology",
        base_daily=6,
        weekend_factor=0.72,
        holiday_factor=0.70,
        los_mean_hours=52,
        los_sigma=0.32,
        los_min_hours=8,
        los_max_hours=180,
        target_los_hours=48,
        patients_per_rn=3,
        hour_weights=_day_profile(1.5, 0.40),
    ),
    ServiceLine(
        "ORTH",
        "Orthopedics",
        base_daily=6,
        weekend_factor=0.48,
        holiday_factor=0.40,
        los_mean_hours=64,
        los_sigma=0.30,
        los_min_hours=8,
        los_max_hours=220,
        target_los_hours=60,
        patients_per_rn=4,
        hour_weights=_day_profile(1.7, 0.28),
    ),
    ServiceLine(
        "WH",
        "Women's Health",
        base_daily=7,
        weekend_factor=0.88,
        holiday_factor=0.80,
        los_mean_hours=36,
        los_sigma=0.30,
        los_min_hours=6,
        los_max_hours=120,
        target_los_hours=36,
        patients_per_rn=4,
        hour_weights=_day_profile(1.45, 0.55),
    ),
)

WARDS: tuple[Ward, ...] = (
    Ward("ED-A", "ED", "Emergency A", 30, 34, 4, 1.0),
    Ward("MED-1", "MED", "Medicine 1", 24, 28, 5, 0.50),
    Ward("MED-2", "MED", "Medicine 2", 18, 22, 5, 0.32),
    Ward("MED-3", "MED", "Medicine overflow", 12, 16, 5, 0.18),
    Ward("SURG-1", "SURG", "Surgery 1", 32, 36, 4, 1.0),
    Ward("CARD-1", "CARD", "Cardiology", 16, 18, 3, 1.0),
    Ward("ORTH-1", "ORTH", "Orthopedics", 18, 20, 4, 1.0),
    Ward("WH-1", "WH", "Women's Health", 14, 16, 4, 1.0),
)

HOLIDAYS = frozenset({date(2026, 5, 25), date(2026, 6, 19)})

SERVICE_LINE_IDS = tuple(item.service_line_id for item in SERVICE_LINES)
WARD_IDS = tuple(item.ward_id for item in WARDS)
SERVICE_LINE_NAMES = {item.service_line_id: item.name for item in SERVICE_LINES}
WARD_NAMES = {item.ward_id: item.name for item in WARDS}
WARDS_BY_ID = {item.ward_id: item for item in WARDS}
SERVICE_LINES_BY_ID = {item.service_line_id: item for item in SERVICE_LINES}

MODEL_NAIVE = "seasonal_naive"
MODEL_HW = "holt_winters"
MODEL_LGBM = "lightgbm"
MODEL_CANDIDATES = (MODEL_NAIVE, MODEL_HW, MODEL_LGBM)
# When validation WAPE ties, keep the simpler model.
MODEL_TIE_BREAK = (MODEL_NAIVE, MODEL_HW, MODEL_LGBM)

DEFAULT_WEIGHTS = {
    "unmet_bed_days": 100.0,
    "overtime_hour": 25.0,
    "temporary_bed_day": 40.0,
    "disruption_discharge": 15.0,
}

NOTICE = (
    "Synthetic data for a portfolio project. These are planning estimates, "
    "not clinical advice, and they do not describe a real hospital."
)

ASSUMPTIONS = [
    "All timestamps in the analytical model are America/Chicago wall times.",
    "Cancelled registrations are stored but excluded from arrivals and occupancy.",
    "Open encounters occupy a bed through the as-of hour and are excluded from length-of-stay averages.",
    "Usable beds equal staffed beds minus blocked beds. A zero usable-bed count makes occupancy null.",
    "Available beds in the capacity feed are usable supply, not vacant beds.",
    "Daily census forecasts use Little's Law: arrivals times training-window mean length of stay.",
    "Future staffed capacity, unless a scenario changes it, equals the last seven observed days.",
    "Scenario costs are unitless operational proxies. Weights are editable and shown with every result.",
    "Staffing ratios are configurable planning assumptions, not a staffing standard or a clinical rule.",
    "No protected characteristic and no individual clinical detail is used to rank or deny capacity.",
]
