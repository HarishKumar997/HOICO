import { ScenarioPlanner } from "@/components/ScenarioPlanner";
import { loadDashboard } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function ScenariosPage() {
  const data = await loadDashboard();
  if (data.status !== "ready" || !data.scenarios) {
    return <p className="empty">Scenarios appear after the pipeline writes the snapshot.</p>;
  }
  return (
    <>
      <h1>Scenario planner</h1>
      <p className="lede">
        These are simulated operational options for the next seven days. The grid is the PuLP result for the slider steps.
        Arbitrary values can be sent to the local API. Nothing here assigns a patient to a bed.
      </p>
      <section className="panel">
        <ScenarioPlanner
          baseline={data.scenarios.baseline}
          grid={data.scenarios.grid}
          infeasibleExample={data.scenarios.infeasible_example}
        />
      </section>
      <section className="panel">
        <h2>Assumptions carried with every result</h2>
        <ul className="clean">
          {data.assumptions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </>
  );
}
