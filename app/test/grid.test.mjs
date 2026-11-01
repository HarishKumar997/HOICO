import test from "node:test";
import assert from "node:assert/strict";
import { findScenario } from "../lib/grid.mjs";

const grid = [
  {
    scenario_name: "base",
    status: "feasible",
    parameters: { demand_uplift: 0, bed_availability: 1, extra_discharge_boost: 0 },
  },
  {
    scenario_name: "tight",
    status: "infeasible",
    parameters: { demand_uplift: 0.3, bed_availability: 0.8, extra_discharge_boost: 10 },
  },
];

test("snaps to the precomputed optimizer result", () => {
  const found = findScenario(grid, 0.3, 0.8, 10);
  assert.equal(found.scenario_name, "tight");
  assert.equal(found.status, "infeasible");
});

test("returns null when the slider is off the grid", () => {
  assert.equal(findScenario(grid, 0.15, 1, 0), null);
});
