"""Validate, quarantine, and deduplicate source frames."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from hoico.config import CANCELLED_STATUS, TIMEZONE
from hoico.quality.dedup import deduplicate
from hoico.quality.rules import (
    capacity_reject_reason,
    discharge_reject_reason,
    encounter_reject_reason,
    event_reject_reason,
    staffing_reject_reason,
)

LOCAL_TZ = ZoneInfo(TIMEZONE)


@dataclass
class PreparedTable:
    accepted: pd.DataFrame
    quarantined: pd.DataFrame
    duplicates_removed: int


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    return frame.to_dict(orient="records")


def _split(frame: pd.DataFrame, reasons: list[str | None]) -> tuple[pd.DataFrame, pd.DataFrame]:
    marked = frame.copy()
    marked["reject_reason"] = reasons
    bad = marked[marked["reject_reason"].notna()].copy()
    good = marked[marked["reject_reason"].isna()].drop(columns=["reject_reason"]).copy()
    return good, bad


def _optional_epoch(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        return None
    return int(value)


def _hour_label(epoch: int) -> str:
    moment = datetime.fromtimestamp(int(epoch), LOCAL_TZ).replace(minute=0, second=0, microsecond=0)
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def occupied_bounds(
    arrival_epoch: int,
    departure_epoch: int | None,
    status: str,
    as_of_epoch: int,
) -> tuple[int, int] | None:
    """Inclusive local-hour epoch bounds. Cancelled stays and empty stays return None."""
    if status == CANCELLED_STATUS:
        return None
    end_exclusive = as_of_epoch if departure_epoch is None else int(departure_epoch)
    if end_exclusive <= int(arrival_epoch):
        return None
    arrival = datetime.fromtimestamp(int(arrival_epoch), LOCAL_TZ)
    end_moment = datetime.fromtimestamp(end_exclusive, LOCAL_TZ) - timedelta(seconds=1)
    first = arrival.replace(minute=0, second=0, microsecond=0)
    if end_moment < first:
        return None
    last = end_moment.replace(minute=0, second=0, microsecond=0)
    return int(first.timestamp()), int(last.timestamp())


def _coerce_epoch(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if column in frame.columns:
        frame = frame.copy()
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def prepare_encounters(frame: pd.DataFrame, as_of_epoch: int) -> PreparedTable:
    frame = _coerce_epoch(frame, "arrival_epoch")
    frame = _coerce_epoch(frame, "departure_epoch")
    frame = _coerce_epoch(frame, "source_updated_epoch")
    good, bad = _split(frame, [encounter_reject_reason(row) for row in _records(frame)])
    good, removed = deduplicate(good, ["encounter_id"], "source_updated_epoch")
    if good.empty:
        good["arrival_hour_local"] = []
        good["first_occupied_epoch"] = []
        good["last_occupied_epoch"] = []
        return PreparedTable(good, bad, removed)
    hours = []
    firsts = []
    lasts = []
    for row in _records(good):
        arrival_epoch = int(row["arrival_epoch"])
        hours.append(_hour_label(arrival_epoch))
        departure_epoch = _optional_epoch(row.get("departure_epoch"))
        bounds = occupied_bounds(
            arrival_epoch,
            departure_epoch,
            str(row["encounter_status"]),
            as_of_epoch,
        )
        if bounds is None:
            firsts.append(pd.NA)
            lasts.append(pd.NA)
        else:
            firsts.append(bounds[0])
            lasts.append(bounds[1])
    good["arrival_hour_local"] = hours
    good["first_occupied_epoch"] = firsts
    good["last_occupied_epoch"] = lasts
    return PreparedTable(good.reset_index(drop=True), bad.reset_index(drop=True), removed)


def prepare_capacity(frame: pd.DataFrame) -> PreparedTable:
    good, bad = _split(frame, [capacity_reject_reason(row) for row in _records(frame)])
    good, removed = deduplicate(
        good, ["facility_id", "ward_id", "timestamp_epoch"], "source_updated_epoch"
    )
    return PreparedTable(good.reset_index(drop=True), bad.reset_index(drop=True), removed)


def prepare_staffing(frame: pd.DataFrame) -> PreparedTable:
    good, bad = _split(frame, [staffing_reject_reason(row) for row in _records(frame)])
    good, removed = deduplicate(
        good, ["unit_id", "role_group", "timestamp_epoch"], "source_updated_epoch"
    )
    return PreparedTable(good.reset_index(drop=True), bad.reset_index(drop=True), removed)


def prepare_discharges(frame: pd.DataFrame, known_encounters: set[str]) -> PreparedTable:
    reasons = [
        discharge_reject_reason(row, known_encounters=known_encounters) for row in _records(frame)
    ]
    good, bad = _split(frame, reasons)
    good, removed = deduplicate(good, ["encounter_id"], "source_updated_epoch")
    return PreparedTable(good.reset_index(drop=True), bad.reset_index(drop=True), removed)


def prepare_events(frame: pd.DataFrame) -> PreparedTable:
    good, bad = _split(frame, [event_reject_reason(row) for row in _records(frame)])
    good, removed = deduplicate(good, ["event_id"], "source_updated_epoch")
    return PreparedTable(good.reset_index(drop=True), bad.reset_index(drop=True), removed)
