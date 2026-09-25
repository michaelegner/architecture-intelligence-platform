#!/usr/bin/env bash
# Generated from the frozen runbook docs/real-world-validation/v0.5.0/apache-airflow/runbook.md (blocks 1-10, verbatim) at candidate aa04a15.
# Deviations: RUN_DIR fixed; NEO4J_PASSWORD from a 0600 file; the v0.3 readiness helpers the
# runbook names, with their bare 'docker compose' calls routed through frozen_compose (the
# frozen rule; a bare call would miss the fixed project name); window bounds saved to files.
export AIP_CHECKOUT=/home/michael/code/ArchitectureIntelligencePlatform   # frozen in profile.md
export DOSSIER="$AIP_CHECKOUT/docs/real-world-validation/v0.5.0/apache-airflow"
export RUNTIME="$DOSSIER/runtime"
export RUN_DIR=/tmp/claude-1001/-home-michael-code-ArchitectureIntelligencePlatform/dea4adeb-9305-40aa-944d-829d6415b869/scratchpad/i5-s7/airflow
# Every Compose call goes through frozen_compose (PR #243 review). It uses exactly the frozen
# file, a fixed project name and no env file. So it ignores any gitignored .env (which could set
# COMPOSE_FILE) and any docker-compose.override.yml; the clean-checkout gate can see neither.
frozen_compose() {
  docker compose -p airflow-i5 --project-directory "$RUNTIME" -f "$RUNTIME/docker-compose.yml" \
    --env-file /dev/null "$@"
}
export NEO4J_PASSWORD="$(cat /tmp/claude-1001/-home-michael-code-ArchitectureIntelligencePlatform/dea4adeb-9305-40aa-944d-829d6415b869/scratchpad/i5-s7/airflow/.neo4j-password)"
export FERNET_KEY="$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")"
echo '==> runbook block 2'
set -euo pipefail
cd "$AIP_CHECKOUT"
[ "$(pwd -P)" = "$AIP_CHECKOUT" ]                         # the one frozen absolute location (I5 §12)
[ -z "$(git status --porcelain)" ] || { echo "checkout is not clean" >&2; exit 1; }
export AIP_CANDIDATE_SHA="$(git rev-parse HEAD)"
echo "$AIP_CANDIDATE_SHA" | grep -Eq '^[0-9a-f]{40}$'
echo "$AIP_CANDIDATE_SHA" > "$RUN_DIR/candidate-sha"

# The upstream-supplied OpenAPI is byte-identical to the pin (profile.md).
curl -sSfL -o "$RUN_DIR/openapi.yml" \
  https://raw.githubusercontent.com/apache/airflow/3adbbe1c58e4532df1964cb7794805e763816ee8/airflow-core/src/airflow/api_fastapi/core_api/openapi/v2-rest-api-generated.yaml
cmp "$RUN_DIR/openapi.yml" "$RUNTIME/declarations/airflow-apiserver/openapi.yml"
echo '==> runbook block 3'
cd "$RUNTIME"
: "${NEO4J_PASSWORD:?}" "${FERNET_KEY:?}" "${AIP_CANDIDATE_SHA:?}"
unset COMPOSE_PROFILES   # no extra profiles; frozen_compose already fixes the file and ignores .env

