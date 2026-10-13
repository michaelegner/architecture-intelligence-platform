# AIP — Consumer Attribution Evidence-Capture Check

**Status:** Planned  
**Input:** Round 5 result and synthesis  
**Purpose:** Close the remaining evidence gap before deciding whether broker-mediated consumer attribution justifies a bounded semantic completion.

This is a **small evidence check**, not another candidate round and not an implementation increment.

## 1. Question

> **Can broker-held runtime state independently establish that a concrete consumer identity is attached to a destination in a specific environment, and can that identity be mapped to a Service without guessing?**

The check exists to test Round 5 promotion-rule condition 2 and to provide concrete broker-native evidence for reasoning about condition 5. It does not assume a common consumer abstraction.

## 2. Primary case

Use **hungCS22hcmiu/ecommerce-system** at the Round 5 frozen revision:

`cd65365838ea880185a02e6536fa347439bfa274`

Prefer the smallest runnable Kafka/Compose slice already supported by the repository.

Use one existing event flow, preferably the `orders.created` / payment flow already evaluated in Round 3 and Round 5.

Do not modify application behavior or instrumentation to manufacture evidence.

## 3. Capture

Capture the smallest broker-held evidence needed to show:

- destination/topic identity;
- Kafka consumer-group identity;
- active group/member state where available;
- the environment/run in which the observation was made.

Prefer the repository's existing `kafka-consumer-groups --describe` path.

Store the raw command output unchanged, together with:

- exact repository revision;
- exact command(s);
- Compose/services started;
- capture timestamp;
- enough environment/config context to reproduce the run.

## 4. Service mapping

Separately record the source/config evidence that maps the captured broker-native consumer identity to a Service.

The mapping must be explicit enough to defend. For example, a Service configuration or listener definition may declare the captured group id.

Do **not** conclude `group name == Service name` merely because the strings are equal.

Keep these two claims separate:

1. broker evidence: consumer identity G is attached to destination D;
2. source/config evidence: Service S uses consumer identity G.

Only their qualified combination may support a Service-level attribution.

## 5. Result

Record one compact result:

| Field | Content |
|---|---|
| System | repository + frozen revision |
| Environment | capture context |
| Destination | broker-native identity |
| Consumer identity | broker-native identity |
| Broker evidence | raw capture + provenance |
| Service mapping | source/config evidence |
| Attribution supported? | Yes / unresolved / no |
| Remaining ambiguity | what cannot safely be established |
| Semantic implication | what this evidence would require AIP to preserve, without proposing a model yet |

The decisive question is:

> **Does independent broker state plus separately attributable source/config evidence support a Service↔consumer↔destination relationship without equating the broker-native consumer identity with an AIP Subscription?**

## 6. Optional cross-check

Only if cheap after the Kafka capture, repeat the same evidence shape for one RabbitMQ reserve such as **dotnet/eShop** or **daonhan/Microservices-in-.NET** using broker bindings/consumer state.

This is optional. Do not expand the check into general broker-topology research.

## 7. Out of scope

- new AIP canonical entities or relations;
- Kafka/RabbitMQ ingestion adapters;
- changing Topic/Queue/Subscription semantics;
- routing predicates, lag, offsets, rebalancing, DLQ/retry topology;
- another coding-agent baseline;
- selecting the final v0.8 validation system.

## 8. Exit

The check ends with one of three outcomes:

- **SUPPORTED EVIDENCE PATH** — broker state establishes the consumer attachment and source/config maps it to a Service without guessing;
- **UNRESOLVED MAPPING** — broker state exists but cannot safely be attributed to a Service;
- **NO PRACTICAL EVIDENCE PATH** — the required independent evidence cannot be captured reasonably.

Only **SUPPORTED EVIDENCE PATH** is sufficient to move from the Round 5 recurring question toward defining a semantic-completion scope.

Even then, this check does **not** decide the canonical abstraction. It supplies the concrete evidence shape needed for that decision.
