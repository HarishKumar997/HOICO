"""Stage runner used by the CLI and the Airflow DAG."""

from __future__ import annotations

import json
import logging
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from hoico.config import FACILITY_ID, HISTORY_START, WARDS
from hoico.forecasting.engine import run_forecast, write_evaluation_report
from hoico.generate.synthetic import generate, write_bundle
from hoico.optimization.engine import ScenarioParams, WardDay, baseline_params, grid_params, solve_scenario
from hoico.paths import docs_dir, generated_dir, lake_dir, raw_dir, repo_root, sample_dir
from hoico.publishing.snapshot import build_snapshot
from hoico.transforms.medallion import run_medallion
from hoico.warehouse.load import append_run, database_url, ensure_schemas, load_lake, replace_table

logger = logging.getLogger(__name__)


def _time(stage: str, fn):
    started = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - started
    logger.info("stage %s finished in %.1f seconds", stage, elapsed)
    return result, elapsed


def stage_generate() -> str:
    bundle = generate()
    batch_id = write_bundle(bundle, raw_dir())
    sample_end = HISTORY_START + timedelta(days=13)
    sample = generate(start=HISTORY_START, end=sample_end)
    write_bundle(sample, sample_dir())
    logger.info("generated batch %s", batch_id)
    return batch_id


def stage_transform() -> dict:
    return run_medallion(raw_dir(), lake_dir())


def stage_load() -> dict[str, int]:
    return load_lake(lake_dir(), database_url())


def stage_dbt() -> None:
    project = repo_root() / "transformations" / "dbt"
    env = os.environ.copy()
    command = [
        sys.executable,
        "-m",
        "dbt.cli.main",
        "build",
        "--project-dir",
        str(project),
        "--profiles-dir",
        str(project),
    ]
    completed = subprocess.run(command, check=False, env=env)
    if completed.returncode != 0:
        raise RuntimeError("dbt build failed")


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root = lake_dir()
    arrivals = pd.read_parquet(root / "gold" / "fact_arrivals_hourly" / "pandas.parquet")
    occupancy = pd.read_parquet(root / "gold" / "fact_occupancy_hourly" / "pandas.parquet")
    encounters = pd.read_parquet(root / "silver" / "encounter" / "pandas.parquet")
    staffing = pd.read_parquet(root / "silver" / "staffing_hourly" / "pandas.parquet")
    return arrivals, encounters, staffing, occupancy


