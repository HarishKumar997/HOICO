import { LinePanel } from "@/components/LinePanel";
import { loadDashboard } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const data = await loadDashboard();
  if (data.status !== "ready" || !data.summary || !data.hourly) {
    return (
      <>
        <h1>Overview</h1>
        <p className="empty">The snapshot has not been generated. Run the pipeline, then refresh this page.</p>
      </>
    );
  }
  const rows = data.hourly.points.map((point) => ({
    label: point.hour.slice(5, 13),
    observed: point.kind === "observed" ? point.value : null,
    forecast: point.kind === "forecast" ? point.value : null,
  }));
  return (
    <>
      <h1>{data.facility.name}</h1>
      <p className="lede">
        As of {data.as_of}, {data.timezone}. Grain: {data.hourly.grain}. Batch {data.freshness?.batch_id}.
      </p>
      <section className="grid">
        <article className="card">
          <div className="label">Next 7 days, arrivals</div>
          <div className="value">{data.summary.next_7_day_arrivals.toFixed(0)}</div>
          <span className="tag forecast">forecast</span>
        </article>
        <article className="card">
          <div className="label">Next 24 hours</div>
          <div className="value">{data.summary.next_24h_arrivals_naive.toFixed(0)}</div>
          <span className="tag forecast">seasonal naive</span>
        </article>
        <article className="card">
          <div className="label">Wards under pressure</div>
          <div className="value">{data.summary.wards_over_pressure_threshold}</div>
          <span className="tag simulated">threshold {data.summary.pressure_threshold}</span>
        </article>
        <article className="card">
          <div className="label">Selected model test WAPE</div>
          <div className="value">{data.summary.test_wape === null ? "—" : data.summary.test_wape.toFixed(3)}</div>
          <span className="tag observed">{data.summary.selected_model}</span>
        </article>
      </section>
      <section className="panel">
        <h2>Facility arrivals, last 48 hours and next 24</h2>
        <p className="meta">{data.hourly.model_note} Unit: {data.hourly.unit}.</p>
        <LinePanel
          rows={rows}
          unit={data.hourly.unit}
          lines={[
            { key: "observed", name: "Observed", color: "#0f5f5c" },
            { key: "forecast", name: "Forecast", color: "#1e4d7b" },
          ]}
        />
      </section>
    </>
  );
}
