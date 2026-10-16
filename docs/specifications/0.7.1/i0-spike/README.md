# v0.7.1 I0.1 — evidence for the semantic freeze

Evidence only. Nothing here is a decision; I0.2 freezes the records required by [I0 §10](../i0-consumer-attribution-semantic-freeze.md).

## 1. Kafka: existing capture against the merged I0 rules

Source: [`consumer-attribution-evidence/`](../../../real-world-validation/v0.8.0/consumer-attribution-evidence/README.md) (no new capture).

| I0 rule | Result |
|---|---|
| §4 attachment = live member assignment | **Pass.** Both groups `Stable` with live members on all three Topics. |
| §3 destination must already be an AIP Topic | **Gap.** The captured system declares no AsyncAPI, so these Topics would be unsupported, not minted. A qualifying fixture needs a declared Topic of the same name. |
| §2 Service mapping: not name equality, resolves to an existing Service | **Partial.** payment-service: deployment-resolved config (`KAFKA_CONSUMER_GROUP`, `GroupID`) plus a hostname in the member id. order-service: group id in `application.yaml` and `@KafkaListener`, but the runtime join is container IP only, which is ephemeral and not usable as authority alone. |
| §4 structured source preferred | **Not met.** Capture is CLI text. The Kafka Admin API (`describeConsumerGroups`) exposes the same facts as typed fields (group state, member id, client id, host, assignment); desk check against the API, not executed here. |
| §6 point in time | One local run; no window; no message processing. |

Reading: the capture is sufficient for **semantics**. A refresh is only needed for **I1 fixtures** (declared Topic, structured output, a stable mapping source).

## 2. RabbitMQ contrast (shapes S1–S4)

Raw: [`rabbitmq/raw/`](rabbitmq/raw/), setup: [`rabbitmq/commands.md`](rabbitmq/commands.md), script: [`rabbitmq/shapes.py`](rabbitmq/shapes.py). RabbitMQ 3.13.7, management API.

| Observation | Evidence |
|---|---|
| Native consumer identity is **vhost + queue + consumer tag + channel**. There is no group concept. | `01-consumers` |
| Attachment = a live consumer registered on a **Queue**. The destination is a Queue, not a Topic or Subscription. | `01-consumers`, `02-queues` |
| S1: two consumers on one queue are competing consumers of one connection. They must not become two Services. | `01-consumers` (`s1-c1`, `s1-c2`, same connection) |
| S2: fan-out is expressed by exchange **bindings** to separate queues, not by consumers. Consumer attribution stays per queue. | `03-bindings`, `01-consumers` |
| S4: a bound queue with no consumer has `consumers: 0`, which is no attachment evidence and not a negative. | `02-queues`, `03-bindings` |
| Service-mapping evidence offered by the broker: connection user and the client-supplied `connection_name` property. Both are client-asserted, not authoritative. The consumer-to-connection join key is the peer address string, which is ephemeral. | `01-consumers`, `04-connections` |
| Default-exchange bindings exist for every queue; they are not routing intent. | `03-bindings` |

**Proposed outcome: SOURCE_SPECIFIC.** Attribution works (live consumer on a declared Queue plus an independent Service mapping), but the native identity (consumer tag on a Queue, no group) must stay source-specific and must not be coerced to a Kafka consumer group or a Subscription. No MODEL_GAP seen in S1–S4.

## 3. Handed to I0.2

- accepted Service-mapping sources for Kafka (stable config; IP join only as corroboration);
- common carrier vs source-specific carriers, given Section 2;
- deterministic id inputs (broker scope, environment, native kind and id) and temporal-compatibility wording;
- whether the Kafka refresh (declared Topic, structured output) is I1 fixture work or an I0 requirement.
