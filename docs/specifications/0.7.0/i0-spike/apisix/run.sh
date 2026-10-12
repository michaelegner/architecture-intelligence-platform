#!/usr/bin/env bash
# One deterministic APISIX capture run: fresh container, fixed traffic, normalized metric extract.
set -euo pipefail
cd "$(dirname "$0")"
docker rm -f apisix-spike >/dev/null 2>&1 || true
docker run -d --name apisix-spike --network spike-net -p 19080:9080 -p 19091:9091 \
  -v "$PWD/config.yaml:/usr/local/apisix/conf/config.yaml:ro" \
  -v "$PWD/apisix.yaml:/usr/local/apisix/conf/apisix.yaml:ro" \
  apache/apisix@sha256:9a7e45dc943fbf10ec916d1232bae4cda9302ae28a4696cfb83c2da01d261141 >/dev/null
sleep 10
req() { curl -s -o /dev/null -H "apikey: SPIKE-FAKE-KEY-$1" localhost:19080/orders; }
for i in 1 2 3; do req ALPHA; done; req BETA; req GAMMA; curl -s -o /dev/null localhost:19080/orders
sleep 8
# normalization: keep only apisix_http_status, drop node (runtime IP), sort lines
curl -s localhost:19091/apisix/prometheus/metrics | grep -E '^apisix_http_status' \
  | sed -E 's/,node="[^"]*"//' | sort
