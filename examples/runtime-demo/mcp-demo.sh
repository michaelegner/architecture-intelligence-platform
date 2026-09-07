#!/usr/bin/env bash
# Runnable short path through the v0.4.0 MCP hero demo (examples/runtime-demo/hero-demo.md).
#
# Does exactly what that walkthrough does by hand - bring up AIP without the live traffic
# generator, import the declared architecture, seed one timestamp-frozen OTLP batch, then drive
# tools/list -> get_architecture_drift -> get_evidence over plain HTTP/JSON-RPC - and prints the
# interesting parts of each answer. Read hero-demo.md for what every step means and why the
# observation window below is a fixed constant rather than "now - 24h".
#
# Usage:
#   examples/runtime-demo/mcp-demo.sh          # run the demo, leave the stack up
#   examples/runtime-demo/mcp-demo.sh --down   # tear the stack down (docker compose down -v)
#
# Requires docker (with compose), curl and jq, and a .env at the repo root (cp .env.example .env).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE=(docker compose -f "${REPO_ROOT}/docker-compose.demo.yml")
AIP_URL="${AIP_URL:-http://localhost:8000}"

# Frozen to match seed_frozen_evidence.py's SEED_TIMESTAMP (2026-08-26T12:00:00Z). Never derive
# these from wall-clock time - the whole point of the hero demo is a result that does not move.
WINDOW_START="2026-08-26T00:00:00.000000Z"
WINDOW_END="2026-08-27T00:00:00.000000Z"
ENVIRONMENT="demo"
SERVICE_ID="service:order-service"

MCP_HEADERS=(
  -H 'content-type: application/json'
  -H 'accept: application/json, text/event-stream'
  -H 'mcp-protocol-version: 2026-07-28'
)
META='{"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}}'

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

if [[ "${1:-}" == "--down" ]]; then
  step "Tearing the demo stack down"
  "${COMPOSE[@]}" down -v
  exit 0
fi
if [[ $# -gt 0 ]]; then
  echo "error: unknown argument: $1 (usage: mcp-demo.sh [--down])" >&2
  exit 2
fi

for tool in docker curl jq; do
  command -v "$tool" >/dev/null || { echo "error: '$tool' is required but not installed" >&2; exit 1; }
done
[[ -f "${REPO_ROOT}/.env" ]] || { echo "error: no .env at ${REPO_ROOT} - run: cp .env.example .env" >&2; exit 1; }

# 1. Bring up AIP + neo4j + collector, but deliberately NOT the live traffic-generator service:
#    the only evidence in the graph must be the frozen batch seeded in step 3.
step "Starting architecture-intelligence, neo4j and otel-collector"
"${COMPOSE[@]}" up -d --build architecture-intelligence otel-collector
# Built now, not by the `run --build` below: a later build would recreate the already-running
# architecture-intelligence container in the middle of the demo.
"${COMPOSE[@]}" build traffic-generator

step "Waiting for ${AIP_URL}/health"
for _ in $(seq 1 60); do
  curl -sf "${AIP_URL}/health" >/dev/null && break
  sleep 2
done
curl -sf "${AIP_URL}/health" >/dev/null || { echo "error: AIP did not become healthy" >&2; exit 1; }

# 2. Declared architecture: examples/ declares OrderService -> ProductService, SENDS payment-q and
#    SENDS unused-q. LegacyPricingService is declared nowhere.
step "Importing the declared architecture (POST /api/import)"
curl -sf -X POST "${AIP_URL}/api/import" | jq '{imported_services: (.services | keys)}'

# 3. One fixed-timestamp OTLP batch through the real collector -> AIP ingestion path.
step "Seeding frozen runtime evidence"
"${COMPOSE[@]}" run --rm --no-deps traffic-generator python seed_frozen_evidence.py

# The collector batches for 5s before forwarding, so the seeded spans reach AIP shortly *after*
# seed_frozen_evidence.py exits - ask the graph, don't guess with a fixed sleep.
step "Waiting for the seeded evidence to land in the graph"
RELATIONS_URL="${AIP_URL}/api/runtime/relations?environment=${ENVIRONMENT}&since=${WINDOW_START}&until=${WINDOW_END}"
observed=0
for _ in $(seq 1 30); do
  observed="$(curl -sf "${RELATIONS_URL}" | jq '.relations | length')" || observed=0
  [[ "${observed}" -gt 0 ]] && break
  sleep 2
done
[[ "${observed}" -gt 0 ]] || { echo "error: no observed relations arrived within 60s" >&2; exit 1; }
echo "observed relations in [${WINDOW_START}, ${WINDOW_END}): ${observed}"

step "Discovering the tools (tools/list)"
curl -s "${AIP_URL}/mcp" "${MCP_HEADERS[@]}" -H 'mcp-method: tools/list' \
  -d "$(jq -n --argjson meta "$META" '{jsonrpc: "2.0", id: 1, method: "tools/list", params: {_meta: $meta}}')" \
  | jq -r '.result.tools[].name'

step "Asking get_architecture_drift about ${SERVICE_ID}"
DRIFT="$(curl -s "${AIP_URL}/mcp" "${MCP_HEADERS[@]}" \
  -H 'mcp-method: tools/call' -H 'mcp-name: get_architecture_drift' \
  -d "$(jq -n --argjson meta "$META" --arg service "$SERVICE_ID" --arg env "$ENVIRONMENT" \
        --arg wstart "$WINDOW_START" --arg wend "$WINDOW_END" '{
          jsonrpc: "2.0", id: 2, method: "tools/call",
          params: {
            name: "get_architecture_drift",
            arguments: {request: {service_id: $service, observation_context: {environment: $env, window_start: $wstart, window_end: $wend}}},
            _meta: $meta
          }
        }')")"
# Kept in a variable rather than a temp file - a snap-packaged jq cannot read the host's /tmp.
printf '%s' "${DRIFT}" | jq -e '.result.structuredContent' >/dev/null || {
  echo "error: unexpected MCP response:" >&2
  printf '%s\n' "${DRIFT}" >&2
  exit 1
}
printf '%s' "${DRIFT}" | jq '.result.structuredContent
  | {snapshot_id: .snapshot.snapshot_id, outcome, limitations,
     claims: [.claims[] | {dependency: .object.name, via: .delivery.via.name, qualification, evidence_refs}]}'

# 4. Resolve the answer's own opaque evidence references - at the SAME snapshot, so both calls read
#    one immutable graph state.
step "Resolving that answer's evidence_refs with get_evidence (same snapshot)"
curl -s "${AIP_URL}/mcp" "${MCP_HEADERS[@]}" \
  -H 'mcp-method: tools/call' -H 'mcp-name: get_evidence' \
  -d "$(jq -n --argjson meta "$META" \
        --argjson refs "$(printf '%s' "${DRIFT}" | jq -c '.result.structuredContent.evidence_refs')" \
        --arg snapshot "$(printf '%s' "${DRIFT}" | jq -r '.result.structuredContent.snapshot.snapshot_id')" '{
          jsonrpc: "2.0", id: 3, method: "tools/call",
          params: {
            name: "get_evidence",
            arguments: {request: {evidence_refs: $refs, snapshot_id: $snapshot}},
            _meta: $meta
          }
        }')" \
  | jq '[.result.structuredContent.data.records[] | {id, evidence_type, source_type, source_locator}]'

step "Done - the stack is still running"
cat <<EOF
Service Explorer:  ${AIP_URL}/
Full walkthrough:  examples/runtime-demo/hero-demo.md
Tear down with:    examples/runtime-demo/mcp-demo.sh --down
EOF
