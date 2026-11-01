"""Daily HOICO batch. Each task calls the same CLI as a local run."""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "hoico",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=45),
}

with DAG(
    dag_id="hoico_daily",
    description="Generate, validate, forecast, and publish the HOICO planning batch.",
    start_date=datetime(2026, 6, 1),
    schedule="0 6 * * *",
    catchup=False,
    default_args=default_args,
    tags=["hoico"],
) as dag:
    previous = None
    for stage in ("generate", "transform", "load", "dbt", "forecast", "scenarios", "snapshot"):
        task = BashOperator(
            task_id=stage,
            bash_command=f"cd /opt/hoico && /opt/hoico-venv/bin/python -m hoico.cli {stage}",
        )
        if previous is not None:
            previous >> task
        previous = task
