"""API validation does not require a loaded warehouse."""

from fastapi.testclient import TestClient

from hoico.api.main import create_app
from hoico.optimization.engine import WardDay


class FakeWarehouse:
    def ping(self) -> str:
        return "ok"

    def query(self, sql: str, params=None):
        if "fact_arrivals_daily" in sql:
            return [{"service_line": "ED", "arrival_date": "2026-06-30", "arrivals": 70, "series_kind": "observed"}]
        if "forecast_arrivals" in sql:
            return [
                {
                    "service_line": "ED",
                    "target_date": "2026-07-01",
                    "horizon_days": 1,
                    "yhat": 71,
                    "yhat_lower": 60,
                    "yhat_upper": 80,
                    "baseline_yhat": 68,
                    "model_name": "seasonal_naive",
                    "series_kind": "forecast",
                }
            ]
        return []

    def ward_days(self):
        return [WardDay("ED-A", 0, "2026-07-01", 12, 10, 20, 6, 4, 2)]


def test_health_and_invalid_parameters():
    client = TestClient(create_app(FakeWarehouse()))
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    rejected = client.get("/api/forecasts", params={"service_line": "NOT_REAL", "horizon": 14})
    assert rejected.status_code == 422
    bad_horizon = client.get("/api/forecasts", params={"horizon": 0})
    assert bad_horizon.status_code == 422
    bad_scenario = client.post(
        "/api/scenarios/compare",
        json={"scenarios": [{"name": "bad", "demand_uplift": 5}]},
    )
    assert bad_scenario.status_code == 422


def test_scenario_compare_returns_baseline():
    client = TestClient(create_app(FakeWarehouse()))
    response = client.post(
        "/api/scenarios/compare",
        json={"scenarios": [{"name": "uplift", "demand_uplift": 0.1}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["baseline"]["status"] == "baseline"
    assert body["scenarios"][0]["status"] in {"feasible", "infeasible"}
    assert "reason_summary" in body["scenarios"][0]
    assert body["scenarios"][0]["assumptions"]
