# Runbook — Quarkus Super Heroes

Ordered, reproducible process (I1 §28). **I2.2 owns and fully specifies phases 1-9** (setup through
traffic execution); **phases 10-12 belong to I2.3** (the first qualifying run itself) and are only
stubbed here so the file stays a complete pipeline reference — see the note at the end of each.

All commands assume a shell at the root of *this* repository (`architecture-intelligence-platform`)
unless otherwise noted. Artifacts referenced below live under
`docs/real-world-validation/quarkus-super-heroes/runtime/`.

## 1. Prerequisites

```text
Docker (with Compose v2)
curl, jq (readiness/drain-barrier checks in phases 5 and 9)
~10 GB free disk (6 Quarkus JVM images - the 4 REST services + event-statistics + grpc-locations -
plus Mongo/2×Postgres/MariaDB/Kafka/Apicurio/Neo4j/Collector)
Internet access (clone GitHub, pull base images, pull Maven dependencies)
Ports free on the host: 7474, 7687, 8000, 8082-8087, 8089, 4317, 4318, 9092
```

No JDK/Maven needs to be installed on the host — phase 3 builds each service's jar inside a pinned
`maven:3.9.16-eclipse-temurin-25` container.

## 2. Fetch the pinned upstream version

```bash
export QUARKUS_SUPERHEROES_CHECKOUT="$HOME/quarkus-super-heroes-i2"   # anywhere outside this repo
git clone https://github.com/quarkusio/quarkus-super-heroes.git "$QUARKUS_SUPERHEROES_CHECKOUT"
git -C "$QUARKUS_SUPERHEROES_CHECKOUT" checkout 8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
```

This checkout is **never committed into this repository** (I1 §36/§39) — `docker-compose.yml`
below reads it only through `$QUARKUS_SUPERHEROES_CHECKOUT`.

## 3. Build the six required services' images at the pinned commit

