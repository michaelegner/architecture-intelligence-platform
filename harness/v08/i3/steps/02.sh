#!/usr/bin/env bash
# Step 2: start flow A (tenant, Redpanda -> Kafka) with checkpoints and group-offset sync for
# Catalog and Image. Continue only when replication has caught up on tenant.tenant.events.
source "$(dirname "$0")/../lib.sh"
require "the catalog topics exist empty on Kafka (step 1)" -- recorded_ok 01-kafka-end
require "flow A is stopped" -- not_running mm2-flow-a
record 02 flow-a-up -- frozen_compose --profile mm2-flow-a up -d mm2-flow-a
p1b 02 mm2-flow-a kafka
collect_a() {
  record 02 flow-a-offsets -- dump_topic "$KAFKA" mm2-flow-a-offsets &&
    record 02 redpanda-end -- rpk_end tenant.tenant.events
}
check 02 replication --collect collect_a -- replication --offsets "$RAW/02-flow-a-offsets.txt" \
  --source-end "$RAW/02-redpanda-end.txt" --format rpk --topic tenant.tenant.events
echo "step 2 done"
