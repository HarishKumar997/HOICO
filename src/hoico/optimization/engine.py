"""Constrained 7-day ward plan. Costs are proxies, not invoices or clinical priorities."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pulp

from hoico.config import ASSUMPTIONS, DEFAULT_WEIGHTS

SHIFT_HOURS = 12.0
UNMET_TOLERANCE = 0.05


@dataclass(frozen=True)
class WardDay:
    ward_id: str
    day_index: int
    service_date: str
    projected_census: float
    staffed_beds: int
    physical_beds: int
    available_rn: float
    patients_per_rn: float
    max_extra_discharges: int = 2


@dataclass(frozen=True)
class ScenarioParams:
    name: str
    demand_uplift: float = 0.0
    bed_availability: float = 1.0
    staffing_availability: float = 1.0
    extra_discharge_boost: int = 0
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    force_do_nothing: bool = False


def _validate(params: ScenarioParams) -> None:
    if params.demand_uplift < -0.9 or params.demand_uplift > 2:
        raise ValueError("demand_uplift must be between -0.9 and 2")
    if params.bed_availability <= 0 or params.bed_availability > 1.5:
        raise ValueError("bed_availability must be greater than 0 and at most 1.5")
    if params.staffing_availability <= 0 or params.staffing_availability > 1.5:
        raise ValueError("staffing_availability must be greater than 0 and at most 1.5")
    if params.extra_discharge_boost < 0:
        raise ValueError("extra_discharge_boost cannot be negative")
    for key, value in params.weights.items():
        if value < 0:
            raise ValueError(f"weight {key} cannot be negative")
    missing = [key for key in DEFAULT_WEIGHTS if key not in params.weights]
    if missing:
        raise ValueError(f"weights missing {', '.join(missing)}")


def solve_scenario(days: list[WardDay], params: ScenarioParams) -> dict[str, object]:
    _validate(params)
    problem = pulp.LpProblem(f"hoico_{params.name}", pulp.LpMinimize)
    extra: dict[tuple[str, int], pulp.LpVariable] = {}
    overtime: dict[tuple[str, int], pulp.LpVariable] = {}
    discharges: dict[tuple[str, int], pulp.LpVariable] = {}
    served: dict[tuple[str, int], pulp.LpVariable] = {}
    unmet: dict[tuple[str, int], pulp.LpVariable] = {}
    projected_by_key: dict[tuple[str, int], float] = {}
    staffed_by_key: dict[tuple[str, int], int] = {}

    for item in days:
        key = (item.ward_id, item.day_index)
        max_usable = int(math.floor(item.physical_beds * params.bed_availability))
        staffed = min(int(item.staffed_beds), max_usable)
        max_extra = max(0, max_usable - staffed)
        max_discharges = int(item.max_extra_discharges) + int(params.extra_discharge_boost)
        projected = max(0.0, float(item.projected_census) * (1.0 + params.demand_uplift))
        if params.force_do_nothing:
            max_extra = 0
            max_discharges = 0
        token = f"{id(problem)}_{item.ward_id}_{item.day_index}".replace("-", "_")
        extra[key] = pulp.LpVariable(f"extra_{token}", 0, max_extra, pulp.LpInteger)
        overtime[key] = pulp.LpVariable(
            f"ot_{token}",
            0,
            0 if params.force_do_nothing else 12,
        )
        discharges[key] = pulp.LpVariable(
            f"dc_{token}",
            0,
            max_discharges,
            pulp.LpInteger,
        )
        served[key] = pulp.LpVariable(f"served_{token}", 0)
        unmet[key] = pulp.LpVariable(f"unmet_{token}", 0)
        projected_by_key[key] = projected
        staffed_by_key[key] = staffed
        problem += served[key] + unmet[key] + discharges[key] == projected
        problem += served[key] <= staffed + extra[key]
        rn_on_shift = item.available_rn * params.staffing_availability
        problem += served[key] <= (rn_on_shift + overtime[key] * (1.0 / SHIFT_HOURS)) * item.patients_per_rn
        problem += extra[key] <= max_extra

    problem += pulp.lpSum(
        params.weights["unmet_bed_days"] * unmet[key]
        + params.weights["overtime_hour"] * overtime[key]
        + params.weights["temporary_bed_day"] * extra[key]
        + params.weights["disruption_discharge"] * discharges[key]
        for key in extra
    )
    status_code = problem.solve(pulp.PULP_CBC_CMD(msg=False, threads=1, timeLimit=30))
    status_name = pulp.LpStatus.get(status_code, "Unknown")
    decisions = []
    unmet_total = 0.0
    extra_total = 0.0
    overtime_total = 0.0
    discharge_total = 0.0
    for item in days:
        key = (item.ward_id, item.day_index)
        unmet_value = float(pulp.value(unmet[key]) or 0.0)
        extra_value = float(pulp.value(extra[key]) or 0.0)
        overtime_value = float(pulp.value(overtime[key]) or 0.0)
        discharge_value = float(pulp.value(discharges[key]) or 0.0)
        served_value = float(pulp.value(served[key]) or 0.0)
        unmet_total += unmet_value
        extra_total += extra_value
        overtime_total += overtime_value
        discharge_total += discharge_value
        max_usable = int(math.floor(item.physical_beds * params.bed_availability))
        decisions.append(
            {
                "ward_id": item.ward_id,
                "service_date": item.service_date,
                "projected_census": round(projected_by_key[key], 3),
                "staffed_beds": staffed_by_key[key],
                "max_usable_beds": max_usable,
                "extra_beds": round(extra_value, 3),
                "overtime_hours": round(overtime_value, 3),
                "extra_discharges": round(discharge_value, 3),
                "served_census": round(served_value, 3),
                "unmet_bed_days": round(unmet_value, 3),
            }
        )
    if status_name != "Optimal":
        label = "solver_failed"
    elif params.force_do_nothing:
        label = "baseline"
    elif unmet_total > UNMET_TOLERANCE:
        label = "infeasible"
    else:
        label = "feasible"
    objective = float(pulp.value(problem.objective) or 0.0)
    reason = (
        f"{params.name} is {label}. "
        f"Open {extra_total:.1f} temporary bed-days, schedule {overtime_total:.1f} overtime hours, "
        f"and add {discharge_total:.1f} discharge slots. "
        f"Unmet bed-days are {unmet_total:.1f}. "
        f"Weights are unmet {params.weights['unmet_bed_days']}, "
        f"overtime {params.weights['overtime_hour']}, "
        f"temporary beds {params.weights['temporary_bed_day']}, "
        f"disruption {params.weights['disruption_discharge']}."
    )
    return {
        "scenario_name": params.name,
        "status": label,
        "solver_status": status_name,
        "objective": round(objective, 6),
        "unmet_bed_days": round(unmet_total, 4),
        "extra_beds": round(extra_total, 4),
        "overtime_hours": round(overtime_total, 4),
        "extra_discharges": round(discharge_total, 4),
        "parameters": {
            "demand_uplift": params.demand_uplift,
            "bed_availability": params.bed_availability,
            "staffing_availability": params.staffing_availability,
            "extra_discharge_boost": params.extra_discharge_boost,
            "weights": params.weights,
            "force_do_nothing": params.force_do_nothing,
        },
        "assumptions": list(ASSUMPTIONS),
        "constraint_status": {
            "beds_within_physical": all(
                row["staffed_beds"] + row["extra_beds"] <= row["max_usable_beds"] + 1e-6 for row in decisions
            ),
            "decisions_non_negative": all(
                row["extra_beds"] >= -1e-6 and row["overtime_hours"] >= -1e-6 and row["extra_discharges"] >= -1e-6
                for row in decisions
            ),
            "unmet_within_tolerance": unmet_total <= UNMET_TOLERANCE,
        },
        "reason_summary": reason,
        "decisions": decisions,
    }


def baseline_params() -> ScenarioParams:
    return ScenarioParams(name="baseline_do_nothing", force_do_nothing=True)


def grid_params() -> list[ScenarioParams]:
    scenarios = []
    for uplift in (-0.2, -0.1, 0.0, 0.1, 0.2, 0.3):
        for availability in (0.8, 0.9, 1.0):
            for boost in (0, 5, 10):
                scenarios.append(
                    ScenarioParams(
                        name=f"uplift_{uplift:+.0%}_beds_{availability:.0%}_discharges_{boost}",
                        demand_uplift=uplift,
                        bed_availability=availability,
                        extra_discharge_boost=boost,
                    )
                )
    return scenarios
