#!/usr/bin/env bash
# Step 5: drain. The remaining Redpanda consumers catch up: Product Query (catalog.product.events,
# catalog.attribute.events) and Category Query (catalog.category.events, catalog.attribute.events).
source "$(dirname "$0")/../lib.sh"
require "the moved groups read zero live attachment (step 4)" -- passed 04-groups-state
collect_product() { record 05 product-query-describe -- rpk group describe ecommerce-product-query-service; }
check 05 product-query-lag --collect collect_product -- lag \
  --describe "$RAW/05-product-query-describe.txt" --format rpk \
  --group ecommerce-product-query-service --topic catalog.product.events --topic catalog.attribute.events
collect_category() { record 05 category-query-describe -- rpk group describe ecommerce-category-query-service; }
check 05 category-query-lag --collect collect_category -- lag \
  --describe "$RAW/05-category-query-describe.txt" --format rpk \
  --group ecommerce-category-query-service --topic catalog.category.events --topic catalog.attribute.events
echo "step 5 done"
