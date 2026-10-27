#!/usr/bin/env bash
# P5 (I3 spec §4): the group-offset-sync probe on the separate probe flow, never on flow A or B.
# Redpanda source, Kafka target, no active consumer on Kafka: MirrorMaker 2 must install the
# translated committed offset of the probe group and emit a decodable checkpoint. Then everything
# the probe created - and only that - is removed, also when the probe stops early.
source "$(dirname "$0")/../lib.sh"
TOPIC=aip-probe.events
GROUP=aip-probe-group
require "flow A is stopped" -- not_running mm2-flow-a
require "flow B is stopped" -- not_running mm2-flow-b
require "the probe topic does not exist yet" -- absent_redpanda_topic "$TOPIC"

# Teardown of exactly what the probe created, each name verified before it is removed. The probe
# topic did not exist before (precondition); the other names belong to the probe flow only.
teardown() {
  record P5 probe-stop -- frozen_compose --profile mm2-probe rm -sf mm2-probe || true
  local topic
  for topic in "$TOPIC" mm2-offset-syncs.kprobe.internal; do
    if ! absent_redpanda_topic "$topic"; then
      record P5 "rm-redpanda-$topic" -- rpk topic delete "$topic" || true
    fi
  done
  for topic in "$TOPIC" mm2-probe-configs mm2-probe-offsets mm2-probe-status rpprobe.checkpoints.internal; do
    if ktool "$KAFKA" kafka-topics.sh --describe --topic "$topic" >/dev/null 2>&1; then
      record P5 "rm-kafka-$topic" -- ktool "$KAFKA" kafka-topics.sh --delete --topic "$topic" || true
    fi
  done
  record P5 rm-redpanda-group -- rpk group delete "$GROUP" || true
  record P5 rm-kafka-group -- ktool "$KAFKA" kafka-consumer-groups.sh --delete --group "$GROUP" || true
}
trap teardown EXIT

record P5 create-topic -- rpk topic create "$TOPIC" -p 1 -r 1
record P5 produce -- bash -c "printf 'probe-1\nprobe-2\nprobe-3\n' | docker exec -i redpanda rpk topic produce $TOPIC"
record P5 consume -- rpk topic consume "$TOPIC" -g "$GROUP" -n 3
record P5 probe-up -- frozen_compose --profile mm2-probe up -d mm2-probe
p1b P5 mm2-probe kafka

collect_probe() {
  record P5 source-group -- rpk group describe "$GROUP" &&
    record P5 target-group -- ktool "$KAFKA" kafka-consumer-groups.sh --describe --group "$GROUP" &&
    record P5 checkpoints -- dump_topic "$KAFKA" rpprobe.checkpoints.internal CheckpointFormatter &&
    record P5 offset-syncs -- dump_topic "$REDPANDA" mm2-offset-syncs.kprobe.internal OffsetSyncFormatter
}
check P5 sync --collect collect_probe -- handoff --source-groups "$RAW/P5-source-group.txt" \
  --checkpoints "$RAW/P5-checkpoints.txt" --target-groups "$RAW/P5-target-group.txt" \
  --offset-syncs "$RAW/P5-offset-syncs.txt" --group "$GROUP" --topic "$TOPIC"
echo "P5 PASSED"
