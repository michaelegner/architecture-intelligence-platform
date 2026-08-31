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

wait_for_http architecture-intelligence http://localhost:8000/health
wait_for_http rest-fights               http://localhost:8082/q/health/ready
wait_for_http rest-heroes               http://localhost:8083/q/health/ready
wait_for_http rest-villains              http://localhost:8084/q/health/ready
wait_for_http rest-narration             http://localhost:8087/q/health/ready
wait_for_http event-statistics           http://localhost:8085/q/health/ready
wait_for_http grpc-locations             http://localhost:8089/q/health/ready
wait_for_tcp  otel-collector              localhost 4318
```

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

WINDOW_END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "environment=quarkus-i2 window_start=$WINDOW_START window_end=$WINDOW_END"
```

`traffic.sh` (I2 spec §19) exercises, in the order `FightService.java` actually calls them: hero +
villain retrieval (one `GET /api/fights/randomfighters` call triggers both), the `grpc-locations`
dependency (`GET /api/fights/randomlocation`), a fight (`POST /api/fights` — persists and publishes
to Kafka topic `fights`, which `event-statistics` consumes), and narration (`POST
/api/fights/narrate`, a separate call from `performFight`). Record `window_start`/`window_end` —
I2.3 needs this exact pair to query AIP's runtime facts for `environment=quarkus-i2`.

## 9. Wait for the Collector to drain, then confirm OTLP ingestion

`otel-collector-config.yaml`'s batch processor can legally hold the tail of phase 8's spans for up
to its configured `timeout: 5s` before forwarding a partial batch — recording `WINDOW_END`
immediately after `traffic.sh` bounds when the traffic *finished*, not when AIP has actually
received the last batch. Querying AIP right away risks a race where the final spans are still
sitting in the Collector's buffer, silently turning a real `CONFIRMED`/`OBSERVED_ONLY` fact into a
missing one depending on timing alone (PR #40 review F2). Insert an explicit drain barrier before
treating the window as closed:

```bash
sleep 15   # comfortably longer than otel-collector-config.yaml's 5s batch timeout

for i in $(seq 1 15); do
  COUNT="$(curl -sf "http://localhost:8000/api/runtime/relations?environment=quarkus-i2" | jq 'length')"
  [ "${COUNT:-0}" -gt 0 ] && break
  sleep 2
done

if [ "${COUNT:-0}" -eq 0 ]; then
  echo "no runtime relations observed for environment=quarkus-i2 after waiting - check: docker compose logs otel-collector" >&2
  exit 1
fi
```

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
