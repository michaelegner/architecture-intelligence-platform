#!/usr/bin/env bash
# v0.8 I4 §5: the I3 helpers (record, check, ktool, rpk, dump_topic, rpk_end, listed, ...) bound to
# the I4 run home. Only the Compose identity changes: the Kafka-only project `aip-v08-i4`, started
# from the run home (outside the AIP checkout). Nothing here starts, stops or changes anything.
set -euo pipefail

I4_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_HOME="${I4_RUN_HOME:?set I4_RUN_HOME to the run home}"
PACKAGE="$RUN_HOME/package"
export I3_RAW_DIR="$PACKAGE/raw"
# shellcheck source=../i3/lib.sh
source "$I4_DIR/../i3/lib.sh"

frozen_compose() {
  docker compose -p aip-v08-i4 --project-directory "$RUN_HOME/kafka" \
    -f "$RUN_HOME/kafka/docker-compose.kafka.yml" --env-file /dev/null "$@"
}

# The groups and topics the operator's ground truth covers (the plan key, K1-K4), independent of
# what the agent configured.
REDPANDA_GROUPS=(ecommerce-catalog-service ecommerce-category-query-service ecommerce-image-service
  ecommerce-product-query-service)
MOVED_GROUPS=(ecommerce-catalog-service ecommerce-image-service)
TENANT_TOPIC=tenant.tenant.events
CATALOG_TOPICS=(catalog.product.events catalog.category.events catalog.attribute.events)

# verdict NN NAME -- CHECKER-ARGS...: one I3 checker rule, evaluated once after the wave (no polling:
# S4 reads a settled state). A FAILED verdict is recorded as a finding; it does not stop the script.
verdict() {
  local nn="$1" name="$2"
  shift 3
  python3 "$I3_DIR/checker.py" "$@" --elapsed 0 --deadline 0 --out "$RAW/$nn-$name.check.json" || true
}
