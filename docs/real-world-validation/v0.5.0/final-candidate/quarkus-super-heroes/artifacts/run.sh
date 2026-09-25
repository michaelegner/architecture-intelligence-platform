#!/usr/bin/env bash
# Generated from the frozen runbook docs/real-world-validation/v0.5.0/quarkus-super-heroes/runbook.md (blocks 1-10, verbatim) at candidate aa04a15.
# Deviations: RUN_DIR fixed to the session run-record dir; NEO4J_PASSWORD from a 0600 file;
# v0.3 wait helpers + the readiness calls the runbook names; window bounds saved to files.
export AIP_CHECKOUT=/home/michael/code/ArchitectureIntelligencePlatform   # frozen in profile.md
export DOSSIER="$AIP_CHECKOUT/docs/real-world-validation/v0.5.0/quarkus-super-heroes"
export RUNTIME="$DOSSIER/runtime"
export RUN_DIR=/tmp/claude-1001/-home-michael-code-ArchitectureIntelligencePlatform/dea4adeb-9305-40aa-944d-829d6415b869/scratchpad/i5-s7/quarkus
# Every Compose call goes through frozen_compose (PR #243 review). It uses exactly the frozen
# file, a fixed project name and no env file. So it ignores any gitignored .env (which could set
# COMPOSE_FILE) and any docker-compose.override.yml; the clean-checkout gate can see neither.
frozen_compose() {
  docker compose -p qsh-i5 --project-directory "$RUNTIME" -f "$RUNTIME/docker-compose.yml" \
    --env-file /dev/null "$@"
}
export NEO4J_PASSWORD="$(cat /tmp/claude-1001/-home-michael-code-ArchitectureIntelligencePlatform/dea4adeb-9305-40aa-944d-829d6415b869/scratchpad/i5-s7/quarkus/.neo4j-password)"
echo '==> runbook block 2'
set -euo pipefail
cd "$AIP_CHECKOUT"
[ "$(pwd -P)" = "$AIP_CHECKOUT" ]                         # the one frozen absolute location (I5 §12)
[ -z "$(git status --porcelain)" ] || { echo "checkout is not clean" >&2; exit 1; }
export AIP_CANDIDATE_SHA="$(git rev-parse HEAD)"
echo "$AIP_CANDIDATE_SHA" | grep -Eq '^[0-9a-f]{40}$'
echo "$AIP_CANDIDATE_SHA" > "$RUN_DIR/candidate-sha"

export QUARKUS_SUPERHEROES_CHECKOUT="$RUN_DIR/quarkus-super-heroes"   # a fresh clone per run
git clone https://github.com/quarkusio/quarkus-super-heroes.git "$QUARKUS_SUPERHEROES_CHECKOUT"
git -C "$QUARKUS_SUPERHEROES_CHECKOUT" checkout --detach 8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
[ "$(git -C "$QUARKUS_SUPERHEROES_CHECKOUT" rev-parse HEAD)" = \
  8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce ]

# Every upstream-supplied input is byte-identical to the pin (profile.md).
for s in rest-fights rest-heroes rest-villains rest-narration; do
  cmp "$QUARKUS_SUPERHEROES_CHECKOUT/$s/src/main/resources/openapi/openapi.yml" \
      "$RUNTIME/declarations/$s/openapi.yml"
done
cmp "$QUARKUS_SUPERHEROES_CHECKOUT/deploy/k8s/java25-kubernetes.yml" \
    "$RUNTIME/k8s/unmodified/java25-kubernetes.yml"

# The upstream-derived copy regenerates byte-for-byte (I5 §5).
(cd "$RUNTIME/k8s" && uv run --project "$AIP_CHECKOUT" python derive_namespaced.py \
  "$QUARKUS_SUPERHEROES_CHECKOUT/deploy/k8s/java25-kubernetes.yml" "$RUN_DIR/namespaced.yml")
