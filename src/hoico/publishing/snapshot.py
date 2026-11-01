"""Aggregate snapshot for the Next.js console and the Vercel demo. No encounter rows."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from hoico.config import (
    ASSUMPTIONS,
    FACILITY_ID,
    FACILITY_NAME,
    HISTORY_END,
    HISTORY_START,
    NOTICE,
    PRESSURE_THRESHOLD,
    SERVICE_LINE_NAMES,
    TIMEZONE,
    WARD_NAMES,
)
from hoico.metrics import pressure_band
from hoico.paths import generated_dir, lake_dir, snapshot_path

FORBIDDEN_KEYS = {"encounter_id", "synthetic_patient_key", "row_payload"}


def _hourly(arrivals: pd.DataFrame) -> list[dict[str, object]]:
    frame = arrivals.copy()
    frame["hour"] = pd.to_datetime(frame["arrival_hour_local"])
    frame["arrivals"] = pd.to_numeric(frame["arrivals"], errors="coerce").fillna(0)
    totals = frame.groupby("hour", as_index=False)["arrivals"].sum().sort_values("hour")
    indexed = {
        pd.Timestamp(row.hour).strftime("%Y-%m-%d %H:%M:%S"): float(row.arrivals)
        for row in totals.itertuples(index=False)
    }
    end = datetime(HISTORY_END.year, HISTORY_END.month, HISTORY_END.day, 23, 0, 0)
    start = end - timedelta(hours=47)
    points = []
    cursor = start
    while cursor <= end:
        label = cursor.strftime("%Y-%m-%d %H:%M:%S")
        points.append(
            {
                "hour": label,
                "value": indexed.get(label, 0.0),
                "kind": "observed",
                "model": "observed",
            }
        )
        cursor += timedelta(hours=1)
    for step in range(1, 25):
        future = end + timedelta(hours=step)
        reference = (future - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        points.append(
            {
                "hour": future.strftime("%Y-%m-%d %H:%M:%S"),
                "value": indexed.get(reference, 0.0),
                "kind": "forecast",
                "model": "seasonal_naive_weekly",
            }
        )
    return points


def _capacity(occupancy: pd.DataFrame, census: pd.DataFrame) -> list[dict[str, object]]:
    frame = occupancy.copy()
    frame["occupied_beds"] = pd.to_numeric(frame["occupied_beds"], errors="coerce").fillna(0)
    frame["usable_beds"] = pd.to_numeric(frame["usable_beds"], errors="coerce")
    frame["census_date"] = frame["census_date"].astype(str).str.slice(0, 10)
    daily = (
        frame.groupby(["ward_id", "census_date"], as_index=False)
        .agg(occupied_beds=("occupied_beds", "mean"), usable_beds=("usable_beds", "mean"))
    )
    recent_dates = sorted(daily["census_date"].unique())[-28:]
    points = []
    for row in daily[daily["census_date"].isin(recent_dates)].itertuples(index=False):
        usable = None if pd.isna(row.usable_beds) else float(row.usable_beds)
        rate = None if usable is None or usable <= 0 else float(row.occupied_beds) / usable
        points.append(
            {
                "date": row.census_date,
                "ward_id": row.ward_id,
                "ward_name": WARD_NAMES.get(row.ward_id, row.ward_id),
                "occupied": round(float(row.occupied_beds), 2),
                "usable_beds": None if usable is None else round(usable, 2),
                "occupancy_rate": None if rate is None else round(rate, 4),
                "pressure": pressure_band(rate),
                "kind": "observed",
            }
        )
    last_week = sorted(daily["census_date"].unique())[-7:]
    usable_lookup = (
        daily[daily["census_date"].isin(last_week)].groupby("ward_id")["usable_beds"].mean().to_dict()
    )
    forecast_dates = sorted(census["target_date"].unique())[:14]
    for row in census[census["target_date"].isin(forecast_dates)].itertuples(index=False):
        usable = usable_lookup.get(row.ward_id)
        usable_value = None if usable is None or pd.isna(usable) else float(usable)
        rate = None if not usable_value else float(row.yhat_census) / usable_value
        points.append(
            {
                "date": str(row.target_date),
                "ward_id": row.ward_id,
                "ward_name": WARD_NAMES.get(row.ward_id, row.ward_id),
                "occupied": round(float(row.yhat_census), 2),
                "usable_beds": None if usable_value is None else round(usable_value, 2),
                "occupancy_rate": None if rate is None else round(rate, 4),
                "pressure": pressure_band(rate),
                "kind": "forecast",
            }
        )
    return points


def _assert_aggregate(payload: object) -> None:
    if isinstance(payload, dict):
        banned = FORBIDDEN_KEYS.intersection(payload)
        if banned:
            raise ValueError(f"snapshot contains encounter-level keys: {sorted(banned)}")
        for value in payload.values():
            _assert_aggregate(value)
    elif isinstance(payload, list):
        for item in payload:
            _assert_aggregate(item)


def build_snapshot() -> object:
    summary = json.loads((generated_dir() / "forecast_summary.json").read_text(encoding="utf-8"))
    report = json.loads((lake_dir() / "transform_report.json").read_text(encoding="utf-8"))
    scenarios = json.loads((generated_dir() / "scenarios.json").read_text(encoding="utf-8"))
    daily = pd.read_parquet(generated_dir() / "daily_arrivals.parquet")
    serving = pd.read_parquet(generated_dir() / "serving_arrivals.parquet")
    arrivals = pd.read_parquet(generated_dir() / "arrivals_hourly.parquet")
    occupancy = pd.read_parquet(generated_dir() / "occupancy_hourly.parquet")
    census = pd.read_parquet(generated_dir() / "serving_census.parquet")

    series = []
    for service_line, part in daily.groupby("service_line"):
        points = [
            {"date": str(row.date), "actual": float(row.arrivals), "kind": "observed"}
            for row in part.sort_values("date").itertuples(index=False)
        ]
        forecast_part = serving[serving["service_line"] == service_line].sort_values("target_date")
        for row in forecast_part.itertuples(index=False):
            points.append(
                {
                    "date": str(row.target_date),
                    "forecast": float(row.yhat),
                    "lower": float(row.yhat_lower),
                    "upper": float(row.yhat_upper),
                    "baseline": float(row.baseline_yhat),
                    "kind": "forecast",
                }
            )
        series.append(
            {
                "service_line": service_line,
                "service_line_name": SERVICE_LINE_NAMES[str(service_line)],
                "points": points,
            }
        )

    capacity = _capacity(occupancy, census)
    forward = [point for point in capacity if point["kind"] == "forecast" and point["date"] <= sorted({p["date"] for p in capacity if p["kind"] == "forecast"})[6]]
    pressured = [point for point in forward if point["pressure"] in {"elevated", "over_capacity"}]
    next_7 = serving[serving["horizon_days"] <= 7]["yhat"].sum()
    hourly = _hourly(arrivals)
    next_24 = sum(point["value"] for point in hourly if point["kind"] == "forecast")
    quarantine = sum(report["quarantine_rows"].values())
    payload = {
        "schema_version": 1,
        "status": "ready",
        "notice": NOTICE,
        "as_of": HISTORY_END.isoformat(),
        "timezone": TIMEZONE,
        "facility": {"id": FACILITY_ID, "name": FACILITY_NAME},
        "freshness": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "batch_id": report["batch_id"],
            "history_start": HISTORY_START.isoformat(),
            "history_end": HISTORY_END.isoformat(),
        },
        "summary": {
            "next_7_day_arrivals": round(float(next_7), 1),
            "next_24h_arrivals_naive": round(float(next_24), 1),
            "wards_over_pressure_threshold": len({point["ward_id"] for point in pressured}),
            "selected_model": summary["selected_model"],
            "test_wape": summary["test_wape"],
            "test_mae": summary["test_mae"],
            "baseline_test_wape": summary["baseline_test_wape"],
            "baseline_test_mae": summary["baseline_test_mae"],
            "pressure_threshold": PRESSURE_THRESHOLD,
        },
        "forecasts": {
            "grain": "facility x service line x day",
            "unit": "eligible arrivals per day",
            "horizon_days": 14,
            "issue_date": HISTORY_END.isoformat(),
            "model_name": summary["selected_model"],
            "series": series,
        },
        "hourly": {
            "grain": "facility x hour",
            "unit": "eligible arrivals",
            "model_note": "Next 24 hours use a seasonal naive forecast from the same hour one week earlier.",
            "points": hourly,
        },
        "capacity": {
            "grain": "ward x day",
            "unit": "mean occupied beds and usable beds",
            "threshold": PRESSURE_THRESHOLD,
            "points": capacity,
        },
        "evaluation": summary,
        "quality": {
            "accepted": report["silver_rows"],
            "rejected": report["quarantine_rows"],
            "duplicates_removed": report["duplicates_removed"],
            "rejected_total": quarantine,
            "bronze_rows": report["bronze_rows"],
        },
        "scenarios": {
            "baseline": scenarios["baseline"],
            "grid": scenarios["grid"],
            "infeasible_example": scenarios["infeasible_example"],
        },
        "assumptions": ASSUMPTIONS,
    }
    _assert_aggregate(payload)
    destination = snapshot_path()
    destination.write_text(json.dumps(payload), encoding="utf-8")
    return destination
