# Runbook: `quarkus-super-heroes` (v0.5.0)

This is the ordered, reproducible process for an I5 Slice 5 qualifying run. Steps 1-5 carry over
from the v0.3 runbook (`../../quarkus-super-heroes/runbook.md`), whose helper functions and
rationale still apply. Steps 6-12 are the v0.5 procedure. Manual steps are marked **manual**.

Commands run from the one absolute checkout location frozen in `profile.md`, unless a step says
otherwise:

```bash
export AIP_CHECKOUT=/home/michael/code/ArchitectureIntelligencePlatform
export DOSSIER="$AIP_CHECKOUT/docs/real-world-validation/v0.5.0/quarkus-super-heroes"
export RUNTIME="$DOSSIER/runtime"
```

## 1. Prerequisites

These are the same as v0.3 step 1: Docker with Compose v2, curl, jq, about 10 GB of disk,
internet access, and the listed free ports. `uv` must be installed for this repository.

## 2. Fetch the pinned upstream version and verify the frozen inputs

```bash
export QUARKUS_SUPERHEROES_CHECKOUT="$HOME/quarkus-super-heroes-i5"   # outside this repository
git clone https://github.com/quarkusio/quarkus-super-heroes.git "$QUARKUS_SUPERHEROES_CHECKOUT"
git -C "$QUARKUS_SUPERHEROES_CHECKOUT" checkout 8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce

# Every upstream-supplied input is byte-identical to the pin (profile.md).
for s in rest-fights rest-heroes rest-villains rest-narration; do
  cmp "$QUARKUS_SUPERHEROES_CHECKOUT/$s/src/main/resources/openapi/openapi.yml" \
      "$RUNTIME/declarations/$s/openapi.yml"
done
cmp "$QUARKUS_SUPERHEROES_CHECKOUT/deploy/k8s/java25-kubernetes.yml" \
    "$RUNTIME/k8s/unmodified/java25-kubernetes.yml"

# The upstream-derived copy regenerates byte-for-byte (I5 §5).
cd "$RUNTIME/k8s"
uv run --project "$AIP_CHECKOUT" python derive_namespaced.py \
  "$QUARKUS_SUPERHEROES_CHECKOUT/deploy/k8s/java25-kubernetes.yml" /tmp/qsh-namespaced.yml
cmp /tmp/qsh-namespaced.yml namespaced/java25-kubernetes.namespaced.yml
cd "$AIP_CHECKOUT"
```

Any mismatch stops the run. It means the pin or a frozen input changed (I5 §5).

## 3. Build the six service images at the pinned commit

This is the same as v0.3 step 3. Afterwards, record the built image digests for `results.md`:

```bash
for svc in rest-fights rest-heroes rest-villains rest-narration event-statistics grpc-locations; do
  docker image inspect --format "{{.Id}} quarkus-super-heroes/$svc:8ea0337" \
    "quarkus-super-heroes/$svc:8ea0337"
done
```

## 4. Clean state and configuration

```bash
cd "$RUNTIME"
docker compose down -v            # I5 §11: every run begins from clean AIP and upstream state
export NEO4J_PASSWORD=<a local password>
```

Nothing is edited. The frozen configuration is `config.quarkus-i5.yaml`, `mapping.yaml`,
`declarations/`, `k8s/`, `docker-compose.yml` and `otel-collector-config.yaml`.

## 5. Start the system and wait for readiness

```bash
docker compose up -d
docker compose images --format json > /tmp/qsh-images.json   # the pulled digests, for results.md
```

Wait with the v0.3 `wait_for_http` and `wait_for_tcp` loops (v0.3 runbook step 5) for:
- `architecture-intelligence`;
- the five in-scope services;
- `grpc-locations`;
- the Collector on port 4318.

A timeout stops the run.

## 6. Import every configured source and record the import response

```bash
curl -sf -X POST http://localhost:8000/api/import | tee /tmp/qsh-import.json | jq .
```

**Manual:** record the response in `results.md`. It is expected to show three things (see
`ground-truth.md`, "Checks the comparator cannot express", item 1):
- the declarations source is accepted;
- `qsh-k8s-upstream-unmodified` is `REJECTED_INVALID` with `K8S_RESOURCE_INVALID`;
- `qsh-k8s-namespaced` is `ACCEPTED_WITH_LIMITATIONS` with exactly the frozen limitation list.

Because one source is rejected by design, the top-level `committed` field is `false`. Each
configured source is its own atomic run, so this is expected.

## 7. Verify the OTLP path

This is the same as v0.3 step 7: `docker compose logs -f otel-collector`.

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
mkdir -p "$DOSSIER/artifacts"
PYTHONPATH="$AIP_CHECKOUT" uv run --project "$AIP_CHECKOUT" python -m real_world_validation capture \
  --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j \
  --environment quarkus-i5 --since "$WINDOW_START" --until "$WINDOW_END" \
  --scope-entities service:rest-fights,service:rest-heroes,service:rest-villains,service:rest-narration,service:event-statistics \
  --scope-relation-types PROVIDES,CALLS,SENDS,PUBLISHES_TO,RECEIVES_FROM \
  --aip-config config.quarkus-i5.yaml \
  --out "$DOSSIER/artifacts/actual.yaml"
cd "$AIP_CHECKOUT"
```

## 11. Compare, check the non-comparator expectations, and store the report

```bash
uv run python -m real_world_validation compare \
  --expected "$DOSSIER/expected.yaml" \
  --actual   "$DOSSIER/artifacts/actual.yaml" | tee "$DOSSIER/artifacts/compare.txt"
```

**Manual:** these results go into `results.md`:
- the comparator report;
- the step 6 import response;
- the image digests from steps 3 and 5;
- the window;
- the candidate SHA.

Also record the `ground-truth.md` checks 2 and 3 (the Kubernetes inventory, and no messaging
entities) from public reads at the captured snapshot. Every material mismatch becomes a finding in
`findings.md` with exactly one disposition (I5 §11).

## 12. Tear down

```bash
cd "$RUNTIME" && docker compose down -v
```

A paired rerun for I5 §12 repeats steps 4-12 from this clean state against the same candidate.
