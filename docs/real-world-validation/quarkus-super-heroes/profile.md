# Validation Profile — Quarkus Super Heroes

Bounded profile for I2 (I2 spec §7/§24). This document defines *what is run and why*; the ordered
steps and exact commands live in [`runbook.md`](runbook.md), and the supporting mechanics
(compose file, OTel Collector config, traffic script, declarations tree) live under
[`runtime/`](runtime/) (I2.2).

## Components/processes started

```text
rest-fights         (port 8082)
rest-heroes         (port 8083)
rest-villains       (port 8084)
event-statistics    (port 8085)
rest-narration      (port 8087)
grpc-locations      (port 8089) - required for rest-fights' own startup/health, not AIP-validated
```

`ui-super-heroes` is not started — the profile exercises the fight flow directly (traffic script,
I2.2), not through the UI, per I2 spec §19's "curl / documented endpoints / small deterministic
validation script" option.

## Infrastructure started

```text
MongoDB              rest-fights' fight persistence (quarkus.mongodb.database=fights)
Postgres x2          rest-heroes' and rest-villains' own datastores
MariaDB              grpc-locations' own datastore
Kafka + Apicurio     fights topic transport + Avro schema registry
OTel Collector       telemetry export path shared by all services, forwarding to AIP (runtime/)
```

## Services included in AIP-supported scope

```text
rest-fights, rest-heroes, rest-villains, rest-narration   - PROVIDES/CALLS scope
event-statistics                                          - messaging-boundary ground truth only
                                                             (Kafka consumer; not REST-scoped)
```

## Services excluded from AIP-supported scope

```text
grpc-locations       started (rest-fights depends on it for fight execution) but not represented
                     as an AIP-supported entity - the rest-fights -> grpc-locations dependency is
                     UNSUPPORTED (I2 spec §12)
ui-super-heroes      not started; not an architecture entity under validation
```

`started != supported by AIP` (I2 spec §7) — starting `grpc-locations` is an upstream startup
prerequisite for `rest-fights` to run at all, not an AIP validation target.

## OpenAPI acquisition method per service

Pinned static contract-first files already committed in the pinned repository (I2 spec §9):

```text
rest-fights/src/main/resources/openapi/openapi.yml
rest-heroes/src/main/resources/openapi/openapi.yml
rest-villains/src/main/resources/openapi/openapi.yml
rest-narration/src/main/resources/openapi/openapi.yml
```

No AIP-generated or reconstructed OpenAPI is used.

## OTel export path

Each service already sets `quarkus.otel.exporter.otlp.protocol=http/protobuf` and a distinguishing
`quarkus.otel.resource.attributes` (`app=<quarkus.application.name>`). No source-code
instrumentation change was needed (I2 spec §16) — `runtime/docker-compose.yml` points every
service's `QUARKUS_OTEL_EXPORTER_OTLP_ENDPOINT` at `runtime/otel-collector-config.yaml`'s
Collector, which forwards to AIP's `/v1/traces` (adapted from this repo's own
`examples/runtime-demo/otel-collector-config.yaml`). Each service's `QUARKUS_OTEL_RESOURCE_ATTRIBUTES`
also appends `deployment.environment.name=quarkus-i2` to its existing `app=/application=/system=`
attributes, so every span lands tagged with this profile's environment name below.

## Traffic generation

[`runtime/traffic.sh`](runtime/traffic.sh) (I2 spec §19): a deterministic curl script exercising,
in the exact order `FightService.java` triggers them, hero+villain retrieval (one call), the
`grpc-locations` dependency, a fight (persist + Kafka `fights` publish, consumed by
`event-statistics`), and narration — using the pinned upstream OpenAPI's own documented example
request bodies, not invented payloads. Run between `runbook.md` phase 8's `window_start`/
`window_end`.

## Environment name

```text
quarkus-i2
```

per I2 spec §18's recommendation; wired into every service via `QUARKUS_OTEL_RESOURCE_ATTRIBUTES`
above and into AIP via `runtime/config.quarkus-i2.yaml`'s `runtime_analysis.default_environment`.

## Observation-window method

[`runbook.md`](runbook.md) phase 8 records `window_start`/`window_end` as UTC timestamps taken
immediately before and after `traffic.sh` runs, bracketing only the qualifying traffic and
excluding unrelated startup/health-check traces (I2 spec §18). I2.3 uses this exact pair to query
AIP's runtime facts for `environment=quarkus-i2`.

## External dependencies disabled/mocked/fallback

`rest-narration`'s OpenAI integration is disabled by default
(`quarkus.langchain4j.openai.enable-integration=false`, only enabled under the `%dev,test,openai`
profile) — the qualifying profile SHALL NOT enable the `openai` profile, so no live external
generative-AI call is part of this validation (I2 spec §20). See `ground-truth.md`'s "Known
ambiguities" for how this affects the narration `CALLS` relation's expected runtime status.

## Cleanup/reset procedure

[`runbook.md`](runbook.md)'s "Clean-state requirement": `docker compose down -v` in `runtime/`
drops the Neo4j (`neo4j-quarkus-i2-*`), MongoDB, Postgres×2, MariaDB, and Kafka/Apicurio volumes
together, so a subsequent `docker compose up -d` starts from a genuinely empty graph and empty
datastores (I2 spec §42).

## Mandatory unsupported-mechanism declarations (I2 spec §24)

```text
gRPC (rest-fights -> grpc-locations)         -> unsupported
Kafka topic "fights" (Queue qualification)   -> unsupported
```
