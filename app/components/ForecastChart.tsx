"use client";

import { useMemo, useState } from "react";

import { LinePanel } from "@/components/LinePanel";
import type { Series } from "@/lib/types";

export function ForecastChart({ series, unit }: { series: Series[]; unit: string }) {
  const [serviceLine, setServiceLine] = useState(series[0]?.service_line ?? "ED");
  const rows = useMemo(() => {
    const match = series.find((item) => item.service_line === serviceLine);
    const points = match?.points ?? [];
    const forecastDates = points.filter((point) => point.kind === "forecast").map((point) => point.date);
    const firstForecast = forecastDates[0];
    return points
      .filter((point) => point.kind === "forecast" || (firstForecast && point.date >= shiftDays(firstForecast, -28)))
      .map((point) => ({
        label: point.date.slice(5),
        observed: point.kind === "observed" ? point.actual ?? null : null,
        forecast: point.kind === "forecast" ? point.forecast ?? null : null,
        baseline: point.kind === "forecast" ? point.baseline ?? null : null,
        lower: point.kind === "forecast" ? point.lower ?? null : null,
        upper: point.kind === "forecast" ? point.upper ?? null : null,
      }));
  }, [series, serviceLine]);
  return (
    <>
      <label>
        Service line
        <select value={serviceLine} onChange={(event) => setServiceLine(event.target.value)}>
          {series.map((item) => (
            <option key={item.service_line} value={item.service_line}>
              {item.service_line_name}
            </option>
          ))}
        </select>
      </label>
      <LinePanel
        rows={rows}
        unit={unit}
        lines={[
          { key: "observed", name: "Observed", color: "#0f5f5c" },
          { key: "forecast", name: "Forecast", color: "#1e4d7b" },
          { key: "baseline", name: "Seasonal naive", color: "#8a5a12" },
          { key: "lower", name: "Lower band", color: "#8d8d8d" },
          { key: "upper", name: "Upper band", color: "#8d8d8d" },
        ]}
      />
    </>
  );
}

function shiftDays(isoDate: string, days: number) {
  const [year, month, day] = isoDate.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}
