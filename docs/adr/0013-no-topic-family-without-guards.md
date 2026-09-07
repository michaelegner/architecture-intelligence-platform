# 13. No topic/pub-sub family in the Canonical Model without both safety guards

Status: Accepted — promotes an existing `v0.3` cross-system decision into the ADR index; it does not
re-decide it.

## Context

The Canonical Model's `Queue` carries competing-consumer semantics: `SENDS`/`RECEIVES_FROM` mean a
message flows from one sender to one logical consumer service. There is no topic, subscription, or
fan-out family, and `Message` is deliberately separate from `Queue`
([ADR 0002](0002-canonical-model.md)).

The `v0.3` real-world validation examined exactly this boundary against Quarkus Super Heroes (Kafka)
and Apache Airflow (Celery), and recorded its conclusions in
[`queue-topic-boundary.md`](../real-world-validation/cross-system/decisions/queue-topic-boundary.md)
and
[`messaging-operation-compatibility.md`](../real-world-validation/cross-system/decisions/messaging-operation-compatibility.md):
recognizing a messaging *attribute* is not the same decision as qualifying a *destination* as a
Queue, and no topic family may be introduced absent a release-blocking false claim (none exists —
zero facts are emitted for the Kafka topic in question).

Those records also name what any future widening requires first: a topic-vs-queue guard **and** a
service-identity guard, because `resolve_queue` (`app/telemetry/queue_resolver.py:24`) and
`resolve_service` both mint an entity unconditionally when no declared candidate matches.

That constraint governs `v0.5`'s discovery work, but it is currently reachable only by knowing which
validation dossier to open — which is not where an adapter author looks.

## Decision

Restate the `v0.3` conclusion as a standing architectural constraint:

1. **No topic/pub-sub canonical family** is introduced, and no `SENDS`/`RECEIVES_FROM` fact is
   emitted for a destination whose semantics are not compatible with the competing-consumer `Queue`
   model.
2. **Widening messaging attribute recognition** (`messaging.operation`,
   `messaging.operation.type`, or equivalent in another source) requires both guards to exist first,
   each with a regression test that fails without it: a topic-shaped destination must not produce a
   queue fact, and an unresolved service identity must not be minted into one.
3. **Any adapter proposal that touches messaging cites this ADR** and states which of the two guards
   it depends on. Unsupported beats incorrectly supported: a discovered topic is reported as
   unsupported or unresolved, never as a queue.

## Consequences

- Kafka topics and similar fan-out destinations stay unmodeled rather than modeled wrongly. That is a
  known, deliberate coverage gap, not an oversight.
- `v0.5`'s Kafka Connect candidate cannot land as a straightforward adapter: it will meet this
  constraint immediately, and the guards are its prerequisite, not a follow-up.
- The two `v0.3` decision records remain the authoritative evidence for *why*; this ADR is the index
  entry that makes the constraint discoverable. If the constraint is ever lifted, it is superseded by
  a new ADR citing the guards' regression tests, and the dossier records stay untouched as history.
- The general rule survives beyond messaging: recognizing a signal is not the same decision as
  qualifying a canonical fact from it.