# PR #242 review: the run must mount exactly this dossier's frozen Dag directory. The Compose file
# has no environment override for it, and this check proves it on the resolved configuration.
[ "$(frozen_compose config --format json | jq -r '
    [.services[] | .volumes[]? | select(.target == "/opt/airflow/dags") | .source] | unique | .[]')"   = "$RUNTIME/dags" ] || { echo "Dag mount is not $RUNTIME/dags" >&2; exit 1; }

frozen_compose pull --ignore-buildable   # every third-party image is referenced as tag@digest
echo '==> runbook block 4'
frozen_compose down -v            # I5 §11: every run begins from clean AIP and upstream state
frozen_compose build --no-cache architecture-intelligence
docker image inspect --format '{{.Id}}' "aip-i5-candidate:$AIP_CANDIDATE_SHA" > "$RUN_DIR/aip-image"
echo '==> runbook block 5'
frozen_compose up -d --no-build --force-recreate --scale airflow-worker=2

check_image() {  # <container id> <expected image id>
  local actual
  actual="$(docker inspect --format '{{.Image}}' "$1")"
  [ "$actual" = "$2" ] || { echo "$1 runs $actual, expected $2" >&2; exit 1; }
}
check_image "$(frozen_compose ps -q architecture-intelligence)" "$(cat "$RUN_DIR/aip-image")"
[ "$(frozen_compose exec -T architecture-intelligence printenv AIP_BUILD_REVISION)" = \
  "$AIP_CANDIDATE_SHA" ]
[ "$(frozen_compose ps -q airflow-worker | wc -l)" -eq 2 ]

# Every other image is referenced by digest in docker-compose.yml, so Docker cannot run other
# bytes. Record them anyway.
frozen_compose images --format json > "$RUN_DIR/compose-images.json"
[ -z "$(git -C "$AIP_CHECKOUT" status --porcelain)" ]   # still the clean candidate
echo '==> readiness (v0.3 helpers)'
wait_for_http() {
  local name="$1" url="$2" timeout="${3:-180}" waited=0
  until curl -sf "$url" >/dev/null 2>&1; do
    waited=$((waited + 2))
    if [ "$waited" -ge "$timeout" ]; then
      echo "$name did not become ready within ${timeout}s ($url) - see: docker compose logs $name" >&2
      return 1
    fi
    sleep 2
  done
  echo "$name ready after ${waited}s"
}
wait_for_tcp() {
  local name="$1" host="$2" port="$3" timeout="${4:-60}" waited=0
  until (exec 3<>"/dev/tcp/$host/$port") 2>/dev/null; do
    waited=$((waited + 2))
    if [ "$waited" -ge "$timeout" ]; then
      echo "$name did not open $host:$port within ${timeout}s - see: docker compose logs $name" >&2
      return 1
    fi
    sleep 2
  done
  exec 3<&- 2>/dev/null || true
  echo "$name ready after ${waited}s"
}
wait_for_container_healthy() {
  local container_id="$1" label="$2" timeout="${3:-180}" waited=0
  until [ "$(docker inspect -f '{{.State.Health.Status}}' "$container_id" 2>/dev/null)" = "healthy" ]; do
    waited=$((waited + 2))
    if [ "$waited" -ge "$timeout" ]; then
      # `$label` (e.g. "airflow-worker (<id>)") is a diagnostic string, not a `docker compose logs`
      # target - use the plain `docker logs` form against the actual container ID instead (PR #45
      # final re-review non-blocking follow-up 1).
      echo "$label did not become healthy within ${timeout}s - see: docker logs $container_id" >&2
      return 1
    fi
    sleep 2
  done
  echo "$label healthy after ${waited}s"
}
wait_for_service_healthy() {
  local service="$1" expected_count="$2" timeout="${3:-180}"
  local ids
  ids="$(frozen_compose ps --all --quiet "$service")"
  local actual_count
  actual_count="$(printf '%s\n' "$ids" | grep -c . || true)"
  if [ "$actual_count" -ne "$expected_count" ]; then
    echo "$service: expected exactly $expected_count container(s), found $actual_count - see: docker compose ps --all $service" >&2
    return 1
  fi
  local id state
  for id in $ids; do
    state="$(docker inspect -f '{{.State.Status}}' "$id" 2>/dev/null)"
    case "$state" in
      exited|dead)
        echo "$service ($id) is $state, not starting - see: docker logs $id" >&2
        return 1
        ;;
    esac
    wait_for_container_healthy "$id" "$service ($id)" "$timeout"
  done
}
wait_for_dag_registered() {
  local dag_id="$1" timeout="${2:-120}" waited=0
  until frozen_compose exec -T airflow-scheduler airflow dags details "$dag_id" >/dev/null 2>&1; do
    waited=$((waited + 2))
    if [ "$waited" -ge "$timeout" ]; then
      echo "$dag_id was not registered within ${timeout}s - see: docker compose logs airflow-dag-processor" >&2
      return 1
    fi
    sleep 2
  done
  echo "$dag_id registered after ${waited}s"
}
wait_for_http architecture-intelligence http://localhost:8000/health
wait_for_http airflow-apiserver         http://localhost:8080/api/v2/monitor/health
wait_for_tcp  otel-collector            localhost 4318
wait_for_service_healthy airflow-scheduler     1
wait_for_service_healthy airflow-dag-processor 1
wait_for_service_healthy airflow-triggerer     1
wait_for_service_healthy airflow-worker        2
wait_for_dag_registered i3_validation
echo '==> runbook block 6'
curl -sf -X POST http://localhost:8000/api/import | tee "$RUN_DIR/import.json" | jq .
echo '==> runbook block 7'
WINDOW_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
API_URL=http://localhost:8080 ./traffic.sh
echo '==> runbook block 8'
sleep 15   # longer than otel-collector-config.yaml's 5s batch timeout
RECEIVED=0
for i in $(seq 1 15); do
  RECEIVED="$(frozen_compose logs --since "$WINDOW_START" architecture-intelligence 2>/dev/null \
    | grep -c 'POST /v1/traces HTTP/1.1" 200' || true)"
  [ "${RECEIVED:-0}" -gt 0 ] && break
  sleep 2
done
[ "${RECEIVED:-0}" -gt 0 ] || { echo "no /v1/traces ingestion since $WINDOW_START" >&2; exit 1; }
WINDOW_END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "environment=airflow-i5 window_start=$WINDOW_START window_end=$WINDOW_END"
echo "$WINDOW_START" > "$RUN_DIR/window-start"; echo "$WINDOW_END" > "$RUN_DIR/window-end"
echo '==> runbook block 9'
cd "$AIP_CHECKOUT"
uv run python -m real_world_validation capture \
  --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j \
  --environment airflow-i5 --since "$WINDOW_START" --until "$WINDOW_END" \
  --scope-entities "$(uv run python -c "
import yaml
print(','.join(yaml.safe_load(open('$DOSSIER/expected.yaml'))['scope']['entities']))")" \
  --scope-relation-types PROVIDES,CALLS,SENDS,PUBLISHES_TO,RECEIVES_FROM \
  --out "$RUN_DIR/actual.yaml"
echo '==> runbook block 10'
uv run python -m real_world_validation compare \
  --expected "$DOSSIER/expected.yaml" \
  --actual   "$RUN_DIR/actual.yaml" | tee "$RUN_DIR/compare.txt"
echo '==> DONE (stack left running for public-surfaces and manual checks)'
