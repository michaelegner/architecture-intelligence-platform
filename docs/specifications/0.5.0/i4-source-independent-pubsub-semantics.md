# AIP v0.5.0 I4 Specification — Conditional Source-Independent Pub/Sub Semantics

**Status:** Draft 0.1 — `GO` candidate; implementation is not authorized until this specification and the corresponding ADR are reviewed and merged  
**Target release:** `v0.5.0`  
**Release increment:** I4 — Conditional Source-Independent Pub/Sub Semantics  
**Parent:** `docs/specifications/0.5.0/specification.md`, especially §§4–5, 19–21, 28–31  
**Entry baseline:** I3-complete `main`, commit `571220bdfdbbea118b152833b78e11158fb1429b`  
**Dependencies:** I1 complete; I2 complete; I3 complete  
**Required decision artifact:** ADR 0017, superseding only ADR 0013's prohibition on a Topic/Subscription canonical family while preserving ADR 0013's two safety guards  

---

## 1. Purpose

The v0.5.0 parent specification deliberately makes Pub/Sub conditional. I4 first answers:

> **Can AIP introduce a source-independent Topic/Subscription model that remains semantically correct across materially different broker models, preserves existing Queue behavior, and does not turn incomplete declared or runtime signals into guessed topology?**

The permitted outcomes are:

```text
GO
  -> freeze the generic model and evidence/identity guards
  -> implement the bounded model defined here
  -> qualify it deterministically

DEFER
  -> record the evidence and unresolved semantic boundary
  -> make no Topic/Subscription Canonical Model change
  -> continue v0.5.0 without Pub/Sub semantics
```

This document is a `GO` candidate, not an implementation authorization. Until the decision and ADR are reviewed, ADR 0013 remains authoritative.

---

## 2. Entry state and preserved boundaries

I4 starts from the I3-complete baseline and SHALL preserve:

- the I1 source-adapter seam and deterministic source lifecycle;
- the I1 AsyncAPI 2.6.0 Queue kind/identity guards;
- the v0.4.1 runtime destination-kind guard;
- the v0.4.1 runtime service-identity guard;
- I2 Kubernetes discovery without interaction inference;
- I3 `Service -[DEPLOYED_AS]-> Workload` reconciliation;
- `ArchitectureIntelligenceService` as the single semantic owner;
- REST and standard negotiated MCP as the public adapters;
- exactly three read-only MCP tools;
- public schema version `0.5`;
- deterministic evaluation and snapshot-bound evidence drill-down.

I4 SHALL NOT use `DEPLOYED_AS`, Kubernetes co-location, namespace co-location, Workload identity, Pod identity, Kubernetes Service selection, or Ingress routing as evidence that a messaging relationship exists.

---

## 3. Scope

### 3.1 In scope if I4 = GO

1. Source-independent canonical `Topic` and `Subscription` entities.
2. Deterministic Topic and Subscription identities.
3. The bounded relation family defined in §6.
4. AsyncAPI 2.6.0 mapping into that family.
5. Bounded OpenTelemetry qualification of already-declared Topic/Subscription identities.
6. Evidence/provenance continuity.
7. Inclusion in existing Architecture Intelligence dependency/drift answers.
8. Deterministic qualification against at least two materially different broker semantic fixtures.
9. An explicit Kafka consumer-group negative boundary.
10. Documentation and an I4 completion record.

### 3.2 Explicitly out of scope

```text
live Kafka/Azure Service Bus/Google Pub/Sub/RabbitMQ discovery
Kafka Connect
broker administration APIs
topic/subscription mutation
partition topology, lag, offsets, transactions
delivery-guarantee modeling
schema-registry lifecycle
subscription filter/routing-rule interpretation
broker ACLs or health
choreography inference
messaging Intent
new MCP tools
generic graph-query tools
AsyncAPI 3.x
LLM-based kind/identity/topology inference
fuzzy/name-similarity identity
```

Broker products MAY appear in deterministic semantic fixtures. That does not introduce a broker adapter.

---

## 4. Mandatory decision gate

Before Canonical Model implementation, independent evidence SHALL support all of these distinctions:

```text
Queue != Topic
Topic != Subscription
AsyncAPI Channel != broker destination
consumer instance != Subscription
consumer group != automatically Subscription

Queue + multiple consumers
  -> competing consumers
  -> no fan-out claim

Topic + multiple Subscriptions
  -> fan-out topology

one Subscription + multiple consumer instances
  -> load balancing within one logical Subscription
  -> not additional fan-out

same destination name
  -> no identity equivalence across kind/broker/namespace

runtime destination name alone
  -> insufficient destination-kind evidence

runtime consumer-group name alone
  -> insufficient Subscription identity
```

