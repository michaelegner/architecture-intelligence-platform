#!/usr/bin/env bash
# One deterministic Tyk capture run: fresh Redis/collector/gateway, fixed key names, fixed traffic.
# stdout: normalized configured-access capture, then normalized metric extract.
set -euo pipefail
cd "$(dirname "$0")"
GW=tykio/tyk-gateway@sha256:ec0854f6f8d4f7282a5676cffac9dc179230e467718bac1d3f54afec00380b90
docker rm -f tyk-spike otel-spike redis-spike >/dev/null 2>&1 || true
docker run -d --name redis-spike --network spike-net --network-alias redis redis@sha256:c1e88455c85225310bbea54816e9c3f4b5295815e6dbf80c34d40afc6df28275 >/dev/null
docker run -d --name otel-spike --network spike-net --network-alias otel -p 18889:8889 -v "$PWD/otel.yaml:/etc/otel.yaml:ro" otel/opentelemetry-collector-contrib@sha256:d0ebf65280da2e1b1491d1b93648281afd353d4b9ea19160090303cec9a233bd --config /etc/otel.yaml >/dev/null
docker run -d --name tyk-spike --network spike-net -p 18080:8080 -v "$PWD/tyk.conf:/opt/tyk-gateway/tyk.conf:ro" -v "$PWD/apps:/opt/tyk-gateway/apps:ro" $GW >/dev/null
sleep 8
A='x-tyk-authorization: spike-admin-secret'
mk() { curl -s -X POST "localhost:18080/tyk/keys/$1" -H "$A" -H 'Content-Type: application/json' -d "{\"alias\":\"$2\",\"org_id\":\"spike-org\",\"expires\":0,\"rate\":1000,\"per\":60,\"quota_max\":-1,\"access_rights\":{\"$3\":{\"api_id\":\"$3\",\"api_name\":\"x\",\"versions\":[\"Default\"]}}}" >/dev/null; }
mk spike-orgSPIKEFAKEKEYALPHA spike-alpha orders-api
mk spike-orgSPIKEFAKEKEYBETA spike-beta orders-api
mk spike-orgSPIKEFAKEKEYGAMMA spike-gamma other-api
req() { curl -s -o /dev/null -H "Authorization: $1" localhost:18080/orders/; }
for i in 1 2 3; do req spike-orgSPIKEFAKEKEYALPHA; done; req spike-orgSPIKEFAKEKEYBETA; req spike-orgSPIKEFAKEKEYGAMMA; curl -s -o /dev/null localhost:18080/orders/
sleep 12
echo "## configured-access capture (normalized: sorted by alias, last_updated and key material dropped)"
curl -s localhost:18080/tyk/keys -H "$A" | python3 -c '
import json,sys,subprocess
hs=json.load(sys.stdin)["keys"]
rows=[]
for h in hs:
    d=json.loads(subprocess.check_output(["curl","-s","localhost:18080/tyk/keys/%s?hashed=true"%h,"-H","x-tyk-authorization: spike-admin-secret"]))
    rows.append({"alias":d["alias"],"org_id":d["org_id"],"access_rights":{k:{"api_id":v["api_id"],"versions":v["versions"]} for k,v in sorted(d["access_rights"].items())}})
for r in sorted(rows,key=lambda r:r["alias"]): print(json.dumps(r,sort_keys=True))'
echo "## request-derived measurement (normalized: instance label dropped, sorted)"
curl -s localhost:18889/metrics | grep -E '^tyk_spike' | sed -E 's/,instance="[^"]*"//' | sort
