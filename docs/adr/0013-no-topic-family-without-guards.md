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

## Implementation record (v0.4.1 I2)

Both prerequisite guards named above are now implemented and wired into the production runtime
messaging path (`docs/specifications/0.4.1/i2-messaging-semantic-guards.md`). This ADR is satisfied
by I2, not superseded — the topic/pub-sub prohibition in the Decision above remains in force; only
the two guards it named as prerequisites now exist as executable code.

**Production guard entry points**: `app/telemetry/messaging_guards.py`'s `decide_destination_semantics`
(topic-vs-queue) and `decide_service_identity` (service-identity), both evaluated by
`app/telemetry/adapter.py::correlate_queue_observations` — destination decision first, service
decision second, with no entity/Evidence/fact recorded for a span until both accept (spec §6/§18).
Neither guard is reachable only as an unused helper; both are proven reachable in the production
messaging path itself, not merely as direct-call unit tests.

**Merged candidates**: I2.1 `5cfccf7` (PR #115, guard decisions, unused until wired), I2.2 `aedda84`
(PR #116, atomic production wiring), I2.3 this record's own candidate (PR #117).

**Guard-level and persistence-level regression tests**:
- `tests/unit/test_messaging_guards.py` — the destination guard's D1–D17 matrix and the
  service-identity guard's S1–S16 matrix (spec §25-26), directly against the two pure functions.
- `tests/unit/test_adapter.py` — the composed C1–C17 matrix (spec §27) against the real production
  wiring, plus two mixed HTTP/messaging regressions (spec §33).
- `tests/integration/test_adapter.py` — real-Neo4j persistence proof (spec §29): one positive
  control plus one test per refusal family (topic-shaped destination, unresolved destination,
  placeholder service, ambiguous service, both guards failing), each querying Service nodes, Queue
  nodes, Evidence nodes, and the SENDS/RECEIVES_FROM relation to prove zero new semantic artifacts.
- `tests/unit/test_adapter.py::test_quarkus_shape_destination_guard_reachability_with_a_recognized_operation_type`
  and `test_airflow_shape_service_identity_guard_reachability_with_a_recognized_operation_type` —
  synthetic reachability proofs (spec §30-31): the real captured Quarkus/Airflow attribute shapes
  stay silently unrecognized (operation-attribute recognition is unchanged), but the same
  destination/identity refuses independently once a currently-recognized operation type reaches it.

**Operation-recognition boundary — unchanged**: `messaging.operation.type` values `send`/`receive`/
`process` remain the complete recognized surface (spec §21). The real captured Quarkus/SmallRye
shape (`messaging.operation`, not `.type`) and the real captured Airflow/Celery shape
(`messaging.destination`, not `.destination.name`) both remain silently unrecognized, exactly as
before I2 — confirmed unmodified by `test_legacy_messaging_operation_attribute_shape_is_not_recognized`
and `test_celery_instrumentation_semconv_shape_is_not_recognized`.

**Topic/Subscription — still absent**: no canonical entity or relation family was added. A
topic-shaped or unresolved destination is refused (zero facts), never represented as a placeholder
Queue or any other stand-in.

A future ADR proposing a generic Pub/Sub model may supersede this ADR's prohibition, citing the
guard regression evidence above as its prerequisite — that ADR is `v0.5.0` work, not part of I2.
