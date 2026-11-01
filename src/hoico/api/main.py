"""Read-only planning API. Scenario comparison is the only write-shaped route, and it does not persist."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from hoico.config import DEFAULT_WEIGHTS, NOTICE, SERVICE_LINE_IDS
from hoico.optimization.engine import ScenarioParams, WardDay, baseline_params, solve_scenario
from hoico.warehouse.load import database_url


class ScenarioIn(BaseModel):
    name: str = "custom"
    demand_uplift: float = 0.0
    bed_availability: float = 1.0
    staffing_availability: float = 1.0
    extra_discharge_boost: int = 0
    weights: dict[str, float] | None = None


class CompareIn(BaseModel):
    scenarios: list[ScenarioIn] = Field(default_factory=list)


class Warehouse:
    def __init__(self, url: str | None = None) -> None:
        self.engine = create_engine(url or database_url())

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            frame = pd.read_sql(text(sql), self.engine, params=params or {})
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="Warehouse is not ready. Run the pipeline first.") from exc
        return json_ready(frame)

    def ping(self) -> str:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return "ok"
        except SQLAlchemyError:
            return "unavailable"

    def ward_days(self) -> list[WardDay]:
        rows = self.query(
            """
            SELECT ward_id, day_index, service_date, projected_census, staffed_beds,
                   physical_beds, available_rn, patients_per_rn, max_extra_discharges
            FROM gold.ward_day_input
            """
        )
        if not rows:
            raise HTTPException(status_code=503, detail="Scenario context is empty. Run the pipeline first.")
        return [
            WardDay(
                ward_id=str(row["ward_id"]),
                day_index=int(row["day_index"]),
                service_date=str(row["service_date"])[:10],
                projected_census=float(row["projected_census"]),
                staffed_beds=int(row["staffed_beds"]),
                physical_beds=int(row["physical_beds"]),
                available_rn=float(row["available_rn"]),
                patients_per_rn=float(row["patients_per_rn"]),
                max_extra_discharges=int(row["max_extra_discharges"]),
            )
            for row in rows
        ]


def json_ready(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    copied = frame.copy()
    for column in copied.columns:
        if pd.api.types.is_datetime64_any_dtype(copied[column]):
            copied[column] = copied[column].astype(str)
    return json_clean(copied.to_dict(orient="records"))


def json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_clean(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if pd.isna(value):
            return None
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value if not hasattr(value, "item") else value.item()


def create_app(warehouse: Warehouse | None = None) -> FastAPI:
    app = FastAPI(
        title="HOICO",
        version="1.0.0",
        description=NOTICE,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    store = warehouse or Warehouse()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "database": store.ping(), "notice": NOTICE}

    @app.get("/api/summary")
    def summary(as_of: date | None = None) -> dict[str, Any]:
        arrivals = store.query(
            """
            SELECT service_line, arrival_date, arrivals
            FROM gold.fact_arrivals_daily
            ORDER BY arrival_date, service_line
            """
        )
        forecast = store.query(
            """
            SELECT service_line, target_date, horizon_days, yhat, model_name
            FROM gold.forecast_arrivals
            WHERE horizon_days <= 7
            """
        )
        return {"as_of": None if as_of is None else as_of.isoformat(), "recent_arrivals": arrivals[-42:], "next_7_day_forecast": forecast}

    @app.get("/api/forecasts")
    def forecasts(
        service_line: str | None = None,
        horizon: int = Query(default=14, ge=1, le=14),
    ) -> dict[str, Any]:
        if service_line is not None and service_line not in SERVICE_LINE_IDS:
            raise HTTPException(status_code=422, detail=f"service_line must be one of {', '.join(SERVICE_LINE_IDS)}")
        sql = """
            SELECT issue_date, target_date, facility_id, service_line, horizon_days,
                   yhat, yhat_lower, yhat_upper, baseline_yhat, model_name, model_version, series_kind
            FROM gold.forecast_arrivals
            WHERE horizon_days <= :horizon
        """
        params: dict[str, Any] = {"horizon": horizon}
        if service_line:
            sql += " AND service_line = :service_line"
            params["service_line"] = service_line
        sql += " ORDER BY service_line, target_date"
        return {"horizon": horizon, "unit": "eligible arrivals per day", "series_kind": "forecast", "rows": store.query(sql, params)}

    @app.get("/api/capacity")
    def capacity(
        facility_id: str = "F001",
        date_from: date | None = Query(default=None, alias="from"),
        date_to: date | None = Query(default=None, alias="to"),
    ) -> dict[str, Any]:
        sql = """
            SELECT ward_id, census_date, occupied_beds, usable_beds, occupancy_rate, pressure_band, series_kind
            FROM gold.fact_capacity_pressure
            WHERE facility_id = :facility_id
        """
        params: dict[str, Any] = {"facility_id": facility_id}
        if date_from:
            sql += " AND census_date >= :date_from"
            params["date_from"] = date_from
        if date_to:
            sql += " AND census_date <= :date_to"
            params["date_to"] = date_to
        sql += " ORDER BY census_date, ward_id"
        return {"facility_id": facility_id, "unit": "mean occupied beds / usable beds", "rows": store.query(sql, params)}

    @app.post("/api/scenarios/compare")
    def compare(body: CompareIn) -> dict[str, Any]:
        days = store.ward_days()
        try:
            baseline = solve_scenario(days, baseline_params())
            scenarios = []
            for item in body.scenarios:
                scenarios.append(
                    solve_scenario(
                        days,
                        ScenarioParams(
                            name=item.name,
                            demand_uplift=item.demand_uplift,
                            bed_availability=item.bed_availability,
                            staffing_availability=item.staffing_availability,
                            extra_discharge_boost=item.extra_discharge_boost,
                            weights=item.weights or dict(DEFAULT_WEIGHTS),
                        ),
                    )
                )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"baseline": baseline, "scenarios": scenarios, "notice": NOTICE}

    @app.get("/api/quality/latest")
    def quality() -> dict[str, Any]:
        reasons = store.query(
            """
            SELECT dataset, reject_reason, rejected_rows
            FROM gold.data_quality_results
            ORDER BY rejected_rows DESC
            """
        )
        runs = store.query(
            """
            SELECT status, started_at_utc, finished_at_utc, error
            FROM audit.pipeline_run
            ORDER BY started_at_utc DESC
            LIMIT 10
            """
        )
        return {"reject_reasons": reasons, "pipeline_runs": runs}

    @app.get("/api/model-evaluation")
    def model_evaluation() -> dict[str, Any]:
        rows = store.query(
            """
            SELECT model_name, split_name, service_line, horizon_days, mae, wape, n_points,
                   window_start, window_end, selected, model_version, feature_version, issue_date
            FROM gold.model_evaluation
            ORDER BY split_name, model_name, service_line, horizon_days
            """
        )
        return {"rows": rows, "note": "Test metrics were scored after model selection. They describe synthetic data only."}

    return app


app = create_app()
