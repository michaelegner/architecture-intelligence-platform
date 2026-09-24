#!/usr/bin/env bash
# Generated from the frozen runbook docs/real-world-validation/v0.5.0/lifecycle/runbook.md (blocks 1-5, verbatim) at candidate 174a17c.
# Deviations: RUN_DIR and LIFECYCLE_WORKDIR fixed; NEO4J_PASSWORD from a 0600 file; blocks 4-5 run
# once per target; block 5's diffs are recorded (output + status) instead of aborting, so a
# mismatch becomes a finding and the other target still runs.
set -euo pipefail
export AIP_CHECKOUT=/home/michael/code/ArchitectureIntelligencePlatform   # frozen location (profile.md of both targets)
export LIFECYCLE="$AIP_CHECKOUT/docs/real-world-validation/v0.5.0/lifecycle"
export RUN_DIR=/tmp/claude-1001/-home-michael-code-ArchitectureIntelligencePlatform/dea4adeb-9305-40aa-944d-829d6415b869/scratchpad/i5-s5/lifecycle
export LIFECYCLE_WORKDIR=/tmp/claude-1001/-home-michael-code-ArchitectureIntelligencePlatform/dea4adeb-9305-40aa-944d-829d6415b869/scratchpad/i5-s5/lifecycle-workdir
export NEO4J_PASSWORD="$(cat /tmp/claude-1001/-home-michael-code-ArchitectureIntelligencePlatform/dea4adeb-9305-40aa-944d-829d6415b869/scratchpad/i5-s5/lifecycle/.neo4j-password)"

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
echo '==> runbook block 3'
frozen_compose build --no-cache architecture-intelligence
docker image inspect --format '{{.Id}}' "aip-i5-candidate:$AIP_CANDIDATE_SHA" > "$RUN_DIR/aip-image"
for TARGET in quarkus-super-heroes apache-airflow; do
  export TARGET; echo "==> target $TARGET: runbook block 4"
  run_step() {  # <step>; any extra arguments go to mutate.py
    local step="$1"; shift
    local out="$RUN_DIR/$TARGET/$step"; mkdir -p "$out"
    uv run --project "$AIP_CHECKOUT" python "$LIFECYCLE/mutate.py" "$TARGET" "$step" \
      "$LIFECYCLE_WORKDIR" "$@" > "$out/workdir-digest"
    # Settings are read at startup (app/deps.py), so every step restarts AIP. Neo4j keeps its state.
    frozen_compose up -d --no-build --force-recreate architecture-intelligence
    [ "$(docker inspect --format '{{.Image}}' "$(frozen_compose ps -q architecture-intelligence)")" \
      = "$(cat "$RUN_DIR/aip-image")" ]
    until curl -sf http://localhost:8000/health >/dev/null; do sleep 2; done
    local since; since="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    curl -s -X POST http://localhost:8000/api/import > "$out/import.json"   # also kept when not committed
    frozen_compose logs --since "$since" architecture-intelligence > "$out/aip.log" 2>&1
    for q in Q-INV Q-SRC Q-SRC-SEM Q-OWN Q-SVC Q-REL; do query "$q" "$out/$q.txt"; done
  }
  
  # X's source instance id, from AIP's own identity function (mutate.x_source_instance_id).
  export X_SOURCE_INSTANCE_ID="$(cd "$LIFECYCLE" && uv run --project "$AIP_CHECKOUT" python -c \
    "import mutate; print(mutate.x_source_instance_id(mutate.load_scenario('$TARGET')))")"
  
  frozen_compose down -v
  frozen_compose up -d --no-build neo4j
  until frozen_compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "RETURN 1" >/dev/null 2>&1; do sleep 2; done
  
  for step in S0 L1 L4a L4b L6 L2 R L5; do run_step "$step"; done
  run_step L3 --inventory "$RUN_DIR/$TARGET/L5/Q-INV.txt"   # the tombstone binds the committed L5 inventory
  echo "==> target $TARGET: runbook block 5 (recorded)"
  for pair in L2:L1 L3:L5; do step=${pair%%:*}; pred=${pair##*:}
    for q in Q-SVC Q-REL; do
      uv run --project "$AIP_CHECKOUT" python "$LIFECYCLE/without_x.py" \
        "$RUN_DIR/$TARGET/$pred/$q.txt" "$X_SOURCE_INSTANCE_ID" > "$RUN_DIR/$TARGET/$step/$q.expected"
      set +e; diff "$RUN_DIR/$TARGET/$step/$q.expected" "$RUN_DIR/$TARGET/$step/$q.txt" > "$RUN_DIR/$TARGET/$step/$q.diff"; echo "$step $q diff-exit=$?" | tee -a "$RUN_DIR/$TARGET/diffs.txt"; set -e
    done
  done
done
echo '==> runbook block 6'
frozen_compose down -v
echo '==> DONE'
