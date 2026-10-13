# AIP — Broker Semantic Gap Validation, Round 5

**Status:** Planned  
**Input:** Round 4 result plus the Round 2–3 reserve candidates  
**Purpose:** Test whether the broker-related semantic gaps exposed by Sokol111 and sminerport recur across independently authored systems, and use that evidence to define the smallest justified semantic completion before v0.8.

Round 5 is **not another broad candidate search** and is not a v0.8 product-boundary comparison. It asks whether Round 4 found isolated implementation mismatches or recurring gaps in AIP's core distributed Current-State semantics.

## 1. Question

Round 5 SHALL answer:

> **Across independently authored distributed systems, which broker-mediated relationships matter for cross-service change impact but cannot currently be represented or qualified correctly by AIP?**

The result should distinguish:

- recurring **semantic gaps**;
- source/instrumentation-specific **ingestion gaps**;
- broker-specific details that do not justify canonical semantics;
- cases current AIP already handles correctly.

## 2. Starting findings

Round 4 established two concrete gap shapes:

### Kafka consumer attribution

Sokol111 exposes a real producer/topic/consumer scenario in which source establishes Catalog publishing `ProductUpdatedEvent` to `catalog.product.events`, while Product Query and Image participate as separate Kafka consumer groups.

Current AIP deliberately does not equate a Kafka consumer group with a Subscription and therefore cannot attribute those consumers through its existing Topic/Subscription semantics.

### RabbitMQ routing/binding semantics

sminerport exposes a Products → headers exchange → Orders queue/consumer relationship where routing depends on broker binding predicates such as `x-match=all`, `event=product.update`, and `row-count=1`.

Current AIP has neither a broker-topology ingestion source nor semantics for the binding predicate.

These findings are hypotheses for cross-system validation, not yet the scope of a new semantic release.

## 3. Candidate pool

Revisit the existing reserves before searching for new systems:

- **JYC11/koupang** — Kafka/outbox, service-level agent context, runtime/OTel support;
- **hungCS22hcmiu/ecommerce-system** — Kafka saga/event flows and strong coding-agent documentation;
- **daonhan/Microservices-in-.NET** — RabbitMQ or Azure Service Bus with OpenTelemetry;
- **dotnet/eShop** — RabbitMQ and messaging telemetry;
- **mehdihadeli/food-delivery-microservices** — RabbitMQ/Wolverine, OpenTelemetry and EventCatalog.

Sokol111 and sminerport remain the original Round 4 evidence cases and do not need to be rerun unless a later comparison requires it.

Add a new candidate only if the existing pool lacks an important broker semantic shape needed to test a finding.

## 4. Lightweight evaluation method

Do not repeat the complete Round 1–4 funnel for every candidate.

For each reserve candidate, inspect only enough source, configuration, documentation and available telemetry/broker evidence to answer:

1. What broker-mediated producer/consumer relationship matters for a realistic bounded change?
2. What does repository/source context already establish?
3. What independent runtime or broker evidence exists, or can realistically be captured?
4. What relationship would that evidence establish?
5. Can current AIP represent and qualify it correctly?
6. If not, what exact semantic distinction is missing?

Prefer already documented/captured evidence. A live runtime exercise is warranted only when needed to determine whether a candidate supplies independent evidence for a suspected recurring gap.

## 5. Gap classification

Classify each finding as one of:

- **SUPPORTED** — current AIP semantics can represent and qualify the relationship safely;
- **INGESTION_GAP** — the evidence fits existing semantics but AIP cannot currently ingest/map it;
- **SEMANTIC_GAP** — the evidence supports a product-relevant distributed relationship that current AIP cannot represent without losing or inventing meaning;
- **BROKER_SPECIFIC_DETAIL** — the missing detail is real but does not materially affect the bounded cross-service question;
- **INSUFFICIENT_EVIDENCE** — the candidate does not provide enough independent evidence to decide.

Do not promote an ingestion mismatch into a semantic gap.

Do not normalize broker concepts merely because their names look similar:

