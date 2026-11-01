# Hospital Operations Intelligence & Capacity Optimizer
**Product Requirements Document (PRD)**  
**Version:** 1.0 | **Status:** Portfolio specification / implementation blueprint  
**Owner:** Harish Kumar | **Date:** 29 October 2026

> **Purpose:** A decision-support platform that forecasts hospital demand, anticipates capacity pressure, and helps operations teams compare staffing and bed-allocation scenarios. This is an educational portfolio project using synthetic or appropriately licensed, de-identified data. It is not a clinical decision system.

## 1. Executive summary
Hospital Operations Intelligence & Capacity Optimizer (HOICO) is an end-to-end analytics product for hospital operations leaders. It combines data engineering, forecasting, applied machine learning, operations research, and explainable decision support in one coherent workflow.

The platform ingests patient-flow and operational data, validates and transforms it into trusted analytical datasets, forecasts arrivals and bed demand, identifies operational bottlenecks, and recommends capacity actions subject to configurable constraints. It provides an auditable view of forecast quality, data quality, assumptions, and scenario outcomes.

**Core principle:** forecasts should inform decisions, not pretend to make decisions for hospital staff.

## 2. Problem statement
Hospital operations teams must balance uncertain patient arrivals with finite beds, staff, equipment, and discharge capacity. Demand and length of stay vary by day, season, service line, and operational conditions. Fragmented or delayed data makes it difficult to anticipate bottlenecks and compare interventions consistently.

HOICO addresses this by combining synthetic operational data into a consistent model; forecasting demand at a defined time and service-line grain; estimating bed occupancy and staffing pressure; surfacing data quality issues and forecast uncertainty; comparing capacity scenarios; and documenting the assumptions behind every recommendation.

## 3. Product vision and value proposition
**Vision:** help operations teams see capacity pressure earlier and evaluate possible responses with transparent evidence.

**Value proposition:** move from retrospective dashboards to a reproducible planning workflow that connects historical data, forecasts, constraints, and operational scenarios.

The product should answer:
1. What demand and occupancy should we plan for over the next 24 hours to 14 days?
2. Where is capacity likely to become constrained?
3. How uncertain is the forecast?
4. Which feasible operational scenarios reduce projected pressure?
5. What assumptions, data gaps, and trade-offs drive the recommendation?

## 4. Goals and measurable outcomes
### Product goals
- Deliver an end-to-end pipeline from raw inputs to validated analytical outputs.
- Forecast arrivals and occupancy using time-aware evaluation and simple baselines.
- Demonstrate a constrained optimization or scenario-ranking workflow.
- Make outputs interpretable for operations users and inspectable by technical reviewers.
- Keep the core experience reproducible locally, with optional cloud deployment.

### Engineering success criteria
- A clean setup runs locally using documented commands.
- Invalid records are rejected or quarantined with reason codes, not silently discarded.
- Re-running the same batch does not double-count source events.
- Forecasts use chronological holdout evaluation, not random time-series splits.
- At least one baseline is compared with a more advanced model.
- Forecast metrics are reported by service line and horizon where sample size permits.
- Every optimizer recommendation includes constraints, assumptions, and a reason summary.
- Automated tests cover transformations, metric calculations, and optimization constraints.
- The public demo uses synthetic or approved de-identified data only.
- All accuracy and performance claims have reproducible evidence.

### Portfolio evaluation metrics
- Forecasting: MAE and WAPE for arrivals; occupancy error and interval coverage where supported.
- Data quality: accepted/rejected/duplicate counts, schema failures, referential integrity.
- Pipeline: runtime, rows processed, retry count, and successful-run rate over repeated tests.
- Optimization: projected capacity violations, unmet-demand proxy, overtime/resource-cost proxy, and constraint violations.
- Usability: reviewers can identify horizon, freshness, assumptions, and scenario differences without a walkthrough.

## 5. Non-goals and safety boundaries
- No diagnosis, triage, treatment, or clinical recommendations.
- No automated decisions about individual patients.
- No real patient-level data in the public repository or demo.
- No claim that synthetic results prove real-world hospital impact.
- No production integration with an EHR in the portfolio MVP.
- No opaque recommendation without visible assumptions and constraints.
- No claim of clinical validation, regulatory compliance, or production readiness unless independently established.

## 6. Users and personas
- **Hospital operations manager:** needs forecast demand, occupancy pressure, and feasible options.
- **Capacity / bed manager:** needs ward-level views, capacity definitions, and bottleneck periods.
- **Data analyst / scientist:** needs documented datasets, reproducible features, model metrics, and drift checks.
- **Technical reviewer / recruiter:** needs architecture, code quality, tests, trade-offs, and implementation evidence.