### 4.1 Independent semantic evidence

Azure Service Bus distinguishes queues from topics/subscriptions: queues are point-to-point competing-consumer destinations; topic subscriptions receive independent copies and consumers compete within one subscription.

Google Cloud Pub/Sub independently exposes the same important distinction: multiple subscriptions on one topic create fan-out, while multiple subscriber instances on one subscription load-balance the subscription's messages.

OpenTelemetry distinguishes messaging consumer groups from messaging subscriptions. I4 SHALL preserve that distinction.

Kafka is therefore primarily a negative normalization fixture: a Kafka consumer group MAY supply bounded evidence, but SHALL NOT automatically mint or resolve a canonical Subscription.

References:

- https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-queues-topics-subscriptions
- https://cloud.google.com/pubsub/docs/pubsub-basics
- https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/
- https://opentelemetry.io/docs/specs/semconv/registry/attributes/messaging/
- https://kafka.apache.org/documentation/#design

### 4.2 GO condition

The gate passes only if review accepts this source-independent abstraction:

```text
Queue
  competing-consumer destination

Topic
  publish destination whose downstream fan-out is expressed by distinct Subscriptions

Subscription
  stable named logical delivery entity associated with exactly one Topic;
  consumers may compete within it

consumer group
  distinct runtime/broker construct;
  relevant evidence but not automatically Subscription
```

If either positive broker fixture requires a broker-specific production exception, the outcome SHALL be `DEFER`.

---

## 5. ADR 0017

I4 SHALL add `docs/adr/0017-source-independent-pubsub-semantics.md`.

ADR 0017 SHALL:

- record the `GO` or `DEFER` decision;
- cite this specification and the independent evidence;
- supersede ADR 0013 only with respect to the Topic/Subscription prohibition;
- retain ADR 0013's destination-semantics guard;
- retain ADR 0013's service-identity guard;
- prohibit generic `Destination` normalization;
- prohibit consumer-group-to-Subscription equivalence;
- prohibit runtime-only Topic/Subscription minting;
- record that no new MCP tool or live broker adapter is introduced.

---

## 6. Canonical semantic model if GO

### 6.1 Existing Queue model remains unchanged

```text
Service -[SENDS]-> Queue
Service -[RECEIVES_FROM]-> Queue
Queue   -[CARRIES]-> Message
Queue   -[DEAD_LETTERS_TO]-> Queue    # where already qualified
```

### 6.2 New entities

```text
Topic
  id
  name
  protocol: string | null
  namespace: string | null

Subscription
  id
  name
  protocol: string | null
  namespace: string | null
```

A Subscription SHALL NOT contain consumer-instance lists, consumer groups, partitions, offsets, lag, filter expressions, or delivery guarantees.

### 6.3 New relations

```text
Service      -[PUBLISHES_TO]-> Topic
Subscription -[SUBSCRIPTION_OF]-> Topic
Service      -[RECEIVES_FROM]-> Subscription
Topic        -[CARRIES]-> Message
```

No other generic Pub/Sub relation is introduced by I4.

Fan-out is represented by distinct Subscription paths. Multiple instances of one logical Service behind one Subscription remain competing/load-balanced consumers and collapse to one logical consumer relation with unioned evidence.

Multiple distinct logical Services apparently consuming through one Subscription SHALL NOT be interpreted as fan-out; the public dependency result falls back to the Subscription with an unresolved/ambiguous limitation.

---

## 7. Canonical identity

Topic and Subscription identity SHALL be deterministic, path-independent, broker/namespace scoped, type-distinct, Unicode-normalized, and stable across equivalent replay.

Names alone are never canonical identity.

### 7.1 Topic

```text
topic_owner_key =
  length-delimited(
    stable broker id,
    normalized namespace-or-empty,
    exact normalized topic/channel address
  )

topic_id = topic:owned:<sha256(topic_owner_key)>
```

Protocol/vendor, server URL, Channel name, namespace name, or `messaging.system` alone SHALL NOT establish Topic identity.

### 7.2 Subscription

```text
subscription_owner_key =
  length-delimited(
    stable broker id,
    normalized namespace-or-empty,
    canonical Topic id,
    exact normalized subscription name
  )

subscription_id = subscription:owned:<sha256(subscription_owner_key)>
```

