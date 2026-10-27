#!/usr/bin/env bash
# Step 1 (parent §4.2): Kafka up; the three catalog topics created empty on Kafka with the Redpanda
# partition counts; flows A and B configured and both stopped; allow-lists disjoint.
source "$(dirname "$0")/../lib.sh"
require "the preflight passed" -- passed P1a-p1a
require "P3 passed" -- passed P3-p3
require "P4 passed" -- recorded_ok P4-from-k3d
require "P5 passed" -- passed P5-sync
require "flow A is stopped" -- not_running mm2-flow-a
require "flow B is stopped" -- not_running mm2-flow-b
for topic in catalog.product.events catalog.category.events catalog.attribute.events; do
  record 01 "redpanda-$topic" -- rpk topic describe "$topic"
  partitions="$(awk '$1 == "PARTITIONS" {print $2}' "$RAW/01-redpanda-$topic.txt")"
  [[ "$partitions" =~ ^[0-9]+$ ]] || stop "no partition count for $topic on Redpanda"
  record 01 "kafka-create-$topic" -- ktool "$KAFKA" kafka-topics.sh --create --topic "$topic" \
    --partitions "$partitions" --replication-factor 1
done
record 01 kafka-end -- ktool "$KAFKA" kafka-get-offsets.sh --topic-partitions 'catalog\..*'
python3 -c 'import sys; sys.exit(0 if all(l.rsplit(":",1)[1].strip()=="0" for l in open(sys.argv[1]) if l.strip()) else 1)' \
  "$RAW/01-kafka-end.txt" || stop "a catalog topic on Kafka is not empty"
echo "step 1 done"
