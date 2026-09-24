# 17. Source-independent Topic/Subscription semantics, with both ADR 0013 guards retained

Status: Accepted — implemented in `v0.5.0` I4 (Slices 1-6, #228-#233 plus the Slice 6 completion
PR; see [`i4-completion-record.md`](../specifications/0.5.0/i4-completion-record.md)). The `GO`
decision was recorded in I4 Slice 1. It supersedes
[ADR 0013](0013-no-topic-family-without-guards.md) **only** with respect to ADR 0013's
Topic/Subscription prohibition.

## Context

[ADR 0013](0013-no-topic-family-without-guards.md) prohibited a topic/pub-sub canonical family
until two guards existed. The first was a topic-vs-queue destination guard, and the second a
service-identity guard. It named the condition for lifting that prohibition: a new ADR citing the
guards' regression tests.

`v0.4.1` I2 implemented both guards in the production runtime messaging path:
`decide_destination_semantics` and `decide_service_identity` in
`app/telemetry/messaging_guards.py`, evaluated by
`app/telemetry/adapter.py::correlate_queue_observations`. Their regression evidence is
`tests/unit/test_messaging_guards.py` (the D1–D17 and S1–S16 matrices),
`tests/unit/test_adapter.py` (the composed C1–C17 matrix and the Quarkus/Airflow reachability
proofs) and `tests/integration/test_adapter.py` (real-Neo4j zero-artifact refusal proofs). ADR
0013's own implementation record lists them.

The `v0.5.0` parent specification made Pub/Sub conditional on a `GO`/`DEFER` gate.
[`i4-source-independent-pubsub-semantics.md`](../specifications/0.5.0/i4-source-independent-pubsub-semantics.md)
(Draft 0.3, merged at `f98e48b`) is the governing specification.
[`i4-decision-evidence.md`](../specifications/0.5.0/i4-decision-evidence.md) records the
independent evidence. Azure Service Bus and Google Cloud Pub/Sub both distinguish competing
consumption on a queue from Topic fan-out through distinct Subscriptions, and from load balancing
inside one Subscription. OpenTelemetry keeps `messaging.destination.subscription.name` separate from
`messaging.consumer.group.name`. A Kafka consumer group is a partition/offset construct, not a
broker-held named Subscription. Neither positive broker needs a broker-specific production
exception.

## Decision

**`GO`.** AIP introduces the bounded source-independent Pub/Sub family defined by the I4
specification.

1. **Canonical family.** The only generic Pub/Sub entities are `Topic` and `Subscription`, and the
   only relations are `Service -[PUBLISHES_TO]-> Topic`, `Subscription -[SUBSCRIPTION_OF]-> Topic`,
   `Service -[RECEIVES_FROM]-> Subscription` and `Topic -[CARRIES]-> Message`. The existing Queue
   model and Queue claim ids are unchanged. Fan-out is expressed only by distinct Subscriptions.
2. **Both ADR 0013 guards are retained.** `decide_destination_semantics` and
   `decide_service_identity` stay in force, and I4 reuses them. It does not replace them, and it
   does not add a second Service-identity implementation (I4 spec §9).
3. **No generic `Destination` normalization.** Queue, Topic and Subscription are type-distinct,
   with distinct identity prefixes (`queue:`, `topic:`, `subscription:`). No supertype and no
   name-based equivalence exists across them.
4. **No consumer-group-to-Subscription equivalence.** A consumer group may be bounded evidence
   metadata. It never mints, resolves, or aliases a Subscription, and it is not an input to
   Subscription identity.
5. **No runtime-only Topic/Subscription minting.** Runtime evidence may only qualify
   already-declared Topic/Subscription topology.
6. **Bounded OpenTelemetry widening.** I4 cites ADR 0013 decision #2. Operation classification
   continues to read only `messaging.operation.type`. Destination-side recognition widens by
   exactly two keys, `messaging.destination.subscription.name` and `messaging.consumer.group.name`.
   This is permitted because both guards named in decision #2 exist and remain in the path.
7. **No new public surface family.** I4 adds no MCP tool, keeping exactly three: no generic graph
   tool, no live broker adapter, and no broker administration API. Topic/Subscription reach the
   public contract only through the existing dependency, drift and evidence answers at
   `schema_version` `0.5`.

## Consequences

- ADR 0013's Status line records that it is superseded in part. Its destination-semantics and
  service-identity guards, and its "unsupported beats incorrectly supported" rule, remain
  authoritative for everything outside the bounded family above.
- Topic kind requires positive evidence, and Subscription requires explicit stable identity. A
  Channel, a `subscribe` operation, protocol/vendor, or `messaging.system` never establishes either.
- Subscription-specific dead-letter configuration differs materially across brokers. It is retained
  only as an internal Subscription-scoped contribution (I4 spec §10), never as a guessed generic
  target relation.
- The I4 stop conditions (spec §16) apply to any later change. In particular, a broker-specific
  canonical entity or a broker-specific production exception returns this decision to review
  instead of widening it silently.
- If I4 cannot complete, this ADR is superseded by a `DEFER` record rather than silently left
  `Proposed`.
