#!/usr/bin/env bash
# Step 9: restart checks after new traffic. Run the functional test (I3 §6) first, with
# --out "$I3_RAW_DIR/FT-functional.check.json". Then: replication on flow B; consumers caught up on
# both brokers; checks.json collects every verdict. The captures (capture.sh) follow this step.
source "$(dirname "$0")/../lib.sh"
require "Catalog and Image are Stable on Kafka (step 8)" -- passed 08-kafka-groups
require "the functional test passed" -- passed FT-functional
collect_b() {
  record 09 flow-b-offsets -- dump_topic "$REDPANDA" mm2-flow-b-offsets &&
    record 09 kafka-end -- ktool "$KAFKA" kafka-get-offsets.sh --topic-partitions 'catalog\..*'
}
check 09 replication-b --collect collect_b -- replication --offsets "$RAW/09-flow-b-offsets.txt" \
  --source-end "$RAW/09-kafka-end.txt" --format kafka --topic catalog.product.events \
  --topic catalog.category.events --topic catalog.attribute.events
# lag_check BROKER GROUP TOPIC...: one group's lag on Redpanda (rpk) or Kafka.
collect_lag() {
  if [[ "$LAG_BROKER" == rpk ]]; then
    record 09 "${LAG_GROUP#ecommerce-}-describe" -- rpk group describe "$LAG_GROUP"
  else
    record 09 "${LAG_GROUP#ecommerce-}-describe" -- ktool "$KAFKA" kafka-consumer-groups.sh \
      --describe --group "$LAG_GROUP"
  fi
}
lag_check() {
  LAG_BROKER="$1" LAG_GROUP="$2"
  shift 2
  local short="${LAG_GROUP#ecommerce-}" args=() topic
  for topic in "$@"; do args+=(--topic "$topic"); done
  check 09 "$short-lag" --collect collect_lag -- lag --describe "$RAW/09-$short-describe.txt" \
    --format "$LAG_BROKER" --group "$LAG_GROUP" "${args[@]}"
}
lag_check rpk ecommerce-product-query-service catalog.product.events catalog.attribute.events
lag_check rpk ecommerce-category-query-service catalog.category.events catalog.attribute.events
lag_check kafka ecommerce-catalog-service tenant.tenant.events
lag_check kafka ecommerce-image-service tenant.tenant.events catalog.product.events
python3 "$I3_DIR/checker.py" collect "$RAW" --out "$RAW/../checks.json"
echo "step 9 done"
