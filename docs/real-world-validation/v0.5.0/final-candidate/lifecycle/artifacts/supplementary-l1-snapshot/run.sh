#!/usr/bin/env bash
# Generated from the frozen runbook docs/real-world-validation/v0.5.0/lifecycle/runbook.md (blocks 1-5, verbatim) at candidate aa04a15.
# Deviations: RUN_DIR and LIFECYCLE_WORKDIR fixed; NEO4J_PASSWORD from a 0600 file; blocks 4-5 run
# once per target; block 5's diffs are recorded (output + status) instead of aborting, so a
# mismatch becomes a finding and the other target still runs.
set -euo pipefail
export AIP_CHECKOUT=/home/michael/code/ArchitectureIntelligencePlatform   # frozen location (profile.md of both targets)
export LIFECYCLE="$AIP_CHECKOUT/docs/real-world-validation/v0.5.0/lifecycle"
export RUN_DIR=/tmp/claude-1001/-home-michael-code-ArchitectureIntelligencePlatform/dea4adeb-9305-40aa-944d-829d6415b869/scratchpad/i5-s7/lifecycle-snapshot
export LIFECYCLE_WORKDIR=/tmp/claude-1001/-home-michael-code-ArchitectureIntelligencePlatform/dea4adeb-9305-40aa-944d-829d6415b869/scratchpad/i5-s7/lifecycle-workdir
export NEO4J_PASSWORD="$(cat /tmp/claude-1001/-home-michael-code-ArchitectureIntelligencePlatform/dea4adeb-9305-40aa-944d-829d6415b869/scratchpad/i5-s7/lifecycle/.neo4j-password)"

# Every Compose call goes through frozen_compose. It uses exactly the frozen file, a fixed project
# name and no env file, so a gitignored .env or an override file cannot change the run.
frozen_compose() {
  docker compose -p i5-lifecycle --project-directory "$LIFECYCLE" \
    -f "$LIFECYCLE/docker-compose.lifecycle.yml" --env-file /dev/null "$@"
}
unset COMPOSE_PROFILES

# The frozen read-only queries (../queries/*.cypher). --access-mode read makes a write fail.
query() {  # <Q-name> <output file>
  frozen_compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
    --access-mode read --format plain < "$LIFECYCLE/../queries/$1.cypher" > "$2"
}
echo '==> runbook block 2'
cd "$AIP_CHECKOUT"
[ "$(pwd -P)" = "$AIP_CHECKOUT" ]
[ -z "$(git status --porcelain)" ] || { echo "checkout is not clean" >&2; exit 1; }
export AIP_CANDIDATE_SHA="$(git rev-parse HEAD)"
echo "$AIP_CANDIDATE_SHA" | grep -Eq '^[0-9a-f]{40}$'
echo "$AIP_CANDIDATE_SHA" > "$RUN_DIR/candidate-sha"
# SUPPLEMENTARY (Slice 7, disclosed): the ledger's L1 row also names "the dependencies snapshot_id
# of one declared Service equals its S0 value", which the frozen runbook never captures. This
# replays blocks 4's S0 and L1 only, on the same verified image (not rebuilt; its id is checked),
# and adds one read-only GET after each import. Nothing else differs from runbook block 4.
cp "$(dirname "$RUN_DIR")/lifecycle/aip-image" "$RUN_DIR/aip-image"
[ "$(docker image inspect --format '{{.Id}}' "aip-i5-candidate:$AIP_CANDIDATE_SHA")" = "$(cat "$RUN_DIR/aip-image")" ]
declare -A SERVICE=([quarkus-super-heroes]=service:rest-heroes [apache-airflow]=service:airflow-apiserver)
for TARGET in quarkus-super-heroes apache-airflow; do
  export TARGET; echo "==> target $TARGET: S0, L1 + dependencies snapshot"
  frozen_compose down -v
  frozen_compose up -d --no-build neo4j
  until frozen_compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "RETURN 1" >/dev/null 2>&1; do sleep 2; done
  for step in S0 L1; do
    out="$RUN_DIR/$TARGET/$step"; mkdir -p "$out"
    uv run --project "$AIP_CHECKOUT" python "$LIFECYCLE/mutate.py" "$TARGET" "$step" "$LIFECYCLE_WORKDIR" > "$out/workdir-digest"
    frozen_compose up -d --no-build --force-recreate architecture-intelligence
    [ "$(docker inspect --format '{{.Image}}' "$(frozen_compose ps -q architecture-intelligence)")" = "$(cat "$RUN_DIR/aip-image")" ]
    until curl -sf http://localhost:8000/health >/dev/null; do sleep 2; done
    curl -s -X POST http://localhost:8000/api/import > "$out/import.json"
    for q in Q-INV Q-SRC Q-SRC-SEM Q-OWN Q-SVC Q-REL; do query "$q" "$out/$q.txt"; done
    curl -s "http://localhost:8000/api/services/${SERVICE[$TARGET]}/dependencies" > "$out/dependencies.json"
  done
done
frozen_compose down -v
echo '==> DONE'
