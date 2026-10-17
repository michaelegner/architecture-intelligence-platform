# AIP v0.7.1 I2 — Service Mapping and Consumer Attribution

**Status:** Draft  
**Governs:** v0.7.1 I2 from [specification.md](specification.md)  
**Depends on:** completed I0 ([semantic decision](i0-semantic-decision.md), [handoff](i0-i1-i2-handoff.md)) and completed I1 ([completion record](i1-completion-record.md), [I1 → I2 handoff](i1-i2-handoff.md))  
**Entry outcome:** I1 = `READY_FOR_I2`

## 1. Goal

I2 adds the independent Service-mapping path and combines it with the Kafka broker attachment delivered by I1.

It shall establish, inside one AIP snapshot:

> **Which declared Service, if any, can be attributed to each Kafka consumer identity, and therefore to each broker attachment, without treating either evidence path as sufficient on its own?**

The governing derivation remains:

~~~text
broker evidence: consumer identity G is attached to Topic D at T
+
mapping evidence: Service S uses consumer identity G
=
qualified attribution: Service S is attributable as a consumer of D at T
~~~

The result is still **Current State**. It does not establish message processing, authorization, ownership, policy, Intent, or that the mapping itself was observed at T.

I2 produces deterministic internal state for I3. It adds no REST/MCP/public schema and does not authorize a sixth MCP tool.

## 2. Frozen inputs

I2 shall not reinterpret these I0/I1 decisions:

- Kafka consumer identity is the consumer group id in broker/environment scope;
- `KafkaConsumerGroup` is neither a Service nor a Subscription;
- broker attachment is a live assignment to an already-declared Topic at capture time T;
- attachment does not mean message processing;
- member id, client id and host are not retained by AIP and are not mapping inputs;
- a Service mapping must be explicit, provenance-bearing and environment-compatible;
- name equality by itself is not mapping authority;
- runtime host/IP equality is corroboration only and cannot establish the mapping;
- Service resolution uses `decide_service_identity` and only its `DECLARED` outcome may establish a mapping;
- an `OBSERVED_ONLY` Service outcome is rejected for attribution and must never mint a Service;
- attachment and mapping combine only in the same environment and the same snapshot generation;
- reconciliation outcomes are exactly `RESOLVED`, `UNRESOLVED`, `AMBIGUOUS`, `CONFLICT`;
- no precedence rule silently chooses between contradictory accepted mappings;
- missing broker evidence never means "not consuming".

I2 consumes the I1 snapshot-visible carrier contract `kafka_consumer_state_v1`; it does not change I1 ids, source ownership, lifecycle or capture semantics.

## 3. Scope and non-goals

I2 implements only:

1. one explicit operator-supplied Kafka consumer-group → Service mapping source;
2. deterministic mapping-source lifecycle and provenance;
3. DECLARED-only Service resolution and mapping reconciliation;
4. derived Service-level attribution for I1 Kafka attachments;
5. deterministic snapshot state and the I2 → I3 handoff.

Out of scope:

- public REST/MCP answer shape, pagination or public evidence vocabulary (I3);
- a RabbitMQ production source or RabbitMQ Service mapping (I4 remains semantic contrast only);
- automatic mapping from group names, Service names, repository names, labels, hostnames or IP addresses;
- deployment-resolved mapping as a second production authority;
- generic broker-consumer mapping across source families;
- creating or strengthening existing `RECEIVES_FROM` relationships;
- creating a Subscription, Topic or Service;
- message-processing confirmation;
- history, mapping effective intervals or a generic temporal model;
- authorization, ownership, policy, Intent, compliance or Assessment.

## 4. Mapping source

### 4.1 Separate evidence source

The first supported mapping authority is the operator mapping artifact frozen by I0 D3.

It shall be a **separate configured source** from `kafka_consumer_state`. Broker attachment and Service mapping therefore have independent source ids, revisions, lifecycle and evidence.

The exact configuration key and internal class names may be frozen in I2.1, but the source registration shall contain at least:

- configured source id;
- fixture root / mapping file path;
- stable Kafka broker id;
- environment.

Several mapping-source registrations may target the same broker/environment. They are independent authorities and are intentionally allowed so agreement and conflict can be represented.

Changing broker id or environment changes the mapping source instance identity. Removing a mapping-source registration retires only that source's mapping carriers.

### 4.2 Artifact contract

