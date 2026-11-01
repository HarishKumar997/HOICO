export type Point = {
  date: string;
  actual?: number;
  forecast?: number;
  lower?: number;
  upper?: number;
  baseline?: number;
  kind: "observed" | "forecast";
};

export type Series = {
  service_line: string;
  service_line_name: string;
  points: Point[];
};

export type CapacityPoint = {
  date: string;
  ward_id: string;
  ward_name: string;
  occupied: number;
  usable_beds: number | null;
  occupancy_rate: number | null;
  pressure: string;
  kind: "observed" | "forecast";
};

export type Scenario = {
  scenario_name: string;
  status: string;
  objective: number;
  unmet_bed_days: number;
  extra_beds: number;
  overtime_hours: number;
  extra_discharges: number;
  reason_summary: string;
  parameters: {
    demand_uplift: number;
    bed_availability: number;
    staffing_availability: number;
    extra_discharge_boost: number;
    weights: Record<string, number>;
    force_do_nothing: boolean;
  };
  assumptions: string[];
  constraint_status: Record<string, boolean>;
  decisions: Array<Record<string, number | string>>;
};

export type Dashboard = {
  schema_version: number;
  status: "ready" | "not_generated";
  notice: string;
  as_of: string;
  timezone: string;
  facility: { id: string; name: string };
  freshness: {
    generated_at: string;
    batch_id: string;
    history_start: string;
    history_end: string;
  } | null;
  summary: {
    next_7_day_arrivals: number;
    next_24h_arrivals_naive: number;
    wards_over_pressure_threshold: number;
    selected_model: string;
    test_wape: number | null;
    test_mae: number | null;
    baseline_test_wape: number | null;
    baseline_test_mae: number | null;
    pressure_threshold: number;
  } | null;
  forecasts: {
    grain: string;
    unit: string;
    horizon_days: number;
    issue_date: string;
    model_name: string;
    series: Series[];
  } | null;
  hourly: {
    grain: string;
    unit: string;
    model_note: string;
    points: Array<{ hour: string; value: number; kind: string; model: string }>;
  } | null;
  capacity: {
    grain: string;
    unit: string;
    threshold: number;
    points: CapacityPoint[];
  } | null;
  evaluation: {
    selected_model: string;
    validation_wape: Record<string, number | null>;
    test_wape: number | null;
    test_mae: number | null;
    baseline_test_wape: number | null;
    baseline_test_mae: number | null;
    interval_coverage: number | null;
    windows: Record<string, string[]>;
  } | null;
  quality: {
    accepted: Record<string, number>;
    rejected: Record<string, number>;
    duplicates_removed: Record<string, number>;
    rejected_total: number;
    bronze_rows: Record<string, number>;
  } | null;
  scenarios: {
    baseline: Scenario;
    grid: Scenario[];
    infeasible_example: Scenario;
  } | null;
  assumptions: string[];
};
