import { ForecastChart } from "@/components/ForecastChart";
import { loadDashboard } from "@/lib/data";

export const dynamic = "force-dynamic";

export default async function ForecastPage() {
  const data = await loadDashboard();
  if (data.status !== "ready" || !data.forecasts || !data.evaluation) {
    return <p className="empty">Forecasts appear after the pipeline writes the snapshot.</p>;
  }
  const coverage = data.evaluation.interval_coverage;
  return (
    <>
      <h1>Demand forecast</h1>
      <p className="lede">
        {data.forecasts.grain}. Horizon {data.forecasts.horizon_days} days issued {data.forecasts.issue_date}.
        Model {data.forecasts.model_name}. Values are {data.forecasts.unit}.
      </p>
      <section className="panel">
        <ForecastChart series={data.forecasts.series} unit={data.forecasts.unit} />
      </section>
      <section className="panel">
        <h2>Holdout</h2>
        <p>
          Validation chose the model. The test window {data.evaluation.windows.test[0]} to {data.evaluation.windows.test[data.evaluation.windows.test.length - 1]} was scored after that choice.
          Selected test WAPE {fmt(data.evaluation.test_wape)}. Seasonal-naive test WAPE {fmt(data.evaluation.baseline_test_wape)}.
          Residual band coverage {coverage === null ? "not computed" : `${(coverage * 100).toFixed(1)}%`}.
        </p>
      </section>
    </>
  );
}

function fmt(value: number | null) {
  return value === null ? "null" : value.toFixed(3);
}
