#!/usr/bin/env bash
# Deterministic traffic script for the Apache Airflow I3 validation profile (I3 spec §33).
#
# Calls only Airflow's own stable /api/v2 endpoints - never an AIP-specific endpoint. Performs, in
# order: (1) readiness check, (2) auth via the configured FabAuthManager token endpoint
# (`/auth/token`, providers/fab/src/airflow/providers/fab/auth_manager/api_fastapi/routes/login.py
# @ the pinned commit), (3) the remaining 8 of the 9 selected read/write operations
# (`../profile.md`'s "Bounded public REST API endpoints exercised"), (4) trigger the deterministic
# i3_validation Dag with a caller-chosen dag_run_id, (5) poll the Dag Run, (6) verify both tasks
# completed with the expected queue/state. It does NOT print window_start/window_end - the
# observation window and its drain barrier are the runbook's responsibility (`../runbook.md` phase
# 6), not this script's (PR #45 review F1: a script-local timestamp and the runbook's own timestamp
# raced each other and neither waited for the OTLP drain).

set -euo pipefail

API_URL="${API_URL:-http://localhost:8080}"
DAG_ID="i3_validation"
DAG_RUN_ID="aip-i3-validation-$(date -u +%Y%m%dT%H%M%SZ)"

echo "==> GET /api/v2/monitor/health (readiness)" >&2
curl -sS -f "${API_URL}/api/v2/monitor/health" >&2
echo >&2

echo "==> POST /auth/token (FabAuthManager)" >&2
TOKEN="$(
  curl -sS -f -X POST "${API_URL}/auth/token" \
    -H 'Content-Type: application/json' \
    -d '{"username":"airflow","password":"airflow"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
)"
AUTH_HEADER="Authorization: Bearer ${TOKEN}"

echo "==> GET /api/v2/dags" >&2
curl -sS -f -H "${AUTH_HEADER}" "${API_URL}/api/v2/dags" >&2
echo >&2

echo "==> GET /api/v2/dags/${DAG_ID}" >&2
curl -sS -f -H "${AUTH_HEADER}" "${API_URL}/api/v2/dags/${DAG_ID}" >&2
echo >&2

echo "==> GET /api/v2/variables" >&2
curl -sS -f -H "${AUTH_HEADER}" "${API_URL}/api/v2/variables" >&2
echo >&2

echo "==> POST /api/v2/dags/${DAG_ID}/dagRuns (trigger, fixed dag_run_id=${DAG_RUN_ID})" >&2
curl -sS -f -X POST -H "${AUTH_HEADER}" -H 'Content-Type: application/json' \
  "${API_URL}/api/v2/dags/${DAG_ID}/dagRuns" \
  -d "{\"dag_run_id\": \"${DAG_RUN_ID}\", \"logical_date\": null}" >&2
echo >&2

echo "==> GET /api/v2/dags/${DAG_ID}/dagRuns (list)" >&2
curl -sS -f -H "${AUTH_HEADER}" "${API_URL}/api/v2/dags/${DAG_ID}/dagRuns" >&2
echo >&2

echo "==> GET /api/v2/dags/${DAG_ID}/dagRuns/${DAG_RUN_ID} (poll until terminal)" >&2
for _ in $(seq 1 60); do
  STATE="$(
    curl -sS -f -H "${AUTH_HEADER}" \
      "${API_URL}/api/v2/dags/${DAG_ID}/dagRuns/${DAG_RUN_ID}" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])'
  )"
  echo "  state=${STATE}" >&2
  case "${STATE}" in
    success) break ;;
    failed) echo "Dag Run failed - see: docker compose logs airflow-scheduler airflow-worker" >&2; exit 1 ;;
  esac
  sleep 2
done
[ "${STATE}" = "success" ] || { echo "Dag Run did not reach success within timeout" >&2; exit 1; }

echo "==> GET /api/v2/dags/${DAG_ID}/dagRuns/${DAG_RUN_ID}/taskInstances (verify)" >&2
TASK_INSTANCES="$(
  curl -sS -f -H "${AUTH_HEADER}" \
    "${API_URL}/api/v2/dags/${DAG_ID}/dagRuns/${DAG_RUN_ID}/taskInstances"
)"
echo "${TASK_INSTANCES}" >&2
echo "${TASK_INSTANCES}" | python3 -c '
import json, sys

data = json.load(sys.stdin)
by_id = {ti["task_id"]: ti for ti in data["task_instances"]}

expected_ids = {"task_a", "task_b"}
actual_ids = set(by_id)
assert actual_ids == expected_ids, f"expected exactly {expected_ids}, got {actual_ids}"

for task_id, ti in by_id.items():
    state, queue = ti["state"], ti["queue"]
    assert state == "success", f"{task_id}: expected state=success, got {state!r}"
    assert queue == "default", f"{task_id}: expected queue=default, got {queue!r}"

print("task instance assertions passed: task_a and task_b both success on queue=default", file=sys.stderr)
'

echo "==> GET /api/v2/dags/${DAG_ID}/dagRuns/${DAG_RUN_ID}/taskInstances/task_a (single)" >&2
curl -sS -f -H "${AUTH_HEADER}" \
  "${API_URL}/api/v2/dags/${DAG_ID}/dagRuns/${DAG_RUN_ID}/taskInstances/task_a" >&2
echo >&2

echo "==> traffic complete (dag_run_id=${DAG_RUN_ID})" >&2
