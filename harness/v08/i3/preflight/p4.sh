#!/usr/bin/env bash
# P4 (I3 spec §4): Kafka runs, and its advertised listener answers from a Compose container and from
# a k3d workload. The probe pod is removed by --rm; no other pod is touched.
source "$(dirname "$0")/../lib.sh"
require "the Sokol111 Redpanda container runs" -- docker exec redpanda rpk cluster health
record P4 kafka-up -- frozen_compose up -d kafka
record P4 from-compose -- ktool "$KAFKA" kafka-broker-api-versions.sh ||
  stop "P4: kafka:29092 does not answer from a Compose container"
KAFKA_IMAGE="$(sed -n 's/^    image: \(apache\/kafka:.*\)$/\1/p' "$ENV_DIR/docker-compose.i3.yml" | head -1)"
record P4 from-k3d -- kubectl -n dev run aip-i3-kafka-probe --rm -i --restart=Never \
  --image="$KAFKA_IMAGE" --command -- /opt/kafka/bin/kafka-broker-api-versions.sh \
  --bootstrap-server "$KAFKA" || stop "P4: kafka:29092 does not answer from a k3d pod"
echo "P4 PASSED"
