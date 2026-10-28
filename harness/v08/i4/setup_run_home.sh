#!/usr/bin/env bash
# v0.8 I4 §5: fills the run home (outside the AIP checkout) for one phase.
#   setup_run_home.sh RUN_HOME kafka    the Kafka-only Compose file in RUN_HOME/kafka/
#   setup_run_home.sh RUN_HOME before   AIP's before-wave profile and inputs (needs package/captures/b-r)
#   setup_run_home.sh RUN_HOME after    AIP's after-wave profile and inputs (needs a-r and a-k); S4 only
# AIP's inputs directory holds exactly one phase: the agent can see AIP's mounts (docker inspect), so
# no after-wave input exists in the run home before S4.
set -euo pipefail
I4_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$I4_DIR/../../.." && pwd)"
SPEC="$REPO/docs/specifications/0.8.0"
RUN_HOME="$(cd "${1:?RUN_HOME}" && pwd -P)"
PHASE="${2:?kafka, before or after}"
stop() { echo "STOP: $*" >&2; exit 2; }
case "$RUN_HOME/" in "$(cd "$REPO" && pwd -P)"/*) stop "$RUN_HOME is inside the AIP checkout" ;; esac

if [[ "$PHASE" == kafka ]]; then
  mkdir -p "$RUN_HOME/kafka"
  cp "$I4_DIR/environment/docker-compose.kafka.yml" "$RUN_HOME/kafka/"
  cp "$I4_DIR/environment/docker-compose.aip.yml" "$RUN_HOME/"
  exit 0
fi
[[ "$PHASE" == before || "$PHASE" == after ]] || stop "unknown phase $PHASE"
INPUTS="$RUN_HOME/aip/inputs"
rm -rf "$INPUTS" && mkdir -p "$INPUTS/declarations" "$INPUTS/mapping"
cp -a "$SPEC/i1-evidence/catalog" "$INPUTS/catalog"
cp "$SPEC/i1-evidence/event-topic-lookup.json" "$INPUTS/"
cp -a "$SPEC/i1-evidence/mapping/sokol111-local" "$INPUTS/mapping/"
if [[ "$PHASE" == before ]]; then
  [[ -f "$RUN_HOME/package/captures/b-r/kafka-consumer-state.json" ]] || stop "capture B-R first"
  cp -a "$SPEC/i1-evidence/declarations/sokol111-local" "$INPUTS/declarations/"
  cp -a "$RUN_HOME/package/captures/b-r" "$INPUTS/b-r"
else
  for name in a-r a-k; do
    [[ -f "$RUN_HOME/package/captures/$name/kafka-consumer-state.json" ]] || stop "capture $name first"
    cp -a "$RUN_HOME/package/captures/$name" "$INPUTS/$name"
  done
  cp -a "$SPEC/i3-evidence/declarations/sokol111-local" "$SPEC/i3-evidence/declarations/sokol111-kafka" \
    "$INPUTS/declarations/"
  cp -a "$SPEC/i1-evidence/mapping/sokol111-kafka" "$INPUTS/mapping/"
fi
cp "$I4_DIR/environment/config.$PHASE.yaml" "$RUN_HOME/aip/config.yaml"
echo "run home ready for the $PHASE-wave AIP"
