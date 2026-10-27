#!/usr/bin/env bash
# v0.8 I3 §7: one consumer-state capture through harness/kafka-capture/capture.py, with the ground
# truth G (describe of each allow-listed group) just before and G' just after it, as in v0.7.2.
#   capture.sh c1-prime   Redpanda, the four C1 groups, before step 1
#   capture.sh a-r        Redpanda, the same four groups, after step 9
#   capture.sh a-k        Kafka, Catalog and Image, after step 9
# The capture lands in $I3_RAW_DIR/../captures/<name>/kafka-consumer-state.json.
source "$(dirname "$0")/lib.sh"
NAME="${1:?capture name: c1-prime, a-r or a-k}"
C1_GROUPS=(ecommerce-catalog-service ecommerce-category-query-service ecommerce-image-service
  ecommerce-product-query-service)
case "$NAME" in
  c1-prime) NN=C1p BROKER_ID=kafka:sokol111-local HOST_BOOTSTRAP=localhost:9092 GROUPS_=("${C1_GROUPS[@]}") ;;
  a-r) NN=AR BROKER_ID=kafka:sokol111-local HOST_BOOTSTRAP=localhost:9092 GROUPS_=("${C1_GROUPS[@]}") ;;
  a-k) NN=AK BROKER_ID=kafka:sokol111-kafka HOST_BOOTSTRAP=localhost:19092
    GROUPS_=(ecommerce-catalog-service ecommerce-image-service) ;;
  *) stop "unknown capture $NAME" ;;
esac
if [[ "$NAME" != c1-prime ]]; then
  require "step 9 passed" -- passed 09-image-service-lag
  require "the after-wave declarations are committed" -- \
    git -C "$REPO" diff --quiet HEAD -- docs/specifications/0.8.0/i3-evidence/declarations
fi

ground_truth() {  # ground_truth LABEL: describe every allow-listed group on the capture's broker
  local label="$1" group
  for group in "${GROUPS_[@]}"; do
    if [[ "$BROKER_ID" == kafka:sokol111-local ]]; then
      record "$NN" "$label-$group" -- rpk group describe "$group"
    else
      # The offset rows (--describe) and the group state (--describe --state).
      record "$NN" "$label-$group" -- ktool "$KAFKA" kafka-consumer-groups.sh --describe --group "$group"
      record "$NN" "$label-$group-state" -- ktool "$KAFKA" kafka-consumer-groups.sh --describe --state \
        --group "$group"
    fi
  done
}

OUT="$RAW/../captures/$NAME"
mkdir -p "$OUT"
group_args=()
for group in "${GROUPS_[@]}"; do group_args+=(--group "$group"); done
ground_truth g
if [[ "$NAME" == a-r ]]; then
  # §7 moved groups: Catalog and Image read Empty or Dead on Redpanda; a missing group stops the run.
  cat "$RAW/AR-g-ecommerce-catalog-service.txt" "$RAW/AR-g-ecommerce-image-service.txt" >"$RAW/AR-g-moved.txt"
  check AR moved-state --deadline "$GROUP_STATE_DEADLINE_SECONDS" -- state --describe "$RAW/AR-g-moved.txt" --format rpk \
    --group ecommerce-catalog-service --group ecommerce-image-service --allow Empty --allow Dead
fi
record "$NN" capture -- env KAFKA_BOOTSTRAP_SERVERS="$HOST_BOOTSTRAP" PYTHONPATH="$REPO" \
  uv run --project "$REPO" --with confluent-kafka==2.16.0 python "$REPO/harness/kafka-capture/capture.py" \
  --broker-id "$BROKER_ID" --environment local "${group_args[@]}" --out "$OUT/kafka-consumer-state.json"
ground_truth g-prime
# checks.json holds every verdict so far, including this capture's (rewritten after each capture).
python3 "$I3_DIR/checker.py" collect "$RAW" --out "$RAW/../checks.json"
echo "capture $NAME done"
