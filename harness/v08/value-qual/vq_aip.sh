#!/usr/bin/env bash
# v0.8 value qualification (spec §6.1): AIP is removed during F- and T- sessions, not stopped.
#   vq_aip.sh RUN_HOME down     remove AIP and its datastore containers (and the graph volume)
#   vq_aip.sh RUN_HOME up       start AIP, import B-R, check the nine I2 §8.1 rows and the snapshot id
#   vq_aip.sh RUN_HOME check    AIP answers, with the nine rows and the recorded snapshot id
# The first `up` records the snapshot id in RUN_HOME/aip-snapshot.txt; every later `up` and `check`
# must give the same id. Needs AIP_IMAGE and AIP_NEO4J_PASSWORD exported (v0.8 README, S1).
set -euo pipefail

VQ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_HOME="$(cd "${1:?RUN_HOME}" && pwd -P)"
ACTION="${2:?up, down or check}"
AIP_URL="http://127.0.0.1:8000"
stop() { echo "STOP: $*" >&2; exit 2; }
compose() { (cd "$RUN_HOME" && docker compose -f docker-compose.aip.yml "$@"); }

check() {
  local answer
  answer="$(curl -fsS -X POST "$AIP_URL/api/binding-picture" -H 'Content-Type: application/json' \
    -d '{"bounded_context_id": "catalog-management", "environment": "local", "broker_ids": ["kafka:sokol111-local"], "limit": 200}')" ||
    stop "AIP does not answer"
  python3 "$VQ_DIR/vq_aip_check.py" "$RUN_HOME/aip-snapshot.txt" <<<"$answer"
}

case "$ACTION" in
  down)
    compose down -v
    left="$(docker ps -a --filter "label=com.docker.compose.project=aip-v08-i4-aip" -q)"
    [[ -z "$left" ]] || stop "AIP containers remain: $left"
    echo "AIP removed"
    ;;
  up)
    [[ -f "$RUN_HOME/aip/config.yaml" ]] || stop "run setup_run_home.sh RUN_HOME before first"
    compose up -d
    for _ in $(seq 60); do curl -fsS "$AIP_URL/health" >/dev/null 2>&1 && break; sleep 2; done
    curl -fsS -X POST "$AIP_URL/api/import" >/dev/null || stop "the import failed"
    check
    ;;
  check) check ;;
  *) stop "unknown action $ACTION" ;;
esac
