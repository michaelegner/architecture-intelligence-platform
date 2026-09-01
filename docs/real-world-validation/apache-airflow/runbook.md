# Runbook — Apache Airflow

Ordered, reproducible process (I1 §28). **I3.2 owns and fully specifies phases 1-7** (setup through
Phase B's raw telemetry qualification and reset); **phases 8-10 belong to I3.3** (the first
qualifying AIP comparison itself) and are only stubbed here so the file stays a complete pipeline
reference — see the note at the end of each, matching `quarkus-super-heroes/runbook.md`'s own
phase-ownership split.

All commands assume a shell at the root of *this* repository (`architecture-intelligence-platform`)
unless otherwise noted. Artifacts referenced below live under
`docs/real-world-validation/apache-airflow/runtime/`.

## 1. Prerequisites

```text
Docker (with Compose v2)
curl, jq, python3 (stdlib only - readiness/token/poll helpers below, no extra pip packages)
CPU: 2 cores minimum, 4 recommended (I3 spec §57 - matches the official Compose file's own
    documented minimum for this exact component set: Postgres, Redis, 4 Airflow role containers,
    2 worker replicas, AIP, Neo4j, Collector)
RAM: 8 GB minimum, 12 GB recommended
~6 GB free disk (apache/airflow image + Postgres/Redis/Neo4j/Collector + AIP)
Internet access (pull apache/airflow:3.3.1, postgres:16.15, redis:7.2-bookworm, the pinned Collector
digest, and this repo's own image build)
Ports free on the host: 7474, 7687, 8000, 8080, 4317, 4318
Expected startup time: under 2 minutes to every service healthy from a clean `docker compose up -d`
    (observed during I3.2's own runs); investigate rather than wait past ~5 minutes.
```

Unlike Quarkus (I2.2), no external checkout/build step is needed — Airflow ships prebuilt release
images, so `docker-compose.yml`'s `AIRFLOW_IMAGE_NAME` pin is used directly.

## 2. Configure the profile

```bash
export NEO4J_PASSWORD=<a local password>
export FERNET_KEY=$(python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
```

