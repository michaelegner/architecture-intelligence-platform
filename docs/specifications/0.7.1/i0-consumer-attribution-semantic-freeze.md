# AIP v0.7.1 I0 — Consumer Attribution Semantic Freeze

**Status:** Draft  
**Governs:** v0.7.1 I0 from [specification.md](specification.md)  
**Baseline:** published v0.7.0 and the existing Kafka attribution capture

## 1. Goal

Freeze the smallest semantics needed for:

> **For destination D in environment E, which Services can the available evidence safely attribute as consumers, and with what qualification?**

I0 is semantic work only. It does not implement Kafka ingestion or a public API.

## 2. Core Rule

Keep three things distinct:

- **broker attachment:** broker evidence says consumer identity G is attached to destination D;
- **Service mapping:** independent evidence says Service S uses G;
- **derived attribution:** only their qualified combination may establish that S consumes D.

The derivation must retain both evidence paths.

A Service mapping is valid only when it resolves to an already-established Service through the existing messaging Service-identity guard (`decide_service_identity`). Name equality alone is insufficient, and broker evidence must never mint a Service.

## 3. Identity

These identities remain distinct:

- Kafka consumer group != AIP Subscription;
- RabbitMQ consumer/binding shape != Kafka consumer group;
- broker-native consumer identity != Service;
- consumer-group member != Service;
- attachment != message processing.

I0 freezes a minimal consumer-identity carrier with:

- source-native kind and id;
- broker/source scope;
- environment/context;
- deterministic AIP id.

The carrier may be common or source-specific, but it must preserve native meaning.

Destination D must already resolve to an AIP Topic, Queue, or Subscription through the existing messaging destination guards. Broker evidence may qualify that destination but must not mint a runtime-only destination.

## 4. Kafka Reference

Kafka is the v0.7.1 production reference.

The existing capture shows:

- group/member state identifies attachment to Topics;
- separate configuration/runtime evidence maps the group to a Service.

I0 decides whether to reuse or refresh that capture.

Its limits remain explicit: one local Compose run, point-in-time state, one ephemeral container-IP join, client-library-specific member identity, and no message-processing evidence.

Deployment-resolved configuration or another stable reviewed source is preferred for Service mapping.

For Kafka in v0.7.1, **attachment at capture time requires live group/member assignment to the Topic**. Committed offsets or historical group state without a live member assignment may be retained as evidence, but do not establish current attachment.

## 5. RabbitMQ Contrast

Before freezing the carrier, I0 tests at least one RabbitMQ consumer/binding shape.

Record one outcome:

- **REPRESENTABLE** — the same carrier preserves the native distinction;
- **SOURCE_SPECIFIC** — attribution works, but the native identity must stay source-specific;
- **MODEL_GAP** — the model cannot represent the case safely.

A MODEL_GAP may narrow v0.7.1 to Kafka. A RabbitMQ production adapter is not required.

## 6. Time

Broker state may be point-in-time.

Freeze these rules:

- capture at time T is not a v0.7.0 measurement window;
- old broker state is not proof of current attachment;
- attachment and Service mapping combine only when environment/context and temporal basis are compatible.

No generic temporal model is required.

## 7. Reconciliation

Freeze these internal outcomes:

- **RESOLVED**
- **UNRESOLVED**
- **AMBIGUOUS**
- **CONFLICT**

Examples:

- group + one accepted mapping to one existing Service -> RESOLVED;
- group + no accepted Service mapping -> UNRESOLVED;
- two plausible Services with no accepted authority selecting one -> AMBIGUOUS;
- two independently accepted mapping sources that should agree resolve to different Services -> CONFLICT.

AMBIGUOUS means several candidates remain and no accepted evidence selects one. CONFLICT means accepted evidence sources that should agree contradict each other; I0 defines no precedence rule that silently chooses a winner.

Public answer vocabulary remains I2/I3 work.

## 8. Required Cases

I0 must define expected semantics for:

- attachment + Service mapping -> attributable;
- attachment + no Service mapping -> unresolved;
- Service mapping + insufficient broker evidence -> not a negative;
- ambiguous/conflicting mapping;
- incompatible environment/time;
- multiple group members without inventing multiple Services;
- one group attached to multiple Topics;
- group attached to a destination AIP does not already declare -> unsupported; do not mint the destination;
- Service mapping to an identity that does not resolve through the existing Service guard -> unresolved; do not mint the Service;
- committed offsets/historical group state without live member assignment -> not current attachment;
- unsupported broker object;
- attachment without message-processing evidence.

Missing broker evidence never means "not consuming".

## 9. Lifecycle

Freeze only what I1 needs:

- deterministic ids;
- source ownership;
- authoritative removal;
- deterministic snapshot shape;
- identical replay is a no-op;
- no new attribution state when the source is unconfigured.

The meaning of the five v0.7.0 MCP tools remains unchanged.

## 10. Deliverables

I0 produces only:

1. **semantic decision record** — carrier, attachment/mapping, reconciliation, time;
2. **Kafka evidence decision** — reuse or refresh, plus mapping authority;
3. **RabbitMQ contrast record** — REPRESENTABLE, SOURCE_SPECIFIC, or MODEL_GAP.

These records are produced in follow-up I0 PRs after this specification; the final I0 decision/completion PR freezes them and records the outcome.

## 11. Exit

I0 is ready for I1 when:

- broker identity and Service identity remain distinct;
- attachment and mapping semantics are frozen;
- temporal compatibility is defined;
- deterministic identity/lifecycle rules are frozen;
- Kafka evidence is accepted or refresh is explicitly required;
- RabbitMQ has a recorded contrast outcome;
- I1 does not need to invent semantic meaning.

**Outcome:** READY_FOR_I1 or NARROW_AND_REVIEW.
