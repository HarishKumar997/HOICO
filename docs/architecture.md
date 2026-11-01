# Architecture

HOICO keeps one Python package, `hoico`, for generation, validation, forecasting, and scenarios. Spark, dbt, the API, Airflow, and the console call that package or the tables it publishes.

Analytical timestamps are America/Chicago wall times. Ingestion time is stored separately in UTC. The as-of date for the shipped synthetic history is 30 June 2026. The history starts 5 March 2026 so the split is 90 training days, 14 validation days, and 14 test days.

## Layers

Bronze is the raw CSV and the operational-event JSON, plus source name, batch id, ingestion time, and source row number. The batch id is a hash of the source bytes. Bronze is overwritten on a rerun.

Silver applies the reason codes in `hoico.quality.rules`, then keeps the row with the latest `source_updated_epoch` for each business key. Invalid rows go to quarantine with the reason, batch id, and a payload. They are not dropped quietly.

Spark builds hourly arrival counts and hourly occupancy. Occupancy is the count of non-cancelled encounters whose stay overlaps a real local hour from the calendar. Spring-forward hours that do not exist are not invented, because the join uses the calendar rather than a fixed 3600-second step. Usable beds are staffed beds minus blocked beds. The occupancy rate is null when usable beds are zero.

Those hourly facts land in Postgres `spark_gold`. dbt builds `gold.fact_arrivals_daily`, `gold.fact_capacity_pressure`, and `gold.data_quality_results`. Forecast and scenario tables are written by Python into `gold` after dbt, so dbt does not recompute the model.

## Serving

FastAPI reads the gold tables. The Next.js console reads `app/data/public-snapshot.json`, which contains aggregates only. In Docker, that file is mounted into the web container. The scenario controls snap to a grid the CBC solver already computed. The local API can score a case that is not on the grid.

## Out of the running path

Databricks Free Edition can run the same medallion function and write Delta tables. Vercel Hobby can host the console against the committed snapshot. Both need the user's own login and are documented as optional.