## 7. Scope and delivery phases
### Release 1 — Local MVP (must-have)
- Deterministic synthetic-data generator.
- CSV and mock REST API ingestion.
- PostgreSQL for reference and analytical serving tables.
- Python transformations and PySpark batch processing.
- Bronze / Silver / Gold layers using Parquet locally.
- Data validation, quarantine, deduplication, and run metadata.
- Demand and occupancy baselines plus one suitable forecasting model.
- Chronological model evaluation and documented results.
- Scenario simulator with explicit capacity constraints.
- FastAPI read-only endpoints.
- Streamlit dashboard or lightweight React/Next.js UI.
- pytest, Docker Compose, `.env.example`, `.gitignore`, and GitHub Actions CI.
- README, architecture diagram, data dictionary, and limitations.

### Release 2 — Operational maturity
- Apache Airflow orchestration with dependencies, retries, timeouts, and backfills.
- dbt models and tests for SQL transformations where supported.
- MLflow experiment tracking and reproducible runs.
- Monitoring for freshness, volume anomalies, feature drift, and forecast error.
- Pipeline/model run audit tables and clear API/UI error states.

### Release 3 — Cloud and scale demonstration
- Databricks implementation using PySpark and Delta Lake.
- Databricks Workflows/Jobs for cloud execution.
- Optional cloud object storage and selected warehouse if access/cost is appropriate.
- CI checks and documented deployment procedure.
- Vercel-hosted frontend; compute-heavy jobs run outside Vercel.
- Publish sanitized aggregate outputs only.

### Stretch goals
- OR-Tools or PuLP optimization with detailed staffing and bed constraints.
- Probabilistic forecasts and calibrated prediction intervals.
- Kafka/Redpanda for simulated event streaming.
- Geospatial catchment analysis using GeoPandas/PostGIS.
- SHAP or permutation importance where appropriate.
- Terraform or infrastructure-as-code.

## 8. Functional requirements

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-01 | Generate/load synthetic data | Must | Fixed seed is reproducible; no real patient identifiers |
| FR-02 | Ingest source data | Must | Captures source, batch/run ID, timestamp, counts, errors |
| FR-03 | Validate schema/business rules | Must | Invalid rows quarantined with reason codes |
| FR-04 | Deduplicate and process incrementally | Must | Stable keys and rerun behavior documented and tested |
| FR-05 | Bronze/Silver/Gold layers | Must | Raw data traceable; downstream layers rebuildable |
| FR-06 | Model hospital operations | Must | Grain, keys, time zone, capacity and formulas documented |
| FR-07 | Forecast arrivals | Must | Baseline and model compared on chronological holdout |
| FR-08 | Forecast occupancy/capacity pressure | Should | Assumptions documented; no future data leakage |
| FR-09 | Report uncertainty | Should | Intervals or scenario ranges shown where supported |
| FR-10 | Simulate capacity scenarios | Must | User can vary assumptions and compare outcomes |
| FR-11 | Recommend feasible actions | Should | Constraints respected and rationale displayed |
| FR-12 | Track model performance | Must | Metrics include evaluation period, horizon, baseline, version |
| FR-13 | Expose read-only API | Should | Documented schemas and clear errors |
| FR-14 | Provide operations dashboard | Must | Forecast, capacity, quality/freshness, scenarios displayed |
| FR-15 | Automate tests and CI | Must | Critical tests run in CI and fail the check when broken |
| FR-16 | Orchestrate jobs | Should | DAG shows dependencies, retries, timeouts, backfill |
| FR-17 | Databricks path | Stretch for MVP | Successful run documented; local path remains usable |
| FR-18 | Document setup and trade-offs | Must | New developer can run demo and understand limitations |

## 9. Data sources and contracts
Start with generated synthetic data. Public datasets may be used only after reviewing licensing, access terms, field definitions, and privacy restrictions. Publicly accessible health data is not automatically unrestricted.

### Proposed entities
- **encounters:** encounter_id, synthetic_patient_key, arrival_time, departure_time, service_line, arrival_mode, operational_acuity_category, encounter_status.
- **bed_capacity:** timestamp, facility_id, ward_id, staffed_beds, available_beds, blocked_beds.
- **staffing:** timestamp, unit_id, role_group, scheduled_staff, available_staff, absence_count.
- **discharges:** encounter_id, discharge_time, discharge_status, delay_category.
- **operational_events:** event_id, event_type, event_time, unit_id, severity, source_updated_at.
- **calendar:** date, hour, day_of_week, holiday_flag, seasonal indicators as appropriate.

