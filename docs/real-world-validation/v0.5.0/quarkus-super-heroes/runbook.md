# Runbook: `quarkus-super-heroes` (v0.5.0)

This is the ordered, reproducible process for an I5 Slice 5 qualifying run. The v0.3 runbook
(`../../quarkus-super-heroes/runbook.md`) supplies helper functions and rationale that still apply.
The v0.5 procedure is below. Manual steps are marked **manual**. **Any failed check stops the run.**

**Run identity (I5 §11; PR #240 review).** A run reports three identities:
- its candidate SHA;
- the frozen profile;
- its image identities.

Steps 2-5 make those identities the bytes that actually run:
- the AIP checkout must be the clean, frozen checkout of the candidate;
- the AIP image and the six service images are rebuilt from scratch for every run;
- every builder, base and third-party image is pulled by its frozen digest;
- each running container is checked against what was just built, before any import or traffic.

```bash
export AIP_CHECKOUT=/home/michael/code/ArchitectureIntelligencePlatform   # frozen in profile.md
export DOSSIER="$AIP_CHECKOUT/docs/real-world-validation/v0.5.0/quarkus-super-heroes"
export RUNTIME="$DOSSIER/runtime"
export RUN_DIR="$(mktemp -d)"                                             # this run's records
# Every Compose call goes through frozen_compose (PR #243 review). It uses exactly the frozen
# file, a fixed project name and no env file. So it ignores any gitignored .env (which could set
# COMPOSE_FILE) and any docker-compose.override.yml; the clean-checkout gate can see neither.
frozen_compose() {
  docker compose -p qsh-i5 --project-directory "$RUNTIME" -f "$RUNTIME/docker-compose.yml" \
    --env-file /dev/null "$@"
}
export NEO4J_PASSWORD='replace-with-a-local-password'
```

`docker-compose.yml` requires `NEO4J_PASSWORD`, `AIP_CANDIDATE_SHA` and
`QUARKUS_SUPERHEROES_CHECKOUT`, and it interpolates no other variable. Compose checks them for every
command, including `down`. The last two
are exported by step 2. Run every step in this one shell, including the step 12 teardown.

## 1. Prerequisites

These are the same as v0.3 step 1: Docker with Compose v2, curl, jq, about 10 GB of disk, internet
access, and the listed free ports. `uv` must be installed for this repository.

## 2. Verify the candidate checkout, the pin, and the frozen inputs

```bash
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
```

A dirty AIP checkout, a different location, or any mismatch stops the run. It means the candidate,
the pin or a frozen input is not what the run would report (I5 §§5, 12). The upstream checkout is
a fresh clone inside `$RUN_DIR` for every run, so no earlier build output is ever reused.

## 3. Build the six service images from scratch at the pin

The Maven builder and the upstream `Dockerfile.jvm` base image are pulled by their frozen digests
(`upstream.md`). The base is re-tagged locally under the tag its Dockerfile names, and the build
runs with `--pull=false`. So the unmodified upstream Dockerfile builds on exactly the frozen bytes.
`--no-cache` guarantees that no layer from an earlier build is reused.

```bash
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
```

## 4. Clean state, then build the AIP candidate image from the verified checkout

```bash
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
```

The image is built from `$AIP_CHECKOUT`, which step 2 verified as the clean candidate, and it is
named `aip-i5-candidate:<candidate SHA>`. The build argument `AIP_BUILD_REVISION` makes the running
app report that SHA as its `Producer.build_revision`.

**Disclosed limitation.** The AIP `Dockerfile` bases (`python:3.14-slim`, `ghcr.io/astral-sh/uv:latest`)
are candidate build inputs, not target-profile inputs. Their resolved identity is captured in the
recorded AIP image id. I6 owns the release build gates.

Nothing in the frozen configuration is edited: `config.quarkus-i5.yaml`, `mapping.yaml`,
`declarations/`, `k8s/`, `docker-compose.yml` and `otel-collector-config.yaml`.

## 5. Start the system, verify what runs, and wait for readiness

```bash
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
```

Then wait for readiness with the v0.3 `wait_for_http` and `wait_for_tcp` loops (v0.3 runbook step
5) for:
- `architecture-intelligence`;
- the five in-scope services;
- `grpc-locations`;
- the Collector on port 4318.

A timeout stops the run.

## 6. Import every configured source and record the import response

```bash
curl -sf -X POST http://localhost:8000/api/import | tee "$RUN_DIR/import.json" | jq .
```

**Manual:** record the response in `results.md`. It is expected to show three things (see
`ground-truth.md`, "Checks the comparator cannot express", item 1):
- the declarations source is accepted;
- `qsh-k8s-upstream-unmodified` is `REJECTED_INVALID` with `K8S_RESOURCE_INVALID`;
- `qsh-k8s-namespaced` is `ACCEPTED_WITH_LIMITATIONS` with exactly the frozen limitation list.

Because one source is rejected by design, the top-level `committed` field is `false`. Each
configured source is its own atomic run, so this is expected.

## 7. Verify the OTLP path

This is the same as v0.3 step 7: `frozen_compose logs -f otel-collector`.

## 8. Start the observation window and run the frozen traffic

```bash
WINDOW_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
FIGHTS_URL=http://localhost:8082 ./traffic.sh
```

## 9. Close the window deterministically

This uses the v0.3 step 9 loop, with two v0.5 changes:
- the environment is `quarkus-i5`;
- the loop counts only the CALLS that `expected.yaml` expects `CONFIRMED`. The four
  `NOT_OBSERVED_IN_WINDOW` calls are never exercised.

```bash
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
```

## 10. Capture AIP's actual facts and deployment outcomes

Run this from `runtime/`. `--aip-config` resolves `mapping.yaml` relative to the working directory,
and the mapping artifact is the same file the AIP container mounts. So the capture's
`ArchitectureIntelligenceService` is built from the same configuration as the running app
(`app.mcp.wiring.production_service_kwargs`).

```bash
cd "$RUNTIME"
PYTHONPATH="$AIP_CHECKOUT" uv run --project "$AIP_CHECKOUT" python -m real_world_validation capture \
  --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j \
  --environment quarkus-i5 --since "$WINDOW_START" --until "$WINDOW_END" \
  --scope-entities service:rest-fights,service:rest-heroes,service:rest-villains,service:rest-narration,service:event-statistics \
  --scope-relation-types PROVIDES,CALLS,SENDS,PUBLISHES_TO,RECEIVES_FROM \
  --aip-config config.quarkus-i5.yaml \
  --out "$RUN_DIR/actual.yaml"
cd "$AIP_CHECKOUT"
```

## 11. Compare, check the non-comparator expectations, and store the report

```bash
uv run python -m real_world_validation compare \
  --expected "$DOSSIER/expected.yaml" \
  --actual   "$RUN_DIR/actual.yaml" | tee "$RUN_DIR/compare.txt"
```

Every run output stays in `$RUN_DIR`, outside the checkout. That keeps the candidate checkout clean,
so a paired rerun passes step 2 and step 5 again.

**Manual:** these results go into `results.md`:
- the comparator report;
- the step 6 import response;
- the run identities in `$RUN_DIR`: `candidate-sha`, `service-images`, `aip-image` and
  `compose-images.json`;
- the window;
- the candidate SHA.

Also record the `ground-truth.md` checks 2 and 3 (the Kubernetes inventory, and no messaging
entities) from public reads at the captured snapshot. Every material mismatch becomes a finding in
`findings.md` with exactly one disposition (I5 §11).

## 12. Tear down

```bash
cd "$RUNTIME" && frozen_compose down -v
```

A paired rerun for I5 §12 sets a new `RUN_DIR="$(mktemp -d)"` and repeats steps 2-12 from this
clean state. Step 2 must derive the same `AIP_CANDIDATE_SHA`; if HEAD moved, it is a different
candidate. The `$RUN_DIR` records are committed to the dossier's `artifacts/` and `results.md` only
afterwards, in the Slice 5 results PR.