cmp "$RUN_DIR/namespaced.yml" "$RUNTIME/k8s/namespaced/java25-kubernetes.namespaced.yml"
echo '==> runbook block 3'
MAVEN=maven@sha256:dd8e01b3be719853578c07b57ff8d9bbbbfe746f802226f05b19689420815221
BASE=registry.access.redhat.com/ubi10/openjdk-25-runtime
BASE_DIGEST=sha256:c49d36c03d0a9472935b9f318f709c4cf158afa2dc204099f1f463cfbf9d4626
docker pull "$MAVEN"
docker pull "$BASE@$BASE_DIGEST"
docker tag "$BASE@$BASE_DIGEST" "$BASE:1.24"   # the FROM line of every upstream Dockerfile.jvm

: > "$RUN_DIR/service-images"
for svc in rest-fights rest-heroes rest-villains rest-narration event-statistics grpc-locations; do
  docker run --rm -v "$QUARKUS_SUPERHEROES_CHECKOUT:/workspace" -w "/workspace/$svc" \
    "$MAVEN" ./mvnw -q package -DskipTests
  docker build --no-cache --pull=false \
    -f "$QUARKUS_SUPERHEROES_CHECKOUT/$svc/src/main/docker/Dockerfile.jvm" \
    -t "quarkus-super-heroes/$svc:8ea0337" "$QUARKUS_SUPERHEROES_CHECKOUT/$svc"
  echo "$svc $(docker image inspect --format '{{.Id}}' "quarkus-super-heroes/$svc:8ea0337")" \
    >> "$RUN_DIR/service-images"
done
echo '==> runbook block 4'
cd "$RUNTIME"
: "${NEO4J_PASSWORD:?}" "${AIP_CANDIDATE_SHA:?}" "${QUARKUS_SUPERHEROES_CHECKOUT:?}"  # PR #240 review
unset COMPOSE_PROFILES   # no extra profiles; frozen_compose already fixes the file and ignores .env

