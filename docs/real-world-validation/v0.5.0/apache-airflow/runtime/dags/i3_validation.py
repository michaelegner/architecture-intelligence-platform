# I3 validation workload (I3 spec §32). Test configuration only, not an Airflow architecture
# modification: no external network dependency, no LLM call, no non-deterministic output required
# for validation, runs on the qualifying Celery queue ("default"), two ordered tasks, finishes
# quickly, safe to run repeatedly. Emits only deterministic logs - no AIP-specific declarations.

from __future__ import annotations

import datetime

from airflow.sdk import DAG, task


@task(queue="default")
def task_a() -> str:
    print("i3_validation: task_a running")
    return "task_a done"


@task(queue="default")
def task_b(_upstream: str) -> None:
    print("i3_validation: task_b running")


with DAG(
    dag_id="i3_validation",
    description="AIP I3 deterministic validation workload (upstream.md, ground-truth.md)",
    schedule=None,
    start_date=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    catchup=False,
    is_paused_upon_creation=False,
    tags=["aip-i3-validation"],
) as dag:
    task_b(task_a())
