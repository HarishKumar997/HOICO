"""Load Parquet facts into Postgres. A rerun replaces serving tables."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

SCHEMAS = ("ref", "silver", "spark_gold", "gold", "audit", "staging")


def database_url() -> str:
    import os

    return os.environ.get(
        "HOICO_DATABASE_URL",
        "postgresql+psycopg://hoico:hoico@localhost:5432/hoico",
    )


def ensure_schemas(engine) -> None:
    with engine.begin() as conn:
        for schema in SCHEMAS:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))


def replace_table(frame: pd.DataFrame, schema: str, name: str, engine) -> int:
    cleaned = frame.copy()
    cleaned.to_sql(
        name,
        engine,
        schema=schema,
        if_exists="replace",
        index=False,
        chunksize=500,
        method="multi",
    )
    return int(len(cleaned))


def append_run(engine, row: dict[str, object]) -> None:
    pd.DataFrame([row]).to_sql(
        "pipeline_run",
        engine,
        schema="audit",
        if_exists="append",
        index=False,
    )


def load_lake(lake_dir: Path, url: str | None = None) -> dict[str, int]:
    engine = create_engine(url or database_url())
    ensure_schemas(engine)
    report = json.loads((lake_dir / "transform_report.json").read_text(encoding="utf-8"))
    from hoico.generate.synthetic import reference_frames

    refs = reference_frames()
    counts: dict[str, int] = {}
    batches = {
        ("ref", "facility"): refs["facility"],
        ("ref", "service_line"): refs["service_line"],
        ("ref", "ward"): refs["ward"],
        ("silver", "encounter"): _read(lake_dir / "silver" / "encounter" / "pandas.parquet"),
        ("silver", "bed_capacity_hourly"): _read(lake_dir / "silver" / "bed_capacity_hourly" / "pandas.parquet"),
        ("silver", "staffing_hourly"): _read(lake_dir / "silver" / "staffing_hourly" / "pandas.parquet"),
        ("silver", "discharge"): _read(lake_dir / "silver" / "discharge" / "pandas.parquet"),
        ("silver", "operational_event"): _read(lake_dir / "silver" / "operational_event" / "pandas.parquet"),
        ("silver", "calendar_hour"): _read(lake_dir / "silver" / "calendar_hour" / "pandas.parquet"),
        ("silver", "quarantine_row"): _read(lake_dir / "quarantine" / "rows" / "pandas.parquet"),
        ("spark_gold", "fact_arrivals_hourly"): _read(lake_dir / "gold" / "fact_arrivals_hourly" / "pandas.parquet"),
        ("spark_gold", "fact_occupancy_hourly"): _read(lake_dir / "gold" / "fact_occupancy_hourly" / "pandas.parquet"),
    }
    for (schema, name), frame in batches.items():
        counts[f"{schema}.{name}"] = replace_table(frame, schema, name, engine)
    replace_table(
        pd.DataFrame(
            [
                {
                    "batch_id": report["batch_id"],
                    "loaded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "report_json": json.dumps(report),
                }
            ]
        ),
        "audit",
        "batch_manifest",
        engine,
    )
    engine.dispose()
    return counts


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)
