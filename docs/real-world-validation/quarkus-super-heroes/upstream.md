# Upstream Identity — Quarkus Super Heroes

```text
project name:       Quarkus Superheroes Sample ("Quarkus Super Heroes")
repository:          https://github.com/quarkusio/quarkus-super-heroes
license:             Apache-2.0
pinned commit:       8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce
default branch at pin time: main
pin date:            2026-08-31
validation profile revision: this dossier's own commit history
JVM requirement:     Java 25 (root README.md: "The base JVM version for all the applications is Java 25.")
```

Confirmed live at plan time via the GitHub API (`GET /repos/quarkusio/quarkus-super-heroes/commits/8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce`):
commit exists, message "Bump quarkus.platform.version from 3.38.3 to 3.39.1 (#2262)".

A validation result applies only to this pinned commit (I1 §8). Changing the pinned revision
requires a documented reason, a new exact SHA, a ground-truth review against the new SHA, and a
profile re-freeze (I2 spec §4).

## Relevant upstream components

```text
ui-super-heroes    React UI served via Quarkus Quinoa               (out of AIP-supported scope)
rest-villains      Villain REST API, Hibernate ORM with Panache
rest-heroes        Hero REST API, Hibernate Reactive with Panache
rest-narration     Narration REST API, integrates OpenAI via LangChain4J
grpc-locations     Location gRPC API, Kotlin + gRPC                 (out of AIP-supported scope)
rest-fights        Fight REST API orchestrating fights - MongoDB, Kafka, resilience patterns
event-statistics   Event-driven microservice consuming Kafka events, serves stats via WebSockets
Grafana LGTM Stack All services export traces/metrics/logs via OpenTelemetry (OTLP)
```

Source: root `README.md` @ pinned commit.

## Relevant upstream documentation

```text
Repository README        README.md
Full documentation       https://quarkus.io/quarkus-super-heroes
Fight service README     rest-fights/README.md
Event statistics README  event-statistics/README.md
Narration service README rest-narration/README.md
```

## Why this is classified as External Reference Architecture, not production software

Quarkus Super Heroes is Red Hat's own sample/demo application for showcasing Quarkus features
(REST, reactive/blocking HTTP, Hibernate ORM/Reactive with Panache, Kafka messaging, gRPC,
LangChain4J/OpenAI integration, OpenTelemetry). It is independently authored (not created for or
by AIP), exercises real synchronous REST, asynchronous Kafka messaging, gRPC, and OpenTelemetry —
satisfying I2 spec §5.1's role definition — but per parent spec §5.1 it **SHALL NOT be described as
production software**. Its value for I2 is architectural realism under a controlled, well-documented
topology, not production-grade operational maturity.
