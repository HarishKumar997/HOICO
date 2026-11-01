export default function AboutPage() {
  return (
    <>
      <h1>About this project</h1>
      <p className="lede">
        HOICO is a portfolio system for hospital operations planning. It forecasts demand, shows where staffed beds may be tight, and compares feasible operational scenarios. It does not diagnose, triage, or recommend treatment.
      </p>
      <section className="panel">
        <h2>What is implemented</h2>
        <ul className="clean">
          <li>Deterministic synthetic data, CSV ingestion, and a small local REST feed for operational events.</li>
          <li>PySpark Bronze, Silver, and Gold files in Parquet and Delta, with quarantine reason codes and deduplication.</li>
          <li>PostgreSQL serving tables and dbt models for daily arrivals, pressure bands, and quality counts.</li>
          <li>Seasonal naive, Holt-Winters, and LightGBM compared on a chronological holdout, tracked in MLflow.</li>
          <li>A PuLP/CBC scenario model with explicit constraints, a do-nothing baseline, and infeasible cases.</li>
          <li>FastAPI, this console, an Airflow DAG, pytest, and GitHub Actions.</li>
          <li>A Databricks Free Edition bundle and a Vercel Hobby configuration. Both are optional and use only synthetic aggregates.</li>
        </ul>
      </section>
      <section className="panel">
        <h2>What this is not</h2>
        <ul className="clean">
          <li>Not clinically validated, not regulatory software, and not integrated with an EHR.</li>
          <li>Not evidence that a real hospital would see these error rates or this occupancy.</li>
          <li>Not a Databricks commercial trial and not a paid database. Those paths can bill a cloud account, so they are omitted.</li>
          <li>Kafka, geospatial catchment analysis, and Terraform are out of scope.</li>
        </ul>
      </section>
      <section className="panel">
        <h2>How to read a number</h2>
        <p>
          Charts label observed, forecast, and simulated values. Occupancy is occupied beds divided by usable beds. Usable beds are staffed beds minus blocked beds. A zero usable-bed count leaves occupancy undefined. Scenario costs are weights you can read on the result, not invoices.
        </p>
      </section>
    </>
  );
}
