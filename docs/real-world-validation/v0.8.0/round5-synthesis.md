# Round 5 — Synthesis

**Spec:** [spec-round5-broker-semantic-gap-validation.md](spec-round5-broker-semantic-gap-validation.md) §5, §7–§9  
**Inputs:** [candidate records](round5-candidate-records.md), [probe](round5-evidence/aip_probe_output.txt), [Round 4 result](round4-result.md)

## 1. What recurs

| Finding | Systems (independent) | Count |
|---|---|---|
| **Consumer endpoint ↔ Service ↔ destination** is known from source/config (Kafka consumer group, RabbitMQ per-service queue) but AIP cannot attribute the consumer from evidence | Kafka: Sokol111, koupang, hungCS22hcmiu. RabbitMQ: sminerport, eShop, daonhan | 6 |
| Operation/destination attribute keys used by hand-written instrumentation are not the ones AIP reads (`messaging.destination`, `messaging.operation`, `messaging.operation.name`) | Sokol111, eShop, daonhan; koupang/hungCS emit none | 3 + 2 |
| Destination identity differs from consumer endpoint: exchange + routing key vs per-service queue | eShop (direct), daonhan (fanout), sminerport (headers) | 3 |
| Routing predicate decides who receives (headers `x-match`) | sminerport only | 1 |
| Framework-generated destination identity | food-delivery (Wolverine) | 1 |

## 2. Classification by §5

| Finding | Classification | Why |
|---|---|---|
| Consumer attribution (Kafka group, RabbitMQ queue) | **SEMANTIC_GAP**, recurring | Kafka group ≠ Subscription and queue ≠ Topic Subscription (§5 rules) mean current Topic/Subscription semantics cannot carry it from evidence. For RabbitMQ the *declared* form is supported (Pitstop: declared Topic + named Subscription overlays), but nothing derives or qualifies it from independent evidence |
| Attribute-key mismatch | **INGESTION_GAP** | Evidence fits existing semantics; AIP reads `messaging.operation.type` (send/receive/process) and `messaging.destination.name` only. Not promoted (§5) |
| Destination identity (routing key vs queue) | **SEMANTIC_GAP**, weak evidence | eShop labels a routing key `destination_kind=queue`; AIP then records both sides on one observed-only Queue named after the event. That is an instrumentation mislabel, but it shows the model has no way to say "this name is a routing key, not the consumer's queue". One strong system, others compatible |
| Headers-exchange predicate | **BROKER_SPECIFIC_DETAIL** | Only one system; consumer set is already answerable if the consumer endpoint is attributed; the predicate affects *whether a message arrives*, not *which service owns the endpoint* |
| Fanout binding key (daonhan) | **BROKER_SPECIFIC_DETAIL** | Ignored by the broker; irrelevant to the question |
| Service Bus topic + subscription (daonhan ASB mode) | **SUPPORTED** | Matches AIP's Subscription semantics; useful as a control |
| Framework-generated names (food-delivery) | **INSUFFICIENT_EVIDENCE** | Not decidable without running or reading Wolverine |

## 3. Section 8 questions

| Question | Finding |
|---|---|
| Consumer attribution | **Needed.** Six systems; the baseline already knows the answer from source, so the value is qualifying it with independent evidence (is that consumer actually attached to this destination in this environment?) |
| Broker route/binding | **Partly.** Needed only to the extent a binding names the consumer endpoint; not needed as predicate semantics |
| Destination identity | **Needed as a guard**, not as a new entity: a routing key must not be read as a consumer queue |
| Runtime participation | **Needed**, and not answerable from current spans: no candidate emits consumer-group or queue identity on spans. Broker-held state (Kafka describe-groups, RabbitMQ bindings/consumers) is the plausible independent source and is cheaply capturable in hungCS and koupang; **not captured in this round** |
| Routing-predicate relevance | **Evidence detail**, not canonical semantics |

## 4. Promotion rule (§7) applied to consumer attribution

| Condition | Result |
|---|---|
| 1. Recurring cross-service change-impact question | Met: "which services consume this destination" in 6 systems |
| 2. Independent evidence can establish it | Plausible, **not demonstrated**: broker state exists and is queried by repository scripts (hungCS), but nothing was captured or ingested in Round 5. This is the open point |
| 3. Current AIP cannot represent without inventing/collapsing meaning | Met: group ≠ Subscription by design; the eShop probe shows what collapsing looks like |
| 4. More than one independent system | Met: three Kafka + three RabbitMQ systems |
| 5. Smallest extension source-independent at canonical level | Met in principle: a Service-owned *consumer endpoint* identified by broker-native identity and attached to a destination; adapters stay broker-specific |

Result: **consumer attribution is a candidate for product work, conditional on condition 2.**
Nothing else survives the rule: routing predicates (1 system), framework-generated identity
(undecidable) and the attribute-key mismatch (ingestion) are not promoted.

## 5. Proposed smallest scope (not implemented)

The architecture question that must become answerable:

> **For destination D in environment E, which Services own an attached consumer endpoint, and is that attachment declared, observed, or both, without equating a Kafka consumer group or RabbitMQ queue with a Topic Subscription?**

Explicitly out of scope: broker topology modelling in general, header/routing-predicate semantics,
rebalancing/lag/offsets, framework-generated names, DLQ/retry topology.

## 6. Before any semantic-completion release

Round 5 supports a *candidate*, not a decision. One gap in the evidence must be closed first, and
it is cheap: capture the broker-held consumer state for one Kafka reserve (hungCS or koupang from
their own Compose files; `kafka-consumer-groups --describe` is already in hungCS's scripts) and,
if possible, RabbitMQ bindings/consumers for eShop or daonhan, then confirm the evidence names the
consumer endpoint and a Service-mapping source (config) exists. If that evidence cannot be
captured or cannot be mapped to a Service, record "no semantic-completion scope justified".

## 7. Observation outside Round 5 scope

AIP creates an observed-only Queue from `messaging.destination_kind=queue` plus a destination name
(eShop probe). With a mislabelled routing key this yields a fact that looks like a shared
point-to-point queue. This is a consequence of v0.4.1 queue semantics and an instrumentation error,
not a Round 5 finding to act on; it is recorded so the owner can decide separately.