# Every bind mount must come from this dossier's runtime/ or from the verified pinned clone (step 2).
frozen_compose config --format json | jq -r \
  '.services[] | .volumes[]? | select(.type == "bind") | .source' | sort -u |
  while read -r src; do
    case "$src" in
      "$RUNTIME"/*|"$QUARKUS_SUPERHEROES_CHECKOUT"/*) ;;
      *) echo "unexpected bind mount source: $src" >&2; exit 1 ;;
    esac
  done

frozen_compose down -v            # I5 §11: every run begins from clean AIP and upstream state
frozen_compose build --no-cache architecture-intelligence
docker image inspect --format '{{.Id}}' "aip-i5-candidate:$AIP_CANDIDATE_SHA" > "$RUN_DIR/aip-image"
echo '==> runbook block 5'
frozen_compose up -d --no-build --force-recreate

# Every running container must use exactly the image this run built or pinned.
check_image() {  # <compose service> <expected image id>
  local actual
  actual="$(docker inspect --format '{{.Image}}' "$(frozen_compose ps -q "$1")")"
  [ "$actual" = "$2" ] || { echo "$1 runs $actual, expected $2" >&2; exit 1; }
}
check_image architecture-intelligence "$(cat "$RUN_DIR/aip-image")"
while read -r svc id; do check_image "$svc-java25" "$id"; done < "$RUN_DIR/service-images"
[ "$(frozen_compose exec -T architecture-intelligence printenv AIP_BUILD_REVISION)" = \
  "$AIP_CANDIDATE_SHA" ]

# The third-party images are referenced by digest in docker-compose.yml, so Docker cannot run
# other bytes. Record them anyway.
frozen_compose images --format json > "$RUN_DIR/compose-images.json"
[ -z "$(git -C "$AIP_CHECKOUT" status --porcelain)" ]   # still the clean candidate
echo '==> readiness (v0.3 helpers)'
wait_for_http() {
  local name="$1" url="$2" timeout="${3:-180}" waited=0
  until curl -sf "$url" >/dev/null 2>&1; do
    waited=$((waited + 2))
    if [ "$waited" -ge "$timeout" ]; then
      echo "$name did not become ready within ${timeout}s ($url) - see: docker compose logs $name" >&2
      return 1
    fi
    sleep 2
  done
  echo "$name ready after ${waited}s"
}
wait_for_tcp() {
  local name="$1" host="$2" port="$3" timeout="${4:-60}" waited=0
  until (exec 3<>"/dev/tcp/$host/$port") 2>/dev/null; do
    waited=$((waited + 2))
    if [ "$waited" -ge "$timeout" ]; then
      echo "$name did not open $host:$port within ${timeout}s - see: docker compose logs $name" >&2
      return 1
    fi
    sleep 2
  done
  exec 3<&- 2>/dev/null || true
  echo "$name ready after ${waited}s"
}
wait_for_http architecture-intelligence  http://localhost:8000/health
wait_for_http rest-fights-java25         http://localhost:8082/q/health/ready
wait_for_http rest-heroes-java25         http://localhost:8083/q/health/ready
wait_for_http rest-villains-java25       http://localhost:8084/q/health/ready
wait_for_http rest-narration-java25      http://localhost:8087/q/health/ready
wait_for_http event-statistics-java25    http://localhost:8085/q/health/ready
wait_for_http grpc-locations-java25      http://localhost:8089/q/health/ready
wait_for_tcp  otel-collector             localhost 4318
echo '==> runbook block 6'
curl -sf -X POST http://localhost:8000/api/import | tee "$RUN_DIR/import.json" | jq .
echo '==> runbook block 7'
WINDOW_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
FIGHTS_URL=http://localhost:8082 ./traffic.sh
echo '==> runbook block 8'
EXPECTED_CONFIRMED="$(
  uv run --project "$AIP_CHECKOUT" python -c "
import yaml
doc = yaml.safe_load(open('$DOSSIER/expected.yaml'))
print(sum(1 for f in doc['expected']['relations']
          if f['type'] == 'CALLS' and f.get('status') == 'CONFIRMED'))
"
)"   # 3
MAX_WAIT=60; WAITED=0; CONFIRMED=0; WINDOW_END=""
while [ "$WAITED" -lt "$MAX_WAIT" ]; do
  NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  CONFIRMED="$(curl -sfG http://localhost:8000/api/analysis/runtime/confirmed \
    --data-urlencode environment=quarkus-i5 --data-urlencode "since=$WINDOW_START" \
    --data-urlencode "until=$NOW" | jq '.relations | length')"
  if [ "${CONFIRMED:-0}" -ge "$EXPECTED_CONFIRMED" ]; then WINDOW_END="$NOW"; break; fi
  sleep 2; WAITED=$((WAITED + 2))
done
[ -n "$WINDOW_END" ] || { echo "window did not close: $CONFIRMED/$EXPECTED_CONFIRMED" >&2; exit 1; }
echo "environment=quarkus-i5 window_start=$WINDOW_START window_end=$WINDOW_END"
echo "$WINDOW_START" > "$RUN_DIR/window-start"; echo "$WINDOW_END" > "$RUN_DIR/window-end"
echo '==> runbook block 9'
cd "$RUNTIME"
PYTHONPATH="$AIP_CHECKOUT" uv run --project "$AIP_CHECKOUT" python -m real_world_validation capture \
  --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j \
  --environment quarkus-i5 --since "$WINDOW_START" --until "$WINDOW_END" \
  --scope-entities service:rest-fights,service:rest-heroes,service:rest-villains,service:rest-narration,service:event-statistics \
  --scope-relation-types PROVIDES,CALLS,SENDS,PUBLISHES_TO,RECEIVES_FROM \
  --aip-config config.quarkus-i5.yaml \
  --out "$RUN_DIR/actual.yaml"
cd "$AIP_CHECKOUT"
echo '==> runbook block 10'
uv run python -m real_world_validation compare \
  --expected "$DOSSIER/expected.yaml" \
  --actual   "$RUN_DIR/actual.yaml" | tee "$RUN_DIR/compare.txt"
echo '==> DONE (stack left running for public-surfaces and manual checks)'
