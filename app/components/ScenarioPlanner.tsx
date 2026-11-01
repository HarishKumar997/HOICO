"use client";

import { useMemo, useState } from "react";

import { findScenario } from "@/lib/grid.mjs";
import type { Scenario } from "@/lib/types";

const uplifts = [-0.2, -0.1, 0, 0.1, 0.2, 0.3];
const beds = [0.8, 0.9, 1];
const discharges = [0, 5, 10];

export function ScenarioPlanner({
  baseline,
  grid,
  infeasibleExample,
}: {
  baseline: Scenario;
  grid: Scenario[];
  infeasibleExample: Scenario;
}) {
  const [uplift, setUplift] = useState(0);
  const [bedAvailability, setBedAvailability] = useState(1);
  const [dischargeBoost, setDischargeBoost] = useState(0);
  const [showInfeasible, setShowInfeasible] = useState(false);
  const [live, setLive] = useState<string>("");

  const selected = useMemo(
    () => findScenario(grid, uplift, bedAvailability, dischargeBoost) as Scenario | null,
    [grid, uplift, bedAvailability, dischargeBoost],
  );
  const active = showInfeasible ? infeasibleExample : selected;

  async function runLive() {
    setLive("Contacting the local API…");
    try {
      const response = await fetch("/api/proxy/scenarios", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenarios: [
            {
              name: "console",
              demand_uplift: uplift,
              bed_availability: bedAvailability,
              extra_discharge_boost: dischargeBoost,
            },
          ],
        }),
      });
      const body = await response.json();
      if (!response.ok) {
        setLive(body.detail || "The API rejected this case.");
        return;
      }
      const scenario = body.scenarios[0];
      setLive(`${scenario.status}. ${scenario.reason_summary}`);
    } catch {
      setLive("The local API is not reachable. The grid result above is still the precomputed optimizer output.");
    }
  }

  return (
    <div>
      <div className="controls">
        <label>
          Demand change
          <select value={uplift} onChange={(event) => { setShowInfeasible(false); setUplift(Number(event.target.value)); }}>
            {uplifts.map((value) => (
              <option key={value} value={value}>{value >= 0 ? "+" : ""}{Math.round(value * 100)}%</option>
            ))}
          </select>
        </label>
        <label>
          Bed availability
          <select value={bedAvailability} onChange={(event) => { setShowInfeasible(false); setBedAvailability(Number(event.target.value)); }}>
            {beds.map((value) => (
              <option key={value} value={value}>{Math.round(value * 100)}%</option>
            ))}
          </select>
        </label>
        <label>
          Extra discharge slots
          <select value={dischargeBoost} onChange={(event) => { setShowInfeasible(false); setDischargeBoost(Number(event.target.value)); }}>
            {discharges.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <button type="button" className="secondary" onClick={() => setShowInfeasible(true)}>
          Show an infeasible input
        </button>
        <button type="button" onClick={runLive}>
          Compare on the local API
        </button>
      </div>
      <div className="grid" style={{ marginTop: "1rem" }}>
        <Result title="Baseline, do nothing" scenario={baseline} />
        <Result title={showInfeasible ? "Infeasible example" : "Selected scenario"} scenario={active} />
      </div>
      {live ? <p>{live}</p> : null}
      {active ? (
        <div className="panel">
          <h2>Ward-day decisions</h2>
          <p className="meta">Simulated planning actions. Not a staffing order.</p>
          <table>
            <thead>
              <tr>
                <th>Ward</th>
                <th>Date</th>
                <th>Projected census</th>
                <th>Extra beds</th>
                <th>Overtime hours</th>
                <th>Extra discharges</th>
                <th>Unmet bed-days</th>
              </tr>
            </thead>
            <tbody>
              {active.decisions.slice(0, 16).map((row) => (
                <tr key={`${row.ward_id}-${row.service_date}`}>
                  <td>{row.ward_id}</td>
                  <td>{row.service_date}</td>
                  <td>{row.projected_census}</td>
                  <td>{row.extra_beds}</td>
                  <td>{row.overtime_hours}</td>
                  <td>{row.extra_discharges}</td>
                  <td>{row.unmet_bed_days}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty">That combination is not on the precomputed grid.</p>
      )}
    </div>
  );
}

function Result({ title, scenario }: { title: string; scenario: Scenario | null }) {
  if (!scenario) {
    return (
      <article className="card">
        <div className="label">{title}</div>
        <p>No precomputed result.</p>
      </article>
    );
  }
  return (
    <article className="card">
      <div className="label">{title}</div>
      <p><span className={`tag ${scenario.status}`}>{scenario.status}</span></p>
      <p>{scenario.reason_summary}</p>
      <p className="meta">Objective proxy {scenario.objective}. Unmet bed-days {scenario.unmet_bed_days}.</p>
    </article>
  );
}