Use random synthetic keys. Avoid names, contact details, government IDs, exact addresses, or realistic patient identifiers.

### Grain and time conventions
- Arrivals: one row per facility/service line/time bucket.
- Capacity: one row per facility/ward/time bucket.
- Encounters: one row per synthetic encounter.
- Staffing: one row per unit/role/time bucket.
- State the time zone; distinguish event time from ingestion time.

### Data-quality rules
- Encounter ID unique under documented source rules.
- Arrival cannot occur after departure for completed encounters.
- Staffed beds are non-negative and do not exceed configured physical capacity unless explicitly modelled as an exception.
- Required service-line and unit keys must exist.
- Timestamps and controlled categories must parse and conform to allowed values.
- Late-arriving/corrected records have documented handling.
- Rejected rows include `reject_reason`, `batch_id`, and source metadata.

## 10. Analytical model and metric definitions
### Suggested tables
`dim_facility`, `dim_service_line`, `dim_ward`, `dim_date_time`, `fact_encounter`, `fact_bed_capacity_hourly`, `fact_staffing_hourly`, `fact_discharge`, `fact_arrivals_hourly`, `forecast_arrivals`, `forecast_occupancy`, `scenario_results`, `pipeline_run_audit`, `data_quality_results`, `model_evaluation`.

### Metric definitions
- **Arrivals:** count of eligible encounters by arrival timestamp and time bucket.
- **Occupancy:** occupied beds divided by staffed, usable beds for the same ward/time bucket; define blocked-bed and zero-denominator handling.
- **Capacity pressure:** projected demand or occupancy relative to configured staffed capacity, with explicit thresholds.
- **Length of stay:** elapsed time between arrival and departure for eligible completed encounters; document incomplete encounters.
- **Discharge delay:** measured against an explicitly defined operational target, not assumed to be universal.
- **Staffing gap:** required-staff proxy minus available staff, only where a validated staffing rule exists.

These are operational portfolio metrics, not universal clinical standards.

## 11. Forecasting and evaluation
### Forecast target
Start with hourly or daily arrivals by service line. Derive occupancy only when the simulated data and flow assumptions support it. Keep the forecast grain and horizon explicit.

### Development sequence
1. Establish a seasonal-naïve baseline (e.g., same hour/day in a prior comparable period).
2. Add an appropriate statistical model such as exponential smoothing if supported.
3. Test LightGBM/XGBoost only if the data supports a feature-based model.
4. Compare models on the same chronological holdout and horizon.
5. Report MAE and WAPE where appropriate; explain zero-denominator handling.
6. Inspect residuals by service line, time of day, weekday/weekend, and horizon.
7. Report interval coverage if prediction intervals are produced.
8. Store model version, feature version, training window, evaluation window, and parameters.

### Leakage controls
- Do not randomly split time series for final evaluation.
- Features must be available at the forecast issue time.
- Fit preprocessing only on training data.
- Keep final holdout untouched until model selection is complete.
- Always compare with a baseline and document synthetic-data limitations.

## 12. Capacity optimization and scenario engine
Begin with a transparent scenario engine. A mathematical optimizer is optional after the baseline workflow is correct.

### Scenario controls
- demand uplift/reduction by a defined percentage;
- staffed-bed availability;
- planned discharge capacity or delay assumption;
- staffing availability by role/unit;
- configurable overtime or temporary-capacity cost proxy.

### Example objective and constraints
Minimize a documented weighted operational cost proxy across unmet capacity, overtime, temporary capacity, and disruption, subject to explicit constraints. Weights must be editable and explained. Staffing and bed capacity cannot exceed configured maxima; resource assignments must be non-negative; infeasible scenarios must be labelled; clinical triage and patient-level treatment actions are out of scope.

### Acceptance criteria
- Same inputs and parameters produce the same result.
- Every result shows assumptions and constraint status.
- Infeasible scenarios are clearly labelled.
- UI distinguishes forecast, scenario, and recommendation.
- A baseline scenario is always available for comparison.

## 13. Technology architecture

