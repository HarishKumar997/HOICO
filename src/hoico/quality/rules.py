"""Row-level contracts shared by tests and the Spark medallion job."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from hoico.config import (
    ACUITY_CATEGORIES,
    ARRIVAL_MODES,
    DELAY_CATEGORIES,
    DISCHARGE_STATUSES,
    ENCOUNTER_STATUSES,
    EVENT_TYPES,
    ROLE_GROUPS,
    SERVICE_LINE_IDS,
    WARD_IDS,
)

REASON_MISSING_ENCOUNTER = "missing_encounter_id"
REASON_INVALID_TIMESTAMP = "invalid_timestamp"
REASON_ARRIVAL_AFTER_DEPARTURE = "arrival_after_departure"
REASON_UNKNOWN_SERVICE_LINE = "unknown_service_line"
REASON_UNKNOWN_WARD = "unknown_ward"
REASON_INVALID_CATEGORY = "invalid_category"
REASON_MISSING_DEPARTURE = "missing_departure"
REASON_NEGATIVE_STAFFED_BEDS = "negative_staffed_beds"
REASON_STAFFED_EXCEEDS_PHYSICAL = "staffed_beds_exceed_physical"
REASON_NEGATIVE_STAFF = "negative_staff_count"
REASON_ORPHAN_DISCHARGE = "orphan_discharge"
REASON_UNKNOWN_UNIT = "unknown_unit"
REASON_MISSING_EVENT = "missing_event_id"

ENCOUNTER_REASONS = (
    REASON_MISSING_ENCOUNTER,
    REASON_INVALID_TIMESTAMP,
    REASON_UNKNOWN_SERVICE_LINE,
    REASON_UNKNOWN_WARD,
    REASON_INVALID_CATEGORY,
    REASON_MISSING_DEPARTURE,
    REASON_ARRIVAL_AFTER_DEPARTURE,
)


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and value != value:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "nat"}


def _as_int(value: Any) -> int | None:
    if _blank(value):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if _blank(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_timestamp(value: Any) -> datetime | None:
    if _blank(value):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for parser in (
        lambda raw: datetime.fromisoformat(raw.replace("Z", "+00:00")),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d %H:%M:%S"),
        lambda raw: datetime.strptime(raw, "%Y-%m-%d"),
    ):
        try:
            return parser(text)
        except ValueError:
            continue
    return None


def encounter_reject_reason(row: dict[str, Any], known_wards: set[str] | None = None) -> str | None:
    """Return the first reason this encounter fails, or None when it is usable."""
    wards = known_wards if known_wards is not None else set(WARD_IDS)
    if _blank(row.get("encounter_id")):
        return REASON_MISSING_ENCOUNTER
    arrival = parse_timestamp(row.get("arrival_time"))
    epoch = _as_int(row.get("arrival_epoch"))
    if arrival is None or epoch is None:
        return REASON_INVALID_TIMESTAMP
    service_line = str(row.get("service_line") or "").strip()
    if service_line not in SERVICE_LINE_IDS:
        return REASON_UNKNOWN_SERVICE_LINE
    ward_id = str(row.get("ward_id") or "").strip()
    if ward_id not in wards:
        return REASON_UNKNOWN_WARD
    if str(row.get("arrival_mode") or "").strip() not in ARRIVAL_MODES:
        return REASON_INVALID_CATEGORY
    if str(row.get("operational_acuity_category") or "").strip() not in ACUITY_CATEGORIES:
        return REASON_INVALID_CATEGORY
    status = str(row.get("encounter_status") or "").strip()
    if status not in ENCOUNTER_STATUSES:
        return REASON_INVALID_CATEGORY
    if status == "completed":
        departure = parse_timestamp(row.get("departure_time"))
        departure_epoch = _as_int(row.get("departure_epoch"))
        if departure is None or departure_epoch is None:
            return REASON_MISSING_DEPARTURE
        if departure_epoch < epoch:
            return REASON_ARRIVAL_AFTER_DEPARTURE
    return None


def capacity_reject_reason(row: dict[str, Any]) -> str | None:
    if _blank(row.get("ward_id")) or str(row.get("ward_id")).strip() not in WARD_IDS:
        return REASON_UNKNOWN_WARD
    if parse_timestamp(row.get("timestamp")) is None or _as_int(row.get("timestamp_epoch")) is None:
        return REASON_INVALID_TIMESTAMP
    staffed = _as_float(row.get("staffed_beds"))
    physical = _as_float(row.get("physical_beds"))
    blocked = _as_float(row.get("blocked_beds"))
    if staffed is None or physical is None or blocked is None:
        return REASON_INVALID_CATEGORY
    if staffed < 0 or blocked < 0 or physical < 0:
        return REASON_NEGATIVE_STAFFED_BEDS
    exception = str(row.get("capacity_exception") or "").strip().lower() in {"1", "true", "yes"}
    if staffed > physical and not exception:
        return REASON_STAFFED_EXCEEDS_PHYSICAL
    return None


def staffing_reject_reason(row: dict[str, Any]) -> str | None:
    if str(row.get("unit_id") or "").strip() not in WARD_IDS:
        return REASON_UNKNOWN_UNIT
    if str(row.get("role_group") or "").strip() not in ROLE_GROUPS:
        return REASON_INVALID_CATEGORY
    if parse_timestamp(row.get("timestamp")) is None:
        return REASON_INVALID_TIMESTAMP
    scheduled = _as_float(row.get("scheduled_staff"))
    available = _as_float(row.get("available_staff"))
    absence = _as_float(row.get("absence_count"))
    if scheduled is None or available is None or absence is None:
        return REASON_INVALID_CATEGORY
    if scheduled < 0 or available < 0 or absence < 0:
        return REASON_NEGATIVE_STAFF
    return None


def discharge_reject_reason(row: dict[str, Any], known_encounters: set[str] | None = None) -> str | None:
    encounter_id = str(row.get("encounter_id") or "").strip()
    if _blank(encounter_id):
        return REASON_MISSING_ENCOUNTER
    if known_encounters is not None and encounter_id not in known_encounters:
        return REASON_ORPHAN_DISCHARGE
    if parse_timestamp(row.get("discharge_time")) is None:
        return REASON_INVALID_TIMESTAMP
    if str(row.get("discharge_status") or "").strip() not in DISCHARGE_STATUSES:
        return REASON_INVALID_CATEGORY
    if str(row.get("delay_category") or "").strip() not in DELAY_CATEGORIES:
        return REASON_INVALID_CATEGORY
    return None


def event_reject_reason(row: dict[str, Any]) -> str | None:
    if _blank(row.get("event_id")):
        return REASON_MISSING_EVENT
    if str(row.get("event_type") or "").strip() not in EVENT_TYPES:
        return REASON_INVALID_CATEGORY
    if parse_timestamp(row.get("event_time")) is None:
        return REASON_INVALID_TIMESTAMP
    if str(row.get("unit_id") or "").strip() not in WARD_IDS:
        return REASON_UNKNOWN_UNIT
    return None