Each service needs a jar built (containerized, using the exact pinned `maven:3.9.16-eclipse-temurin-25`
image so no host JDK 25 is required) and then packaged into its own runtime image via its own
`src/main/docker/Dockerfile.jvm` — **not** pulled from `quay.io/quarkus-super-heroes/*:java25-latest`
(`runtime/README.md` explains why that tag doesn't represent this exact commit). `grpc-locations`
is included because `rest-fights` depends on it to start, even though it is not part of AIP's
supported/compared scope (`profile.md`).

```bash
set -euo pipefail   # a failed build must stop the loop, not silently leave stale local images

for svc in rest-fights rest-heroes rest-villains rest-narration event-statistics grpc-locations; do
  docker run --rm -v "$QUARKUS_SUPERHEROES_CHECKOUT:/workspace" -w "/workspace/$svc" \
    maven:3.9.16-eclipse-temurin-25 ./mvnw -q package -DskipTests

  docker build -f "$QUARKUS_SUPERHEROES_CHECKOUT/$svc/src/main/docker/Dockerfile.jvm" \
    -t "quarkus-super-heroes/$svc:8ea0337" "$QUARKUS_SUPERHEROES_CHECKOUT/$svc"
done
```

## 4. Configure the profile

Nothing to edit — `runtime/docker-compose.yml`, `runtime/config.quarkus-i2.yaml`, and
`runtime/otel-collector-config.yaml` are already the frozen I2.2 configuration. Set the two
required environment variables (`docker-compose.yml`'s `NEO4J_PASSWORD`/`QUARKUS_SUPERHEROES_CHECKOUT`
guards fail fast if either is missing):

```bash
export NEO4J_PASSWORD=<a local password>
# QUARKUS_SUPERHEROES_CHECKOUT already exported in phase 2
```

## 5. Start the system

```bash
cd docs/real-world-validation/quarkus-super-heroes/runtime
docker compose up -d
```

`architecture-intelligence` waits on `neo4j`'s healthcheck; the six Quarkus services wait on their
own datastores/Kafka/Apicurio — but Compose's `depends_on` only orders container *starts*, not
application readiness, so a clean multi-service boot (Mongo/2×Postgres/MariaDB/Kafka/Apicurio/Neo4j
plus seven application containers) has no fixed duration. A one-shot `curl` right after `up -d` is
therefore a race, not a readiness gate (PR #40 review F3) — wait with a bounded, retried loop
instead:

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

wait_for_http architecture-intelligence  http://localhost:8000/health
wait_for_http rest-fights-java25         http://localhost:8082/q/health/ready
wait_for_http rest-heroes-java25         http://localhost:8083/q/health/ready
wait_for_http rest-villains-java25       http://localhost:8084/q/health/ready
wait_for_http rest-narration-java25      http://localhost:8087/q/health/ready
wait_for_http event-statistics-java25    http://localhost:8085/q/health/ready
wait_for_http grpc-locations-java25      http://localhost:8089/q/health/ready
wait_for_tcp  otel-collector             localhost 4318
```

(`name` above is each service's actual `docker-compose.yml` service key, e.g. `rest-fights-java25`
— not the bare `rest-fights` — so a timeout's suggested `docker compose logs $name` command
actually resolves.)

Proceed to phase 6 only once every check above succeeds; a timeout means investigate
(`docker compose logs <service>`) rather than retrying the import/traffic phases against a
half-started stack.

## 6. Import declared architecture sources into AIP

```bash
curl -sf -X POST http://localhost:8000/api/import
```

This imports `runtime/declarations/{rest-fights,rest-heroes,rest-villains,rest-narration}/openapi.yml`
(verbatim pinned contracts) and `runtime/declarations/rest-fights/architecture.yaml` (the frozen
manifest, `runtime/README.md`) — the same `POST /api/import` endpoint and
`sources.directories`-driven mechanism this repo's own runtime demo uses
(`docker-compose.demo.yml`), pointed at `runtime/config.quarkus-i2.yaml`'s `sources.directories:
[declarations]` instead.

## 7. Configure/verify OTLP routing

Already wired: every validated service's `QUARKUS_OTEL_EXPORTER_OTLP_ENDPOINT` points at
`otel-collector:4318` (`docker-compose.yml`), and `otel-collector-config.yaml`'s `otlphttp/aip`
exporter forwards every batch to `architecture-intelligence:8000/v1/traces`. No source-code
instrumentation change was needed (I2 spec §16) — confirm the path is live by tailing the
Collector's `debug` exporter output once phase 8 sends traffic:

```bash
docker compose logs -f otel-collector
```

## 8. Start the observation window, then execute traffic

```bash
WINDOW_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

FIGHTS_URL=http://localhost:8082 ./traffic.sh
```

`traffic.sh` (I2 spec §19) exercises, in the order `FightService.java` actually calls them: hero +
villain retrieval (one `GET /api/fights/randomfighters` call triggers both), the `grpc-locations`
dependency (`GET /api/fights/randomlocation`), a fight (`POST /api/fights` — persists and publishes
to Kafka topic `fights`, which `event-statistics` consumes), and narration (`POST
/api/fights/narrate`, a separate call from `performFight`). `WINDOW_END` is not stamped here —
phase 9 determines it, because the raw completion timestamp of `traffic.sh` is not itself a safe
window boundary (see below).

## 9. Close the observation window deterministically, then confirm OTLP ingestion

`otel-collector-config.yaml`'s batch processor can legally hold the tail of phase 8's spans for up
to its configured `timeout: 5s` before forwarding a partial batch, and the narration call's span in
particular has been observed to land several seconds after `traffic.sh` itself returns (I2.4's
"Revalidation" section; I4.4's `revalidation.md` run 1 recorded a ~5s gap) — a `WINDOW_END` stamped
immediately after `traffic.sh` completes is therefore not a safe boundary: querying AIP against it
risks a race where a real `CONFIRMED` fact is still sitting in the Collector's buffer, silently
reading back as `NOT_OBSERVED_IN_WINDOW` depending on timing alone (PR #40 review F2; I4.4 review
F3 — an earlier version of this phase left closing that gap to per-run operator judgment, which
produced two different, undocumented `WINDOW_END` values across I4.4's two runs).

Close the window only once every relation phase 8's traffic is declared to confirm has actually
landed, bounded by a maximum wait — never by stamping `WINDOW_END` up front and hoping, and never by
an ad hoc post hoc widening:

```bash
EXPECTED_CALLS="$(
  uv run python -c "
import yaml
doc = yaml.safe_load(open('../expected.yaml'))
print(sum(1 for f in doc['expected']['relations'] if f['type'] == 'CALLS'))
"
)"   # derived from expected.yaml, not hand-typed — stays correct if the frozen scope ever changes

MAX_WAIT=60   # comfortably longer than the 5s batch timeout plus the observed narration lag
WAITED=0
CONFIRMED=0
WINDOW_END=""

while [ "$WAITED" -lt "$MAX_WAIT" ]; do
  NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  CONFIRMED="$(
    curl -sfG "http://localhost:8000/api/analysis/runtime/confirmed" \
      --data-urlencode "environment=quarkus-i2" \
      --data-urlencode "since=$WINDOW_START" \
      --data-urlencode "until=$NOW" \
    | jq '.relations | length'
  )"
  if [ "${CONFIRMED:-0}" -ge "$EXPECTED_CALLS" ]; then
    WINDOW_END="$NOW"
    break
  fi
  sleep 2
  WAITED=$((WAITED + 2))
