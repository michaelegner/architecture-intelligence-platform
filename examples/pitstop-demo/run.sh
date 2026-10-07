#!/usr/bin/env bash
# v0.6.2 Pitstop demo (spec §4.3): one command, a local replay of an authored OTLP fixture.
#
#   examples/pitstop-demo/run.sh          start, import, replay, check, print prompt
#   examples/pitstop-demo/run.sh --down   stop and delete the demo's data
#
# Needs only docker (with Compose) and curl. See README.md and PROVENANCE.md. `--live` (a continuously
# running instrumented Pitstop) is a later increment and is rejected here.
set -euo pipefail

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$DEMO_DIR/../.." && pwd)"
# Run-local state lives outside examples/, which the release golden path pins file by file.
RUN_DIR="$REPO_ROOT/.aip-pitstop-demo"
AIP_URL="http://localhost:8000"
COLLECTOR_URL="http://localhost:4318"
ENVIRONMENT="pitstop-demo"
# One whole UTC day wholly in the past: the only kind of window that is stable under later evidence
# (docs/specifications/0.6.2/i0-hardening.md §4.2). Shared literals with check_ready.CONTEXT.
WINDOW_START="2026-10-06T00:00:00Z"
WINDOW_END="2026-10-06T23:59:59Z"
SERVICE_ID="service:workshop-management-api"

compose() {
  docker compose -p aip-pitstop-demo --project-directory "$REPO_ROOT" \
    -f "$DEMO_DIR/docker-compose.yml" --env-file /dev/null "$@"
}

fail() {
  echo "error: $*" >&2
  exit 1
}

case "${1:-}" in
  --down)
    [[ $# -eq 1 ]] || { echo "usage: $0 [--down]" >&2; exit 2; }
    PITSTOP_DEMO_NEO4J_PASSWORD=unused compose down -v --remove-orphans
    rm -rf "$RUN_DIR"
    echo "Demo stopped and its data deleted."
    exit 0
    ;;
  --live)
    echo "error: --live is not available yet: the live mode needs an instrumented Pitstop fork" >&2
    exit 2
    ;;
  "") ;;
  *)
    echo "usage: $0 [--down]" >&2
    exit 2
    ;;
esac

for tool in docker curl; do
  command -v "$tool" >/dev/null || fail "'$tool' is required"
done
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required"

mkdir -p "$RUN_DIR"
if [[ ! -s "$RUN_DIR/neo4j-password" ]]; then
  (umask 077 && head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n' >"$RUN_DIR/neo4j-password")
fi
PITSTOP_DEMO_NEO4J_PASSWORD="$(cat "$RUN_DIR/neo4j-password")"
export PITSTOP_DEMO_NEO4J_PASSWORD

if [[ -n "$(compose ps -q 2>/dev/null)" ]]; then
  fail "the demo is already running; use '$0 --down' first for a fresh replay"
fi
for port in 8000 4318; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    fail "port $port is in use (the Quarkus and minimal demos also use 8000); stop it first"
  fi
done

echo "==> Starting AIP, Neo4j and the OpenTelemetry Collector (first run builds the AIP image)"
compose up -d --build --wait

echo "==> Importing the nine operator-authored AsyncAPI overlays (all or nothing)"
curl -sS --fail-with-body -X POST "$AIP_URL/api/import" -o "$RUN_DIR/import.json" \
  || fail "import failed: $(cat "$RUN_DIR/import.json" 2>/dev/null)"

fence() {
  compose exec -T architecture-intelligence python examples/runtime-demo/read_revision_fence.py --json \
    | tr -dc '0-9'
}

echo "==> Replaying the authored OpenTelemetry observation window"
before="$(fence)"
curl -sS --fail-with-body -X POST "$COLLECTOR_URL/v1/traces" -H 'content-type: application/json' \
  --data-binary "@$DEMO_DIR/fixtures/otlp.json" >/dev/null || fail "the collector rejected otlp.json"
last=""
for _ in $(seq 1 30); do
  sleep 3
  current="$(fence)"
  if [[ -n "$current" && "$current" != "$before" && "$current" == "$last" ]]; then
    break
  fi
  last="$current"
done
[[ -n "$current" && "$current" != "$before" && "$current" == "$last" ]] \
  || fail "the replayed observations were not ingested within 90s"

# Enforce "nothing is ingesting any more": a later OTLP post would change the graph snapshot and
# stale the evidence references of answers already given. AIP and Neo4j stay up for exploration.
compose stop otel-collector

echo "==> Checking the WorkshopManagementAPI answer against the expected topology"
compose exec -T architecture-intelligence python pitstop/check_ready.py <"$RUN_DIR/import.json" \
  >"$RUN_DIR/dependencies.json" || { cat "$RUN_DIR/dependencies.json" >&2; exit 1; }

cat >"$RUN_DIR/context.json" <<JSON
{
  "mcp_url": "$AIP_URL/mcp",
  "service_id": "$SERVICE_ID",
  "observation_context": {
    "environment": "$ENVIRONMENT",
    "window_start": "$WINDOW_START",
    "window_end": "$WINDOW_END"
  }
}
JSON

cat >"$RUN_DIR/prompt.txt" <<PROMPT
In the Pitstop service WorkshopManagementAPI, replace the StartTime and EndTime fields of the
MaintenanceJobFinished event with a single Duration field: the workshop only needs to report how
long a job took. Plan the change. Before planning, use the AIP MCP server to establish which
messaging destination WorkshopManagementAPI publishes to, which services AIP resolves as receiving
from it, what was observed, and where the evidence stops.

Query service:workshop-management-api with environment "$ENVIRONMENT", window_start
"$WINDOW_START" and window_end "$WINDOW_END" (one whole UTC day). Use get_service_dependencies
and get_evidence, and resolve evidence at the snapshot the answer returned; if get_evidence
refuses the snapshot as stale, ask the dependency question again for the same window and retry,
at most three times. AIP has no receiver-side question: the receivers are the claims in the
publisher's answer. Receipt is per messaging destination (the exchange), never per event type, and
AIP holds no payload or field-level knowledge: which receiver reads StartTime or EndTime is
something you must inspect yourself. Keep facts returned by AIP apart from your own suggestions,
and treat every receiver as unknown until inspected.
PROMPT

cat <<DONE

Pitstop demo is ready (a replay of an authored fixture; nothing is ingesting any more).

  MCP server:  $AIP_URL/mcp   (standard negotiated MCP, no API key needed)
  REST:        $AIP_URL/api/services/$SERVICE_ID/dependencies?environment=$ENVIRONMENT&from=$WINDOW_START&to=$WINDOW_END
  Window:      $ENVIRONMENT, $WINDOW_START to $WINDOW_END

Agent prompt (also in $RUN_DIR/prompt.txt):

$(sed 's/^/  /' "$RUN_DIR/prompt.txt")

Stop and delete the demo's data with: $0 --down
DONE