The first artifact schema is:

~~~text
aip-kafka-consumer-service-mapping/1
~~~

It contains exactly one broker id, one environment, and a sorted list of mappings.

Each mapping entry contains:

~~~text
group_id
service_name
service_namespace   # optional
~~~

Rules:

- `group_id` is the exact Kafka group id; no case folding or normalization;
- broker id and environment must exactly match the source registration;
- `service_name` is non-empty and identifies the declared Service target asserted by the operator;
- `service_namespace`, when present, participates in the existing Service-identity guard;
- one artifact may contain at most one entry for an exact group id; a duplicate group entry rejects that artifact rather than inventing intra-source precedence;
- entries and object keys are normalized/sorted deterministically;
- unknown fields are rejected;
- the artifact carries no credentials, tokens, client ids, member ids or hosts.

The artifact is configuration evidence, not a broker capture. It has no observation window and does not claim that the mapping was observed at the broker capture time T.

A byte-identical artifact replay is a semantic no-op. A later valid artifact for the same configured mapping source authoritatively replaces only that source's prior mapping entries. An invalid/rejected artifact removes nothing previously accepted.

### 4.3 Mapping does not mint broker identity

A mapping entry references the I1 Kafka consumer identity domain by:

~~~text
broker id
environment
exact group id
~~~

and therefore the I1 consumer-id formula using source kind `kafka_consumer_state`.

The mapping source shall not create a `KafkaConsumerGroup` when I1 has no such group carrier. Mapping evidence may exist without broker evidence; that is required to preserve the two evidence paths independently.

## 5. Service resolution and mapping reconciliation

### 5.1 Entry resolution

For each mapping entry, I2 resolves `service_name` / `service_namespace` against the current declared Service candidates using `decide_service_identity`.

This path does not add a new name-similarity rule. The operator mapping itself is the relationship assertion; the Service selector is only accepted when the existing guard resolves it to one declared Service.

The outcomes are:

| Guard result | I2 entry result |
|---|---|
| accepted + `DECLARED` | resolved Service candidate |
| accepted + `OBSERVED_ONLY` | `UNRESOLVED`; do not create the Service |
| ambiguous identity | `AMBIGUOUS` |
| conflicting identity | `CONFLICT` |
| placeholder/otherwise refused | `UNRESOLVED` |

I2 shall not use runtime host/IP data to upgrade any of these outcomes.

### 5.2 Consumer-level reconciliation

All valid mapping entries for the same I1 consumer identity are reconciled without source precedence.

Rules, in order:

1. if two or more resolved entries identify different declared Service ids -> `CONFLICT`;
2. if any accepted entry has a Service-identity conflict -> `CONFLICT`;
3. if all resolved entries, when any exist, identify one distinct Service id -> `RESOLVED` to that Service; evidence from every agreeing resolved entry is retained;
4. if no entry resolves and at least one entry is ambiguous -> `AMBIGUOUS`;
5. otherwise -> `UNRESOLVED`.

Unresolved or ambiguous entries do not become alternative Services. They remain explainable source evidence and limitations.

Two independent mapping sources that resolve the same group to the same Service strengthen provenance, not cardinality: the result is still one Service mapping.

## 6. Derived Service-level attribution

Attribution is derived from the **current snapshot**, not persisted as a new canonical relationship.

For each I1 `KafkaConsumerAttachment`:

~~~text
consumer identity G
→ Topic D
at T
~~~

I2 evaluates the reconciled Service mapping for G in the same broker/environment and same snapshot generation.

The attribution row is:

| Mapping outcome | Attribution outcome |
|---|---|
| `RESOLVED` to Service S | `RESOLVED`: S attributable to D from G at T |
| no mapping / unresolved mapping | `UNRESOLVED` |
| `AMBIGUOUS` | `AMBIGUOUS` |
| `CONFLICT` | `CONFLICT` |

A resolved attribution retains evidence from **both** paths:

- I1 broker attachment evidence;
- I2 mapping evidence.

It also retains:

- consumer id and exact Kafka group id;
- broker id and environment;
- Topic id;
- Service id only for `RESOLVED`;
- broker capture time T;
- mapping source ids/revisions that contributed to the mapping outcome.

The precise claim is:

> In this snapshot, mapping evidence attributes Service S to consumer identity G, and broker evidence observed G attached to Topic D at T.

