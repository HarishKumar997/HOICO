"""Spark medallion: Bronze files, tested Silver rules, Gold hourly facts."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from hoico.config import CANCELLED_STATUS, FACILITY_ID, HISTORY_END, TIMEZONE
from hoico.ingest.mock_api import fetch_operational_events
from hoico.quality.prepare import (
    prepare_capacity,
    prepare_discharges,
    prepare_encounters,
    prepare_events,
    prepare_staffing,
)

logger = logging.getLogger(__name__)
LOCAL_TZ = ZoneInfo(TIMEZONE)


def as_of_epoch(history_end: datetime | None = None) -> int:
    end = HISTORY_END if history_end is None else history_end
    if isinstance(end, datetime):
        boundary = end
    else:
        boundary = datetime(end.year, end.month, end.day, tzinfo=LOCAL_TZ) + timedelta(days=1)
    return int(boundary.timestamp())


def attach_metadata(frame: pd.DataFrame, source_name: str, batch_id: str) -> pd.DataFrame:
    stamped = frame.copy()
    stamped["source_name"] = source_name
    stamped["batch_id"] = batch_id
    stamped["ingested_at_utc"] = datetime.now(ZoneInfo("UTC")).isoformat(timespec="seconds")
    stamped["source_row_number"] = range(1, len(stamped) + 1)
    return stamped


def load_raw_frames(raw_dir: Path) -> tuple[dict[str, pd.DataFrame], str]:
    batch_id = (raw_dir / "batch_id.txt").read_text(encoding="utf-8").strip()
    frames = {
        "encounters": attach_metadata(
            pd.read_csv(raw_dir / "encounters.csv", dtype=str, keep_default_na=False),
            "encounters_csv",
            batch_id,
        ),
        "bed_capacity": attach_metadata(
            pd.read_csv(raw_dir / "bed_capacity.csv", dtype=str, keep_default_na=False),
            "bed_capacity_csv",
            batch_id,
        ),
        "staffing": attach_metadata(
            pd.read_csv(raw_dir / "staffing.csv", dtype=str, keep_default_na=False),
            "staffing_csv",
            batch_id,
        ),
        "discharges": attach_metadata(
            pd.read_csv(raw_dir / "discharges.csv", dtype=str, keep_default_na=False),
            "discharges_csv",
            batch_id,
        ),
        "calendar": attach_metadata(
            pd.read_csv(raw_dir / "calendar.csv", dtype=str, keep_default_na=False),
            "calendar_csv",
            batch_id,
        ),
    }
    events = pd.DataFrame(fetch_operational_events(raw_dir / "operational_events.json"))
    frames["operational_events"] = attach_metadata(events, "operational_events_rest", batch_id)
    return frames, batch_id


def prepare_all(frames: dict[str, pd.DataFrame], batch_as_of: int) -> dict[str, object]:
    encounters = prepare_encounters(frames["encounters"], batch_as_of)
    known = set(encounters.accepted["encounter_id"].astype(str))
    capacity = prepare_capacity(frames["bed_capacity"])
    staffing = prepare_staffing(frames["staffing"])
    discharges = prepare_discharges(frames["discharges"], known)
    events = prepare_events(frames["operational_events"])
    return {
        "encounters": encounters,
        "bed_capacity": capacity,
        "staffing": staffing,
        "discharges": discharges,
        "operational_events": events,
        "calendar": frames["calendar"],
    }


def _write_both(frame: pd.DataFrame, spark_df: object, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    parquet_path = destination / "parquet"
    delta_path = destination / "delta"
    frame.to_parquet(destination / "pandas.parquet", index=False)
    spark_df.write.mode("overwrite").parquet(str(parquet_path))
    spark_df.write.format("delta").mode("overwrite").save(str(delta_path))


def build_spark():
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession

    builder = (
        SparkSession.builder.master("local[2]")
        .appName("hoico")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.driver.memory", "1g")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def run_medallion(raw_dir: Path, lake_dir: Path) -> dict[str, object]:
    """Overwrite Bronze, Silver, and Gold. A second run with the same source does not append."""
    frames, batch_id = load_raw_frames(raw_dir)
    prepared = prepare_all(frames, as_of_epoch())
    spark = build_spark()
    try:
        from pyspark.sql import functions as F

        for name, frame in frames.items():
            bronze = spark.createDataFrame(frame.astype(str))
            _write_both(frame, bronze, lake_dir / "bronze" / name)

        silver_frames = {
            "encounter": prepared["encounters"].accepted,
            "bed_capacity_hourly": prepared["bed_capacity"].accepted,
            "staffing_hourly": prepared["staffing"].accepted,
            "discharge": prepared["discharges"].accepted,
            "operational_event": prepared["operational_events"].accepted,
            "calendar_hour": prepared["calendar"],
        }
        for name, frame in silver_frames.items():
            if frame.empty:
                continue
            silver = spark.createDataFrame(frame.astype(str))
            _write_both(frame, silver, lake_dir / "silver" / name)

        quarantine_parts = []
        for dataset, table in (
            ("encounter", prepared["encounters"].quarantined),
            ("bed_capacity", prepared["bed_capacity"].quarantined),
            ("staffing", prepared["staffing"].quarantined),
            ("discharge", prepared["discharges"].quarantined),
            ("operational_event", prepared["operational_events"].quarantined),
        ):
            if table.empty:
                continue
            slim = table.copy()
            slim["dataset"] = dataset
            slim["row_payload"] = slim.apply(lambda row: json.dumps(row.to_dict(), default=str), axis=1)
            quarantine_parts.append(slim[["dataset", "reject_reason", "batch_id", "source_name", "row_payload"]])
        quarantine = (
            pd.concat(quarantine_parts, ignore_index=True)
            if quarantine_parts
            else pd.DataFrame(columns=["dataset", "reject_reason", "batch_id", "source_name", "row_payload"])
        )
        if not quarantine.empty:
            _write_both(quarantine, spark.createDataFrame(quarantine.astype(str)), lake_dir / "quarantine" / "rows")

        arrivals, occupancy = _gold_facts(spark, silver_frames, F)
        _write_both(arrivals, spark.createDataFrame(arrivals), lake_dir / "gold" / "fact_arrivals_hourly")
        _write_both(occupancy, spark.createDataFrame(occupancy), lake_dir / "gold" / "fact_occupancy_hourly")
    finally:
        spark.stop()

    report = {
        "batch_id": batch_id,
        "facility_id": FACILITY_ID,
        "bronze_rows": {name: int(len(frame)) for name, frame in frames.items()},
        "silver_rows": {
            "encounter": int(len(prepared["encounters"].accepted)),
            "bed_capacity_hourly": int(len(prepared["bed_capacity"].accepted)),
            "staffing_hourly": int(len(prepared["staffing"].accepted)),
            "discharge": int(len(prepared["discharges"].accepted)),
            "operational_event": int(len(prepared["operational_events"].accepted)),
        },
        "quarantine_rows": {
            "encounter": int(len(prepared["encounters"].quarantined)),
            "bed_capacity": int(len(prepared["bed_capacity"].quarantined)),
            "staffing": int(len(prepared["staffing"].quarantined)),
            "discharge": int(len(prepared["discharges"].quarantined)),
            "operational_event": int(len(prepared["operational_events"].quarantined)),
        },
        "duplicates_removed": {
            "encounter": int(prepared["encounters"].duplicates_removed),
            "bed_capacity": int(prepared["bed_capacity"].duplicates_removed),
            "staffing": int(prepared["staffing"].duplicates_removed),
            "discharge": int(prepared["discharges"].duplicates_removed),
            "operational_event": int(prepared["operational_events"].duplicates_removed),
        },
        "gold_rows": {
            "fact_arrivals_hourly": int(len(arrivals)),
            "fact_occupancy_hourly": int(len(occupancy)),
        },
    }
    lake_dir.mkdir(parents=True, exist_ok=True)
    (lake_dir / "transform_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("medallion complete batch %s", batch_id)
    return report


def _gold_facts(spark, silver_frames: dict[str, pd.DataFrame], functions) -> tuple[pd.DataFrame, pd.DataFrame]:
    encounters = spark.createDataFrame(silver_frames["encounter"].astype(str))
    calendar = spark.createDataFrame(silver_frames["calendar_hour"].astype(str))
    capacity = spark.createDataFrame(silver_frames["bed_capacity_hourly"].astype(str))
    eligible = encounters.filter(functions.col("encounter_status") != CANCELLED_STATUS)
    arrivals_spark = (
        eligible.groupBy("facility_id", "service_line", "arrival_hour_local")
        .agg(functions.count(functions.lit(1)).alias("arrivals"))
        .withColumn("census_date", functions.substring(functions.col("arrival_hour_local"), 1, 10))
        .withColumn("series_kind", functions.lit("observed"))
    )
    staying = eligible.filter(functions.col("first_occupied_epoch").isNotNull()).select(
        "encounter_id",
        "ward_id",
        functions.col("first_occupied_epoch").cast("long").alias("first_occupied_epoch"),
        functions.col("last_occupied_epoch").cast("long").alias("last_occupied_epoch"),
    )
    hours = calendar.select(
        functions.col("hour_start_epoch").cast("long").alias("hour_start_epoch"),
        "hour_start_local",
        functions.col("calendar_date").alias("census_date"),
    )
    occupied = (
        staying.join(
            functions.broadcast(hours),
            (hours.hour_start_epoch >= staying.first_occupied_epoch)
            & (hours.hour_start_epoch <= staying.last_occupied_epoch),
            "inner",
        )
        .groupBy("ward_id", "hour_start_local", "census_date")
        .agg(functions.countDistinct("encounter_id").alias("occupied_beds"))
    )
    supply = capacity.select(
        "facility_id",
        "ward_id",
        "hour_start_local",
        functions.substring(functions.col("hour_start_local"), 1, 10).alias("census_date"),
        functions.col("staffed_beds").cast("double").alias("staffed_beds"),
        functions.col("blocked_beds").cast("double").alias("blocked_beds"),
        functions.col("physical_beds").cast("double").alias("physical_beds"),
    )
    occupancy_spark = (
        supply.join(occupied.drop("census_date"), ["ward_id", "hour_start_local"], "left")
        .withColumn("occupied_beds", functions.coalesce(functions.col("occupied_beds").cast("double"), functions.lit(0.0)))
        .withColumn("usable_beds", functions.col("staffed_beds") - functions.col("blocked_beds"))
        .withColumn(
            "occupancy_rate",
            functions.when(
                functions.col("usable_beds") > 0,
                functions.col("occupied_beds") / functions.col("usable_beds"),
            ),
        )
        .withColumn("series_kind", functions.lit("observed"))
    )
    arrivals = arrivals_spark.toPandas().reset_index(drop=True)
    occupancy = occupancy_spark.toPandas().reset_index(drop=True)
    arrivals["arrivals"] = arrivals["arrivals"].astype(int)
    occupancy["occupied_beds"] = pd.to_numeric(occupancy["occupied_beds"], errors="coerce").fillna(0.0)
    occupancy["usable_beds"] = pd.to_numeric(occupancy["usable_beds"], errors="coerce")
    occupancy["staffed_beds"] = pd.to_numeric(occupancy["staffed_beds"], errors="coerce")
    occupancy["blocked_beds"] = pd.to_numeric(occupancy["blocked_beds"], errors="coerce")
    occupancy["occupancy_rate"] = pd.to_numeric(occupancy["occupancy_rate"], errors="coerce")
    return arrivals, occupancy
