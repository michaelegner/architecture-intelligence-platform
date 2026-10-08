#!/usr/bin/env bash
# v0.6.2 Pitstop LIVE demo (spec §4.3): a continuously running, instrumented Pitstop with a controlled traffic
# generator, a Collector and AIP, all in one local Compose project.
#
#   PITSTOP_FORK_DIR=/path/to/pitstop-fork examples/pitstop-demo/run.sh --live         start (builds the images)
#   examples/pitstop-demo/run.sh --live --check [--date YYYY-MM-DD]                    check a completed UTC day
#   examples/pitstop-demo/run.sh --live --down                                         stop and delete everything
#
# Needs docker (Compose v2), curl and the instrumented private Pitstop fork (PITSTOP_FORK_DIR; commit 15b21c6 or
# later, see PROVENANCE.md). Answers refer to the last COMPLETED UTC day, so the first one is available after the
# next UTC midnight: --check says so until then. Not a replay: see run.sh for that.
set -euo pipefail

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$DEMO_DIR/../.." && pwd)"
RUN_DIR="$REPO_ROOT/.aip-pitstop-live"
AIP_URL="http://localhost:8000"
ENVIRONMENT="pitstop-demo"
SERVICE_ID="service:workshop-management-api"
PROJECT="aip-pitstop-live"
SERVICES="vehiclemanagementapi customermanagementapi workshopmanagementapi auditlogservice invoiceservice reportingservice notificationservice timeservice workshopmanagementeventhandler"

compose() {
  docker compose -p "$PROJECT" --project-directory "$REPO_ROOT" \
    -f "$DEMO_DIR/live/docker-compose.yml" --env-file /dev/null "$@"
}

fail() {
  echo "error: $*" >&2
  exit 1
}

usage() {
  echo "usage: $0 | --check [--date YYYY-MM-DD] | --down" >&2
  exit 2
}

