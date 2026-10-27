#!/usr/bin/env bash
# Step 4: stop Image. To continue, the Catalog and Image groups on Redpanda must read zero live
# attachment: Empty, or Dead as reported by the broker. A group that cannot be described stops the
# run. The wait depends on the consumers leaving, not on MirrorMaker 2 (GROUP_STATE_DEADLINE_SECONDS).
source "$(dirname "$0")/../lib.sh"
require "Image caught up after Catalog stopped (step 3)" -- passed 03-image-lag
record 04 scale-image -- scale ecommerce-image-service 0
stopped 04 ecommerce-image-service
collect_groups() {
  record 04 groups-describe -- rpk group describe ecommerce-catalog-service ecommerce-image-service
}
check 04 groups-state --collect collect_groups --deadline "$GROUP_STATE_DEADLINE_SECONDS" -- \
  state --describe "$RAW/04-groups-describe.txt" --format rpk --group ecommerce-catalog-service \
  --group ecommerce-image-service --allow Empty --allow Dead
echo "step 4 done"
