# AIP v0.7.1 I1 — Kafka Consumer-State Source

**Status:** Draft  
**Governs:** v0.7.1 I1 from [specification.md](specification.md)  
**Depends on:** completed I0 and its [semantic decision](i0-semantic-decision.md) / [handoff](i0-i1-i2-handoff.md)

## 1. Goal

Implement the smallest deterministic Kafka source needed to establish:

> **Kafka consumer identity G is attached to already-declared Topic D at capture time T.**

I1 adds broker evidence only.

It does **not** implement Service mapping, Service-level attribution, reconciliation, a public answer, or a RabbitMQ adapter. Those remain I2–I4 work.

## 2. Frozen I0 Rules

I1 must not reinterpret:

- Kafka native consumer identity = consumer group id;
- consumer identity remains distinct from Service and Subscription;
- attachment requires a **live member assignment** to a Topic;
- committed offsets or historical group state alone are not current attachment;
- destination must already exist as a declared AIP Topic;
- broker evidence never mints a Topic or Service;
- attachment is point-in-time at capture time T;
- identical replay is a no-op;
- an accepted complete capture may authoritatively replace this source's attachments;
- failed or partial capture removes nothing.

## 3. Source Identity

Add one Kafka consumer-state source kind.

A configured source has:

- configured source id;
- explicit stable broker id;
- environment;
- path to one normalized Kafka capture.

The stable broker id must use the same identity domain as declared Topic ownership (x-aip-broker-id / existing broker identity rules). Bootstrap-server addresses are not broker identity.

The source instance id is deterministic from:

~~~text
configured source id
stable broker id
environment
~~~

The Kafka consumer identity id follows I0 D1:

~~~text
consumer:
  sha256(length-delimited(
    source kind,
    stable broker id,
    environment,
    exact group id
  ))
~~~

Group id is preserved verbatim as the source-native id.

## 4. Capture Contract

Production ingestion consumes a **structured normalized capture**, not human-formatted Kafka CLI output.

A separate capture step uses Kafka Admin API-equivalent data and records at least:

- capture time T;
- stable broker id and environment;
- Kafka version / capture-tool version where available;
- consumer groups;
- group state;
- members;
- each member's topic assignments;
- capture completeness.

Member ids, client ids, host addresses and partition assignments are retained only as evidence detail needed to explain the attachment. They are not canonical Services or consumer identities.

The normalized capture must be deterministic: stable field representation and sorted groups, members and assignments.

Credentials, security properties and broker secrets must never enter the retained capture.

## 5. Completeness and Lifecycle

Authoritative removal is allowed only from a **complete accepted capture**.

A complete capture requires:

- successful enumeration of the configured Kafka consumer-group scope;
- successful description of every enumerated group needed by that scope;
- no acquisition error or explicitly missing/truncated group result;
- a valid capture time, broker id and environment.

If completeness cannot be established, reject the capture and preserve prior accepted state.

For a later complete capture:

- attachments absent from the new capture are removed for this source;
- live assignments in the new capture replace the prior attachment set;
- identical semantic input is a no-op.

A group with no live member assignment contributes no current attachment at T.

## 6. Topic Resolution

For every live topic assignment, I1 resolves the destination through the existing declared Topic identity rules.

The join uses:

- configured stable broker id;
- Kafka namespace = empty;
- exact topic name/address.

The derived Topic id must already exist in the upstream canonical model.

If no declared Topic exists, I1 records the source fact as unsupported/unresolved evidence as appropriate, but creates no Topic and no attachment edge.

Name similarity, group id, member id, bootstrap host, or Service name must never create or select a Topic.

## 7. Canonical State

I1 adds only the minimum internal state needed by I2:

### Consumer identity

Source-qualified carrier from I0 D1:

- deterministic consumer id;
- source-native kind = Kafka consumer group;
- exact group id;
- broker scope;
- environment;
- source ownership/provenance.

### Attachment

One point-in-time attachment for each:

~~~text
consumer identity G
→ declared Topic D
at capture time T
~~~

Several members of the same group do not create several consumer identities.

One group assigned to several Topics creates one attachment per Topic.

Attachment does not mean that a message was processed.

## 8. Evidence and Provenance

Every accepted attachment must be explainable by retained source evidence containing:

- source instance/revision;
- broker id and environment;
- capture time;
- group id;
- member/assignment detail supporting the Topic attachment;
- capture completeness.

Evidence remains source-qualified. I1 does not expose a new public answer.

## 9. Required Qualification Cases

At minimum:

| Case | Expected result |
|---|---|
| live group member assigned to declared Topic | attachment recorded |
| several members of one group on one Topic | one consumer identity / one Topic attachment |
| one group on several Topics | distinct Topic attachments |
| committed offsets but no live members | no current attachment |
| live assignment to undeclared Topic | unsupported/unresolved; Topic not minted |
| same group id on different broker/environment | distinct consumer identities |
| identical replay | no semantic change |
| later complete capture removes assignment | prior attachment removed |
| failed/partial capture | prior state preserved |
| unconfigured Kafka source | no new state; v0.7.0 behavior unchanged |
| member/client/host changes but group+Topic remain | same consumer identity and attachment semantics |
| secret/canary input | absent from retained capture/provenance/diagnostics |

Expected results should be authored independently from the production adapter.

## 10. Implementation Shape

Keep I1 small:

**I1.1 — source contract + fixture**  
Freeze source registration, capture schema, ids and independent expected vectors.

**I1.2 — capture + replay source**  
Add structured Kafka capture, source discovery and normalized replay.

**I1.3 — canonical attachment + lifecycle**  
Persist consumer carriers/attachments, enforce declared-Topic guard, replay/removal and evidence.

**I1.4 — completion + I2 handoff**  
Record deterministic replay/regressions and hand I2 the stable carrier/attachment contract.

Slices may be combined when review is simpler.

## 11. I1 → I2 Handoff

I2 receives:

- deterministic consumer identity;
- broker id + environment;
- capture time T;
- resolved declared Topic id;
- attachment evidence/provenance;
- source revision/lifecycle identity;
- unsupported/unresolved source cases.

I2 owns:

- mapping artifact format;
- accepted Service mapping;
- DECLARED-only Service resolution;
- RESOLVED / UNRESOLVED / AMBIGUOUS / CONFLICT;
- derived Service-level attribution.

## 12. Exit

I1 is complete when:

- a structured Kafka capture can be replayed deterministically;
- live assignments produce attachment only to already-declared Topics;
- no Topic, Subscription or Service is minted from broker state;
- consumer ids and source ownership match I0;
- complete capture replacement and failed/partial preservation are tested;
- secrets do not enter retained state;
- no-source behavior remains unchanged;
- the I1 → I2 handoff is explicit.

**Outcome:** READY_FOR_I2 or NARROW_AND_REVIEW.
