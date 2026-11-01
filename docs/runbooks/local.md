# Local run

1. Install Docker Desktop and give it about 8 GB of memory if you also start Airflow.
2. From the repo root:

```bash
docker compose -f infra/docker-compose.yml --profile core up --build
```

3. Wait until the `pipeline` service exits successfully. The API listens on port 8000 and the console on port 3000.
4. Refresh the console after the snapshot file changes. It is mounted from `app/data/public-snapshot.json`.
5. Run the batch again with:

```bash
docker compose -f infra/docker-compose.yml --profile core run --rm pipeline
```

Encounter counts in `silver.encounter` stay flat across that rerun. `audit.pipeline_run` gains a row.

Airflow, profile `full`, uses the database `airflow` on the same Postgres instance. The DAG `hoico_daily` calls `/opt/hoico-venv/bin/python` so HOICO's SQLAlchemy 2 install does not replace the SQLAlchemy 1.4 that Airflow 2.10 needs. Each stage retries twice and has 45 minutes. Trigger it from the Airflow UI. Backfill is off. To rerun a day that already succeeded, clear the task in the UI and let the scheduler run it again.

MLflow writes to `mlruns/` and, in the full profile, serves the UI on port 5000.

Demo passwords live in `.env.example`. They are for this local stack only.