Binding the Topic id prevents identical Subscription names on different Topics from colliding.

Queue, Topic, and Subscription ids SHALL use distinct prefixes and never alias merely because names match.

A consumer-group identifier SHALL NOT be fed into the Subscription identity formula.

---

## 8. AsyncAPI 2.6.0 mapping

I4 SHALL NOT expand dialect support. AsyncAPI 3.x remains `REJECTED_UNSUPPORTED`.

An AsyncAPI Channel remains a source-language construct:

```text
Channel != Queue
Channel != Topic
Channel != Subscription
```

### 8.1 Destination kind

The existing extension `x-aip-destination-kind: queue` is widened to exactly:

```text
queue
topic
```

No `pubsub`, `broadcast`, `fanout`, vendor-product, or protocol synonym is admitted.

All existing Queue evidence paths/conflict rules remain unchanged.

A Topic is eligible only when positive Topic-kind evidence and stable broker/namespace identity both exist. Topic SHALL NOT be inferred from protocol/vendor, a `publish` operation, a `subscribe` operation, `messaging.system`, or the absence of Queue evidence.

Contradictory Queue/Topic evidence is `REJECTED_CONFLICT`; no precedence chooses a winner.

### 8.2 Topic publication

For a qualified Topic channel, AsyncAPI's application-perspective `publish` produces:

```text
Service -[PUBLISHES_TO]-> Topic
Topic   -[CARRIES]-> Message
```

Existing Message and payload-schema identity rules are reused unchanged.

### 8.3 Subscription declaration

AsyncAPI `subscribe` identifies direction but does not identify a broker Subscription.

A qualified Topic `subscribe` operation SHALL therefore require an explicit non-empty `x-aip-subscription-name` to establish Subscription identity.

```yaml
channels:
  orders:
    x-aip-destination-kind: topic
    subscribe:
      x-aip-subscription-name: billing
      message:
        $ref: '#/components/messages/OrderCreated'
```

This produces:

```text
Subscription(billing) -[SUBSCRIPTION_OF]-> Topic(orders)
Service                -[RECEIVES_FROM]-> Subscription(billing)
Topic                   -[CARRIES]-> Message(OrderCreated)
```

Without explicit Subscription identity, AIP SHALL NOT synthesize one from Service name, Channel name, operationId, consumer group, handler name, or source path. Supported Topic publication/message semantics MAY remain, while subscribe-side topology is omitted with a stable limitation/diagnostic.

---

## 9. OpenTelemetry runtime mapping

Runtime evidence MAY qualify behavior against existing declared Topic/Subscription topology.

Runtime evidence SHALL NOT mint an `OBSERVED_ONLY` Topic or Subscription in I4.

I4 SHALL NOT opportunistically widen the existing messaging operation-attribute key boundary. Pub/Sub semantics and semantic-convention-key migration are separate changes.

A runtime Topic can resolve only when destination name is present, exactly one declared Topic candidate matches under the broker/namespace rule, any present kind evidence is compatible, and the existing Service identity guard accepts.

A bare runtime destination name is insufficient. If Queue and Topic both remain viable, the observation is unresolved and creates no messaging fact.

`messaging.destination_kind=queue` preserves existing Queue behavior. `topic` may confirm a declared Topic but SHALL NOT mint one.

A consumer observation supports `Service -[RECEIVES_FROM]-> Subscription` only when the declared Topic resolves exactly, the declared Subscription resolves exactly, `SUBSCRIPTION_OF` links them, the Service identity guard accepts, and runtime Subscription identity matches exactly.

`messaging.consumer.group.name` MAY be retained as bounded evidence metadata but SHALL NOT create a Subscription, resolve a Subscription by itself, or act as an implicit alias.

I4 reuses the existing messaging `decide_service_identity` guard and SHALL NOT create a second Service-identity implementation.

---

## 10. Subscription-specific dead-letter handling

The parent qualification matrix requires a subscription-specific dead-letter case, but broker semantics differ materially. For example, Google Pub/Sub associates a dead-letter Topic with a Subscription, while other systems expose different constructs.

I4 therefore SHALL NOT introduce a generic `Subscription -[DEAD_LETTERS_TO]-> Queue` or force every target into Topic.

When declared evidence contains Subscription-specific dead-letter configuration, AIP SHALL preserve that it belongs to the exact Subscription, retain bounded provenance/source-pointer evidence, prevent leakage to sibling Subscriptions, and avoid creating a generic canonical target relation.

Existing Queue `DEAD_LETTERS_TO` behavior remains unchanged.

