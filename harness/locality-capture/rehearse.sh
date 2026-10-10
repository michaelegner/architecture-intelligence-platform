#!/usr/bin/env bash
# Controlled two-Workload capture, REHEARSAL (v0.6.0 I2.6a; I1 capture runbook §4 and §9).
#
# Runs the runbook §4 procedure once against a throwaway kind cluster and writes every artifact and
# pin into OUT (default: ./out). Its output is labelled REHEARSAL - NOT I5 evidence (runbook §8/§9).
# The offline replay into AIP is replay/run-replay.sh; this script only acquires.
#
# Usage: harness/locality-capture/rehearse.sh [--actual] [OUT]
# --actual acquires a new I5 recording; no AIP evaluation is performed.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
ACTUAL=false
if [[ "${1:-}" == --actual ]]; then ACTUAL=true; shift; fi
CLUSTER=aip-locality-rehearsal
SOURCE=aip-locality-rehearsal
LABEL="REHEARSAL - NOT I5 evidence"
if $ACTUAL; then
    [[ $# == 1 && ! -e "$1" ]] || { echo "actual capture requires one new output directory" >&2; exit 1; }
    RUN_ID="$(date -u +%Y%m%dt%H%M%Sz)-$$"
    CLUSTER="aip-locality-i5-$RUN_ID"
    SOURCE="aip-locality-i5-$RUN_ID"
    LABEL=ACTUAL_CONTROLLED_REFERENCE
    [[ -z "$(git -C "$REPO" status --porcelain)" ]] || { echo "commit harness before actual acquisition" >&2; exit 1; }
fi
OUT="$(mkdir -p "${1:-$HERE/out}" && cd "${1:-$HERE/out}" && pwd)"
NS=aip-locality
NODE_IMAGE='kindest/node:v1.31.2@sha256:18fbefc20a7113353c7b75b5c869d7145a6abd6269154825872dc59c1329912e'
APP_IMAGE=aip-locality-harness:rehearsal
if $ACTUAL; then APP_IMAGE="aip-locality-harness:$RUN_ID"; fi
TRAFFIC_SECONDS="${TRAFFIC_SECONDS:-330}"   # runbook §4 step 5: >= 5 minutes
CANARY_SECONDS="${CANARY_SECONDS:-120}"     # runbook §4 step 7: 2 more minutes of canary traffic
LOG="$OUT/run-log.txt"
: > "$LOG"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }
stop() { log "STOP CONDITION: $*"; exit 1; }
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
kc() { kubectl --context "kind-$CLUSTER" "$@"; }

# Runbook §4: one UTC day, starting at or after 01:00Z and finishing by 22:00Z.
hour=$(date -u +%H)
if ((10#$hour < 1 || 10#$hour >= 21)); then stop "start at $(now) leaves no margin inside 01:00Z-22:00Z"; fi
DAY=$(date -u +%Y-%m-%d)
if $ACTUAL; then
    [[ "$TRAFFIC_SECONDS" =~ ^[0-9]+$ && "$CANARY_SECONDS" =~ ^[0-9]+$ ]] || stop "invalid traffic duration"
    ((TRAFFIC_SECONDS >= 300 && CANARY_SECONDS >= 120)) || stop "traffic durations below runbook minimum"
    log "label $LABEL; harness HEAD $(git -C "$REPO" rev-parse HEAD)"
    log "command: bash harness/locality-capture/rehearse.sh --actual $OUT"
    mkdir -p "$OUT/harness" "$OUT/declarations" "$OUT/replay"
    cp -r "$HERE/app" "$OUT/harness/app"
    cp "$HERE/rehearse.sh" "$HERE/capture_metadata.py" "$OUT/harness/"
    cp -r "$HERE/declarations/." "$OUT/declarations/"
    cp "$HERE/replay/collector-replay.yaml" "$HERE/replay/replay.py" "$OUT/replay/"
fi

# 0. Pins
log "pins: $(kind version)"
log "pins: $(kubectl version --client 2>/dev/null | head -1)"
log "pins: docker server $(docker version --format '{{.Server.Version}}')"
log "pins: node image $NODE_IMAGE"
docker build -q -t "$APP_IMAGE" "$HERE/app" >/dev/null
log "pins: app image $APP_IMAGE id $(docker image inspect --format '{{.Id}}' "$APP_IMAGE")"
log "pins: collector image $(grep -o 'otel/opentelemetry-collector-contrib:[^ ]*' "$HERE/manifests/collector.yaml")"

# 1. Throwaway cluster and cluster identity
if $ACTUAL; then
    if kind get clusters 2>/dev/null | grep -Fxq "$CLUSTER"; then stop "cluster already exists"; fi
else
    kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true
fi
kind create cluster --name "$CLUSTER" --image "$NODE_IMAGE" >>"$LOG" 2>&1
kc wait --for=condition=Ready node --all --timeout=120s >>"$LOG"
CLUSTER_UID=$(kc get namespace kube-system -o jsonpath='{.metadata.uid}')
log "CLUSTER_UID=$CLUSTER_UID (kubectl get namespace kube-system -o jsonpath='{.metadata.uid}')"
log "api server: $(kc get nodes -o jsonpath='{.items[0].status.nodeInfo.kubeletVersion}')"

# 2. Load the one app image (orders, orders-canary, pricing, legacy-pricing)
kind load docker-image "$APP_IMAGE" --name "$CLUSTER" >>"$LOG" 2>&1

# 3. Namespace, Collector, providers
mkdir -p "$OUT/manifests"
kc create namespace "$NS" >>"$LOG"
for name in collector pricing legacy-pricing; do
    sed "s|aip-locality-harness:rehearsal|$APP_IMAGE|g" "$HERE/manifests/$name.yaml" > "$OUT/manifests/$name.yaml"
    kc apply -f "$OUT/manifests/$name.yaml" >>"$LOG"
done
kc -n "$NS" rollout status deployment/otel-collector deployment/pricing deployment/legacy-pricing \
    --timeout=180s >>"$LOG"

# 4. Both caller Workloads at once (the overlap), CLUSTER_UID substituted as applied
for name in orders orders-canary; do
    sed -e "s/\${CLUSTER_UID}/$CLUSTER_UID/" -e "s|aip-locality-harness:rehearsal|$APP_IMAGE|g" "$HERE/manifests/$name.yaml" > "$OUT/manifests/$name.yaml"
    kc apply -f "$OUT/manifests/$name.yaml" >>"$LOG"
done
kc -n "$NS" rollout status deployment/orders deployment/orders-canary --timeout=180s >>"$LOG"

pod_of() { kc -n "$NS" get pod -l "app=$1" -o jsonpath='{.items[*].metadata.name} {.items[*].metadata.uid}'; }
read -r P1_NAME P1_UID <<<"$(pod_of orders)"
read -r P2_NAME P2_UID <<<"$(pod_of orders-canary)"
[[ -n "$P1_UID" && -n "$P2_UID" && "$P1_UID" != "$P2_UID" ]] || stop "P1/P2 not uniquely identified"
log "P1 $P1_NAME uid $P1_UID (Deployment orders)"
log "P2 $P2_NAME uid $P2_UID (Deployment orders-canary)"
if $ACTUAL; then
    kc -n "$NS" logs deployment/otel-collector > "$OUT/collector-start.log"
    P1_WORKLOAD_UID=$(kc -n "$NS" get deployment orders -o jsonpath='{.metadata.uid}')
    P2_WORKLOAD_UID=$(kc -n "$NS" get deployment orders-canary -o jsonpath='{.metadata.uid}')
    [[ -n "$P1_WORKLOAD_UID" && -n "$P2_WORKLOAD_UID" && "$P1_WORKLOAD_UID" != "$P2_WORKLOAD_UID" ]] || stop "distinct Workload UIDs missing"
fi

# 5. Traffic
TRAFFIC_START=$(now); log "traffic start $TRAFFIC_START"
sleep "$TRAFFIC_SECONDS"
[[ "$(pod_of orders)" == "$P1_NAME $P1_UID" ]] || stop "P1 was replaced during the traffic window"
[[ "$(pod_of orders-canary)" == "$P2_NAME $P2_UID" ]] || stop "P2 was replaced during the traffic window"

envelope() { # $1=c1|c2 $2=capturedAt: the v0.5 KubernetesSourceSnapshot form (runbook §4)
    local dir="$OUT/$1" digest
    if $ACTUAL; then
        (cd "$REPO" && uv run python -m harness.locality-capture.capture_metadata envelope "$OUT" "$1" "$2" "$SOURCE" "$CLUSTER_UID")
        return
    fi
    digest=$(sha256sum "$dir/resources.yaml" | cut -d' ' -f1)
    cat > "$dir/envelope.yaml" <<EOF
apiVersion: aip.dev/v1
kind: KubernetesSourceSnapshot
metadata:
  id: aip-locality-rehearsal-$1
  revision: rehearsal-$1-${2//:/-}
  producer: aip-locality-rehearsal
  capturedAt: "$2"
source:
  configuredSourceId: aip-locality-rehearsal
  configuredScopeId: aip-locality-rehearsal-scope
  clusterUid: $CLUSTER_UID
  clusterIdentityEvidenceRef: kube-system-namespace-uid
  mode: CAPTURED_RESOURCE
scope:
  namespaces:
    - $NS
  resourceTypes:
    - v1/Namespace
    - v1/Pod
    - v1/Service
    - apps/v1/Deployment
    - apps/v1/StatefulSet
    - apps/v1/DaemonSet
    - apps/v1/ReplicaSet
    - networking.k8s.io/v1/Ingress
completeness:
  status: COMPLETE
  authorityRef: aip-locality-rehearsal-self-declared-authority
  expectedPriorInventoryRevision: null
files:
  - path: resources.yaml
    sha256: $digest
EOF
}
capture() { # $1=c1|c2: two non-atomic kubectl get calls, disclosed (runbook §4)
    mkdir -p "$OUT/$1"
    kc get namespace "$NS" -o yaml > "$OUT/$1/ns.yaml"
    if $ACTUAL; then
        kc -n "$NS" get deployment,statefulset,daemonset,replicaset,pod,service,ingress -o yaml > "$OUT/$1/rest.yaml"
    else
        kc -n "$NS" get deployment,replicaset,pod,service,ingress -o yaml > "$OUT/$1/rest.yaml"
    fi
    local at; at=$(now)
    # Two YAML documents, so a `---` separator between them (as in the precedent's committed
    # resources.yaml). Rehearsal attempts 1 and 2 omitted it and were discarded: the importer
    # rejects the merged mapping as K8S_SNAPSHOT_INCOMPLETE (duplicate mapping key). The raw
    # kubectl outputs are kept alongside for provenance.
    { cat "$OUT/$1/ns.yaml"; echo '---'; cat "$OUT/$1/rest.yaml"; } > "$OUT/$1/resources.yaml"
    envelope "$1" "$at"
    log "$1 capturedAt $at"
}

# 6. C1: the overlap, P1 and P2 both Running
for pod in "$P1_NAME" "$P2_NAME"; do
    [[ "$(kc -n "$NS" get pod "$pod" -o jsonpath='{.status.phase}')" == Running ]] || stop "$pod not Running at C1"
done
capture c1

# 7. Promotion: delete Deployment orders, wait until P1 is gone, 2 more minutes of canary traffic
kc -n "$NS" delete deployment orders --wait=true >>"$LOG"
kc -n "$NS" wait --for=delete "pod/$P1_NAME" --timeout=120s >>"$LOG" 2>&1 || true
kc -n "$NS" get pod "$P1_NAME" >/dev/null 2>&1 && stop "P1 still present after promotion"
log "P1 gone"
sleep "$CANARY_SECONDS"
[[ "$(pod_of orders-canary)" == "$P2_NAME $P2_UID" ]] || stop "P2 was replaced before C2"

# 8. C2: post-promotion, P1 absent
capture c2

# 9. Stop traffic, flush the Collector (batch timeout 10s), copy out the recording
kc -n "$NS" scale deployment/orders-canary --replicas=0 >>"$LOG"
kc -n "$NS" wait --for=delete "pod/$P2_NAME" --timeout=120s >>"$LOG" 2>&1 || true
sleep 20
TRAFFIC_END=$(now); log "traffic end $TRAFFIC_END"
docker cp "$CLUSTER-control-plane:/var/local/aip-otlp/otlp.jsonl" "$OUT/otlp.jsonl"
log "otlp.jsonl lines $(wc -l < "$OUT/otlp.jsonl") sha256 $(sha256sum "$OUT/otlp.jsonl" | cut -d' ' -f1)"

# Export identities before teardown so failed checks retain their acquisition context.
cat > "$OUT/identities.env" <<EOF
DAY=$DAY
CLUSTER_UID=$CLUSTER_UID
P1_NAME=$P1_NAME
P1_UID=$P1_UID
P2_NAME=$P2_NAME
P2_UID=$P2_UID
TRAFFIC_START=$TRAFFIC_START
TRAFFIC_END=$TRAFFIC_END
EOF
# Runbook §4: the captures and the traffic on one UTC day
for stamp in "$TRAFFIC_START" "$TRAFFIC_END" $(grep -h capturedAt "$OUT"/c*/envelope.yaml | tr -d "\"' " | cut -d: -f2-); do
    [[ "$stamp" == "$DAY"* ]] || stop "timestamp $stamp is not on $DAY"
done

if $ACTUAL; then
    cat >> "$OUT/identities.env" <<EOF
SOURCE_ID=$SOURCE
CLUSTER_NAME=$CLUSTER
P1_WORKLOAD_UID=$P1_WORKLOAD_UID
P2_WORKLOAD_UID=$P2_WORKLOAD_UID
EOF
    kc -n "$NS" logs deployment/otel-collector > "$OUT/collector-end.log"
    python3 "$HERE/replay/analyze.py" "$OUT/otlp.jsonl" "$OUT/identities.env" > "$OUT/analysis.json"
    (cd "$REPO" && uv run python -m harness.locality-capture.capture_metadata verify "$OUT")
fi
# 10. Teardown only the cluster created by this invocation, after export/checks.
kind delete cluster --name "$CLUSTER" >>"$LOG" 2>&1
log "done: artifacts in $OUT ($LABEL)"
