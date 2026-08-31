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
~10 GB free disk (5 Quarkus JVM images + Mongo/2×Postgres/MariaDB/Kafka/Apicurio/Neo4j)
Internet access (clone GitHub, pull base images, pull Maven dependencies)
Ports free on the host: 7474, 7687, 8000, 8082-8087, 8089, 4317, 4318, 9092
```

No JDK/Maven needs to be installed on the host — phase 3 builds each service's jar inside a
`maven:*-eclipse-temurin-25` container.

## 2. Fetch the pinned upstream version

```bash
export QUARKUS_SUPERHEROES_CHECKOUT="$HOME/quarkus-super-heroes-i2"   # anywhere outside this repo
git clone https://github.com/quarkusio/quarkus-super-heroes.git "$QUARKUS_SUPERHEROES_CHECKOUT"
git -C "$QUARKUS_SUPERHEROES_CHECKOUT" checkout 8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
```

This checkout is **never committed into this repository** (I1 §36/§39) — `docker-compose.yml`
below reads it only through `$QUARKUS_SUPERHEROES_CHECKOUT`.

## 3. Build the five validated services' images at the pinned commit

Each service needs a jar built (containerized, so no host JDK 25 is required) and then packaged
into its own runtime image via its own `src/main/docker/Dockerfile.jvm` — **not** pulled from
`quay.io/quarkus-super-heroes/*:java25-latest` (`runtime/README.md` explains why that tag doesn't
represent this exact commit).

```bash
for svc in rest-fights rest-heroes rest-villains rest-narration event-statistics; do
  docker run --rm -v "$QUARKUS_SUPERHEROES_CHECKOUT:/workspace" -w "/workspace/$svc" \
    maven:3.9-eclipse-temurin-25 ./mvnw -q package -DskipTests

  docker build -f "$QUARKUS_SUPERHEROES_CHECKOUT/$svc/src/main/docker/Dockerfile.jvm" \
    -t "quarkus-super-heroes/$svc:8ea0337" "$QUARKUS_SUPERHEROES_CHECKOUT/$svc"
done
```

`grpc-locations` also needs an image, since `rest-fights` depends on it to start (it is not part of
AIP's supported/compared scope, `profile.md`):

```bash
docker run --rm -v "$QUARKUS_SUPERHEROES_CHECKOUT:/workspace" -w /workspace/grpc-locations \
  maven:3.9-eclipse-temurin-25 ./mvnw -q package -DskipTests

docker build -f "$QUARKUS_SUPERHEROES_CHECKOUT/grpc-locations/src/main/docker/Dockerfile.jvm" \
  -t quarkus-super-heroes/grpc-locations:8ea0337 "$QUARKUS_SUPERHEROES_CHECKOUT/grpc-locations"
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

`architecture-intelligence` waits on `neo4j`'s healthcheck; the five validated services plus
`grpc-locations`/`event-statistics` wait on their own datastores. Verify readiness:

```bash
curl -sf http://localhost:8000/health          # AIP
curl -sf http://localhost:8082/q/health/ready   # rest-fights
curl -sf http://localhost:8083/q/health/ready   # rest-heroes
curl -sf http://localhost:8084/q/health/ready   # rest-villains
curl -sf http://localhost:8087/q/health/ready   # rest-narration
curl -sf http://localhost:8085/q/health/ready   # event-statistics
```

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

## 9. Send/capture runtime observations

By the end of phase 8, AIP has already received and persisted every OTLP batch the traffic in phase
8 produced (the Collector forwards synchronously; there is no separate "capture" step to run). No
further action is needed here — I2.3 begins by *reading back* what AIP now holds.

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