---

## 11. Persistence, evidence, and snapshot identity

If GO, graph persistence SHALL support `Topic` and `Subscription` plus exactly the new relation triples from §6, using the existing I1 ownership/inventory/replay/conflict/tombstone engine. No parallel lifecycle engine is permitted.

Every declared Pub/Sub artifact SHALL retain source instance/revision/locator/pointer, semantic digest, adapter/version, broker/namespace evidence, kind evidence, identity inputs, and mapping-rule identity/version.

Runtime evidence SHALL remain bounded/sanitized and SHALL NOT capture arbitrary message payloads, headers, credentials, broker configuration, filters, or policy expressions.

Every public Pub/Sub evidence ref SHALL resolve through `ArchitectureIntelligenceService.get_evidence`, REST evidence resolution, and negotiated MCP `get_evidence` at the same snapshot.

Topic/Subscription public state SHALL participate in snapshot identity. I4 GO SHALL bump `_CANONICALIZATION_VERSION` from `2` to `3` exactly when that public state lands.

Derived dependency claim ids SHALL NOT be snapshot inputs.

---

## 12. Public Architecture Intelligence

I4 adds zero MCP tools and zero public transport modes. The tool count remains exactly three:

```text
get_service_dependencies
get_architecture_drift
get_evidence
```

`ArchitectureIntelligenceService` remains the only semantic owner. REST and MCP SHALL not independently derive Pub/Sub topology or reinterpret Queue/Topic/Subscription semantics.

### 12.1 Public entity types

Public `EntityType` SHALL add `TOPIC` and `SUBSCRIPTION`. `EntityRef` MAY reuse bounded `protocol`/`namespace` metadata for Queue/Topic/Subscription only.

Public `EvidenceRelationType` SHALL add exactly:

```text
PUBLISHES_TO
SUBSCRIPTION_OF
```

`RECEIVES_FROM` and `CARRIES` are reused.

### 12.2 Delivery contract

`DeliveryKind` remains `SYNC_HTTP | ASYNC_MESSAGE`.

`DeliveryRelationType` adds `PUBLISHES_TO`.

`DeliveryRef` gains an optional `subscription: EntityRef | null` with these invariants:

```text
SYNC_HTTP
  relation_type = CALLS
  via.type = OPERATION
  subscription = null

ASYNC_MESSAGE + Queue
  relation_type = SENDS
  via.type = QUEUE
  subscription = null

ASYNC_MESSAGE + Pub/Sub
  relation_type = PUBLISHES_TO
  via.type = TOPIC
  subscription = null | SUBSCRIPTION
```

A non-null Subscription must be `SUBSCRIPTION_OF` the `via` Topic in the same accepted snapshot.

### 12.3 Dependency projection

```text
Topic known, no usable Subscription path
  -> object = Topic
  -> DIRECT_TARGET_FALLBACK

Subscription known, consumer unresolved
  -> object = Subscription
  -> DIRECT_TARGET_FALLBACK

Subscription known, exactly one logical consumer Service
  -> object = Service
  -> RESOLVED_SERVICE

multiple instances of same logical Service
  -> one logical consumer, evidence union

multiple distinct logical Services on one Subscription
  -> fallback to Subscription + ambiguity limitation

two distinct Subscriptions
  -> two distinct routed claims
```

### 12.4 Claim identity compatibility

Existing HTTP/Queue claim ids SHALL remain byte-identical.

The claim-id canonical payload gains one optional field, `subscription_id`, which is omitted entirely for every pre-I4 claim.

For Pub/Sub:

```text
delivery_via_id = Topic id
subscription_id = Subscription id when a Subscription path exists
```

This keeps `DeliveryRef.via` semantically honest while making distinct Subscription routes deterministically distinct.

The public schema remains `schema_version = "0.5"` because v0.5.0 has not shipped; committed v0.5 schemas must be widened explicitly before qualification.

---

## 13. Required qualification

### 13.1 Source matrix

At minimum:

- existing Queue channels remain unchanged;
- Topic with stable broker identity maps to Topic;
- Topic `publish` maps to `PUBLISHES_TO`;
- Topic Message maps to `Topic CARRIES Message`;
- Topic `subscribe` plus explicit Subscription name maps Subscription topology;
- missing Subscription identity never guesses one;
- Queue/Topic kind conflict rejects atomically;
- same names across kinds/brokers/namespaces remain distinct;
- same Subscription name under different Topics remains distinct;
- Subscription-specific dead-letter configuration remains scoped and does not mint a generic target relation;
- protocol/vendor only never establishes kind;
- AsyncAPI 3.x remains rejected.