It does **not** claim that the mapping was independently observed at T, that S processed a message, or that S still consumes D after T.

### Mapping without attachment

A resolved mapping with no I1 attachment produces **no Service-level consumer attribution and no negative claim**.

An I1 group in `Empty` or `Dead` state therefore does not become "Service S does not consume D". The mapping may remain present as configuration evidence, but there is no attachment-derived attribution row.

### One group, several Topics

One resolved mapping for G combined with attachments to D1 and D2 yields two distinct attribution rows. It does not create two Services.

## 7. Snapshot and lifecycle

### 7.1 Internal carriers

I2 may persist only source-qualified mapping carriers/evidence owned by the mapping source.

It shall not persist:

- a new `RECEIVES_FROM` edge;
- a Service→Topic canonical edge;
- a Subscription derived from the group;
- a broker-derived Service.

Mapping resolution and Service-level attribution are pure deterministic derivations over the current snapshot state.

This ensures I0 D4's same-snapshot rule: removing/changing either evidence path changes the derived result on the next snapshot without leaving stale attribution state behind.

### 7.2 Snapshot block

I2 adds one conditional internal snapshot block:

~~~text
kafka_consumer_attribution_v1
~~~

It contains, in deterministic order:

- accepted mapping-source identities/revisions and mapping entries;
- per-consumer mapping reconciliation outcome;
- per-I1-attachment attribution outcome;
- Service id only where resolved;
- evidence ids from both paths;
- limitation/reason codes needed to explain unresolved, ambiguous or conflicting outcomes.

The block is present when at least one accepted mapping carrier or I1 Kafka attachment exists. It is absent when neither source contributes state.

With no Kafka consumer-state source and no mapping source configured, the v0.7.0 snapshot and behavior remain unchanged.

### 7.3 Lifecycle cases

- removing an I1 attachment removes its derived attribution but not the mapping;
- removing a mapping entry/source leaves the I1 attachment intact and changes its derived attribution to `UNRESOLVED`;
- replacing a mapping source with an agreeing target updates provenance without creating a second attribution;
- replacing it with a different target may produce `CONFLICT` when another accepted source still disagrees;
- rejected/partial mapping import preserves the previous accepted mapping state;
- byte-identical mapping replay is a no-op.

## 8. Evidence and safety

Every mapping and attribution outcome must remain explainable from source-qualified evidence.

At minimum, mapping evidence retains:

- mapping source instance id and revision/content digest;
- broker id and environment;
- exact group id;
- asserted Service selector;
- the resolution outcome and resolved Service id when applicable.

I2 keeps this evidence internal. It does not widen public `SourceType`, public evidence endpoints, natural-language/Cypher reachability, or MCP exposure; I3 owns those choices.

No mapping artifact or diagnostic may contain credential fields or credential values. Required architectural identifiers such as group id and Service name are retained because they are the mapping claim itself; I2 does not attempt to classify arbitrary identifier text as a secret by shape.

## 9. Required qualification cases

Expected results shall be authored independently from the production reconciliation code.

| Case | Expected result |
|---|---|
| attachment + one explicit mapping to one DECLARED Service | `RESOLVED`; Service attribution contains both evidence paths |
| attachment + no mapping | `UNRESOLVED`; broker-native consumer remains visible |
| mapping + no attachment | mapping retained; no Service-level attribution and no negative claim |
| mapping target would be `OBSERVED_ONLY` | `UNRESOLVED`; Service not minted |
| mapping target matches several declared Services | `AMBIGUOUS` |
| mapping target conflicts with declared Service identity | `CONFLICT` |
| two accepted mapping sources resolve one group to different Services | `CONFLICT`; no precedence |
| two accepted mapping sources resolve one group to the same Service | one `RESOLVED` mapping with both provenance paths |
| mapping source environment differs from attachment environment | no cross-join; attachment remains unresolved in its environment |
| mapping source broker differs from attachment broker | no cross-join |
| one group attached to two Topics + one resolved Service mapping | two resolved attribution rows, one Service |
| group has several members | member count does not change Service cardinality |
| I1 attachment removed by later complete capture | derived attribution disappears; mapping remains |
| mapping entry removed by later complete artifact | attachment remains; derived outcome becomes `UNRESOLVED` |
| mapping artifact broker/environment mismatches registration | mapping source rejected; prior accepted state preserved |
| duplicate group entry inside one artifact | mapping source rejected; prior accepted state preserved |
| invalid/partial mapping artifact | prior accepted mapping state preserved |
| no mapping source configured | I1 broker state unchanged; no Service mapping is invented |
| no I1 or mapping source configured | v0.7.0 behavior/snapshot unchanged |
| resolved attribution inspected twice from identical state | byte-identical semantic result |

