# Round 5 — Result

**Spec:** [spec-round5-broker-semantic-gap-validation.md](spec-round5-broker-semantic-gap-validation.md) §9–§11  
**Date:** 2026-10-13  
**Detail:** [candidate records](round5-candidate-records.md) · [synthesis](round5-synthesis.md) · [probe evidence](round5-evidence/)

## Outcome

1. **One recurring product question: consumer attribution.** Six independent systems (Kafka:
   Sokol111, koupang, hungCS22hcmiu; RabbitMQ: sminerport, eShop, daonhan) expose the same
   consumer-attribution need in source/config. Current AIP has no demonstrated evidence path for
   qualifying that runtime attachment in these cases. Round 5 established the question, **not** the
   canonical abstraction: consumer groups, queues and Service Bus subscriptions are deliberately
   different, and no common concept is assumed.
2. **It is a candidate, not yet a justified release scope.** The promotion rule's condition 2
   (independent evidence demonstrably establishes it) is plausible but unproven, and condition 5 (a source-independent canonical abstraction) is open: no candidate
   emits consumer identity on spans, and broker-held state was not captured in this round.
3. **Not promoted:** headers-exchange predicates (sminerport only: remains a SEMANTIC_GAP, single
   system, kept out of the scope so one RabbitMQ mechanism does not drive it), fanout binding keys
   (irrelevant), framework-generated names (undecidable), attribute-key mismatches (an ingestion
   gap in the 3 systems that emit mismatched keys: Sokol111, eShop, daonhan; koupang and hungCS
   emit no messaging spans, which is missing evidence, not a key mismatch).
4. **Semantic control:** daonhan's Azure Service Bus Topic/Subscription shape fits existing AIP semantics; runtime qualification was not evaluated in Round 5.

## Proposed smallest scope (if conditions 2 and 5 are met)

> For destination D in environment E, which Services can available evidence safely attribute as consumers, through what broker-native evidence, and with what qualification?

Unsupported by design: general broker topology, routing predicates, lag/offsets/rebalancing,
framework-generated names, DLQ/retry topology.

## Recommended next step (owner decision)

A small **evidence-capture check** before any semantic work: capture broker-held consumer state for
one Kafka reserve (hungCS22hcmiu/ecommerce-system or koupang, both Compose-based; hungCS's own
script already runs `kafka-consumer-groups --describe`) and, if cheap, RabbitMQ bindings/consumers
for eShop or daonhan. If it cannot be captured or mapped to a Service, record that no
semantic-completion scope is justified.

## v0.8 validation system recommendation (§10)

Not selected. In order of fit for the validated gap, each still needing the Round 4-style
runnability and fairness check that Round 5 did not perform:

1. **hungCS22hcmiu/ecommerce-system** (Kafka, Compose, strong Claude Code baseline, broker group state
   already scripted) or **koupang** for Kafka attribution.
2. **daonhan/Microservices-in-.NET** as a cross-broker qualifier: one codebase with a Service Bus
   mode whose shape fits existing semantics and an unsupported RabbitMQ mode, plus agent docs.
3. **dotnet/eShop** as the recognisable RabbitMQ qualifier (high public-demo value; also exercises the
   destination-identity guard).

Sokol111 and sminerport stay as Round 4 evidence cases.

## Exit criteria (§11)

| Criterion | Status |
|---|---|
| Reserves checked against the Round 4 hypotheses | Done: five records; food-delivery undecidable |
| ≥2 independent systems per proposed gap | Met for consumer attribution (6) |
| Semantic gaps separated from ingestion gaps and broker details | Done |
| Short scope or explicit "none justified" | Scope proposed, conditional on evidence capture |
| Systems suitable for qualifying the scope | Named (hungCS/koupang, daonhan, eShop), unverified for runnability |
| Updated v0.8 system recommendation | Given, with the verification still owed |

## Limitations

- Static inspection of shallow clones; nothing run live; no agent baselines.
- Span profiles are source-derived (eShop, daonhan); koupang/hungCS emit no messaging spans; food-delivery's Wolverine instrumentation and daonhan's Service Bus instrumentation were not inspected.
- No broker-held evidence was captured; condition 2 of the promotion rule is therefore open.
