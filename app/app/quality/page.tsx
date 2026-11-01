import { loadDashboard } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function QualityPage() {
  const data = await loadDashboard();
  if (data.status !== "ready" || !data.quality || !data.evaluation) {
    return <p className="empty">Quality results appear after the pipeline writes the snapshot.</p>;
  }
  return (
    <>
      <h1>Data and model quality</h1>
      <p className="lede">
        Rejected rows stay in the quarantine set with a reason code. A rerun replaces the batch instead of appending it.
      </p>
      <section className="grid">
        <article className="card">
          <div className="label">Quarantined rows</div>
          <div className="value">{data.quality.rejected_total}</div>
        </article>
        <article className="card">
          <div className="label">Duplicate encounters removed</div>
          <div className="value">{data.quality.duplicates_removed.encounter ?? 0}</div>
        </article>
        <article className="card">
          <div className="label">Accepted encounters</div>
          <div className="value">{data.quality.accepted.encounter ?? 0}</div>
        </article>
        <article className="card">
          <div className="label">Batch</div>
          <div className="value" style={{ fontSize: "1rem" }}>{data.freshness?.batch_id}</div>
        </article>
      </section>
      <section className="panel">
        <h2>Validation WAPE by model</h2>
        <table>
          <thead>
            <tr><th>Model</th><th>Validation WAPE</th><th>Role</th></tr>
          </thead>
          <tbody>
            {Object.entries(data.evaluation.validation_wape).map(([model, value]) => (
              <tr key={model}>
                <td>{model}</td>
                <td>{value === null ? "null" : value.toFixed(4)}</td>
                <td>{model === data.evaluation?.selected_model ? "selected" : "compared"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h2>Quarantine counts</h2>
        <table>
          <thead><tr><th>Dataset</th><th>Rejected</th></tr></thead>
          <tbody>
            {Object.entries(data.quality.rejected).map(([name, count]) => (
              <tr key={name}><td>{name}</td><td>{count}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
