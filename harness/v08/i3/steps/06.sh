#!/usr/bin/env bash
# Step 6: offset hand-off for Catalog and Image on tenant.tenant.events. Per group and partition:
# (a) the final committed offset on Redpanda, the latest checkpoint, (c) the offset installed on
# Kafka, and the offset syncs. Rule: checkpoint upstream = (a) and (c) = checkpoint downstream.
# The replay amount is measured or estimated from these positions, never assumed (I3 §5).
source "$(dirname "$0")/../lib.sh"
require "the remaining consumers drained (step 5)" -- passed 05-product-query-lag
require "the remaining consumers drained (step 5)" -- passed 05-category-query-lag
collect_handoff() {
  record 06 source-groups -- rpk group describe ecommerce-catalog-service ecommerce-image-service &&
    record 06 checkpoints -- dump_topic "$KAFKA" redpanda.checkpoints.internal CheckpointFormatter &&
    record 06 target-groups -- ktool "$KAFKA" kafka-consumer-groups.sh --describe \
      --group ecommerce-catalog-service --group ecommerce-image-service &&
    record 06 offset-syncs -- dump_topic "$REDPANDA" mm2-offset-syncs.kafka.internal OffsetSyncFormatter
}
check 06 handoff --collect collect_handoff -- handoff --source-groups "$RAW/06-source-groups.txt" \
  --checkpoints "$RAW/06-checkpoints.txt" --target-groups "$RAW/06-target-groups.txt" \
  --offset-syncs "$RAW/06-offset-syncs.txt" --group ecommerce-catalog-service \
  --group ecommerce-image-service --topic tenant.tenant.events
echo "step 6 done"
