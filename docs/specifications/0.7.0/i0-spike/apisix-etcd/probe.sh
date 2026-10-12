#!/usr/bin/env bash
# APISIX 3.19.0 in etcd/Admin-API mode: duplicate username, credentials resource, capture surface.
# Fake credentials only. Requires: docker network spike-net, the whoami upstream (see ../README.md).
set -euo pipefail
cd "$(dirname "$0")"
docker rm -f etcd-spike apisix-spike >/dev/null 2>&1 || true
docker run -d --name etcd-spike --network spike-net --network-alias etcd \
  -e ETCD_ADVERTISE_CLIENT_URLS=http://etcd:2379 -e ETCD_LISTEN_CLIENT_URLS=http://0.0.0.0:2379 \
  quay.io/coreos/etcd@sha256:d967d98a12dc220a1a290794711dba7eba04b8ce465e12b02383d1bfbb33e159 /usr/local/bin/etcd >/dev/null
docker run -d --name apisix-spike --network spike-net -p 19080:9080 -p 19091:9091 -p 19180:9180 \
  -v "$PWD/config.yaml:/usr/local/apisix/conf/config.yaml:ro" \
  apache/apisix@sha256:9a7e45dc943fbf10ec916d1232bae4cda9302ae28a4696cfb83c2da01d261141 >/dev/null
sleep 12
H='X-API-KEY: spike-admin-key-fake'; A=localhost:19180/apisix/admin
echo "PUT create:          $(curl -s -o /dev/null -w '%{http_code}' -X PUT $A/consumers -H "$H" -d '{"username":"spike-alpha","plugins":{"key-auth":{"key":"SPIKE-FAKE-KEY-ALPHA"}}}')"
echo "PUT same username:   $(curl -s -o /dev/null -w '%{http_code}' -X PUT $A/consumers -H "$H" -d '{"username":"spike-alpha","plugins":{"key-auth":{"key":"SPIKE-FAKE-KEY-ALPHA2"}}}')"
echo "POST same username:  $(curl -s -o /dev/null -w '%{http_code}' -X POST $A/consumers -H "$H" -d '{"username":"spike-alpha","plugins":{"key-auth":{"key":"SPIKE-FAKE-KEY-ALPHA3"}}}')"
echo "PUT credential:      $(curl -s -o /dev/null -w '%{http_code}' -X PUT $A/consumers/spike-alpha/credentials/cred-1 -H "$H" -d '{"plugins":{"key-auth":{"key":"SPIKE-FAKE-KEY-CRED1"}}}')"
curl -s -o /dev/null -X PUT $A/routes/orders-route -H "$H" -d '{"uri":"/orders","plugins":{"key-auth":{},"prometheus":{}},"upstream":{"type":"roundrobin","nodes":{"whoami:80":1}}}'
sleep 3
for k in ALPHA ALPHA2 CRED1; do echo "auth $k: $(curl -s -o /dev/null -w '%{http_code}' -H "apikey: SPIKE-FAKE-KEY-$k" localhost:19080/orders)"; done
sleep 15
curl -s localhost:19091/apisix/prometheus/metrics | grep -E '^apisix_http_status' | sed -E 's/,node="[^"]*"//' | sort || true
echo "GET consumer returns plaintext key: $(curl -s $A/consumers/spike-alpha -H "$H" | grep -c SPIKE-FAKE-KEY)"