- Kafka consumer group ≠ Subscription;
- RabbitMQ queue/binding ≠ Topic Subscription;
- Azure Service Bus Subscription ≠ generic consumer group;
- broker connectivity ≠ consumer attribution;
- observed traffic ≠ declared route.

## 6. Candidate record

Use one compact record per candidate:

| Field | Content |
|---|---|
| Candidate | System + frozen revision(s) if inspected deeply |
| Broker model | Kafka / RabbitMQ / ASB / other |
| Bounded change | Event/message/API change used to frame relevance |
| Source-known relationship | What source/config already establishes |
| Independent evidence | Runtime/broker evidence available or realistically capturable |
| Missing AIP distinction | Exact semantic distinction, if any |
| Classification | SUPPORTED / INGESTION_GAP / SEMANTIC_GAP / BROKER_SPECIFIC_DETAIL / INSUFFICIENT_EVIDENCE |
| Recurs Round 4 finding? | Kafka attribution / routing-binding / new / no |
| Product relevance | Why it changes a cross-service investigation question |
| Follow-up | None / qualify further / candidate semantic completion |

## 7. Promotion rule

A broker-related semantic gap is a candidate for product work only when:

1. it affects a recurring distributed architecture/change-impact question across autonomous components;
2. independent evidence can establish the missing relationship;
3. current AIP cannot represent that relationship without inventing or collapsing meaning;
4. the same or closely related distinction appears in more than one independently authored system, or one system demonstrates exceptionally strong independent evidence and product relevance;
5. the smallest correct semantic extension can remain source-independent at the canonical level, even if adapters are broker-specific.

The goal is **not** to model brokers comprehensively.

## 8. Expected semantic questions

Round 5 should specifically test whether the recurring need is one or more of:

- **consumer attribution:** which autonomous Service can safely be attributed as a consumer of a broker-mediated destination in this environment/window?
- **broker route/binding:** which broker-held route or binding connects a producer-side destination to a consumer-side endpoint?
- **destination identity:** what is the stable identity of the queue/topic/subscription/destination actually involved?
- **runtime participation:** which declared/configured consumer relationship is actually active or observed?
- **routing predicate relevance:** does the broker-specific routing condition materially determine the cross-service dependency, or can it remain evidence detail rather than canonical semantics?

Round 5 may discover a different formulation. Do not force all brokers into one abstraction.

## 9. Relation to a semantic-completion release

Round 5 should provide the evidence basis for the smallest justified broker semantic completion before v0.8.

It SHALL NOT implement that completion.

The result should state:

- which semantic gaps are recurring and product-relevant;
- which are only ingestion compatibility issues;
- the smallest architecture question that needs to become answerable;
- which independent systems can qualify the proposed semantics;
- which broker details remain explicitly unsupported.

If no recurring semantic gap survives this validation, do not create a semantic-completion release merely because Round 4 candidates were inconvenient.

## 10. v0.8 candidate consequence

Round 5 may also identify a stronger v0.8 validation system.

A candidate is interesting for later v0.8 use when it:

- naturally exercises a validated broker semantic gap;
- has a fair and strong repository/source baseline;
- provides independently capturable runtime/broker evidence;
- is reproducible at reasonable setup cost;
- becomes representable after the bounded semantic completion rather than requiring bespoke demo semantics.

System selection remains secondary to validating the product-level semantic gap.

## 11. Exit criteria

Round 5 ends with:

- the reserve candidates checked against the Round 4 broker-gap hypotheses;
- at least two independent systems supporting any semantic gap proposed for promotion, unless a documented exception is justified;
- a clear separation of semantic gaps from ingestion gaps and broker-specific details;
- a short proposed semantic-completion scope, or an explicit decision that no such scope is justified;
- one or more systems suitable for qualifying that scope;
- an updated recommendation for the later v0.8 validation system.

The preferred outcome is not maximum feature coverage. It is the **smallest evidence-backed semantic completion that lets AIP answer an important distributed relationship question correctly without collapsing broker-specific meanings.**
