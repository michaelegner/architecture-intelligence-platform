# Validation Profile — Quarkus Super Heroes

Bounded profile for I2 (I2 spec §7/§24). This document defines *what will be run and why*; the
ordered runbook and traffic script that execute it are I2.2 deliverables, not this one.

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
Kafka + Apicurio     fights topic transport + Avro schema registry
OTel Collector/LGTM  telemetry export path shared by all services
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
`quarkus.otel.resource.attributes` (`app=<quarkus.application.name>`). I2.2 SHALL route this
existing OTLP export to AIP's `/v1/traces` (directly or via a Collector fan-out) — no source-code
instrumentation changes are required, per I2 spec §16.

## Traffic generation

Deferred to I2.2: a deterministic script exercising hero retrieval, villain retrieval, a full fight
execution (which triggers the narration call), and Kafka fight-event publication/consumption (I2
spec §19).

## Environment name

```text
quarkus-i2
```

per I2 spec §18's recommendation.

## Observation-window method

Deferred to I2.2/I2.3: the runbook will record an explicit `window_start`/`window_end` bracketing
only the qualifying traffic run, excluding unrelated startup traces (I2 spec §18).

## External dependencies disabled/mocked/fallback

`rest-narration`'s OpenAI integration is disabled by default
(`quarkus.langchain4j.openai.enable-integration=false`, only enabled under the `%dev,test,openai`
profile) — the qualifying profile SHALL NOT enable the `openai` profile, so no live external
generative-AI call is part of this validation (I2 spec §20). See `ground-truth.md`'s "Known
ambiguities" for how this affects the narration `CALLS` relation's expected runtime status.

## Cleanup/reset procedure

Deferred to I2.2's runbook: reset AIP graph/evidence state, reset MongoDB, reset Kafka topic/consumer
offsets, clear temporary OTel capture state (I2 spec §42).

## Mandatory unsupported-mechanism declarations (I2 spec §24)

```text
gRPC (rest-fights -> grpc-locations)         -> unsupported
Kafka topic "fights" (Queue qualification)   -> unsupported
```
