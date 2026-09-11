#!/usr/bin/env bash
# Runnable short path through the v0.4.0 MCP hero demo (examples/runtime-demo/hero-demo.md), plus
# (v0.4.2 I2) a --serve mode that prepares the same deterministic state for an external coding-agent
# MCP client instead of the scripted direct walkthrough - see
# docs/specifications/0.4.2/i2-client-ready-demo-and-documentation.md.
#
# Does exactly what hero-demo.md does by hand - bring up AIP without the live traffic generator,
# import the declared architecture, seed one timestamp-frozen OTLP batch, then drive
# tools/list -> get_architecture_drift -> get_evidence over plain HTTP/JSON-RPC - and prints the
# interesting parts of each answer. Read hero-demo.md for what every step means and why the
# observation window below is a fixed constant rather than "now - 24h".
#
# Usage:
#   examples/runtime-demo/mcp-demo.sh          # run the full scripted MCP walkthrough
#   examples/runtime-demo/mcp-demo.sh --serve  # prepare the same state, stop before any MCP call
#   examples/runtime-demo/mcp-demo.sh --down   # tear the stack down (docker compose down -v)
#
# Requires docker (with compose), curl and jq, and a .env at the repo root (cp .env.example .env).
# --serve additionally requires no host Python: fixture classification runs inside the already
# running architecture-intelligence container (spec §15.3).

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
CLIENT_GUIDE_PATH="examples/mcp-clients/README.md"

MCP_HEADERS=(
  -H 'content-type: application/json'
  -H 'accept: application/json, text/event-stream'
  -H 'mcp-protocol-version: 2026-07-28'
)
META='{"io.modelcontextprotocol/protocolVersion": "2026-07-28", "io.modelcontextprotocol/clientCapabilities": {}}'

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

# --- argument parsing (spec §10: only these exact shapes are accepted) --------------------------

MODE="full"
if [[ $# -gt 1 ]]; then
  echo "error: too many arguments (usage: mcp-demo.sh [--serve|--down])" >&2
  exit 2
fi
case "${1:-}" in
  "") MODE="full" ;;
  --serve) MODE="serve" ;;
  --down) MODE="down" ;;
  *)
    echo "error: unknown argument: ${1} (usage: mcp-demo.sh [--serve|--down])" >&2
    exit 2
    ;;
esac

if [[ "${MODE}" == "down" ]]; then
  step "Tearing the demo stack down"
  "${COMPOSE[@]}" down -v
  exit 0
fi

# --- phase functions (spec §50) -------------------------------------------------------------

validate_prerequisites() {
  for tool in docker curl jq; do
    command -v "$tool" >/dev/null || { echo "error: '$tool' is required but not installed" >&2; exit 1; }
  done
  [[ -f "${REPO_ROOT}/.env" ]] || { echo "error: no .env at ${REPO_ROOT} - run: cp .env.example .env" >&2; exit 1; }
}

start_stack() {
  # Bring up AIP + neo4j + collector, but deliberately NOT the live traffic-generator service: the
  # only evidence in the graph must be the frozen batch seeded by prepare_fixture_if_empty.
  step "Starting architecture-intelligence, neo4j and otel-collector"
  "${COMPOSE[@]}" up -d --build architecture-intelligence otel-collector
  # Built now, not by the `run --build` below: a later build would recreate the already-running
  # architecture-intelligence container in the middle of the demo.
  "${COMPOSE[@]}" build traffic-generator
}

wait_for_core_services() {
  # docker-compose.demo.yml already gates architecture-intelligence's start on neo4j's own
  # healthcheck (depends_on: condition: service_healthy), so neo4j is healthy by the time `up -d`
  # above returns - this step exists to make that readiness gate explicit and independently
  # verifiable (spec §7 item 7), not to add a second competing wait mechanism.
  step "Confirming neo4j is healthy"
  for _ in $(seq 1 30); do
    status="$("${COMPOSE[@]}" ps neo4j --format '{{.Health}}' 2>/dev/null || true)"
    [[ "${status}" == "healthy" ]] && break
    sleep 2
  done
  [[ "${status}" == "healthy" ]] || { echo "error: neo4j did not become healthy" >&2; exit 1; }

  step "Waiting for ${AIP_URL}/health"
  for _ in $(seq 1 60); do
    curl -sf "${AIP_URL}/health" >/dev/null && break
    sleep 2
  done
  curl -sf "${AIP_URL}/health" >/dev/null || { echo "error: AIP did not become healthy within 120s" >&2; exit 1; }
}

