#!/usr/bin/env bash
# Step 8: start Catalog and Image on Kafka. Tilt renders the charts without a Helm release, so this
# step renders each chart's ConfigMap exactly as the Tiltfile does (ecommerce-infrastructure@07c0599,
# environments/local/Tiltfile lines 149-152 and 209-217: `helm dependency build`, release name =
# chart name, namespace dev, values/<chart>.yaml then values.debug.yaml) plus the I3 overlay. It
# checks that the rendered ConfigMap is the one the deployment mounts and differs only in
# kafka.brokers, applies it and scales the deployment back to 1. Tilt must not run, or it re-applies
# the old values. To continue, both groups are Stable on Kafka.
source "$(dirname "$0")/../lib.sh"
INFRA="${SOKOL111_INFRA:?set SOKOL111_INFRA to the ecommerce-infrastructure checkout}"
require "flow B runs (step 7)" -- passed 07-mm2-flow-b-p1b
require "Tilt does not run" -- bash -c '! pgrep -f "tilt up" >/dev/null'
for name in catalog image; do
  chart="ecommerce-$name-service"
  record 08 "deps-$name" -- helm dependency build "$INFRA/helm/$chart"
  record 08 "render-$name" -- helm template "$chart" "$INFRA/helm/$chart" --namespace dev \
    -f "$INFRA/environments/local/values/$chart.yaml" -f "$INFRA/helm/$chart/values.debug.yaml" \
    -f "$ENV_DIR/values-i3-$name.yaml" --show-only templates/configmap.yaml
  record 08 "rendered-$name" -- kubectl -n dev create --dry-run=client -o json -f "$RAW/08-render-$name.txt"
  cm="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["metadata"]["name"])' \
    "$RAW/08-rendered-$name.txt")"
  record 08 "live-$name" -- kubectl -n dev get configmap "$cm" -o json ||
    stop "the deployment's ConfigMap $cm does not exist in dev"
  check 08 "configmap-$name" -- configmap --live "$RAW/08-live-$name.txt" \
    --rendered "$RAW/08-rendered-$name.txt"
  record 08 "apply-$name" -- kubectl -n dev apply -f "$RAW/08-render-$name.txt"
  record 08 "scale-$name" -- scale "$chart" 1
done
collect_kafka_groups() {
  record 08 kafka-groups -- ktool "$KAFKA" kafka-consumer-groups.sh --describe --state \
    --group ecommerce-catalog-service --group ecommerce-image-service
}
check 08 kafka-groups --collect collect_kafka_groups --deadline "$APP_START_DEADLINE_SECONDS" -- \
  state --describe "$RAW/08-kafka-groups.txt" --format kafka --group ecommerce-catalog-service \
  --group ecommerce-image-service --allow Stable
echo "step 8 done"