def stage_forecast() -> dict:
    arrivals, encounters, _staffing, occupancy = _load_inputs()
    result = run_forecast(arrivals, encounters)
    write_evaluation_report(result, docs_dir() / "evaluation-report.md")
    engine = create_engine(database_url())
    replace_table(pd.DataFrame(result["evaluation_rows"]), "gold", "model_evaluation", engine)
    replace_table(result["serving_arrivals"], "gold", "forecast_arrivals", engine)
    census = result["serving_census"].copy()
    census["facility_id"] = FACILITY_ID
    census["model_name"] = result["selected_model"]
    census["series_kind"] = "forecast"
    replace_table(census, "gold", "forecast_occupancy", engine)
    summary = {
        key: result[key]
        for key in (
            "selected_model",
            "model_version",
            "feature_version",
            "validation_wape",
            "test_wape",
            "test_mae",
            "baseline_test_wape",
            "baseline_test_mae",
            "interval_coverage",
            "residual_quantile_10",
            "residual_quantile_90",
            "windows",
            "los_days",
        )
    }
    (generated_dir() / "forecast_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    _chart_frames(result, arrivals, occupancy)
    engine.dispose()
    return summary


def _chart_frames(result: dict, arrivals: pd.DataFrame, occupancy: pd.DataFrame) -> None:
    daily = result["daily"].copy()
    daily["date"] = daily["date"].astype(str)
    daily.to_parquet(generated_dir() / "daily_arrivals.parquet", index=False)
    result["serving_arrivals"].to_parquet(generated_dir() / "serving_arrivals.parquet", index=False)
    result["serving_census"].to_parquet(generated_dir() / "serving_census.parquet", index=False)
    occupancy.to_parquet(generated_dir() / "occupancy_hourly.parquet", index=False)
    arrivals.to_parquet(generated_dir() / "arrivals_hourly.parquet", index=False)


def _ward_days(staffing: pd.DataFrame) -> list[WardDay]:
    census = pd.read_parquet(generated_dir() / "serving_census.parquet")
    dates = sorted(census["target_date"].unique())[:7]
    staffing = staffing.copy()
    staffing["available_staff"] = pd.to_numeric(staffing["available_staff"], errors="coerce")
    nurses = staffing[staffing["role_group"].astype(str) == "rn"]
    means = nurses.groupby("unit_id")["available_staff"].mean().to_dict()
    days: list[WardDay] = []
    for ward in WARDS:
        for index, service_date in enumerate(dates):
            match = census[(census["ward_id"] == ward.ward_id) & (census["target_date"] == service_date)]
            projected = float(match["yhat_census"].iloc[0]) if not match.empty else 0.0
            days.append(
                WardDay(
                    ward_id=ward.ward_id,
                    day_index=index,
                    service_date=str(service_date),
                    projected_census=projected,
                    staffed_beds=ward.staffed_beds,
                    physical_beds=ward.physical_beds,
                    available_rn=float(means.get(ward.ward_id, 1.0)),
                    patients_per_rn=ward.patients_per_rn,
                    max_extra_discharges=2,
                )
            )
    return days


def stage_scenarios() -> dict:
    _, _, staffing, _ = _load_inputs()
    days = _ward_days(staffing)
    context = pd.DataFrame([day.__dict__ for day in days])
    baseline = solve_scenario(days, baseline_params())
    grid = [solve_scenario(days, params) for params in grid_params()]
    infeasible = solve_scenario(
        [
            WardDay(
                ward_id="ED-A",
                day_index=0,
                service_date="2026-07-01",
                projected_census=40,
                staffed_beds=10,
                physical_beds=10,
                available_rn=2,
                patients_per_rn=4,
                max_extra_discharges=0,
            )
        ],
        ScenarioParams(name="infeasible_example", demand_uplift=0.5, bed_availability=1.0),
    )
    engine = create_engine(database_url())
    replace_table(context, "gold", "ward_day_input", engine)
    stored = []
    for scenario in [baseline, *grid, infeasible]:
        stored.append(
            {
                "scenario_name": scenario["scenario_name"],
                "status": scenario["status"],
                "objective": scenario["objective"],
                "unmet_bed_days": scenario["unmet_bed_days"],
                "extra_beds": scenario["extra_beds"],
                "overtime_hours": scenario["overtime_hours"],
                "extra_discharges": scenario["extra_discharges"],
                "reason_summary": scenario["reason_summary"],
                "parameters_json": json.dumps(scenario["parameters"]),
                "assumptions_json": json.dumps(scenario["assumptions"]),
                "decisions_json": json.dumps(scenario["decisions"]),
                "constraint_status_json": json.dumps(scenario["constraint_status"]),
                "is_baseline": scenario["scenario_name"] == "baseline_do_nothing",
                "is_infeasible_example": scenario["scenario_name"] == "infeasible_example",
            }
        )
    replace_table(pd.DataFrame(stored), "gold", "scenario_results", engine)
    engine.dispose()
    payload = {"baseline": baseline, "grid": grid, "infeasible_example": infeasible}
    (generated_dir() / "scenarios.json").write_text(json.dumps(payload), encoding="utf-8")
    return {"baseline_status": baseline["status"], "grid": len(grid), "infeasible_status": infeasible["status"]}


def stage_snapshot() -> Path:
    return build_snapshot()


def run_all() -> dict[str, float]:
    timings: dict[str, float] = {}
    report: dict = {}
    started = datetime.now(timezone.utc)
    stages = [
        ("generate", stage_generate),
        ("transform", stage_transform),
        ("load", stage_load),
        ("dbt", stage_dbt),
        ("forecast", stage_forecast),
        ("scenarios", stage_scenarios),
        ("snapshot", stage_snapshot),
    ]
    try:
        for name, fn in stages:
            result, elapsed = _time(name, fn)
            timings[name] = elapsed
            if name == "transform":
                report = result
    except Exception as exc:
        _record("failed", started, timings, str(exc))
        raise
    _record("succeeded", started, timings, "")
    write_benchmark(timings, report)
    return timings


def _record(status: str, started: datetime, timings: dict[str, float], error: str) -> None:
    try:
        engine = create_engine(database_url())
        ensure_schemas(engine)
        append_run(
            engine,
            {
                "status": status,
                "started_at_utc": started.isoformat(timespec="seconds"),
                "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "timings_json": json.dumps(timings),
                "error": error,
                "host": platform.platform(),
            },
        )
        engine.dispose()
    except Exception:
        logger.warning("could not write the pipeline audit row", exc_info=True)


def write_benchmark(timings: dict[str, float], report: dict) -> None:
    (docs_dir() / "benchmark.md").write_text(benchmark_lines(timings, report), encoding="utf-8")


def benchmark_lines(timings: dict[str, float], report: dict) -> str:
    rows = "\n".join(f"- {name}: {elapsed:.1f} seconds" for name, elapsed in timings.items())
    return "\n".join(
        [
            "# Local benchmark",
            "",
            "Measured by `python -m hoico.cli run-all` on the machine that produced this file.",
            f"Platform: {platform.platform()}",
            f"Python: {platform.python_version()}",
            f"CPUs visible to Python: {os.cpu_count()}",
            "",
            "## Stage runtime",
            "",
            rows,
            "",
            "## Rows",
            "",
            "```json",
            json.dumps({k: report.get(k) for k in ("bronze_rows", "silver_rows", "quarantine_rows", "duplicates_removed", "gold_rows")}, indent=2),
            "```",
            "",
            "This is one synthetic community hospital, about four months of hourly history.",
            "It is not a multi-hospital or production-scale benchmark.",
            "",
        ]
    )
