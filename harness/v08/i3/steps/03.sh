#!/usr/bin/env bash
# Step 3: stop Catalog. To continue, Image must have caught up on catalog.product.events (lag 0)
# after Catalog's last pod is gone, so no product event Catalog wrote is unread on Redpanda: the
# catalog topics are never mirrored to Kafka.
source "$(dirname "$0")/../lib.sh"
require "replication caught up on tenant.tenant.events (step 2)" -- passed 02-replication
record 03 scale-catalog -- scale ecommerce-catalog-service 0
stopped 03 ecommerce-catalog-service
collect_image() { record 03 image-describe -- rpk group describe ecommerce-image-service; }
check 03 image-lag --collect collect_image -- lag --describe "$RAW/03-image-describe.txt" \
  --format rpk --group ecommerce-image-service --topic catalog.product.events
echo "step 3 done"
