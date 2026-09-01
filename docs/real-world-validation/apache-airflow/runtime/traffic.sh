#!/usr/bin/env bash
# Deterministic traffic script for the Apache Airflow I3 validation profile (I3 spec §33).
#
# Calls only Airflow's own stable /api/v2 endpoints - never an AIP-specific endpoint. Performs, in
# order: (1) readiness check, (2) auth via the configured FabAuthManager token endpoint
# (`/auth/token`, providers/fab/src/airflow/providers/fab/auth_manager/api_fastapi/routes/login.py
# @ the pinned commit), (3) read operations, (4) trigger the deterministic i3_validation Dag,
# (5) poll the Dag Run, (6) verify both tasks completed, (7) print window_start/window_end for the
# runbook's drain-barrier step. Run this between runbook.md's "start observation window" and
# "end observation window" steps.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8080}"
DAG_ID="i3_validation"

echo "window_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

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

echo "==> GET /api/v2/variables" >&2
curl -sS -f -H "${AUTH_HEADER}" "${API_URL}/api/v2/variables" >&2
echo >&2

echo "==> POST /api/v2/dags/${DAG_ID}/dagRuns (trigger)" >&2
DAG_RUN="$(
  curl -sS -f -X POST -H "${AUTH_HEADER}" -H 'Content-Type: application/json' \
    "${API_URL}/api/v2/dags/${DAG_ID}/dagRuns" \
    -d '{"logical_date": null}'
)"
DAG_RUN_ID="$(echo "${DAG_RUN}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["dag_run_id"])')"
echo "dag_run_id=${DAG_RUN_ID}" >&2

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
curl -sS -f -H "${AUTH_HEADER}" \
  "${API_URL}/api/v2/dags/${DAG_ID}/dagRuns/${DAG_RUN_ID}/taskInstances" >&2
echo >&2

echo "==> traffic complete" >&2
echo "window_end=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