done

if [ -z "$WINDOW_END" ]; then
  echo "only ${CONFIRMED:-0}/$EXPECTED_CALLS expected CALLS relations observed within ${MAX_WAIT}s - check: docker compose logs otel-collector architecture-intelligence" >&2
  exit 1
fi

echo "environment=quarkus-i2 window_start=$WINDOW_START window_end=$WINDOW_END (closed after ${WAITED}s, $CONFIRMED/$EXPECTED_CALLS CALLS confirmed)"
```

`GET /api/analysis/runtime/confirmed` (`app/api/runtime.py`'s `get_confirmed`, spec §43/§47's O2 —
declared ∩ observed) is the endpoint that actually means "CONFIRMED": counting it (not `GET
/api/runtime/relations`, the raw O1 "observed" listing, whose `status` field is always the literal
string `"OBSERVED"` and never `"CONFIRMED"` — an earlier version of this phase queried that endpoint
and filtered for a status value it can never return, which silently never terminated the loop before
its bound) is what makes this a real completion check rather than a "something arrived" check.
Scoping the query to `since`/`until` (not the `from`/`to` query params, which filter by canonical
entity id, not by time) also matters: without it, unrelated startup/health-check traffic from the
clean stack could satisfy the count even if phase 8's qualifying traffic itself produced nothing.

`WINDOW_END` is the wall-clock timestamp at which every expected `CALLS` relation was first
observed `CONFIRMED` — a value the procedure derives itself, bounded by `MAX_WAIT`, not a value an
operator chooses per run. Two runs of this exact procedure may legitimately take a different number
of iterations (real network/scheduling timing varies), which is why `WINDOW_END`'s literal value is
expected to differ run to run — the captured canonical facts and comparator result are what must
match, and do (`revalidation.md`).

Only once this succeeds has AIP actually received and persisted the OTLP batches phase 8's traffic
produced — I2.3 begins by *reading back* what AIP now holds for `[window_start, window_end]`.

---

**Phases 10-12 (execute comparison, store report, tear down) belong to I2.3.** Reference for what
they will do, per the I1 runbook contract (§28) and I2 spec §32's "Phase B/C":

```text
10. Query/capture AIP result   - export AIP's actual canonical facts for environment=quarkus-i2 /
                                   [window_start, window_end] into a real_world_validation actual-
                                   facts capture (real_world_validation/README.md's schema)
    Execute comparison          - uv run python -m real_world_validation compare
                                   --expected docs/real-world-validation/quarkus-super-heroes/expected.yaml
                                   --actual   <the capture above>
11. Store deterministic report  - results.md
12. Tear down environment       - docker compose down -v (this profile); rm -rf
                                   "$QUARKUS_SUPERHEROES_CHECKOUT" (optional, outside this repo)
```

## Clean-state requirement (I1 §29 / I2 spec §42)

Every qualifying run begins from clean state. Before phase 5 (and again before any rerun):

```bash
cd docs/real-world-validation/quarkus-super-heroes/runtime
docker compose down -v   # drops Mongo/Postgres/MariaDB/Kafka/Apicurio/Neo4j volumes too
```

`docker compose down -v` removes the named Neo4j volumes declared in `docker-compose.yml`
(`neo4j-quarkus-i2-data`/`-logs`) along with every infra container's own anonymous volumes, so a
subsequent `docker compose up -d` starts from a genuinely empty graph and empty datastores — no
run depends on unexplained data an earlier run left behind.
