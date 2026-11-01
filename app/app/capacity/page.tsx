import { loadDashboard } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function CapacityPage() {
  const data = await loadDashboard();
  if (data.status !== "ready" || !data.capacity) {
    return <p className="empty">Capacity appears after the pipeline writes the snapshot.</p>;
  }
  const forecast = data.capacity.points.filter((point) => point.kind === "forecast");
  const firstDate = forecast.map((point) => point.date).sort()[0];
  const day = forecast.filter((point) => point.date === firstDate);
  return (
    <>
      <h1>Capacity</h1>
      <p className="lede">
        {data.capacity.grain}. {data.capacity.unit}. Pressure starts at {data.capacity.threshold}.
        The first forecast day is {firstDate}. Observed history is included in the snapshot for comparison.
      </p>
      <section className="panel">
        <h2>Forecast census on {firstDate}</h2>
        <table>
          <thead>
            <tr>
              <th>Ward</th>
              <th>Projected occupied</th>
              <th>Usable beds</th>
              <th>Occupancy</th>
              <th>Pressure</th>
              <th>Kind</th>
            </tr>
          </thead>
          <tbody>
            {day.map((point) => (
              <tr key={point.ward_id}>
                <td>{point.ward_name}</td>
                <td>{point.occupied.toFixed(1)}</td>
                <td>{point.usable_beds === null ? "—" : point.usable_beds.toFixed(1)}</td>
                <td>{point.occupancy_rate === null ? "undefined" : `${(point.occupancy_rate * 100).toFixed(0)}%`}</td>
                <td>{point.pressure}</td>
                <td><span className="tag forecast">forecast</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
