# Runbook: I5 §10 lifecycle scenarios (v0.5.0)

This is the ordered procedure that I5 Slice 5 follows for the lifecycle scenarios frozen in
`README.md`. It uses the same run-identity pattern as the frozen target runbooks (PR #240, #242 and
#243 reviews). **Any failed check stops the run.** Nothing here runs against the upstream pin, and
nothing modifies the frozen dossiers. Every step works on a scratch copy that `mutate.py` builds.

```bash
set -euo pipefail
export AIP_CHECKOUT=/home/michael/code/ArchitectureIntelligencePlatform   # frozen location (profile.md of both targets)
export LIFECYCLE="$AIP_CHECKOUT/docs/real-world-validation/v0.5.0/lifecycle"
export RUN_DIR="$(mktemp -d)"
export LIFECYCLE_WORKDIR="$(mktemp -d)"          # bind-mounted; mutate.py replaces its contents only
export NEO4J_PASSWORD='replace-with-a-local-password'

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
```

## 1. Verify the candidate checkout

```bash
cd "$AIP_CHECKOUT"
[ "$(pwd -P)" = "$AIP_CHECKOUT" ]
[ -z "$(git status --porcelain)" ] || { echo "checkout is not clean" >&2; exit 1; }
export AIP_CANDIDATE_SHA="$(git rev-parse HEAD)"
echo "$AIP_CANDIDATE_SHA" | grep -Eq '^[0-9a-f]{40}$'
echo "$AIP_CANDIDATE_SHA" > "$RUN_DIR/candidate-sha"
```

## 2. Build the AIP candidate image once

```bash
frozen_compose build --no-cache architecture-intelligence
docker image inspect --format '{{.Id}}' "aip-i5-candidate:$AIP_CANDIDATE_SHA" > "$RUN_DIR/aip-image"
```

## 3. Run one target's scenario sequence from clean state

Run this block once with `TARGET=quarkus-super-heroes`, then once with `TARGET=apache-airflow`.
Each target starts from `down -v`, so the targets never share graph state.

```bash
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
  for q in Q-INV Q-SRC Q-OWN Q-SVC; do query "$q" "$out/$q.txt"; done
}

frozen_compose down -v
frozen_compose up -d --no-build neo4j
until frozen_compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "RETURN 1" >/dev/null 2>&1; do sleep 2; done

for step in S0 L1 L4a L4b L6 L2 R L5; do run_step "$step"; done
run_step L3 --inventory "$RUN_DIR/$TARGET/L5/Q-INV.txt"   # the tombstone binds the committed L5 inventory
```

Each step's `workdir-digest` must equal its pinned digest in
`tests/unit/test_i5_lifecycle_freeze.py`. L3 is the exception, because its tombstone is bound at run
time; its digest excludes `tombstones.yaml` and is pinned too.

## 4. Evaluate every step against the frozen expectations

**Manual:** for each target and step, compare `$RUN_DIR/<target>/<step>/` with the expected
outcome in `README.md`. Record in the target's `results.md`:
- the verdict for each step;
- the import responses;
- the Q-outputs;
- the `Removed …` log lines.

Each mismatch becomes a finding with exactly one disposition (I5 §11). The pre-identified
import-report observability limitation (`README.md`) is recorded as a finding whatever the step
verdicts are.

## 5. Tear down

```bash
frozen_compose down -v
```

A rerun uses a new `RUN_DIR` and `LIFECYCLE_WORKDIR`, and it repeats steps 1-5.