The implementation must also retain I0 §8's negative guarantees:

- unsupported destination never mints a destination;
- undeclared Service never mints a Service;
- mapping alone is not broker attachment;
- broker attachment alone is not Service identity;
- attachment is not message processing.

## 10. Implementation shape

Keep I2 bounded.

### I2.1 — mapping contract + independent vectors

Freeze:

- source registration and source-instance identity;
- `aip-kafka-consumer-service-mapping/1`;
- mapping-entry identity and replacement rules;
- exact Service-selector fields;
- reconciliation truth table;
- independently authored known-answer vectors for resolved, unresolved, ambiguous and conflicting cases.

No public answer.

### I2.2 — mapping source + lifecycle

Implement:

- mapping registration/discovery/loader;
- strict artifact validation;
- source-owned mapping carriers/evidence;
- deterministic replay/replacement/removal;
- no consumer, Topic, Subscription or Service minting.

### I2.3 — reconciliation + derived attribution + I3 handoff

Implement:

- DECLARED-only Service resolution through `decide_service_identity`;
- consumer-level `RESOLVED / UNRESOLVED / AMBIGUOUS / CONFLICT`;
- same-snapshot combination with I1 attachments;
- `kafka_consumer_attribution_v1`;
- qualification cases in §9;
- I2 completion record and I2 → I3 handoff.

Slices may be combined if review is clearer.

## 11. I2 → I3 handoff

I3 may rely on:

- I1 consumer identity, Topic attachment and capture time T;
- I2 mapping resolution outcome and mapping provenance;
- I2 per-attachment attribution outcome;
- Service id only when attribution is `RESOLVED`;
- evidence ids for both the broker and mapping paths;
- deterministic `kafka_consumer_attribution_v1`.

I3 must preserve:

- broker-native consumer identity in the answer;
- point-in-time wording for attachment;
- unresolved/ambiguous/conflicting outcomes;
- mapping and attachment as separate evidence paths;
- the fact that resolved attribution is not message-processing evidence.

I3 still owns:

- public request/answer vocabulary;
- REST and MCP shape;
- bounded enumeration/pagination;
- public evidence exposure;
- whether the bounded question belongs in an existing MCP tool or requires a new one. A sixth tool remains unapproved until I3 decides and the owner reviews it.

## 12. Definition of Done

I2 is complete when:

- an explicit mapping artifact is a separate evidence source from Kafka attachment;
- mapping replay/replacement/removal is deterministic;
- mapping entries never mint consumer, Topic, Subscription or Service identities;
- only a `DECLARED` Service-identity outcome establishes a mapping;
- `OBSERVED_ONLY` Service resolution is rejected without minting;
- reconciliation implements exactly the four I0 outcomes with no hidden precedence;
- mapping and attachment combine only in the same broker/environment and current snapshot;
- each resolved attribution carries evidence from both paths and capture time T;
- mapping without attachment produces no negative consumer claim;
- attachment without mapping remains explicit and unresolved;
- attribution is derived, not written into the existing messaging relationship model;
- §9 cases pass against independently authored expected results;
- no-source behavior preserves the v0.7.0 baseline;
- the I2 → I3 handoff is explicit.

**Outcome:** `READY_FOR_I3` or `NARROW_AND_REVIEW`.

## 13. Needs a reviewed amendment if it changes

A reviewed specification amendment is required before changing:

- the operator mapping artifact as the first supported mapping authority;
- separate source ownership for broker attachment and Service mapping;
- exact broker/environment/group identity matching;
- DECLARED-only Service resolution;
- the four reconciliation outcomes or their no-precedence rule;
- the same-snapshot composition rule;
- the rule that mapping without attachment is not a negative;
- the rule that attribution is not message-processing evidence;
- the rule that I2 does not create `RECEIVES_FROM`, Subscription, Topic or Service truth;
- the internal `kafka_consumer_attribution_v1` semantic contents;
- the deferral of public REST/MCP semantics to I3.