| Layer | Primary technology | Purpose / boundary |
|---|---|---|
| Ingestion | Python | Source adapters, validation, run metadata |
| Relational store | PostgreSQL | Local reference and serving tables |
| Distributed processing | PySpark | Batch transforms and scalable preparation |
| Local lake | Parquet | Reproducible columnar files |
| Cloud lakehouse | Databricks + Delta Lake | Cloud Bronze/Silver/Gold path |
| Orchestration | Airflow; Databricks Workflows in cloud | Dependencies, retries, schedules, backfills |
| SQL transformations | dbt Core | Modular SQL, tests and docs where compatible |
| Forecasting/ML | statsmodels, scikit-learn, LightGBM/XGBoost | Baselines and candidate models |
| Optimization | OR-Tools or PuLP | Constraint-based capacity scenarios |
| Model tracking | MLflow | Experiment and model metadata |
| API | FastAPI | Read-only metrics and scenario endpoints |
| UI | Streamlit for MVP; Next.js/React for polished frontend | Dashboard and demo |
| Quality | pytest + dbt tests + custom assertions | Correctness and regression protection |
| Packaging | Docker Compose | Repeatable local environment |
| CI | GitHub Actions | Lint, test, build checks |
| Hosting | Vercel for frontend; suitable compute for ETL | Heavy Spark/Airflow work stays outside Vercel |
| Observability | Structured logs + audit tables | Run status, freshness, failures, model quality |

**Architecture rule:** do not include tools just to inflate the stack. Each component must have a clear role and working demonstration.

## 14. API and dashboard requirements
### Example read-only endpoints
- `GET /api/health`
- `GET /api/summary?as_of=YYYY-MM-DD`
- `GET /api/forecasts?service_line=...&horizon=...`
- `GET /api/capacity?facility_id=...&from=...&to=...`
- `POST /api/scenarios/compare` — validates inputs and returns scenario comparisons.
- `GET /api/quality/latest`
- `GET /api/model-evaluation`

### Dashboard pages
1. Executive overview: arrivals, occupancy, forecast horizon, pressure, data freshness.
2. Demand forecast: observed series, forecast, uncertainty, baseline, evaluation context.
3. Capacity explorer: ward/service-line comparisons and bottleneck periods.
4. Scenario planner: assumptions, feasible actions, constraints and comparison.
5. Data/model quality: accepted/rejected rows, pipeline runs, forecast errors and limitations.
6. About: synthetic-data notice, architecture, methodology, limitations, repository link.

Charts must show units, time range, aggregation grain, and whether values are observed, forecast, or simulated.

## 15. Non-functional requirements
- **Reliability:** safe reruns, explicit failures, no silent data loss.
- **Reproducibility:** pinned dependencies, deterministic seed, documented commands.
- **Privacy:** no real patient-level data in public assets; aggregate outputs only.
- **Security:** secrets in environment variables/secret manager; never in Git.
- **Explainability:** assumptions, constraints, and reason summaries visible.
- **Performance:** benchmark stated hardware and input size; avoid unsupported scale claims.
- **Maintainability:** modular code, clear contracts, readable SQL, useful type hints.
- **Accessibility:** readable contrast, labels, keyboard-friendly controls.
- **Cost:** local-first; cloud jobs opt-in and stopped after use.
- **Portability:** MVP works without cloud credentials.

## 16. Testing and quality gates
### Unit tests
- schema parsing and type conversion;
- arrival and occupancy metrics;
- invalid timestamp/category handling;
- deduplication and watermark logic;
- forecast feature generation without future leakage;
- scenario constraints and infeasibility.

### Integration tests
- source fixture → Bronze → Silver → Gold;
- PostgreSQL load and query checks;
- rerun same batch and verify no duplicate events;
- invalid rows quarantined with reasons;
- deterministic scenario results;
- API schema and invalid-parameter behavior.

### Model tests
- chronological train/validation/test windows;
- baseline comparison;
- no future-derived features;
- metric calculations on known fixtures;
- model metadata stored with evaluation output.

### CI gates
1. Formatting/lint.
2. Unit tests.
3. Lightweight integration tests.
4. API/import/build checks.
5. Optional Docker smoke test.
6. Publish test summary; critical failures fail the check.

## 17. Responsible data use and governance
- Use synthetic patient/encounter identifiers.
- Do not publish actual patient records, real-system screenshots, or confidential employer data.
- Review external dataset terms before use.
- Treat forecasts as planning estimates; humans retain responsibility for operations decisions.
- Do not use protected characteristics or individual-level health details to allocate or deny care.
- Do not present this as clinically validated or certified healthcare software.
- Record lineage, transformation logic, model version, and evaluation windows.

