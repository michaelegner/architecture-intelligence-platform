#!/usr/bin/env bash
# Tyk 5.13.0: two keys sharing one alias are counted in a single series (finding F6).
# Starts the same stack as run.sh (fixed key names, fixed traffic), then adds a second key
# with alias spike-alpha, sends one request with it, and prints the spike-alpha series.
set -euo pipefail
cd "$(dirname "$0")"
./run.sh >/dev/null
A='x-tyk-authorization: spike-admin-secret'
echo "spike-alpha series before duplicate:"
curl -s localhost:18889/metrics | grep 'key_alias="spike-alpha"' | sed -E 's/,instance="[^"]*"//'
curl -s -o /dev/null -X POST localhost:18080/tyk/keys/spike-orgSPIKEFAKEKEYDUP -H "$A" -H 'Content-Type: application/json' \
  -d '{"alias":"spike-alpha","org_id":"spike-org","expires":0,"rate":1000,"per":60,"quota_max":-1,"access_rights":{"orders-api":{"api_id":"orders-api","api_name":"x","versions":["Default"]}}}'
echo "duplicate-alias key request: $(curl -s -o /dev/null -w '%{http_code}' -H 'Authorization: spike-orgSPIKEFAKEKEYDUP' localhost:18080/orders/)"
sleep 12
echo "spike-alpha series after duplicate:"
curl -s localhost:18889/metrics | grep 'key_alias="spike-alpha"' | sed -E 's/,instance="[^"]*"//'
echo "keys sharing alias spike-alpha:"
curl -s localhost:18080/tyk/keys -H "$A" | python3 -c '
import json,sys,subprocess
n=0
for h in json.load(sys.stdin)["keys"]:
    d=json.loads(subprocess.check_output(["curl","-s","localhost:18080/tyk/keys/%s?hashed=true"%h,"-H","x-tyk-authorization: spike-admin-secret"]))
    n+= d["alias"]=="spike-alpha"
print(n)'