# Canonical invocation boundary (spec §15.3): the checker runs inside the already-running
# architecture-intelligence container, never on the host - no host Python is required.
run_fixture_checker() {
  local output
  if ! output="$("${COMPOSE[@]}" exec -T architecture-intelligence python examples/runtime-demo/check_fixture_state.py --json 2>/tmp/aip-fixture-checker.err)"; then
    echo "error: the fixture-state checker failed to run" >&2
    tail -c 2000 /tmp/aip-fixture-checker.err >&2 || true
    exit 1
  fi
  printf '%s' "${output}"
}

wait_for_observed_relations() {
  # The collector batches for 5s before forwarding, so the seeded spans reach AIP shortly *after*
  # seed_frozen_evidence.py exits - ask the graph, don't guess with a fixed sleep.
  local relations_url="${AIP_URL}/api/runtime/relations?environment=${ENVIRONMENT}&since=${WINDOW_START}&until=${WINDOW_END}"
  local observed=0
  for _ in $(seq 1 30); do
    observed="$(curl -sf "${relations_url}" | jq '.relations | length')" || observed=0
    [[ "${observed}" -gt 0 ]] && break
    sleep 2
  done
  [[ "${observed}" -gt 0 ]] || {
    echo "error: frozen telemetry was submitted but the expected observed dependency did not appear within 60s" >&2
    exit 1
  }
  echo "observed relations in [${WINDOW_START}, ${WINDOW_END}): ${observed}"
}

fail_partial_fixture() {
  local check_result="$1"
  echo "error: the deterministic demo fixture is PARTIAL_OR_INCOMPATIBLE - it must be recreated, not repaired" >&2
  printf '%s' "${check_result}" | jq '.mismatches' >&2
  echo "Tear down and retry: examples/runtime-demo/mcp-demo.sh --down" >&2
  exit 1
}

# Shared by both modes (spec §51: "One deterministic demo state, two consumers"). Classifies the
# fixture once; imports + seeds only from EMPTY; never mutates an already-COMPLETE fixture; fails
# non-zero without any implicit repair from PARTIAL_OR_INCOMPATIBLE.
prepare_fixture_if_empty() {
  step "Classifying the deterministic fixture state"
  local check_result classification
  check_result="$(run_fixture_checker)"
  classification="$(printf '%s' "${check_result}" | jq -r '.classification')"
  echo "fixture classification: ${classification}"

  case "${classification}" in
    EMPTY)
      step "Importing the declared architecture (POST /api/import)"
      curl -sf -X POST "${AIP_URL}/api/import" | jq '{imported_services: (.services | keys)}'

      step "Seeding frozen runtime evidence"
      "${COMPOSE[@]}" run --rm --no-deps traffic-generator python seed_frozen_evidence.py

      step "Waiting for the seeded evidence to land in the graph"
      wait_for_observed_relations

      step "Re-checking the fixture state after seeding"
      check_result="$(run_fixture_checker)"
      classification="$(printf '%s' "${check_result}" | jq -r '.classification')"
      [[ "${classification}" == "COMPLETE" ]] || fail_partial_fixture "${check_result}"
      ;;
    COMPLETE)
      echo "fixture is already COMPLETE - skipping declaration re-import and telemetry reseed"
      ;;
    PARTIAL_OR_INCOMPATIBLE)
      fail_partial_fixture "${check_result}"
      ;;
    *)
      echo "error: unexpected fixture classification: ${classification}" >&2
      exit 1
      ;;
  esac
}

print_client_ready_summary() {
  cat <<EOF

AIP demo is ready.

MCP endpoint:
${AIP_URL}/mcp

Service Explorer:
${AIP_URL}

Service:
${SERVICE_ID}

Environment:
${ENVIRONMENT}

Observation window:
${WINDOW_START}
${WINDOW_END}

Client setup:
${CLIENT_GUIDE_PATH}

Stop demo:
examples/runtime-demo/mcp-demo.sh --down
EOF
}

# --- main ------------------------------------------------------------------------------------

validate_prerequisites
start_stack
wait_for_core_services
prepare_fixture_if_empty

if [[ "${MODE}" == "serve" ]]; then
  # Stop here - the next MCP caller must be the user's coding-agent client (spec §11), not this
  # script. No tools/list or tools/call is issued past this point.
  print_client_ready_summary
  exit 0
fi

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
