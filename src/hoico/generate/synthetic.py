"""Deterministic synthetic hospital. Seed 42 reproduces every file."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from hoico.config import (
    ACUITY_CATEGORIES,
    ARRIVAL_MODES,
    DELAY_CATEGORIES,
    DISCHARGE_STATUSES,
    EVENT_TYPES,
    FACILITY_ID,
    FACILITY_KIND,
    FACILITY_NAME,
    HISTORY_END,
    HISTORY_START,
    HOLIDAYS,
    ROLE_GROUPS,
    SERVICE_LINES,
    SERVICE_LINES_BY_ID,
    TIMEZONE,
    WARDS,
)
from hoico.config import (
    seed as configured_seed,
)

LOCAL_TZ = ZoneInfo(TIMEZONE)


@dataclass
class SyntheticBundle:
    encounters: pd.DataFrame
    bed_capacity: pd.DataFrame
    staffing: pd.DataFrame
    discharges: pd.DataFrame
    operational_events: pd.DataFrame
    calendar: pd.DataFrame
    defect_counts: dict[str, int]


def history_dates(start: date = HISTORY_START, end: date = HISTORY_END) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def local_hours(start: date, end_exclusive: date) -> list[datetime]:
    cursor = datetime(start.year, start.month, start.day, tzinfo=LOCAL_TZ)
    stop = datetime(end_exclusive.year, end_exclusive.month, end_exclusive.day, tzinfo=LOCAL_TZ)
    hours: list[datetime] = []
    while cursor < stop:
        hours.append(cursor)
        cursor += timedelta(hours=1)
    return hours


def _lognormal_mu(mean: float, sigma: float) -> float:
    return math.log(mean) - 0.5 * sigma * sigma


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def _epoch(moment: datetime) -> int:
    return int(moment.timestamp())


def _assign_ward(service_line_id: str, rng: np.random.Generator) -> str:
    choices = [ward for ward in WARDS if ward.service_line_id == service_line_id]
    weights = np.array([ward.arrival_share for ward in choices], dtype=float)
    weights = weights / weights.sum()
    return choices[int(rng.choice(len(choices), p=weights))].ward_id


def _mode_for(service_line_id: str, rng: np.random.Generator) -> str:
    if service_line_id == "ED":
        options, probs = ARRIVAL_MODES[:3], [0.62, 0.28, 0.10]
    elif service_line_id in {"SURG", "ORTH"}:
        options, probs = ARRIVAL_MODES, [0.08, 0.05, 0.12, 0.75]
    else:
        options, probs = ARRIVAL_MODES, [0.20, 0.15, 0.25, 0.40]
    return str(rng.choice(np.array(options), p=np.array(probs)))


def _acuity_for(service_line_id: str, rng: np.random.Generator) -> str:
    if service_line_id == "ED":
        probs = [0.34, 0.36, 0.22, 0.08]
    elif service_line_id == "CARD":
        probs = [0.18, 0.40, 0.32, 0.10]
    else:
        probs = [0.30, 0.46, 0.20, 0.04]
    return str(rng.choice(np.array(ACUITY_CATEGORIES), p=np.array(probs)))


def generate(
    start: date = HISTORY_START,
    end: date = HISTORY_END,
    seed: int | None = None,
    inject_defects: bool = True,
) -> SyntheticBundle:
    rng = np.random.default_rng(configured_seed() if seed is None else seed)
    as_of_end = datetime(end.year, end.month, end.day, tzinfo=LOCAL_TZ) + timedelta(days=1)
    encounters = _encounters(rng, start, end, as_of_end)
    calendar = _calendar(start, end + timedelta(days=1))
    capacity = _capacity(rng, start, end + timedelta(days=1))
    staffing = _staffing(rng, start, end + timedelta(days=1))
    discharges = _discharges(rng, encounters)
    events = _events(rng, start, end)
    defects = {"encounters": 0, "bed_capacity": 0, "staffing": 0, "discharges": 0}
    if inject_defects:
        encounters, discharges, capacity, staffing, defects = _inject_defects(
            encounters, discharges, capacity, staffing, as_of_end
        )
    return SyntheticBundle(
        encounters=encounters,
        bed_capacity=capacity,
        staffing=staffing,
        discharges=discharges,
        operational_events=events,
        calendar=calendar,
        defect_counts=defects,
    )


def _encounters(
    rng: np.random.Generator,
    start: date,
    end: date,
    as_of_end: datetime,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    sequence = 1
    for spec in SERVICE_LINES:
        mu = _lognormal_mu(spec.los_mean_hours, spec.los_sigma)
        hour_probs = np.array(spec.hour_weights)
        for offset, current in enumerate(history_dates(start, end)):
            factor = 1.0 + 0.06 * math.sin(2 * math.pi * offset / 7)
            if current.weekday() >= 5:
                factor *= spec.weekend_factor
            if current in HOLIDAYS:
                factor *= spec.holiday_factor
            count = int(rng.poisson(spec.base_daily * factor))
            if count == 0:
                continue
            hours = rng.choice(24, size=count, p=hour_probs)
            minutes = rng.integers(0, 60, size=count)
            los_hours = np.clip(
                rng.lognormal(mu, spec.los_sigma, size=count),
                spec.los_min_hours,
                spec.los_max_hours,
            )
            cancel_flags = rng.random(count) < 0.02
            for index in range(count):
                arrival = datetime(
                    current.year,
                    current.month,
                    current.day,
                    int(hours[index]),
                    int(minutes[index]),
                    tzinfo=LOCAL_TZ,
                )
                planned_departure = arrival + timedelta(hours=float(los_hours[index]))
                if bool(cancel_flags[index]):
                    status = "cancelled"
                    departure: datetime | None = None
                elif planned_departure >= as_of_end:
                    status = "in_progress"
                    departure = None
                else:
                    status = "completed"
                    departure = planned_departure
                source_updated = arrival + timedelta(minutes=5)
                rows.append(
                    {
                        "encounter_id": f"ENC-{sequence:07d}",
                        "synthetic_patient_key": f"SP-{sequence:07d}",
                        "facility_id": FACILITY_ID,
                        "ward_id": _assign_ward(spec.service_line_id, rng),
                        "service_line": spec.service_line_id,
                        "arrival_time": _iso(arrival),
                        "departure_time": "" if departure is None else _iso(departure),
                        "arrival_epoch": _epoch(arrival),
                        "departure_epoch": "" if departure is None else _epoch(departure),
                        "arrival_mode": _mode_for(spec.service_line_id, rng),
                        "operational_acuity_category": _acuity_for(spec.service_line_id, rng),
                        "encounter_status": status,
                        "source_updated_at": _iso(source_updated),
                        "source_updated_epoch": _epoch(source_updated),
                    }
                )
                sequence += 1
    frame = pd.DataFrame(rows)
    return frame.sort_values(["arrival_epoch", "encounter_id"], kind="mergesort").reset_index(drop=True)


def _calendar(start: date, end_exclusive: date) -> pd.DataFrame:
    rows = []
    for moment in local_hours(start, end_exclusive):
        rows.append(
            {
                "calendar_date": moment.date().isoformat(),
                "hour": moment.hour,
                "day_of_week": moment.strftime("%A"),
                "day_of_week_index": moment.weekday(),
                "is_weekend": bool(moment.weekday() >= 5),
                "holiday_flag": bool(moment.date() in HOLIDAYS),
                "month": moment.month,
                "hour_start_local": moment.strftime("%Y-%m-%d %H:%M:%S"),
                "hour_start_epoch": _epoch(moment),
                "timezone": TIMEZONE,
            }
        )
    return pd.DataFrame(rows)


def _capacity(rng: np.random.Generator, start: date, end_exclusive: date) -> pd.DataFrame:
    rows = []
    for moment in local_hours(start, end_exclusive):
        for ward in WARDS:
            blocked = int(rng.integers(1, 3)) if rng.random() < 0.035 else 0
            blocked = min(blocked, ward.staffed_beds)
            rows.append(
                {
                    "timestamp": _iso(moment),
                    "timestamp_epoch": _epoch(moment),
                    "hour_start_local": moment.strftime("%Y-%m-%d %H:%M:%S"),
                    "facility_id": FACILITY_ID,
                    "ward_id": ward.ward_id,
                    "staffed_beds": ward.staffed_beds,
                    "blocked_beds": blocked,
                    "available_beds": ward.staffed_beds - blocked,
                    "physical_beds": ward.physical_beds,
                    "capacity_exception": "false",
                    "source_updated_at": _iso(moment),
                    "source_updated_epoch": _epoch(moment),
                }
            )
    return pd.DataFrame(rows)


def _staffing(rng: np.random.Generator, start: date, end_exclusive: date) -> pd.DataFrame:
    rows = []
    for moment in local_hours(start, end_exclusive):
        for ward in WARDS:
            scheduled = {
                "rn": int(math.ceil(ward.staffed_beds / ward.patients_per_rn)),
                "aide": int(math.ceil(ward.staffed_beds / 8)),
            }
            for role in ROLE_GROUPS:
                absence = min(int(rng.random() < 0.08), scheduled[role])
                rows.append(
                    {
                        "timestamp": _iso(moment),
                        "timestamp_epoch": _epoch(moment),
                        "hour_start_local": moment.strftime("%Y-%m-%d %H:%M:%S"),
                        "facility_id": FACILITY_ID,
                        "unit_id": ward.ward_id,
                        "role_group": role,
                        "scheduled_staff": scheduled[role],
                        "absence_count": absence,
                        "available_staff": scheduled[role] - absence,
                        "source_updated_at": _iso(moment),
                        "source_updated_epoch": _epoch(moment),
                    }
                )
    return pd.DataFrame(rows)


def _discharges(rng: np.random.Generator, encounters: pd.DataFrame) -> pd.DataFrame:
    rows = []
    completed = encounters[encounters["encounter_status"] == "completed"]
    delay_pool = [item for item in DELAY_CATEGORIES if item != "none"]
    for record in completed.itertuples(index=False):
        spec = SERVICE_LINES_BY_ID[str(record.service_line)]
        arrival = datetime.fromisoformat(str(record.arrival_time))
        departure = datetime.fromisoformat(str(record.departure_time))
        los_hours = (departure - arrival).total_seconds() / 3600
        delayed = los_hours > spec.target_los_hours * 1.2
        if delayed:
            delay = str(rng.choice(np.array(delay_pool)))
            status = str(rng.choice(np.array(DISCHARGE_STATUSES), p=np.array([0.55, 0.30, 0.15])))
        else:
            delay = "none"
            status = str(rng.choice(np.array(DISCHARGE_STATUSES), p=np.array([0.82, 0.14, 0.04])))
        rows.append(
            {
                "encounter_id": record.encounter_id,
                "facility_id": FACILITY_ID,
                "discharge_time": record.departure_time,
                "discharge_epoch": record.departure_epoch,
                "discharge_status": status,
                "delay_category": delay,
                "source_updated_at": record.departure_time,
                "source_updated_epoch": record.departure_epoch,
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "encounter_id",
                "facility_id",
                "discharge_time",
                "discharge_epoch",
                "discharge_status",
                "delay_category",
                "source_updated_at",
                "source_updated_epoch",
            ]
        )
    return pd.DataFrame(rows)


def _events(rng: np.random.Generator, start: date, end: date) -> pd.DataFrame:
    hours = local_hours(start, end + timedelta(days=1))
    picks = np.sort(rng.choice(len(hours), size=min(48, len(hours)), replace=False))
    rows = []
    for index, pick in enumerate(picks, start=1):
        moment = hours[int(pick)]
        ward = WARDS[int(rng.integers(0, len(WARDS)))]
        rows.append(
            {
                "event_id": f"EVT-{index:04d}",
                "event_type": str(rng.choice(np.array(EVENT_TYPES))),
                "event_time": _iso(moment),
                "event_epoch": _epoch(moment),
                "facility_id": FACILITY_ID,
                "unit_id": ward.ward_id,
                "severity": int(rng.integers(1, 4)),
                "source_updated_at": _iso(moment),
                "source_updated_epoch": _epoch(moment),
            }
        )
    return pd.DataFrame(rows)


def _inject_defects(
    encounters: pd.DataFrame,
    discharges: pd.DataFrame,
    capacity: pd.DataFrame,
    staffing: pd.DataFrame,
    as_of_end: datetime,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, int]]:
    base = encounters.iloc[0].to_dict()
    anchor = datetime.fromisoformat(str(base["source_updated_at"]))
    later = anchor + timedelta(days=1)
    earlier = anchor - timedelta(days=1)
    duplicate_old = dict(base)
    duplicate_old.update(
        {
            "encounter_id": "ENC-DUP",
            "synthetic_patient_key": "SP-DUP",
            "arrival_mode": "transfer",
            "source_updated_at": _iso(earlier),
            "source_updated_epoch": _epoch(earlier),
        }
    )
    duplicate_new = dict(duplicate_old)
    duplicate_new.update(
        {
            "arrival_mode": "scheduled",
            "source_updated_at": _iso(later),
            "source_updated_epoch": _epoch(later),
        }
    )
    arrival = datetime.fromisoformat(str(base["arrival_time"]))
    bad_departure = arrival - timedelta(hours=3)
    bad_order = dict(base)
    bad_order.update(
        {
            "encounter_id": "ENC-BAD-ORDER",
            "synthetic_patient_key": "SP-BAD-ORDER",
            "encounter_status": "completed",
            "departure_time": _iso(bad_departure),
            "departure_epoch": _epoch(bad_departure),
            "source_updated_at": _iso(as_of_end - timedelta(hours=1)),
            "source_updated_epoch": _epoch(as_of_end - timedelta(hours=1)),
        }
    )
    bad_service = dict(base)
    bad_service.update(
        {
            "encounter_id": "ENC-BAD-SERVICE",
            "synthetic_patient_key": "SP-BAD-SERVICE",
            "service_line": "NOT_A_SERVICE",
        }
    )
    bad_time = dict(base)
    bad_time.update(
        {
            "encounter_id": "ENC-BAD-TIME",
            "synthetic_patient_key": "SP-BAD-TIME",
            "arrival_time": "not-a-timestamp",
            "arrival_epoch": "",
        }
    )
    missing_departure = dict(base)
    missing_departure.update(
        {
            "encounter_id": "ENC-BAD-DEPARTURE",
            "synthetic_patient_key": "SP-BAD-DEPARTURE",
            "encounter_status": "completed",
            "departure_time": "",
            "departure_epoch": "",
        }
    )
    encounters = pd.concat(
        [
            encounters,
            pd.DataFrame(
                [duplicate_old, duplicate_new, bad_order, bad_service, bad_time, missing_departure]
            ),
        ],
        ignore_index=True,
    )

    first_capacity = capacity.iloc[0].to_dict()
    negative = dict(first_capacity)
    negative.update({"staffed_beds": -1, "available_beds": -1, "blocked_beds": 0})
    overflow_time = datetime.fromisoformat(str(first_capacity["timestamp"])) + timedelta(hours=1)
    overflow = dict(first_capacity)
    overflow.update(
        {
            "timestamp": _iso(overflow_time),
            "timestamp_epoch": _epoch(overflow_time),
            "hour_start_local": overflow_time.strftime("%Y-%m-%d %H:%M:%S"),
            "staffed_beds": 999,
            "available_beds": 999,
            "capacity_exception": "false",
            "source_updated_at": _iso(overflow_time),
            "source_updated_epoch": _epoch(overflow_time),
        }
    )
    capacity = pd.concat([capacity, pd.DataFrame([negative, overflow])], ignore_index=True)

    bad_staff = staffing.iloc[0].to_dict()
    bad_staff.update({"scheduled_staff": -2, "available_staff": -2, "absence_count": 0})
    staffing = pd.concat([staffing, pd.DataFrame([bad_staff])], ignore_index=True)

    orphan_time = as_of_end - timedelta(hours=2)
    orphan = {
        "encounter_id": "ENC-ORPHAN",
        "facility_id": FACILITY_ID,
        "discharge_time": _iso(orphan_time),
        "discharge_epoch": _epoch(orphan_time),
        "discharge_status": "home",
        "delay_category": "none",
        "source_updated_at": _iso(orphan_time),
        "source_updated_epoch": _epoch(orphan_time),
    }
    discharges = pd.concat([discharges, pd.DataFrame([orphan])], ignore_index=True)
    return encounters, discharges, capacity, staffing, {
        "encounters": 6,
        "bed_capacity": 2,
        "staffing": 1,
        "discharges": 1,
    }


def content_hash(blobs: list[bytes]) -> str:
    digest = hashlib.sha256()
    for blob in blobs:
        digest.update(blob)
    return digest.hexdigest()[:16]


def write_bundle(bundle: SyntheticBundle, directory: Path) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    blobs: list[bytes] = []
    frames = {
        "encounters": bundle.encounters,
        "bed_capacity": bundle.bed_capacity,
        "staffing": bundle.staffing,
        "discharges": bundle.discharges,
        "calendar": bundle.calendar,
    }
    for name, frame in frames.items():
        target = directory / f"{name}.csv"
        frame.to_csv(target, index=False)
        blobs.append(target.read_bytes())
    events_path = directory / "operational_events.json"
    payload = bundle.operational_events.to_dict(orient="records")
    events_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    blobs.append(events_path.read_bytes())
    batch_id = content_hash(blobs)
    (directory / "batch_id.txt").write_text(batch_id, encoding="utf-8")
    (directory / "defect_counts.json").write_text(json.dumps(bundle.defect_counts, indent=2), encoding="utf-8")
    return batch_id


def reference_frames() -> dict[str, pd.DataFrame]:
    return {
        "facility": pd.DataFrame(
            [
                {
                    "facility_id": FACILITY_ID,
                    "facility_name": FACILITY_NAME,
                    "facility_kind": FACILITY_KIND,
                    "timezone": TIMEZONE,
                }
            ]
        ),
        "service_line": pd.DataFrame(
            [
                {
                    "service_line_id": item.service_line_id,
                    "service_line_name": item.name,
                    "patients_per_rn": item.patients_per_rn,
                    "target_los_hours": item.target_los_hours,
                }
                for item in SERVICE_LINES
            ]
        ),
        "ward": pd.DataFrame(
            [
                {
                    "ward_id": item.ward_id,
                    "facility_id": FACILITY_ID,
                    "service_line_id": item.service_line_id,
                    "ward_name": item.name,
                    "staffed_beds": item.staffed_beds,
                    "physical_beds": item.physical_beds,
                    "patients_per_rn": item.patients_per_rn,
                    "arrival_share": item.arrival_share,
                }
                for item in WARDS
            ]
        ),
    }
