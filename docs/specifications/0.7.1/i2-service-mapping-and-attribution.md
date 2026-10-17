# AIP v0.7.1 I2 — Service Mapping and Consumer Attribution

**Status:** Draft  
**Governs:** v0.7.1 I2 from [specification.md](specification.md)  
**Depends on:** completed I0 and I1 (`READY_FOR_I2`)

## 1. Goal

Add the missing Service-mapping half of broker-mediated consumer attribution.

For one Kafka consumer attachment from I1:

~~~text
consumer group G is attached to Topic D at T
+
mapping evidence says Service S uses G
=
Service S is attributable as a consumer of D at T
~~~

Broker attachment and Service mapping remain separate evidence paths. Neither is sufficient alone.

I2 is internal Current-State work only. Public REST/MCP exposure stays in I3.

## 2. Rules carried from I0/I1

I2 must preserve these rules:

- Kafka consumer group != Service != Subscription;
- attachment != message processing;
- mapping must be explicit, provenance-bearing and environment-compatible;
- name equality alone is not mapping authority;
- Service resolution uses `decide_service_identity`;
- only a `DECLARED` Service may be accepted;
- an `OBSERVED_ONLY` result must not mint or establish a Service;
- broker id, environment and group id must match exactly;
- attachment and mapping combine only in the same snapshot;
- outcomes are `RESOLVED`, `UNRESOLVED`, `AMBIGUOUS`, `CONFLICT`;
- there is no hidden precedence rule;
- missing attachment or mapping is never a negative claim.

## 3. Mapping source

The first supported mapping source is an operator-supplied artifact, separate from the Kafka broker-state source.

Minimal shape:

~~~text
schema: aip-kafka-consumer-service-mapping/1
broker_id
environment
mappings:
  - group_id
    service_name
    service_namespace   # optional
~~~

Rules:

- exact `group_id`; no normalization;
- broker/environment must match the configured mapping source;
- duplicate group entries in one artifact reject the artifact;
- unknown fields are rejected;
- no credentials, member ids, client ids or hosts;
- byte-identical replay is a no-op;
- a later valid artifact replaces that source's prior mappings;
- a rejected artifact keeps the previous accepted state.

The mapping source may reference a group even when I1 currently has no attachment for it. Mapping evidence must remain independent from broker evidence and must not create a `KafkaConsumerGroup`.

## 4. Service resolution and reconciliation

Each mapping entry resolves its Service through `decide_service_identity`.

| Result | I2 outcome |
|---|---|
| one `DECLARED` Service | candidate for `RESOLVED` |
| `OBSERVED_ONLY` / no declared Service | `UNRESOLVED` |
| several possible declared Services | `AMBIGUOUS` |
| conflicting declared identity | `CONFLICT` |

If several accepted mapping sources exist for the same group:

- all resolve to the same Service -> `RESOLVED`;
- they resolve to different Services -> `CONFLICT`;
- none resolves but at least one is ambiguous -> `AMBIGUOUS`;
- otherwise -> `UNRESOLVED`.

No source silently wins over another.

## 5. Derived attribution

For each I1 attachment, I2 combines the current mapping outcome for the same group, broker and environment.

The mapping artifact has no observation time. It combines with an attachment only in the same environment and snapshot generation; the resulting attribution reports broker capture time T and does not claim that the mapping itself was observed at T.

| Mapping outcome | Attribution |
|---|---|
| `RESOLVED` | Service S attributable to Topic D at capture time T |
| `UNRESOLVED` | unresolved |
| `AMBIGUOUS` | ambiguous |
| `CONFLICT` | conflict |

A resolved attribution must retain both evidence paths:

- I1 attachment evidence;
- I2 mapping evidence.

The claim is deliberately narrow:

> In this snapshot, mapping evidence attributes Service S to consumer group G, and broker evidence observed G attached to Topic D at T.

It does not mean S processed a message or still consumes D after T.

Mapping without attachment creates no consumer attribution and no negative claim.

## 6. Internal state

I2 may persist source-owned mapping carriers/evidence, but attribution itself should be derived from the current snapshot rather than written as a new canonical messaging relationship.

Add one conditional snapshot block:

~~~text
kafka_consumer_attribution_v1
~~~

It contains:

- mapping-source identities/revisions;
- mapping entries;
- per-group reconciliation outcome;
- per-attachment attribution outcome;
- Service id only when resolved;
- evidence ids from both paths;
- reason/limitation codes where needed.

I2 must not create:

- `RECEIVES_FROM`;
- a new Service→Topic relationship;
- a Subscription from a Kafka group;
- a `KafkaConsumerGroup` from mapping evidence;
- a Service from broker evidence.

## 7. Required cases

At minimum:

| Case | Expected |
|---|---|
| attachment + one mapping to one declared Service | `RESOLVED` |
| attachment + no mapping | `UNRESOLVED` |
| mapping + no attachment | mapping retained, no attribution |
| mapping target would be `OBSERVED_ONLY` | `UNRESOLVED`, no Service minted |
| ambiguous declared Service | `AMBIGUOUS` |
| conflicting Service identity | `CONFLICT` |
| two mapping sources -> same Service | one `RESOLVED` result with both provenance paths |
| two mapping sources -> different Services | `CONFLICT` |
| broker/environment mismatch | no cross-join |
| several members in one group + one mapping | one Service attribution, not one per member |
| one group attached to two Topics | two attribution rows, one Service |
| I1 attachment disappears | derived attribution disappears, mapping remains |
| mapping disappears | attachment remains, attribution becomes `UNRESOLVED` |
| rejected mapping update | previous accepted mapping remains |
| no mapping source | no mapping invented; I1 state unchanged |
| no Kafka or mapping source | v0.7.0 behavior unchanged |

Expected results should be authored independently from the production reconciliation code.

## 8. Implementation slices

Keep implementation small:

**I2.1 — mapping contract**  
Freeze artifact format, source identity/lifecycle and independent expected cases.

**I2.2 — mapping + reconciliation**  
Implement source ingestion, DECLARED-only Service resolution and the four outcomes.

**I2.3 — attribution + handoff**  
Derive per-attachment attribution, expose `kafka_consumer_attribution_v1`, complete qualification cases, and hand the stable internal state to I3.

## 9. I2 → I3 handoff

I2 hands I3: consumer group identity, destination, capture time T, reconciliation/attribution outcome, Service id when resolved, and evidence references for both attachment and mapping.

## 10. Exit

I2 is complete when:

- broker attachment and Service mapping remain independent evidence paths;
- only explicit mapping to a declared Service can resolve attribution;
- unresolved, ambiguous and conflicting mappings remain explicit;
- resolved attribution carries both evidence paths and capture time T;
- mapping alone creates no consumer claim or Kafka consumer identity;
- attribution does not create new canonical messaging relationships;
- required cases pass deterministically;
- I1 and v0.7.0 behavior remain unchanged when the new mapping source is absent;
- the I2 → I3 handoff is explicit.

**Outcome:** `READY_FOR_I3` or `NARROW_AND_REVIEW`.