## 18. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Scope becomes too large | Finish local MVP before cloud, streaming, advanced optimization |
| Synthetic data yields unrealistically strong scores | Document simulation rules; no real-world validity claims |
| Data leakage inflates metrics | Chronological split, issue-time feature checks, baseline |
| Optimizer suggests infeasible actions | Encode constraints and test infeasible cases |
| Tools are included without depth | Require working code and evidence per tool |
| Cloud/free-tier limits change | Keep local pipeline reproducible |
| Sensitive data exposure | Synthetic data, `.gitignore`, secret scanning, aggregate outputs |
| UI implies clinical authority | Label outputs as planning estimates and require human oversight |
| Public demo fails | Static aggregate fallback and honest demo status |

## 19. Delivery roadmap

### Milestone A — Data foundation
Build deterministic synthetic data, ingestion, Bronze/Silver/Gold transforms, quality reports, PostgreSQL tables, data dictionary, and tests for transformations/idempotency.
**Exit criteria:** clean local run, quality report, reproducible outputs, tests passing.

### Milestone B — Forecasting
Define grain/horizon, implement seasonal-naïve baseline, train one suitable model, evaluate chronologically, and publish metrics.
**Exit criteria:** reproducible report with baseline, model, period, and limitations.

### Milestone C — Capacity scenarios
Build occupancy metrics, scenario controls and constraints; compare baseline and alternative scenarios; test feasible and infeasible inputs.
**Exit criteria:** deterministic results with visible assumptions and constraint checks.

### Milestone D — Product experience and orchestration
Build API and dashboard; add Airflow, dbt and MLflow where justified; add run tracking and CI.
**Exit criteria:** documented workflow, automated tests, usable demo.

### Milestone E — Cloud and public portfolio
Implement Databricks/Delta path if feasible; deploy frontend to Vercel; publish architecture, methodology, data dictionary, test evidence, and benchmark results.
**Exit criteria:** understandable and reproducible public repository; demo clearly identifies synthetic data and limitations.

## 20. Definition of done
A reviewer can:
- understand the problem and architecture in two minutes;
- clone the repo and run the local pipeline;
- inspect synthetic source data and Bronze/Silver/Gold outputs;
- run tests and observe meaningful failures when rules break;
- reproduce forecast evaluation and baseline comparison;
- change scenario parameters and see constraints reflected;
- understand data assumptions, limitations, and implemented vs planned features.

## 21. Public repository structure

```text
hospital-operations-intelligence/
├── README.md
├── PRD.md
├── docs/
│   ├── architecture.md
│   ├── data-dictionary.md
│   ├── model-card.md
│   ├── evaluation-report.md
│   ├── decisions/
│   └── runbooks/
├── data/
│   ├── samples/              # small synthetic fixtures only
│   └── generated/            # gitignored
├── ingestion/
├── transformations/
│   ├── pyspark/
│   └── dbt/
├── forecasting/
├── optimization/
├── api/
├── app/                      # Streamlit or Next.js
├── orchestration/airflow/
├── tests/
├── scripts/
├── infra/docker-compose.yml
├── .github/workflows/
└── .env.example
```

## 22. Recruiter-facing README checklist
- concise problem statement and honest project status;
- architecture diagram;
- actual implemented stack separated from planned tools;
- quick-start instructions;
- links to PRD, data dictionary, model card, evaluation report;
- actual test results and measured runtime;
- forecast baseline comparison and evaluation period;
- scenario demo with assumptions;
- live demo link if available;
- limitations and synthetic-data notice.

Do not claim real hospital impact, production scale, clinical validity, or improved patient outcomes from synthetic experiments.

## 23. Official technical references
Verify current versions and provider-specific requirements before implementation:
- Databricks medallion architecture: https://docs.databricks.com/gcp/en/lakehouse/medallion
- Apache Airflow DAG concepts: https://airflow.apache.org/docs/apache-airflow/stable/concepts/dags.html
- FastAPI: https://fastapi.tiangolo.com/
- MLflow: https://mlflow.org/docs/latest/
- Vercel Functions: https://vercel.com/docs/functions
- OR-Tools: https://developers.google.com/optimization

---

## Initial product decisions
1. **Local-first:** MVP must run without cloud credentials.
2. **Forecast before optimize:** optimization follows clear forecasts and constraints.
3. **Baseline before advanced ML:** establish whether complexity adds value.
4. **Synthetic data first:** realistic operational patterns without real patient records.
5. **Human oversight:** recommendations are planning aids, not clinical decisions.
6. **Evidence over buzzwords:** every tool maps to a working feature, test, runbook, or measured result.
7. **Separate compute from UI:** Vercel serves the frontend and safe aggregate outputs; Spark, Airflow, and Databricks execute in appropriate environments.
