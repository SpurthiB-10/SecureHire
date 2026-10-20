"""
airflow_dag.py — Reference Airflow DAG (not executed in this scaffold)
------------------------------------------------------------------------
Shows how the ingest -> clean -> load task functions defined in this
package would be scheduled daily in a production Airflow deployment.

Requires `apache-airflow` installed in the Airflow environment; it is
NOT a dependency of the FastAPI backend or the standalone pipeline runner.
To use: copy this file into your Airflow DAGs folder.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from clean import run as run_clean
from ingest import ingest
from load import run as run_load

default_args = {
    "owner": "securehire-ai",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="securehire_etl_pipeline",
    description="Ingest -> Clean -> Load job posting data for SecureHire AI",
    schedule_interval="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["etl", "securehire"],
) as dag:

    def _ingest_task(**context):
        path = ingest()
        context["ti"].xcom_push(key="landed_path", value=str(path))

    def _clean_task(**context):
        landed_path = context["ti"].xcom_pull(key="landed_path", task_ids="ingest")
        path = run_clean(landed_path)
        context["ti"].xcom_push(key="clean_path", value=str(path))

    def _load_task(**context):
        clean_path = context["ti"].xcom_pull(key="clean_path", task_ids="clean")
        run_load(clean_path, load_db=True)

    ingest_op = PythonOperator(task_id="ingest", python_callable=_ingest_task)
    clean_op = PythonOperator(task_id="clean", python_callable=_clean_task)
    load_op = PythonOperator(task_id="load", python_callable=_load_task)

    ingest_op >> clean_op >> load_op
