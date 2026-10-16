# AIP v0.7.1 Release Specification — Broker-Mediated Consumer Attribution

**Status:** Draft  
**Baseline:** published v0.7.0

## 1. Product Question

> **For destination D in environment E, which Services can the available evidence safely attribute as consumers, and with what qualification?**

v0.7.1 adds one bounded Current-State capability: **Service-level consumer attribution from broker evidence**.

The core rule is:

> **Broker attachment does not establish Service identity. Service configuration does not establish broker attachment. Only their qualified combination may establish Service-level consumer attribution.**

Conceptually:

~~~text
broker evidence: consumer identity G is attached to destination D
+
mapping evidence: Service S uses consumer identity G
=
qualified attribution: Service S consumes D
~~~

The two evidence paths remain separate and independently qualified.

## 2. Semantic Boundary

v0.7.1 MUST preserve these distinctions:

- Kafka consumer group != AIP Subscription;
- RabbitMQ queue/binding/consumer shape != Kafka consumer group;
- broker-native consumer identity != Service;
- attachment != message processing;
- configured mapping != observed broker attachment;
- missing broker evidence != "not consuming".

AIP SHALL keep the source-native consumer identity visible enough to explain the attribution.

The release does **not** introduce a generic broker-topology model.

### Time

Broker state may be point-in-time rather than window-based.

I0 SHALL freeze the temporal rule. A capture at time T MUST NOT be treated as equivalent to the v0.7.0 measurement-window model or as proof of current attachment indefinitely.

## 3. Source Strategy

### Kafka

Kafka is the first production source because the existing real-system capture demonstrated a viable evidence path:

- broker-held group/member state identifies attachment to Topics;
- separate configuration/runtime evidence maps the group identity to a Service.

The existing capture may be reused or refreshed, but its limits must stay explicit:

- one local Compose run;
- point-in-time state;
- one Service join uses an ephemeral container IP;
- client libraries expose different member identities;
- no message-processing evidence.

Deployment-resolved configuration or another stable reviewed source SHOULD be the mapping authority where available. Name equality alone is not sufficient.

Production ingestion SHOULD prefer structured broker/admin data; human-formatted CLI output requires an explicit reviewed parser contract.

### RabbitMQ

Before freezing a common carrier, I0 SHALL test the proposed semantics against at least one RabbitMQ consumer/binding shape.

This is a **semantic contrast**, not a requirement for a second production adapter.

If the common model cannot preserve the source-native distinction, v0.7.1 SHALL keep the semantics source-specific or narrow the scope rather than force equivalence.

## 4. Qualification

At minimum, qualification must cover:

- attachment + defensible Service mapping -> attributed;
- attachment + unresolved Service mapping -> unresolved;
- Service mapping + missing/insufficient broker evidence -> not a negative;
- insufficient broker coverage/context remains explicit;
- unsupported source object remains explicit;
- ambiguous or conflicting mapping remains explicit;
- incompatible environment/time context is not combined;
- multiple group members do not imply multiple Services;
- one group consuming multiple Topics yields distinct destination attributions;
- broker-native identity is not coerced to Subscription;
- attachment is not presented as message processing;
- replay is deterministic;
- source revision/removal removes stale facts;
- with no new broker source configured, v0.7.0 behavior remains unchanged.

The real-system qualification SHALL include:

- Kafka;
- one contrasting RabbitMQ shape;
- at least one unresolved/insufficient case;
- an end-to-end public answer.

The product check is intentionally small:

> **Does broker evidence materially improve the answer to "which Services consume this destination?" compared with repository/configuration analysis alone?**

Record mapping effort, unresolved/ambiguous rate, source setup effort, and whether the evidence changes the coding-agent investigation boundary. End with one owner-reviewed disposition: **CONTINUE | NARROW | DEFER | STOP**.

## 5. Public Surface

v0.7.1 SHALL expose the bounded question through the shared semantic service and REST + negotiated MCP. Destination and environment/context are required request inputs.

I3 decides whether this belongs in an existing tool or requires a new tool. A sixth MCP tool is **not** pre-authorized.

The answer must preserve:

- destination and environment/context;
- broker-native consumer identity;
- Service attribution qualification;
- unresolved/ambiguous/conflicting cases;
- evidence for both attachment and Service mapping;
- temporal basis of the evidence.

The public surface remains deterministic, read-only, and secret-free. The meaning of the five v0.7.0 MCP tools remains unchanged.

## 6. Scope

In scope:

- broker-native consumer identity;
- broker attachment;
- Service mapping;
- derived Service-level attribution;
- Kafka production ingestion;
- RabbitMQ semantic cross-check;
- deterministic public answer and real-system qualification.

Out of scope:

- general broker topology;
- routing predicates;
- lag/offset/rebalancing analysis;
- DLQ/retry topology;
- partition ownership;
- generic cross-broker equivalence;
- message-processing confirmation unless independently evidenced;
- authorization, ownership, policy, Intent or compliance;
- v0.8 boundary/composition work.

## 7. Increment Plan

**I0 — Semantic freeze**  
Freeze consumer identity, attachment, mapping, temporal semantics, Kafka/RabbitMQ distinction, reconciliation, qualification cases, deterministic ids, source ownership, and snapshot shape.

**I1 — Kafka source**  
Implement the smallest deterministic Kafka broker-state source with provenance, authoritative removal/replay, and clean absence when unconfigured.

**I2 — Mapping + attribution**  
Implement Service mapping, reconciliation, ambiguity/conflict handling, and derived attribution.

**I3 — Public answer**  
Expose the product question through Architecture Intelligence, REST and MCP.

**I4 — Qualification**  
Run exact-candidate A/B deterministic qualification, Kafka replay, RabbitMQ contrast, public-surface parity, and the lightweight product-value check.

**I5 — Release**  
Use the exact-candidate release process established by v0.7.0. Before freeze, re-check release-facing wording and the current state of every issue/CVE/limitation named in release material.

## 8. Exit Criteria

v0.7.1 is done when:

1. broker identity, Service identity and existing messaging entities remain distinct;
2. attachment and Service mapping are independently evidenced;
3. attribution is derived only from their qualified combination;
4. Kafka ingestion is deterministic and context/time bounded;
5. the semantics survive the RabbitMQ contrast or the scope is explicitly narrowed;
6. unresolved/ambiguous/conflicting cases remain explicit;
7. attachment is not presented as message processing;
8. the public answer is deterministic and evidence-linked;
9. v0.7.0 behavior is unchanged when the new source is absent;
10. exact-candidate A/B and real-system qualification pass;
11. the product-value check ends with an owner-reviewed disposition;
12. the exact release candidate is published and verified.

## 9. Permitted Release Claim

After qualification:

> **AIP v0.7.1 can evidence-qualify which application Services are attributable as consumers of broker-mediated destinations by combining broker-held consumer attachment with independently evidenced Service mapping, while preserving broker-native identity, context and uncertainty.**
