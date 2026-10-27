#!/usr/bin/env bash
# P5 (I3 spec §4): the group-offset-sync probe on the separate probe flow, never on flow A or B.
# Redpanda source, Kafka target, no active consumer on Kafka: MirrorMaker 2 must install the
# translated committed offset of the probe group and emit a decodable checkpoint.
# Ownership: every name the teardown may delete must be absent before the probe starts, so the
# teardown removes only what this attempt created. It runs on exit, also when the probe stops early.
source "$(dirname "$0")/../lib.sh"
TOPIC=aip-probe.events
GROUP=aip-probe-group
REDPANDA_TOPICS=("$TOPIC" mm2-offset-syncs.kprobe.internal)
KAFKA_TOPICS=("$TOPIC" mm2-probe-configs mm2-probe-offsets mm2-probe-status rpprobe.checkpoints.internal)
require "flow A is stopped" -- not_running mm2-flow-a
require "flow B is stopped" -- not_running mm2-flow-b
require "no probe container exists, running or stopped" -- no_container mm2-probe
for topic in "${REDPANDA_TOPICS[@]}"; do
  require "Redpanda has no topic $topic yet" -- absent_redpanda_topic "$topic"
done
for topic in "${KAFKA_TOPICS[@]}"; do
  require "Kafka has no topic $topic yet" -- absent_kafka_topic "$topic"
done
require "Redpanda has no group $GROUP yet" -- absent_redpanda_group "$GROUP"
require "Kafka has no group $GROUP yet" -- absent_kafka_group "$GROUP"

teardown() {
  record P5 probe-stop -- frozen_compose --profile mm2-probe rm -sf mm2-probe || true
  local topic
  for topic in "${REDPANDA_TOPICS[@]}"; do
    if ! absent_redpanda_topic "$topic"; then
      record P5 "rm-redpanda-$topic" -- rpk topic delete "$topic" || true
    fi
  done
  for topic in "${KAFKA_TOPICS[@]}"; do
    if ! absent_kafka_topic "$topic"; then
      record P5 "rm-kafka-$topic" -- ktool "$KAFKA" kafka-topics.sh --delete --topic "$topic" || true
    fi
  done
  if ! absent_redpanda_group "$GROUP"; then
    record P5 rm-redpanda-group -- rpk group delete "$GROUP" || true
  fi
  if ! absent_kafka_group "$GROUP"; then
    record P5 rm-kafka-group -- ktool "$KAFKA" kafka-consumer-groups.sh --delete --group "$GROUP" || true
  fi
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