# ---- --down: by Compose's own project labels, so it needs neither the fork directory nor any compose file ----
# (a plain `docker compose -p ... down` would resolve the project against whatever compose file the current
# directory holds; the AIP repository root has one of its own). Containers go with their anonymous volumes, then
# the project's networks and named volumes.
if [[ "${1:-}" == "--down" ]]; then
  [[ $# -eq 1 ]] || usage
  label="label=com.docker.compose.project=$PROJECT"
  mapfile -t containers < <(docker ps -aq --filter "$label")
  [[ ${#containers[@]} -eq 0 ]] || docker rm -f -v "${containers[@]}" >/dev/null
  mapfile -t networks < <(docker network ls -q --filter "$label")
  [[ ${#networks[@]} -eq 0 ]] || docker network rm "${networks[@]}" >/dev/null
  mapfile -t volumes < <(docker volume ls -q --filter "$label")
  [[ ${#volumes[@]} -eq 0 ]] || docker volume rm "${volumes[@]}" >/dev/null
  rm -rf "$RUN_DIR"
  echo "Live demo stopped and its data deleted."
  exit 0
fi

MODE=start
CHECK_DATE=""
case "${1:-}" in
  "") ;;
  --check)
    MODE=check
    shift
    if [[ "${1:-}" == "--date" ]]; then
      [[ -n "${2:-}" ]] || usage
      CHECK_DATE="$2"
      shift 2
    fi
    [[ $# -eq 0 ]] || usage
    ;;
  *) usage ;;
esac

for tool in docker curl; do
  command -v "$tool" >/dev/null || fail "'$tool' is required"
done
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required"

[[ -n "${PITSTOP_FORK_DIR:-}" ]] || fail "PITSTOP_FORK_DIR must point at the instrumented Pitstop fork (the private fork, commit 15b21c6 or later)"
FORK_SRC="$PITSTOP_FORK_DIR/src"
[[ -f "$FORK_SRC/docker-compose.otel.yml" ]] \
  || fail "$FORK_SRC/docker-compose.otel.yml not found: PITSTOP_FORK_DIR is not the instrumented fork"
export PITSTOP_FORK_DIR

mkdir -p "$RUN_DIR"
if [[ ! -s "$RUN_DIR/neo4j-password" ]]; then
  (umask 077 && head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n' >"$RUN_DIR/neo4j-password")
fi
PITSTOP_DEMO_NEO4J_PASSWORD="$(cat "$RUN_DIR/neo4j-password")"
export PITSTOP_DEMO_NEO4J_PASSWORD
# The instrumented services send their spans to the AIP Collector of this project.
export OTEL_COLLECTOR_ENDPOINT="http://aip-collector:4318"

fence() {
  compose exec -T architecture-intelligence python examples/runtime-demo/read_revision_fence.py --json \
    | tr -dc '0-9'
}

write_context() { # $1 = completed UTC day
  local day="$1" start end
  start="${day}T00:00:00Z"
  end="${day}T23:59:59Z"
  cat >"$RUN_DIR/context.json" <<JSON
{
  "mcp_url": "$AIP_URL/mcp",
  "service_id": "$SERVICE_ID",
  "observation_context": {
    "environment": "$ENVIRONMENT",
    "window_start": "$start",
    "window_end": "$end"
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
"$start" and window_end "$end" (one completed UTC day). Use get_service_dependencies
and get_evidence, and resolve evidence at the snapshot the answer returned; the instance keeps
ingesting, so if get_evidence refuses the snapshot as stale, ask the dependency question again for
the same window and retry, at most three times. AIP has no receiver-side question: the receivers are
the claims in the publisher's answer. Receipt is per messaging destination (the exchange), never per
event type, and AIP holds no payload or field-level knowledge: which receiver reads StartTime or
EndTime is something you must inspect yourself. Keep facts returned by AIP apart from your own
suggestions, and treat every receiver as unknown until inspected.
PROMPT
}

# ---- --check ---------------------------------------------------------------------------------------------------
if [[ "$MODE" == "check" ]]; then
  [[ -s "$RUN_DIR/live-started-on" ]] || fail "the live demo is not running (no $RUN_DIR/live-started-on); start it first"
  started_on="$(cat "$RUN_DIR/live-started-on")"
  day="${CHECK_DATE:-$(date -u -d yesterday +%F)}"
  [[ "$day" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || fail "--date must be YYYY-MM-DD"
  today="$(date -u +%F)"
  if [[ ! "$day" < "$today" ]]; then
    echo "No completed window yet: $day is not wholly in the past (UTC today is $today)."
    exit 3
  fi
  if [[ "$day" < "$started_on" ]]; then
    echo "No completed window yet: the live demo started on $started_on (UTC), so $day holds no traffic."
    echo "The first completed UTC day is $started_on, available after UTC midnight."
    exit 3
  fi
  echo "==> Checking the WorkshopManagementAPI answer for the completed UTC day $day"
  compose exec -T architecture-intelligence python pitstop/check_ready.py --live --date "$day" \
    >"$RUN_DIR/dependencies.json" || { cat "$RUN_DIR/dependencies.json" >&2; exit 1; }
  write_context "$day"
  cat <<DONE

Live demo check passed for the completed UTC day $day.

  MCP server:  $AIP_URL/mcp   (standard negotiated MCP, no API key needed)
  Window:      $ENVIRONMENT, ${day}T00:00:00Z to ${day}T23:59:59Z

Agent prompt (also in $RUN_DIR/prompt.txt):

$(sed 's/^/  /' "$RUN_DIR/prompt.txt")
DONE
  exit 0
fi

# ---- start -------------------------------------------------------------------------------------------------------
if [[ -n "$(compose ps -q 2>/dev/null)" ]]; then
  fail "the live demo is already running; use '$0 --down' first"
fi
if (exec 3<>"/dev/tcp/127.0.0.1/8000") 2>/dev/null; then
  fail "port 8000 is in use (the other demos use it too); stop it first"
fi

build_fork_images() {
  local missing=0 service
  for service in $SERVICES; do
    docker image inspect "pitstop/$service:1.0-otel" >/dev/null 2>&1 || missing=1
  done
  if [[ "$missing" -eq 0 ]]; then
    return
  fi
  echo "==> Building the instrumented Pitstop images (first run; several minutes)"
  "$FORK_SRC/scripts/PackInfrastructureMessaging.sh"
  docker build -t pitstop-dotnet-sdk-base:1.0 "$FORK_SRC" -f "$FORK_SRC/dotnet-sdk-base-dockerfile"
  docker build -t pitstop-dotnet-runtime-base:1.0 "$FORK_SRC" -f "$FORK_SRC/dotnet-runtime-base-dockerfile"
  docker build -t pitstop-dotnet-aspnet-base:1.0 "$FORK_SRC" -f "$FORK_SRC/dotnet-aspnet-base-dockerfile"
  # shellcheck disable=SC2086 # the service list is intentionally word-split
  docker compose -f "$FORK_SRC/docker-compose.yml" -f "$FORK_SRC/docker-compose.otel.yml" build $SERVICES
}
build_fork_images

echo "==> Starting AIP, Neo4j and the OpenTelemetry Collector (first run builds the AIP image)"
compose up -d --build --wait architecture-intelligence neo4j aip-collector

echo "==> Importing the nine operator-authored AsyncAPI overlays (all or nothing) BEFORE any span can arrive"
curl -sS --fail-with-body -X POST "$AIP_URL/api/import" -o "$RUN_DIR/import.json" \
  || fail "import failed: $(cat "$RUN_DIR/import.json" 2>/dev/null)"
compose exec -T architecture-intelligence python pitstop/check_ready.py --import-only <"$RUN_DIR/import.json" \
  || fail "the import differs from the nine accepted overlays"

date -u +%F >"$RUN_DIR/live-started-on"
date -u +%FT%TZ >"$RUN_DIR/live-started-at"
before="$(fence)"

echo "==> Starting the instrumented Pitstop stack and the traffic generator"
compose up -d

echo "==> Waiting for the first spans to be ingested (Pitstop initialises its databases first; up to 15 minutes)"
current="$before"
for _ in $(seq 1 300); do
  sleep 3
  current="$(fence)" || current="$before"
  [[ -n "$current" && "$current" != "$before" ]] && break
done
[[ -n "$current" && "$current" != "$before" ]] \
  || fail "no span was ingested within 15 minutes (see: docker compose -p $PROJECT logs traffic-generator aip-collector)"

cat <<DONE

Pitstop LIVE demo is running (instrumented Pitstop -> Collector -> AIP; a cycle every ${TRAFFIC_INTERVAL_SECONDS:-600}s).

  MCP server:  $AIP_URL/mcp   (standard negotiated MCP, no API key needed)
  Started:     $(cat "$RUN_DIR/live-started-at")

Answers refer to a COMPLETED UTC day. The first one is $(cat "$RUN_DIR/live-started-on"), available after UTC midnight:

  $0 --check          (checks yesterday and prints the agent prompt)

Stop and delete everything with: $0 --down
DONE
