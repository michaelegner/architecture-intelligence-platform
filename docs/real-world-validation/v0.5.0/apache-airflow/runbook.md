# Runbook: `apache-airflow` (v0.5.0)

This is the ordered, reproducible process for an I5 Slice 5 qualifying run. The v0.3 runbook
(`../../apache-airflow/runbook.md`) supplies the readiness helpers and rationale that still apply.
The v0.5 procedure is below, and it follows the run-identity pattern the Quarkus dossier froze
(PR #240 review). Manual steps are marked **manual**. **Any failed check stops the run.**

```bash
export AIP_CHECKOUT=/home/michael/code/ArchitectureIntelligencePlatform   # frozen in profile.md
export DOSSIER="$AIP_CHECKOUT/docs/real-world-validation/v0.5.0/apache-airflow"
export RUNTIME="$DOSSIER/runtime"
export RUN_DIR="$(mktemp -d)"                                             # this run's records
export NEO4J_PASSWORD='replace-with-a-local-password'
export FERNET_KEY="$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")"
```

`docker-compose.yml` requires `NEO4J_PASSWORD`, `FERNET_KEY` and `AIP_CANDIDATE_SHA`, and it
interpolates no other variable (PR #242 review). Compose checks them for every command, including
`down`. Step 2 exports `AIP_CANDIDATE_SHA`. Run every step in this
one shell, including the step 12 teardown. `FERNET_KEY` is generated per run and never committed.

## 1. Prerequisites

These are the same as v0.3 step 1:
- Docker with Compose v2, curl, jq and `uv`;
- `python3` (standard library only; used for `FERNET_KEY` and by `traffic.sh` for JSON parsing);
- internet access;
- free ports 7474, 7687, 8000, 8080, 4317 and 4318.

## 2. Verify the candidate checkout and the frozen input

```bash
set -euo pipefail
cd "$AIP_CHECKOUT"
[ "$(pwd -P)" = "$AIP_CHECKOUT" ]                         # the one frozen absolute location (I5 §12)
[ -z "$(git status --porcelain)" ] || { echo "checkout is not clean" >&2; exit 1; }
export AIP_CANDIDATE_SHA="$(git rev-parse HEAD)"
echo "$AIP_CANDIDATE_SHA" | grep -Eq '^[0-9a-f]{40}$'
echo "$AIP_CANDIDATE_SHA" > "$RUN_DIR/candidate-sha"

# The upstream-supplied OpenAPI is byte-identical to the pin (profile.md).
curl -sSfL -o "$RUN_DIR/openapi.yml" \
  https://raw.githubusercontent.com/apache/airflow/3adbbe1c58e4532df1964cb7794805e763816ee8/airflow-core/src/airflow/api_fastapi/core_api/openapi/v2-rest-api-generated.yaml
cmp "$RUN_DIR/openapi.yml" "$RUNTIME/declarations/airflow-apiserver/openapi.yml"
```

A dirty checkout, a different location, or a mismatch stops the run (I5 §§5, 12).

## 3. Pull the pinned images

```bash
cd "$RUNTIME"
: "${NEO4J_PASSWORD:?}" "${FERNET_KEY:?}" "${AIP_CANDIDATE_SHA:?}"
unset COMPOSE_FILE COMPOSE_PROFILES   # only this dossier's docker-compose.yml, no extra profiles

# PR #242 review: the run must mount exactly this dossier's frozen Dag directory. The Compose file
# has no environment override for it, and this check proves it on the resolved configuration.
[ "$(docker compose config --format json | jq -r '
    [.services[] | .volumes[]? | select(.target == "/opt/airflow/dags") | .source] | unique | .[]')"   = "$RUNTIME/dags" ] || { echo "Dag mount is not $RUNTIME/dags" >&2; exit 1; }

docker compose pull --ignore-buildable   # every third-party image is referenced as tag@digest
```

## 4. Clean state, then build the AIP candidate image from the verified checkout

```bash
docker compose down -v            # I5 §11: every run begins from clean AIP and upstream state
docker compose build --no-cache architecture-intelligence
docker image inspect --format '{{.Id}}' "aip-i5-candidate:$AIP_CANDIDATE_SHA" > "$RUN_DIR/aip-image"
```

**Disclosed limitation.** The AIP `Dockerfile` bases are candidate build inputs, and I6 owns the
release build gates for them (the same as for Quarkus). Their resolved identity is captured in the
recorded AIP image id.

## 5. Start the system, verify what runs, and wait for readiness

```bash
docker compose up -d --no-build --force-recreate --scale airflow-worker=2

check_image() {  # <container id> <expected image id>
  local actual
  actual="$(docker inspect --format '{{.Image}}' "$1")"
  [ "$actual" = "$2" ] || { echo "$1 runs $actual, expected $2" >&2; exit 1; }
}
check_image "$(docker compose ps -q architecture-intelligence)" "$(cat "$RUN_DIR/aip-image")"
[ "$(docker compose exec -T architecture-intelligence printenv AIP_BUILD_REVISION)" = \
  "$AIP_CANDIDATE_SHA" ]
[ "$(docker compose ps -q airflow-worker | wc -l)" -eq 2 ]

# Every other image is referenced by digest in docker-compose.yml, so Docker cannot run other
# bytes. Record them anyway.
docker compose images --format json > "$RUN_DIR/compose-images.json"
[ -z "$(git -C "$AIP_CHECKOUT" status --porcelain)" ]   # still the clean candidate
```

Then run the v0.3 step 3 readiness block (`wait_for_http`, `wait_for_tcp`,
`wait_for_service_healthy`, `wait_for_dag_registered`), with these arguments:
- AIP health;
- `airflow-apiserver` `/api/v2/monitor/health`;
- the Collector on port 4318;
- scheduler, dag-processor and triggerer, 1 each;
- `airflow-worker`, 2;
- Dag `i3_validation` registered.

A timeout stops the run.

## 6. Import every configured source and record the import response

```bash
curl -sf -X POST http://localhost:8000/api/import | tee "$RUN_DIR/import.json" | jq .
```

**Manual:** check that the declarations source is accepted. This is `ground-truth.md`, "Checks the
comparator cannot express", item 1.

## 7. Verify the OTLP path

This is the same as v0.3 step 5: `docker compose logs -f otel-collector`.

## 8. Start the observation window and run the frozen traffic

```bash
WINDOW_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
API_URL=http://localhost:8080 ./traffic.sh
```

## 9. Close the window after the drain barrier

This is the v0.3 step 6 drain barrier, unchanged. Airflow's native spans correlate to no declared
relation, so the drain signal is AIP's own successful `/v1/traces` ingestion:

```bash
sleep 15   # longer than otel-collector-config.yaml's 5s batch timeout
RECEIVED=0
for i in $(seq 1 15); do
  RECEIVED="$(docker compose logs --since "$WINDOW_START" architecture-intelligence 2>/dev/null \
    | grep -c 'POST /v1/traces HTTP/1.1" 200' || true)"
  [ "${RECEIVED:-0}" -gt 0 ] && break
  sleep 2
done
[ "${RECEIVED:-0}" -gt 0 ] || { echo "no /v1/traces ingestion since $WINDOW_START" >&2; exit 1; }
WINDOW_END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "environment=airflow-i5 window_start=$WINDOW_START window_end=$WINDOW_END"
```

## 10. Capture AIP's actual facts

There is no `--aip-config`, because Airflow has no Kubernetes input and no mapping, and
`expected.yaml` has no `deployments`.

```bash
cd "$AIP_CHECKOUT"
uv run python -m real_world_validation capture \
  --neo4j-uri bolt://localhost:7687 --neo4j-user neo4j \
  --environment airflow-i5 --since "$WINDOW_START" --until "$WINDOW_END" \
  --scope-entities "$(uv run python -c "
import yaml
print(','.join(yaml.safe_load(open('$DOSSIER/expected.yaml'))['scope']['entities']))")" \
  --scope-relation-types PROVIDES,CALLS,SENDS,PUBLISHES_TO,RECEIVES_FROM \
  --out "$RUN_DIR/actual.yaml"
```

## 11. Compare, check the non-comparator expectations, and store the report

```bash
uv run python -m real_world_validation compare \
  --expected "$DOSSIER/expected.yaml" \
  --actual   "$RUN_DIR/actual.yaml" | tee "$RUN_DIR/compare.txt"
```

Every run output stays in `$RUN_DIR`, outside the checkout, so a paired rerun passes steps 2 and 5
again.

**Manual:** these results go into `results.md`:
- the comparator report;
- the step 6 import response;
- the run identities in `$RUN_DIR`: `candidate-sha`, `aip-image` and `compose-images.json`;
- the window.

Also record the `ground-truth.md` checks 2 and 3 (no role Services, and no messaging entities) from
public reads at the captured snapshot. Every material mismatch becomes a finding in `findings.md`
with exactly one disposition (I5 §11).

## 12. Tear down

```bash
cd "$RUNTIME" && docker compose down -v
```

A paired rerun for I5 §12 sets a new `RUN_DIR="$(mktemp -d)"` and a new `FERNET_KEY`. It then
repeats steps 2-12 from this clean state. Step 2 must derive the same `AIP_CANDIDATE_SHA`; if HEAD
moved, it is a different candidate. The `$RUN_DIR` records are committed to the dossier's
`artifacts/` and `results.md` only afterwards, in the Slice 5 results PR.