### 13.2 Runtime matrix

At minimum:

- existing Queue guard behavior remains unchanged;
- declared Topic + compatible runtime send may create observed `PUBLISHES_TO` evidence;
- Topic name only cannot mint Topic;
- Queue/Topic ambiguity is unresolved;
- declared Topic + exact declared Subscription + resolved Service may qualify `RECEIVES_FROM Subscription`;
- consumer group only cannot resolve Subscription;
- consumer-group name accidentally equal to Subscription name is still not an implicit match;
- placeholder/ambiguous Service identity creates zero Pub/Sub fact;
- unsupported operation attribute keys remain unsupported;
- span batch ordering has no semantic effect.

### 13.3 Broker-semantic fixtures

I4 GO requires three deterministic fixtures authored independently from production logic:

1. **Azure Service Bus:** Queue competing consumers plus Topic with at least two Subscriptions; multiple instances inside one Subscription remain load-balanced; Subscription-specific dead-letter configuration stays scoped.
2. **Google Cloud Pub/Sub:** one Topic with multiple Subscriptions plus multiple subscriber instances on one Subscription; same generic semantics, no product-specific canonical entity.
3. **Kafka boundary:** Topic plus consumer group/members; Topic may be modeled when declared evidence is sufficient, but consumer group MUST NOT become canonical Subscription.

Each fixture SHALL disclose source documentation/retrieval date, authored scenario data, expected facts, forbidden facts, and unsupported/deferred constructs.

### 13.4 Public-surface qualification

For equivalent requests, direct service, REST, and negotiated MCP SHALL preserve identical Pub/Sub semantics for claims, snapshot, observation context, Topic/Subscription refs, Subscription route, qualification, limitations, ordering, and evidence resolution.

MCP tool count remains exactly three and public read paths cause zero graph writes.

At least two clean full I4 qualification runs from identical state SHALL be byte-identical.

---

## 14. Backward compatibility

Queue non-regression is release-blocking. The following remain unchanged:

```text
Queue identity and shape
SENDS
RECEIVES_FROM Queue
Queue CARRIES Message
Queue DEAD_LETTERS_TO Queue
existing runtime Queue guard outcomes
existing dependency claim ids
existing Queue EntityRef shape
```

Existing Queue data SHALL NOT be implicitly reclassified as Topic.

---

## 15. Implementation slices

Recommended slicing:

### Slice 1 — Decision and canonical foundation

- independent evidence record;
- ADR 0017;
- GO/DEFER decision;
- if GO: Topic/Subscription models, identity helpers, graph schema, public contract skeleton;
- no adapter behavior yet.

### Slice 2 — Declared AsyncAPI vertical slice

- Topic-kind mapping and Topic identity;
- Subscription identity rule;
- PUBLISHES_TO / SUBSCRIPTION_OF / RECEIVES_FROM / CARRIES;
- subscription-specific dead-letter evidence handling;
- importer/replay/atomicity tests.

### Slice 3 — Runtime qualification

- declared Topic/Subscription candidate reads;
- runtime Topic/Subscription resolution;
- consumer-group negative guard;
- bounded observed evidence;
- zero runtime-only Topic/Subscription minting.

### Slice 4 — Architecture Intelligence vertical slice

- Topic/Subscription public refs;
- DeliveryRef Subscription route;
- dependency/drift projection;
- snapshot canonicalization v3;
- REST/service/MCP equivalence;
- evidence drill-down.

### Slice 5 — Deterministic semantic qualification

- Azure Service Bus fixture;
- Google Pub/Sub fixture;
- Kafka negative fixture;
- full matrix;
- two clean byte-identical runs;
- Queue regression record.

### Slice 6 — Documentation and completion record

- required docs updates;
- `docs/specifications/0.5.0/i4-completion-record.md`;
- immutable qualification identity;
- fixture digests;
- GO evidence / ADR identity;
- regression counts;
- I5 handoff.

---

## 16. Stop conditions

Implementation SHALL stop for specification review if any of these becomes necessary:

1. a fourth MCP tool;
2. a live broker API;
3. AsyncAPI 3.x;
4. a generic canonical `Destination` supertype;
5. a broker-specific canonical entity;
6. automatic consumer-group-to-Subscription equivalence;
7. Subscription identity inferred from Service/handler name;
8. Topic identity inferred from protocol/vendor alone;
9. runtime-only Topic/Subscription minting;
10. fuzzy/case-folded/suffix identity matching;
11. a broker-specific production exception to make a positive fixture pass;
12. partitions/lag/offsets/filters/delivery guarantees/transactions becoming necessary for the generic model;
13. a new source family;
14. `DEPLOYED_AS`, Workload identity, co-location, or Kubernetes topology being required as Pub/Sub evidence;
15. widening old/alternate OTel operation keys as part of I4;
16. Queue semantics or Queue claim ids needing to change;
17. multiple distinct Services on one Subscription requiring fan-out interpretation;
18. a schema version beyond the unreleased `0.5` contract;
19. an adapter independently deriving Architecture Knowledge;
20. an LLM/agent becoming a source of kind, identity, or topology truth.

---

## 17. Definition of Done

### DEFER exit

I4 may complete as `DEFER` when the evidence and exact blocking semantic question are recorded, unsupported cases are explicit, no speculative Topic/Subscription production model is committed, Queue behavior remains unchanged, and I5 can proceed with I4 recorded as deferred.

### GO exit

I4 is complete as `GO` only when:

- ADR 0017 is accepted;
- Topic/Subscription semantics are source-independent;
- Queue/Topic/Subscription identities are deterministic and collision-safe;
- Queue non-regression passes;
- AsyncAPI Channel is never automatically a destination;
- Topic kind requires positive evidence;
- Subscription requires explicit stable identity;
- consumer group is never automatically Subscription;
- runtime cannot mint Topic/Subscription;
- competing-consumer and fan-out cases remain distinguishable;
- Subscription-specific dead-letter configuration remains scoped without guessed generic target semantics;
- Azure and Google positive fixtures pass;
- Kafka produces the required negative consumer-group result;
- evidence/provenance drill-down is complete;
- snapshot identity binds new public state;
- public v0.5 schemas validate old/new cases;
- service/REST/MCP semantics agree;
- MCP tool count remains exactly three;
- public reads cause zero graph writes;
- two clean qualification runs are byte-identical;
- all pre-I4 I1/I2/I3/OpenAPI/AsyncAPI/OTel/MCP regressions remain green;
- limitations/unsupported constructs are documented;
- the I4 completion record pins decision/ADR revision, implementation candidate, identity/schema/rule revisions, fixture digests, regression report, and deterministic qualification evidence.

I4 completion is not release qualification. I5 and I6 remain required.

---

## 18. Handoff to I5

If I4 = GO, I4 provides I5 with stable Queue/Topic/Subscription semantics, deterministic identities, positive competing-consumer/fan-out fixtures, the negative consumer-group boundary, runtime no-minting guards, public Pub/Sub dependency projection, same-snapshot evidence drill-down, and exact rule/schema/canonicalization revisions.

I5 may harden this only when independent cross-system evidence demonstrates a general model defect. Target-specific aliases, product-name branches, fixture exceptions, and broker-specific canonical semantics remain prohibited.

If I4 = DEFER, I5 treats Pub/Sub as unsupported/deferred and SHALL NOT reopen it implicitly.

---

## 19. Review checklist before implementation

- [ ] I4 decision is explicit GO or DEFER.
- [ ] Azure Service Bus and Google Pub/Sub independently support the abstraction.
- [ ] Kafka consumer group is not normalized to Subscription.
- [ ] Queue remains competing-consumer semantics.
- [ ] Topic fan-out is represented by distinct Subscriptions.
- [ ] multiple instances on one Subscription are not fan-out.
- [ ] AsyncAPI Channel is not automatically Queue/Topic.
- [ ] `x-aip-destination-kind` is bounded to `queue|topic`.
- [ ] Topic identity requires stable broker/namespace evidence.
- [ ] Subscription identity includes Topic id.
- [ ] `subscribe` direction alone cannot mint Subscription.
- [ ] runtime cannot mint Topic/Subscription.
- [ ] consumer-group name cannot resolve Subscription.
- [ ] existing v0.4.1 destination/service guards remain active.
- [ ] I3 `DEPLOYED_AS` and Kubernetes placement are not Pub/Sub evidence.
- [ ] exactly three MCP tools remain.
- [ ] `ArchitectureIntelligenceService` remains semantic owner.
- [ ] Queue claim ids remain unchanged.
- [ ] canonicalization version bumps to 3 only when new public state lands.
- [ ] schema version remains `0.5`.
- [ ] no live broker adapter is added.
- [ ] no broker-specific production branch is required.

Acceptance of this checklist is the implementation entry gate.