Both are Fernet-compatible secrets generated locally per run (Airflow's own metadata-encryption key)
— neither is committed, logged, or reused across runs; the Python one-liner above uses only the
standard library (no `cryptography` package required — a Fernet key is exactly 32 random bytes,
URL-safe base64 encoded). `docker-compose.yml`'s `NEO4J_PASSWORD`/`FERNET_KEY` guards fail fast if
either is missing. Nothing else needs editing — `runtime/docker-compose.yml`,
`runtime/config.airflow-i3.yaml`, and `runtime/otel-collector-config.yaml` are already the frozen
I3.2 configuration.

## 3. Start the system

```bash
cd docs/real-world-validation/apache-airflow/runtime
docker compose up -d --scale airflow-worker=2
```

Per I3 spec §9's preference for two Celery worker instances (a direct test of runtime-instance vs.
logical-architecture identity, `../ground-truth.md`'s "Multiple runtime instances") — the official
Compose file sets no `container_name` on `airflow-worker`, so this scales without a rewrite. If this
proves operationally impractical, fall back to `--scale airflow-worker=1` with the reason recorded
in `../profile.md` and this file (I3 spec §9 requires the multiple-instance question stay explicit
either way).

Compose's `depends_on` only orders container *starts*, not application readiness (same PR #40 review
F3 lesson Quarkus's runbook already encodes) — wait with a bounded, retried loop instead of racing a
one-shot `curl`:

```bash
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

# The apiserver can report healthy before the scheduler/dag-processor/triggerer/workers have
# finished their own startup (PR #45 review F3) - none of those four expose an HTTP health endpoint
# on the host, so poll each container's own Docker healthcheck status instead (assumes the default
# Compose project name, i.e. this directory's basename "runtime", giving container names
# runtime-<service>-N per `docker compose ps`).
wait_for_container_healthy() {
  local name="$1" timeout="${2:-180}" waited=0
  until [ "$(docker inspect -f '{{.State.Health.Status}}' "$name" 2>/dev/null)" = "healthy" ]; do
    waited=$((waited + 2))
    if [ "$waited" -ge "$timeout" ]; then
      echo "$name did not become healthy within ${timeout}s - see: docker compose logs $name" >&2
      return 1
    fi
    sleep 2
  done
  echo "$name healthy after ${waited}s"
}

# The DAG must actually be parsed and registered before phase 6 triggers it - `airflow dags details`
# succeeds only once the dag-processor has written it to the metadata DB (bounded, retried; no HTTP
# auth token exists yet at this point in the runbook).
wait_for_dag_registered() {
  local dag_id="$1" timeout="${2:-120}" waited=0
  until docker compose exec -T airflow-scheduler airflow dags details "$dag_id" >/dev/null 2>&1; do
    waited=$((waited + 2))
    if [ "$waited" -ge "$timeout" ]; then
      echo "$dag_id was not registered within ${timeout}s - see: docker compose logs airflow-dag-processor" >&2
      return 1
    fi
    sleep 2
  done
  echo "$dag_id registered after ${waited}s"
}

wait_for_http architecture-intelligence http://localhost:8000/health
wait_for_http airflow-apiserver         http://localhost:8080/api/v2/monitor/health
wait_for_tcp  otel-collector            localhost 4318
wait_for_container_healthy runtime-airflow-scheduler-1
wait_for_container_healthy runtime-airflow-dag-processor-1
wait_for_container_healthy runtime-airflow-triggerer-1
wait_for_container_healthy runtime-airflow-worker-1
wait_for_container_healthy runtime-airflow-worker-2
wait_for_dag_registered i3_validation
```

Proceed to phase 4 only once every check above succeeds; a timeout means investigate
(`docker compose logs <service>`) rather than retrying the import/traffic phases against a
half-started stack.

## 4. Import declared architecture into AIP

```bash
curl -sf -X POST http://localhost:8000/api/import
```

This imports `runtime/declarations/airflow-apiserver/openapi.yml` (verbatim pinned contract, the
complete 88-path document) via the same `POST /api/import` endpoint and
`sources.directories`-driven mechanism this repo's own runtime demo uses, pointed at
`runtime/config.airflow-i3.yaml`'s `sources.directories: [declarations]` instead. No manifest is
imported — I3.1 established no `CALLS` ground truth for Airflow.

## 5. Confirm OTLP routing is live

Every Airflow component's `OTEL_EXPORTER_OTLP_ENDPOINT` points at `otel-collector:4318`
(`runtime/docker-compose.yml`), and `otel-collector-config.yaml`'s `otlphttp/aip` exporter forwards
every batch to `architecture-intelligence:8000/v1/traces`. No source-code instrumentation change was
needed (I3 spec §28) — confirm the path is live by tailing the Collector's `debug` exporter output
once phase 6 sends traffic:

```bash
docker compose logs -f otel-collector
```

## 6. Phase B — raw telemetry qualification (I3 spec §48, this task's core responsibility)

This is the step I3.1 deferred: `../ground-truth.md`'s "Provisional scope of this freeze" left the
Celery/Redis messaging boundary open pending independent raw OTel evidence, and I3.2 SHALL close
that freeze gate before I3.3's comparison runs.

```bash
WINDOW_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

API_URL=http://localhost:8080 ./traffic.sh
```

`traffic.sh` (I3 spec §33) authenticates via `POST /auth/token`, confirms readiness, exercises the
remaining 8 of the 9 selected `/api/v2` operations, triggers the `i3_validation` Dag with a
caller-chosen `dag_run_id` (`POST .../dagRuns`), polls it to a terminal state (`GET
.../dagRuns/{dag_run_id}`), and asserts both tasks completed on the expected queue (`GET
.../taskInstances`). It does not itself decide when the observation window ends — task execution is
asynchronous and OTLP may flush after client traffic completes (I3 spec §31: `traffic completion !=
observation window end`), so `traffic.sh` finishing is not sufficient grounds to close the window
(PR #45 review F1 — an earlier version had the script and this runbook independently stamp two
different, undrained `window_end` values).

**Drain barrier — the window closes only once this succeeds.** Quarkus's own runbook phase 9 polls
`GET /api/runtime/relations` and waits for a non-empty result, because Quarkus's REST/Kafka spans are
HTTP-correlated and AIP derives a canonical relation from them. Airflow's native tracing produces
task/dagrun/execution-API spans only (`profile.md`'s "OTel configuration") — these do not correlate
to any declared `Operation`/`Queue`, so `/api/runtime/relations` legitimately stays empty even once
telemetry has landed (confirmed while writing this fix: it returned `{"relations": []}` with actual
spans already ingested). The valid, system-shape-independent drain signal here is AIP's own access
log entry for the ingestion request itself:

```bash
sleep 15   # comfortably longer than otel-collector-config.yaml's 5s batch timeout

for i in $(seq 1 15); do
  RECEIVED="$(
    docker compose logs --since "$WINDOW_START" architecture-intelligence 2>/dev/null \
      | grep -c 'POST /v1/traces HTTP/1.1" 200'
  )"
  [ "${RECEIVED:-0}" -gt 0 ] && break
  sleep 2
done

if [ "${RECEIVED:-0}" -eq 0 ]; then
  echo "AIP logged no successful /v1/traces ingestion since $WINDOW_START after waiting - check: docker compose logs otel-collector architecture-intelligence" >&2
  exit 1
fi

WINDOW_END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "environment=airflow-i3 window_start=$WINDOW_START window_end=$WINDOW_END"
```

Only once this succeeds has AIP actually received the OTLP batches phase 6's traffic produced.
`WINDOW_END` recorded here — after the drain, not immediately after `traffic.sh` exits — is the one
authoritative value I3.3 uses.

Inspect the raw evidence **independently of AIP** — this is a raw-telemetry read, not an AIP query:

```bash
docker compose logs otel-collector | grep -A 30 "Resource attributes" | less
```

Answer, from the raw spans alone, per I3 spec §23's qualification rule (a `SENDS`/`RECEIVES_FROM`
fact is only expected when *all* of these are independently established and raw telemetry exposes
them):

```text
1. Is sender/consumer logical identity sufficiently established from the resource attributes seen
   (scheduler/worker service.name)?
2. Does any span distinguish a queue destination from the bare Redis broker endpoint?
3. Is the actual queue name (the pinned `[operators] default_queue`, "default") visible in any span
   attribute?
4. Is send vs. receive direction visible?
```

If native Airflow tracing does not expose enough messaging attributes to answer these, I3 spec §29
permits adding standard, pinned OpenTelemetry Celery instrumentation (`opentelemetry-instrumentation-celery`)
— **only** to make the existing interaction observable, never "to make AIP pass" — with the decision
and exact pinned version recorded in `../profile.md` before repeating this phase.

**Outcome, either way, closes the freeze gate:**
- If sufficient: amend `../expected.yaml` with the qualified `SENDS`/`RECEIVES_FROM` relation(s) and
  update `../ground-truth.md`'s Change log per its own documented amendment policy.
- If not sufficient: leave/refine the existing `insufficient_evidence`/`unresolved_identity` entries
  with the specific reason raw evidence didn't qualify, and record that in the Change log too.

Either outcome is a valid, spec-compliant Phase B close — spec §23 explicitly allows
`INSUFFICIENT_EVIDENCE`/`UNSUPPORTED` as legitimate results, not just a qualified relation.

## 7. Clean-state / reset procedure (I3 spec §58)

```bash
docker compose down -v
```

Resets the Airflow Postgres volume, Redis broker state, AIP Neo4j state, and the named
`airflow-i3-logs`/`airflow-i3-config`/`airflow-i3-plugins` volumes (Airflow logs, the generated
`airflow.cfg`, and any diagnostic plugin) — spec §58's full list (also: no queued Celery messages and
no Dag Run state survive into the next run). These three are named Docker volumes, not host bind
mounts (PR #45 review F2 — a host bind mount is never removed by `down -v`), so this actually empties
them rather than only claiming to. `dags/` is a host bind mount and is untouched by `down -v`, but it
holds only this repo's own committed `i3_validation.py`, never generated state. Rerun phases 3-6 once
from this clean state to confirm the profile is actually repeatable before treating Phase B's
qualification as trustworthy.

---

**Phases 8-10 (execute comparison, store report, tear down) belong to I3.3.** Reference for what
they will do, per the I1 runbook contract (§28) and I3 spec §48's Phase D:

```text
8. Query/capture AIP result   - export AIP's actual canonical facts for environment=airflow-i3 /
                                  [window_start, window_end] into a real_world_validation actual-
                                  facts capture (real_world_validation/README.md's schema)
   Execute comparison         - uv run python -m real_world_validation compare
                                  --expected docs/real-world-validation/apache-airflow/expected.yaml
                                  --actual   <the capture above>
9. Store deterministic report  - results.md / findings.md
10. Tear down environment      - docker compose down -v (this profile)
```

## Clean-state requirement (I1 §29 / I3 spec §58)

Every qualifying run begins from clean state. Before phase 3 (and again before any rerun):

```bash
cd docs/real-world-validation/apache-airflow/runtime
docker compose down -v
```

`docker compose down -v` removes every named volume declared in `docker-compose.yml`: the Neo4j
volumes (`neo4j-airflow-i3-data`/`-logs`), the Postgres volume (`postgres-db-volume`), Redis's
anonymous volume, and the Airflow `airflow-i3-logs`/`-config`/`-plugins` volumes — so a subsequent
`docker compose up -d` starts from a genuinely empty graph, empty metadata database, empty broker,
and empty Airflow logs/config/plugins state — no run depends on unexplained state an earlier run left
behind.
